# -*- coding: utf-8 -*-
"""Catalogo CanàTV: scaletta da canali.json, stream da WLTV/Sky/Vavoo."""
import json
import logging
import os
import re
import time

import xbmcvfs

from . import utils, wltv


def _log(msg, level=logging.INFO):
    if level >= logging.WARNING or utils.setting_bool("debug"):
        utils.log(msg)


def get_cache_file(name):
    return os.path.join(utils.profile_dir(), "%s.json" % name)


def read_json_file(path):
    try:
        if not xbmcvfs.exists(path):
            return None
        fh = xbmcvfs.File(path, "r")
        try:
            content = fh.read()
        finally:
            fh.close()
        if isinstance(content, bytes):
            content = content.decode("utf-8", "ignore")
        return json.loads(content)
    except Exception as exc:
        _log("Errore lettura %s: %s" % (path, exc), logging.WARNING)
        return None


def write_json_file(path, data):
    try:
        fh = xbmcvfs.File(path, "w")
        try:
            fh.write(json.dumps(data, ensure_ascii=False, indent=2))
        finally:
            fh.close()
        return True
    except Exception as exc:
        _log("Errore scrittura %s: %s" % (path, exc), logging.ERROR)
        return False


def is_cache_valid(cache_file):
    try:
        if not xbmcvfs.exists(cache_file):
            return False
        age = time.time() - xbmcvfs.Stat(cache_file).st_mtime()
        return age < utils.setting_int("cache_ttl", utils.DEFAULT_CACHE_TTL)
    except Exception:
        return False


def fetch_wltv_channels():
    if not utils.setting_bool("wltv_enabled", True):
        _log("WorldLiveTV disabilitato")
        return []
    cache_file = get_cache_file("wltv_channels")
    if is_cache_valid(cache_file):
        cached = read_json_file(cache_file)
        if cached:
            _log("Cache WorldLiveTV: %d" % len(cached))
            return cached
    channels = wltv.fetch_official_lists()
    if channels:
        write_json_file(cache_file, channels)
        _log("WorldLiveTV: %d canali cachati" % len(channels))
    return channels


def fetch_sky_free_channels():
    # I token Akamai di TV8/Cielo durano ~5 minuti: niente cache lunga.
    from . import resolver
    channels = []
    for sky_id, name in utils.SKY_FREE_CHANNELS.items():
        resolved = resolver.resolve_sky_free(sky_id)
        if resolved and resolved.get("url"):
            channels.append(
                {
                    "name": name,
                    "url": resolved["url"],
                    "sky_id": sky_id,
                    "source": "sky_free",
                    "referer": resolved.get("referer") or "",
                }
            )
    return channels


def fetch_vavoo_channels():
    """Scarica catalogo Vavoo Italia per matching canali (fallback)."""
    if not utils.setting_bool("vavoo_enabled", True):
        _log("Vavoo disabilitato")
        return []
    cache_file = get_cache_file("vavoo_channels")
    if is_cache_valid(cache_file):
        cached = read_json_file(cache_file)
        if cached:
            _log("Cache Vavoo: %d" % len(cached))
            return cached
    try:
        from . import vavoo as vavoo_mod
        client = vavoo_mod.VavooClient()
        channels = client.get_channels("Italy")
        if channels:
            write_json_file(cache_file, channels)
            _log("Vavoo: %d canali cachati" % len(channels))
        return channels
    except Exception as exc:
        _log("Errore fetch Vavoo: %s" % exc, logging.WARNING)
        return []


def load_configured_channels():
    path = utils.data_path("channels.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        _log("Errore channels.json: %s" % exc, logging.ERROR)
        return []


def _stable_tvg_id(ch, live=None):
    if live and live.get("tvg_id"):
        return live["tvg_id"]
    if ch.get("wltv_id"):
        return ch["wltv_id"]
    if ch.get("sky_ppv_id"):
        return ch["sky_ppv_id"]
    if ch.get("sky_id"):
        return "sky%s" % ch["sky_id"]
    if ch.get("vavoo_id"):
        return ch["vavoo_id"]
    return utils.slugify(ch.get("name") or "")


def _normalize_vavoo_name(name):
    """Normalizza nome come fa Vavoo addon per il matching."""
    try:
        import unicodedata
        s = unicodedata.normalize("NFKD", name or "").encode("ASCII", "ignore").decode("ascii")
    except Exception:
        s = name or ""
    s = s.upper()
    s = re.sub(r"\s*\.(C|S)\s*$", "", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    if s.endswith("HD") and len(s) > 2:
        s = s[:-2]
    return s


def _build_vavoo_index(vavoo_channels):
    """Indice Vavoo .c/.s (stessa logica Vavoo addon)."""
    index_c = {}
    index_s = {}
    for ch in vavoo_channels:
        name = ch.get("name", "")
        norm = _normalize_vavoo_name(name)
        if not norm:
            continue
        lower = name.lower()
        if "(backup)" in lower:
            continue
        if lower.endswith(".c"):
            index_c.setdefault(norm, ch)
        else:
            index_s.setdefault(norm, ch)
    merged = {}
    for norm, ch in index_s.items():
        merged[norm] = ch
    for norm, ch in index_c.items():
        merged[norm] = ch  # .c vince sempre
    return merged


# Alias espliciti per casi dove il matching automatico non basta
VAVOO_ALIASES = {
    "MSMOTORTV": "MSMOTOR",
    "SENATOITALIANO": "SENATOTV",
    "CLASSTVMODA": "TVMODA",
    "BLOOMBERG": "BLOOMBERGTV4K",
    "FRANCE24ENGLISH": "FRANCE24",
    "SKYSPORTFOOTBALL": "SKYSPORTCALCIO",
    "SKYSPORTCALCIO": "SKYSPORTFOOTBALL",
    "SKYSPORTBASKET": "SKYSPORTNBA",
    "SKYSPORTNBA": "SKYSPORTBASKET",
    "NICKJR": "NICKJUNIOR",
    "NICKJUNIOR": "NICKJR",
    "CNNINTL": "CNN",
    "BBCWORLDNEWS": "BBC",
    "EURONEWS": "EURONEWS",
    "RADIONORBATELEVISION": "RADIONORBATV",
    "SKYSPORT250": "SKYSPORT",
    "SKYSPORT251": "SKYSPORTSERIEA",
    "MEDIASETITALIA2": "ITALIA2",
    "CACCIAEPESCA": "CACCIA",
}


def match_vavoo_channel(ch, vavoo_index):
    """Matcha un canale di channels.json nel catalogo Vavoo."""
    norm = _normalize_vavoo_name(ch.get("name") or "")
    if norm in vavoo_index:
        return vavoo_index[norm]
    alias = VAVOO_ALIASES.get(norm)
    if alias and alias in vavoo_index:
        return vavoo_index[alias]
    return None


def _extract_vavoo_id(vch):
    if not vch:
        return ""
    vid = (vch.get("ids") or {}).get("id", "")
    if not vid:
        vid = (vch.get("url") or "").rstrip("/").split("/")[-1]
    return vid or ""


def build_channel_catalog():
    utils.set_debug()
    configured = load_configured_channels()
    if not configured:
        return []

    wltv_live = fetch_wltv_channels()
    sky_free = fetch_sky_free_channels()
    vavoo_live = fetch_vavoo_channels()

    by_tvgid, by_norm = wltv.index_wltv(wltv_live)
    sky_by_id = {item.get("sky_id"): item for item in sky_free if item.get("sky_id")}
    vavoo_index = _build_vavoo_index(vavoo_live) if vavoo_live else {}

    catalog = []
    matched = 0
    vavoo_matched = 0

    for ch in configured:
        source = ch.get("source") or "wltv"
        item = {
            "lcn": ch.get("lcn"),
            "name": ch.get("name"),
            "group": ch.get("group"),
            "source": source,
            "is_free": bool(ch.get("is_free", source != "sky_pay")),
        }
        for key in ("wltv_id", "sky_id", "sky_ppv_id"):
            if ch.get(key):
                item[key] = ch[key]

        live = None
        url = ""
        play_ref = ""

        # Sorgente primaria
        if source == "wltv":
            live = wltv.match_channel(ch, by_tvgid, by_norm)
            if live:
                wltv.attach_live(item, live)
                matched += 1
            inferred = wltv.infer_play_ref(item)
            if inferred:
                item["play_ref"] = inferred
            pref = item.get("play_ref") or ""
            if pref.startswith("http") and "tvchannels.worldtvlive.eu" in pref:
                url = pref
            else:
                play_ref = inferred or wltv.infer_play_ref(item)
                url = ""
        elif source == "sky_free":
            live = sky_by_id.get(ch.get("sky_id"))
            if live and live.get("url"):
                url = live["url"]
                if live.get("referer"):
                    item["referer"] = live["referer"]
            play_ref = ch.get("sky_id") or ""

        # Vavoo SEMPRE: matching per OGNI canale, anche se la primaria funziona.
        # Ogni canale che esiste nel catalogo Vavoo riceve vavoo_id, cosi
        # play_channel puo sempre provare Vavoo come ultima opzione.
        if vavoo_index:
            vch = match_vavoo_channel(ch, vavoo_index)
            if vch:
                vid = _extract_vavoo_id(vch)
                if vid:
                    item["vavoo_id"] = vid
                    vavoo_matched += 1

        item["tvg_id"] = _stable_tvg_id(ch, live)
        item["url"] = url
        if play_ref:
            item["play_ref"] = play_ref
        catalog.append(item)

    _log("Catalogo: %d canali, WLTV match %d, Vavoo match %d" % (len(catalog), matched, vavoo_matched))
    return catalog


def get_epg_url():
    return utils.setting("wltv_epg_url", utils.DEFAULT_EPG_URL) or utils.DEFAULT_EPG_URL


def refresh_all_caches():
    for name in ("wltv_channels", "sky_free_channels", "vavoo_channels"):
        path = get_cache_file(name)
        if xbmcvfs.exists(path):
            xbmcvfs.delete(path)
    return build_channel_catalog()