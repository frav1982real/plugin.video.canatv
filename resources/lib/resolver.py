# -*- coding: utf-8 -*-
"""Risoluzione stream unificata (wltv / sky_free / sky_pay / vavoo) e ListItem Kodi."""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

import requests
import xbmcgui

from . import utils


def _xor_decrypt(data_b64, key):
    import base64
    data = base64.b64decode(data_b64)
    key_bytes = (key or "").encode()
    if not key_bytes:
        return ""
    out = bytearray()
    for i, byte in enumerate(data):
        out.append(byte ^ key_bytes[i % len(key_bytes)])
    return out.decode("utf-8")


def _sky_pay_template():
    template = utils.setting("sky_pay_api", utils.SKY_PAY_API_DEFAULT) or utils.SKY_PAY_API_DEFAULT
    if "{}" not in template:
        template = utils.SKY_PAY_API_DEFAULT
    return template


def _probe_manifest(url, user_agent=None, referer=None, origin=None, timeout=8, segment_probe=False):
    """Verifica che un URL manifest sia ancora vivo (non scaduto).

    Ritorna True se la GET al manifest risponde 200 e il body
    inizia con un marker di manifest valido (#EXTM3U HLS o
    <MPD DASH). Se segment_probe=True, tenta di scaricare anche
    i primi byte del primo segmento del flusso.
    """
    headers = {
        "User-Agent": user_agent or utils.SKY_UA,
        "Accept": "*/*",
    }
    if referer:
        headers["Referer"] = referer
    if origin:
        headers["Origin"] = origin
    try:
        # Probe manifest principale
        resp_manifest = requests.get(url, headers=headers, timeout=timeout,
                                     stream=True, allow_redirects=True)
        try:
            status = resp_manifest.status_code
            chunk_manifest = next(resp_manifest.iter_content(256), b"")
        finally:
            try:
                resp_manifest.close()
            except Exception:
                pass

        if status != 200:
            utils.log(f"Probe manifest: {url[:80]} -> HTTP {status}")
            return False
        text = chunk_manifest.decode("utf-8", "ignore").lstrip()
        if not any(text.startswith(p) for p in ("#EXTM3U", "<?xml", "<MPD")):
            utils.log(f"Probe manifest: {url[:80]} -> non e' un manifest valido")
            return False

        # Se e' un HLS e richiesto, tenta di scaricare il primo segmento
        if segment_probe and text.startswith("#EXTM3U"):
            m = re.search(r"^#EXTINF:.*\n(\S+)", text, re.MULTILINE)
            if m:
                segment_url_raw = m.group(1).strip()
                segment_url = urljoin(url, segment_url_raw)
                utils.log(f"Probe segmento: {segment_url[:80]}")
                resp_segment = requests.get(segment_url, headers=headers, timeout=timeout, stream=True)
                try:
                    status_segment = resp_segment.status_code
                    # Scarica giusto qualche byte per verificare l'accesso
                    _ = next(resp_segment.iter_content(16), b"")
                finally:
                    try:
                        resp_segment.close()
                    except Exception:
                        pass
                if status_segment != 200:
                    utils.log(f"Probe segmento: {segment_url[:80]} -> HTTP {status_segment}")
                    return False
        utils.log(f"Probe manifest: {url[:80]} -> OK")
        return True
    except Exception as exc:
        utils.log(f"Probe manifest fallito: {url[:60]} ({type(exc).__name__}) - {exc}")
        return False


def resolve_sky_free(sky_id):
    """Risolve TV8 / Cielo / Sky TG24 via API player Sky (non piu apid.sky.it)."""
    if not sky_id:
        return None
    sky_id = str(sky_id)
    referer = utils.SKY_FREE_REFERER.get(sky_id, "https://video.sky.it/")
    headers = {
        "User-Agent": utils.SKY_UA,
        "Accept": "application/json",
        "Referer": referer,
        "Origin": "https://video.sky.it",
    }
    try:
        resp = requests.get(utils.SKY_FREE_API.format(sky_id), headers=headers, timeout=15)
        if resp.status_code != 200:
            utils.log("Sky free API HTTP %s id=%s" % (resp.status_code, sky_id))
            return None
        data = resp.json()
        stream_url = data.get("streaming_url") or data.get("hls_url") or ""
        if not stream_url:
            utils.log("Sky free id=%s: nessun URL (api nuova, apid e vuota)" % sky_id)
            return None
        # Probe: i token Akamai durano ~5 minuti, puo' essere gia' scaduto
        # quando Kodi lo usa. Se scaduto, evita di dare un URL morto.
        if not _probe_manifest(stream_url, user_agent=utils.SKY_UA,
                               referer=referer, origin="https://video.sky.it",
                               segment_probe=True):
            utils.log("Sky free %s: manifest scaduto (probe fallito)" % sky_id)
            return None
        utils.log("Sky free %s: %s" % (sky_id, stream_url[:80]))
        return {
            "url": stream_url,
            "name": utils.SKY_FREE_CHANNELS.get(sky_id, data.get("title") or sky_id),
            "drm": False,
            "use_isa": True,
            "user_agent": utils.SKY_UA,
            "referer": referer,
        }
    except Exception as exc:
        utils.log("Errore resolve Sky free %s: %s" % (sky_id, exc))
        return None


def _pay_id_candidates(sky_ppv_id):
    raw = (sky_ppv_id or "").strip()
    if not raw:
        return []
    seen = []
    variants = [
        raw,
        raw.lower(),
        raw.lower().replace("hd", ""),
        raw.lower().replace("plus1hd", "plus").replace("plus1", "plus"),
        raw.lower().replace("hdplus1", "plus"),
    ]
    if raw.lower().endswith("plus1hd"):
        variants.append(raw.lower()[:-7] + "plus")
    if raw.lower().endswith("plus1"):
        variants.append(raw.lower()[:-5] + "plus")

    # Alias sky_ppv_id equivalenti (bidirezionali).
    # Alcuni canali Sky hanno ID con nome "vecchio" (es. skysportfootball)
    # che pero' corrispondono al canale "ufficiale" (skysportcalcio).
    # Se l'API Sky pay restituisce 404 sull'ID, proviamo l'equivalente.
    alias = utils.SKY_PPV_ALIASES.get(raw.lower())
    if alias:
        variants.append(alias)
        variants.append(alias + "hd")

    for item in variants:
        item = item.strip("_-")
        if item and item not in seen:
            seen.append(item)
    return seen


def resolve_sky_pay(sky_ppv_id):
    if not sky_ppv_id:
        return None
    secret = utils.setting("sky_pay_secret", utils.SKY_PAY_SECRET_DEFAULT) or utils.SKY_PAY_SECRET_DEFAULT
    last_error = None
    for candidate in _pay_id_candidates(sky_ppv_id):
        utils.log("Sky pay: provo candidato %s" % candidate)
        result = _resolve_sky_pay_once(candidate, secret)
        if result:
            return result
        last_error = candidate
    utils.log("Sky pay: nessun id valido partendo da %s (ultimo %s)" % (sky_ppv_id, last_error))
    return None


def _resolve_sky_pay_once(sky_ppv_id, secret):
    api_url = _sky_pay_template().format(sky_ppv_id)
    utils.log("Resolving Sky pay: %s" % sky_ppv_id)
    try:
        resp = requests.get(api_url, headers={"User-Agent": utils.SKY_UA}, timeout=30)
        if resp.status_code != 200:
            utils.log("Sky pay API HTTP %d" % resp.status_code)
            return None
        payload = resp.json()
        if payload.get("error"):
            utils.log("Sky pay %s: %s" % (sky_ppv_id, payload.get("error")))
            return None
        encrypted = payload.get("data") or ""
        if not encrypted:
            return None
        data = json.loads(_xor_decrypt(encrypted, secret))
        manifest = data.get("manifest") or ""
        kid = (data.get("kid") or "").replace("-", "").strip()
        key = (data.get("key") or "").replace("-", "").strip()
        if not (manifest and kid and key):
            utils.log("Sky pay: manifest/kid/key mancanti per %s" % sky_ppv_id)
            return None
        # Probe del manifest: l'API Sky pay restituisce un link che puo'
        # essere scaduto nel momento in cui Kodi lo usa. Se facciamo
        # setResolvedUrl con URL scaduto, Kodi accetta il ListItem,
        # poi il player fallisce e si chiude senza che l'utente veda
        # il fallback Vavoo. Il probe evita questo: se scaduto,
        # ritorniamo None -> resolve_sky_pay prova il prossimo candidato,
        # e alla fine play_channel cade su Vavoo.
        if not _probe_manifest(
            manifest,
            user_agent=utils.SKY_UA,
            referer=utils.NOWTV_HOST,
            origin=utils.NOWTV_HOST,
            segment_probe=True
        ):
            utils.log("Sky pay %s: manifest scaduto (probe fallito)" % sky_ppv_id)
            return None
        expiry_str = data.get("fine") or ""
        if expiry_str and "EXPIRE" not in expiry_str:
            try:
                expiry = datetime.strptime(expiry_str, "%d/%m/%Y %H:%M:%S") + timedelta(hours=2)
                if expiry < datetime.now():
                    utils.log("Sky pay link scaduto (%s) ma provo comunque" % expiry_str)
            except Exception:
                pass
        utils.log("Sky pay %s ok kid=%s manifest=%s" % (sky_ppv_id, kid[:8], manifest[:70]))
        return {
            "url": manifest,
            "name": sky_ppv_id,
            "drm": True,
            "drm_type": "org.w3.clearkey",
            "drm_key": "%s:%s" % (kid, key),
        }
    except Exception as exc:
        utils.log("Errore resolve Sky pay %s: %s" % (sky_ppv_id, exc))
        return None


def resolve_wltv(identifier):
    if not identifier or not identifier.startswith("http"):
        return None
    return {"url": identifier, "name": "wltv", "drm": False, "use_isa": True}


def resolve_vavoo(vavoo_id):
    """Risolve un canale tramite Vavoo.to (fallback universale)."""
    if not vavoo_id:
        return None
    from . import vavoo as vavoo_mod
    try:
        import os
        cache_file = os.path.join(utils.profile_dir(), "vavoo_sig.json")
        client = vavoo_mod.VavooClient(cache_file=cache_file)
        link = "https://vavoo.to/vavoo-iptv/play/%s" % vavoo_id
        resolved, method = client.resolve_with_fallback(link)
        if resolved:
            utils.log("Vavoo %s (%s): %s" % (vavoo_id, method, resolved[:80]))
            return {
                "url": resolved,
                "name": "vavoo",
                "drm": False,
                "use_isa": True,
                "user_agent": utils.SKY_UA,
            }
        return None
    except Exception as exc:
        utils.log("Errore resolve Vavoo %s: %s" % (vavoo_id, exc))
        return None


def _header_string(resolved):
    url = resolved.get("url") or ""
    ua = resolved.get("user_agent") or utils.SKY_UA
    referer = resolved.get("referer") or ""
    extra = dict(resolved.get("headers") or {})
    parts = ["User-Agent=%s" % ua]
    have = {"user-agent"}
    if referer:
        parts.append("Referer=%s" % referer)
        have.add("referer")
        try:
            parsed = urlparse(referer)
            origin = "%s://%s" % (parsed.scheme, parsed.netloc)
            extra.setdefault("Origin", origin)
        except Exception:
            pass
    for key, value in extra.items():
        if not value or key.lower() in have:
            continue
        parts.append("%s=%s" % (key, value))
        have.add(key.lower())
    if "cssott" in url or "nowitlin" in url or "nowtv" in url:
        if "verifypeer" not in have:
            parts.append("verifypeer=false")
    return "&".join(parts)


def _enable_isa(li, url, mime=None):
    is_mpd = ".mpd" in (url or "").lower() or (mime or "").find("dash") >= 0
    if is_mpd:
        mime = mime or "application/dash+xml"
        kind = "mpd"
    else:
        mime = mime or "application/vnd.apple.mpegurl"
        kind = "hls"
    li.setMimeType(mime)
    li.setProperty("inputstream", "inputstream.adaptive")
    li.setProperty("inputstreamaddon", "inputstream.adaptive")
    li.setProperty("inputstream.adaptive.manifest_type", kind)
    li.setProperty("inputstream.adaptive.file_type", kind)


def _apply_isa_headers(li, header_str):
    if not header_str:
        return
    li.setProperty("inputstream.adaptive.stream_headers", header_str)
    li.setProperty("inputstream.adaptive.manifest_headers", header_str)
    li.setProperty("inputstream.adaptive.common_headers", header_str)


def create_listitem(resolved):
    """Costruisce il ListItem. use_isa=True DEVE impostare ISA (bug 1.0.7: era invertito)."""
    if not resolved or not resolved.get("url"):
        return None
    url = resolved["url"]
    header_str = _header_string(resolved)

    li = xbmcgui.ListItem(path=url, offscreen=True)
    li.setContentLookup(False)
    if resolved.get("name"):
        li.setInfo("video", {"title": resolved["name"], "mediatype": "video"})

    if resolved.get("drm"):
        # Stesso schema di Mandrakodi amstaffTest (NowTV/cssott): drm_legacy + header NowTV.
        drm_type = resolved.get("drm_type") or "org.w3.clearkey"
        drm_key = (resolved.get("drm_key") or "").replace("-", "")
        nowtv_headers = "User-Agent=%s&Referer=%s/&Origin=%s&verifypeer=false" % (
            utils.SKY_UA,
            utils.NOWTV_HOST,
            utils.NOWTV_HOST,
        )
        _enable_isa(li, url, "application/dash+xml")
        kodi = utils.kodi_major()
        if kodi >= 21:
            li.setProperty("inputstream.adaptive.drm_legacy", "%s|%s" % (drm_type, drm_key))
            try:
                kid, key = drm_key.split(":", 1)
                drm_cfg = {"org.w3.clearkey": {"license": {"keyids": {kid: key}}}}
                li.setProperty("inputstream.adaptive.drm", json.dumps(drm_cfg))
            except Exception:
                pass
        else:
            li.setProperty("inputstream.adaptive.license_type", "org.w3.clearkey")
            li.setProperty("inputstream.adaptive.license_key", drm_key)
        _apply_isa_headers(li, nowtv_headers)
        utils.log("ListItem DRM kodi=%s key=%s url=%s" % (kodi, drm_key[:12], url[:70]))
        return li

    use_isa = resolved.get("use_isa")
    if use_isa is None:
        low = url.lower()
        use_isa = bool(
            resolved.get("license")
            or ".mpd" in low
            or ".m3u8" in low
            or "hls" in low
            or "relinker" in low
        )

    if use_isa:
        _enable_isa(li, url)
        _apply_isa_headers(li, header_str)
        utils.log("ListItem ISA mime=%s ua_hdr=%s url=%s" % (li.getMimeType() if hasattr(li, "getMimeType") else "?", header_str[:60], url[:80]))
    else:
        li.setPath("%s|%s" % (url, header_str))
        utils.log("ListItem pipe-headers url=%s" % url[:80])

    if resolved.get("license"):
        _enable_isa(li, url)
        li.setProperty("inputstream.adaptive.license_type", "com.widevine.alpha")
        li.setProperty("inputstream.adaptive.license_key", resolved["license"])
        _apply_isa_headers(li, header_str)
    return li


def resolve(source, identifier):
    """Entry point unico: source + identifier del catalogo."""
    utils.set_debug()
    utils.log("resolve(source=%s, identifier=%s)" % (source, identifier))
    source = source or "wltv"
    identifier = identifier or ""
    if source == "sky_free":
        resolved = resolve_sky_free(identifier)
    elif source == "sky_pay":
        resolved = resolve_sky_pay(identifier)
    elif source == "vavoo":
        resolved = resolve_vavoo(identifier)
    elif source == "wltv":
        from . import wltv
        resolved = wltv.resolve(identifier)
    else:
        utils.log("Source sconosciuta: %s" % source)
        return None
    if not resolved or not resolved.get("url"):
        utils.log("resolve: nessun URL per %s/%s" % (source, identifier))
        return None
    if not resolved.get("name"):
        resolved["name"] = identifier
    return create_listitem(resolved)