# -*- coding: utf-8 -*-
"""WorldLiveTV: liste ufficiali + risoluzione stream all'atto del play."""
import json
import re

import requests

from . import utils

API_DOMAIN = "https://tvchannels.worldtvlive.eu/tv"
WLTV_LISTS = ("_dtt_kodi", "_vari", "_regional")

BROWSER_HEADERS = {
    "User-Agent": utils.SKY_UA,
    "Accept": "*/*",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

RAI_BY_ID = {
    "rai1": "Rai 1",
    "rai2": "Rai 2",
    "rai3": "Rai 3",
    "rai4": "Rai 4",
    "rai5": "Rai 5",
    "raimovie": "Rai Movie",
    "raipremium": "Rai Premium",
    "raigulp": "Rai Gulp",
    "raiyoyo": "Rai Yoyo",
    "rainews24": "Rai News 24",
    "raistoria": "Rai Storia",
    "raiscuola": "Rai Scuola",
    "raisport": "Rai Sport",
    "rai4k": "Rai 4K",
}

TVG_ALIASES = {
    "20mediaset": "mediaset20",
    "mediaset20": "20mediaset",
    "tgcom24": "tgcom24",
    "mediasetitalia2": "italia2",
    "italia2": "italia2",
    "27twentyseven": "twentyseven",
    "twentyseven": "twentyseven",
    "explorerchannel": "explorer",
    "bike": "bikechannel",
    "sportitaliaplus": "sportitalia",
    "sportitaliasolocalcio": "sportitaliasolocalcio",
    "gamberorosso": "gamberorosso",
    "supertennis": "supertennis",
    "tv2000": "tv2000",
    "la5": "la5",
    "cine34": "cine34",
    "topcrime": "topcrime",
    "msmotortv": "msmotortv",
    "acisporttv": "acisporttv",
    "laziostylehd": "laziostylechannel",
    "rsila1": "rsila1",
    "rsila2": "rsila2",
}

MEDIASET_CALLSIGNS = {
    "rete4": "R4",
    "canale5": "C5",
    "italia1": "I1",
    "20mediaset": "LB",
    "iris": "KI",
    "la5": "KA",
    "italia2": "I2",
    "mediasetitalia2": "I2",
    "mediasetextra": "KQ",
    "cine34": "B6",
    "topcrime": "LT",
    "tgcom24": "KF",
    "twentyseven": "TS",
    "27twentyseven": "TS",
    "focus": "FU",
    "boing": "KB",
    "cartoonito": "LA",
}
MEDIASET_APPNAME = "web//mediasetplay-web/1.3.2-e49d465"
MEDIASET_INFINITY = "https://mediasetinfinity.mediaset.it"

DISCOVERY_HOSTS = {
    "Nove": {"id": 3, "code": "nove", "host": "nove.tv"},
    "Real Time": {"id": 2, "code": "realtime", "host": "realtime.it"},
    "DMAX": {"id": 4, "code": "dmaxit", "host": "dmax.it"},
    "Giallo": {"id": 27, "code": "giallo", "host": "giallotv.it"},
    "Food Network": {"id": 6, "code": "foodnetwork", "host": "foodnetwork.it"},
    "K2": {"id": 24, "code": "k2", "host": "k2tv.it"},
    "Frisbee": {"id": 26, "code": "frisbee", "host": "frisbeetv.it"},
}


def _get(url, **kwargs):
    headers = dict(BROWSER_HEADERS)
    headers.update(kwargs.pop("headers", {}) or {})
    return requests.get(url, headers=headers, timeout=kwargs.pop("timeout", 20), **kwargs)


def parse_m3u(text):
    channels = []
    current = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            current = line
        elif line and not line.startswith("#") and current:
            def extract(tag):
                match = re.search(r'%s="([^"]*)"' % tag, current)
                return match.group(1) if match else ""

            title_match = re.search(r"#EXTINF:[^,]*,(.+)$", current)
            title = title_match.group(1).strip() if title_match else extract("tvg-name")
            channels.append(
                {
                    "name": title,
                    "url": line,
                    "tvg_id": extract("tvg-id"),
                    "tvg_name": extract("tvg-name") or title,
                    "tvg_logo": extract("tvg-logo"),
                    "group": extract("group-title"),
                }
            )
            current = None
    return channels


def fetch_official_lists():
    """Scarica le liste Kodi ufficiali WLTV (_dtt_kodi, _vari, _regional)."""
    channels = []
    for list_id in WLTV_LISTS:
        try:
            resp = _get("%s/%s/list.m3u8" % (API_DOMAIN, list_id))
            if resp.status_code != 200 or not resp.text.startswith("#EXTM3U"):
                utils.log("WLTV lista %s: HTTP %s" % (list_id, resp.status_code))
                continue
            parsed = parse_m3u(resp.text)
            utils.log("WLTV %s: %d canali" % (list_id, len(parsed)))
            channels.extend(parsed)
        except Exception as exc:
            utils.log("WLTV fetch %s: %s" % (list_id, exc))
    return channels


def index_wltv(live_channels):
    by_tvgid = {}
    by_norm = {}
    for live in live_channels:
        tvg_id = (live.get("tvg_id") or "").lower().strip()
        if tvg_id:
            by_tvgid.setdefault(tvg_id, live)
            compact = re.sub(r"[^a-z0-9]+", "", tvg_id)
            by_tvgid.setdefault(compact, live)
            alias = TVG_ALIASES.get(compact)
            if alias:
                by_tvgid.setdefault(alias, live)
                by_tvgid.setdefault(re.sub(r"[^a-z0-9]+", "", alias), live)
        for label in (live.get("name"), live.get("tvg_name")):
            norm = utils.normalize_name(label or "")
            if norm:
                by_norm.setdefault(norm, live)
    return by_tvgid, by_norm


def match_channel(ch, by_tvgid, by_norm):
    wid = (ch.get("wltv_id") or "").lower().strip()
    if wid:
        if wid in by_tvgid:
            return by_tvgid[wid]
        compact = re.sub(r"[^a-z0-9]+", "", wid)
        if compact in by_tvgid:
            return by_tvgid[compact]
        alias = TVG_ALIASES.get(compact)
        if alias and alias in by_tvgid:
            return by_tvgid[alias]
    norm = utils.normalize_name(ch.get("name") or "")
    if norm and norm in by_norm:
        return by_norm[norm]
    return None


def play_ref_from_live(live):
    """Converte l'URL WLTV in un riferimento risolvibile da CanàTV."""
    url = (live.get("url") or "").strip()
    if url.startswith("plugin://plugin.video.wltvhelper/play/"):
        rest = url.split("/play/", 1)[1]
        parts = rest.split("/", 1)
        if len(parts) == 2:
            return "%s:%s" % (parts[0], requests.utils.unquote(parts[1]))
        return rest
    if url.startswith("http"):
        return url
    return ""


def attach_live(item, live):
    if not live:
        return item
    item["play_ref"] = play_ref_from_live(live)
    if live.get("url", "").startswith("http"):
        item["url"] = live["url"]
    if live.get("tvg_logo"):
        item["tvg_logo"] = live["tvg_logo"]
    if live.get("tvg_id"):
        item["tvg_id"] = live["tvg_id"]
    item["live_source"] = "wltv"
    return item


def _resolve_rai(search):
    search = RAI_BY_ID.get(re.sub(r"[^a-z0-9]+", "", (search or "").lower()), search)
    data = _get("https://www.raiplay.it/dirette.json").json()
    target = utils.normalize_name(search)
    relinker = ""
    for channel in data.get("contents") or []:
        name = channel.get("channel") or ""
        if utils.normalize_name(name) == target or target.startswith(utils.normalize_name(name)):
            relinker = ((channel.get("video") or {}).get("content_url") or "")
            break
    if not relinker:
        return None
    joined = relinker + ("&" if "?" in relinker else "?") + "output=63&forceUserAgent=raiplayappletv"
    payload = _get(joined).json()
    videos = payload.get("video") or []
    url = videos[0] if videos else ""
    if not url or "video_no_available" in url:
        joined = relinker + ("&" if "?" in relinker else "?") + "output=63&forceUserAgent=raiplayhbbtv"
        payload = _get(joined).json()
        videos = payload.get("video") or []
        url = videos[0] if videos else ""
    if not url or "video_no_available" in url:
        return None
    return {"url": url, "drm": False, "user_agent": utils.SKY_UA}


HBBTV_UA = "HbbTV/1.6.1"

# Stream ufficiali clear (no DRM) da Tundrak/IPTV-Italia
MEDIASET_CLR = {
    "C5": "c5",
    "I1": "i1",
    "R4": "r4",
    "LB": "lb",
    "KI": "ki",
    "KA": "ka",
    "I2": "i2",
    "KQ": "kq",
    "B6": "b6",
    "LT": "lt",
    "KF": "kf",
    "TS": "ts",
    "FU": "fu",
    "KB": "kb",
    "LA": "la",
}

# Playlist ufficiale Tundrak/IPTV-Italia (stabili, no token)
LA7_CLEAR = "https://d3749synfikwkv.cloudfront.net/v1/master/3722c60a815c199d9c0ef36c5b73da68a62b09d1/cc-74ylxpgd78bpb/Live.m3u8"
LA7_CLEAR_ALT = "https://d15umi5iaezxgx.cloudfront.net/LA7/CLN/HLS/Live.m3u8"
LA7_CLEAR_AKAMAI = "https://live-la7-lh.akamaihd.net/i/LA7_1@199280/master.m3u8"
LA7_CLEAR_AKAMAI_ALT = "https://live-la7-lh.akamaihd.net/i/LA7_1@199280/index_3000_av-p.m3u8"
LA7D_CLEAR = "https://d15umi5iaezxgx.cloudfront.net/LA7D/CLN/HLS/Live.m3u8"
LA7D_CLEAR_AKAMAI = "https://live-la7-lh.akamaihd.net/i/LA7_2@199281/index_3000_av-p.m3u8"


def _mediaset_callsign(search):
    raw = (search or "").strip()
    if raw.startswith("$"):
        return raw[1:].upper()
    compact = re.sub(r"[^a-z0-9]+", "", raw.lower())
    if compact in MEDIASET_CALLSIGNS:
        return MEDIASET_CALLSIGNS[compact]
    wanted = utils.normalize_name(raw)
    for name, code in (
        ("Canale 5", "C5"), ("Italia 1", "I1"), ("Rete 4", "R4"),
        ("20 Mediaset", "LB"), ("Iris", "KI"), ("La 5", "KA"),
        ("Italia 2", "I2"), ("Mediaset Extra", "KQ"), ("Cine 34", "B6"),
        ("Top Crime", "LT"), ("TgCom 24", "KF"), ("Twentyseven", "TS"),
        ("Focus", "FU"), ("Boing", "KB"), ("Cartoonito", "LA"),
    ):
        if utils.normalize_name(name) == wanted:
            return code
    return raw.upper()[:4]


def _first_reachable(urls, headers, timeout=8):
    """Primo URL che risponde 200 con manifesto HLS/DASH. Se tutti 403 (geo) torna il primo."""
    first = ""
    for url in urls:
        if not url:
            continue
        if not first:
            first = url
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
            status = resp.status_code
            chunk = b""
            try:
                chunk = next(resp.iter_content(640), b"")
            except Exception:
                pass
            try:
                resp.close()
            except Exception:
                pass
            text = chunk.decode("utf-8", "ignore")
            ok = status == 200 and (
                "#EXTM3U" in text or "<MPD" in text or "<?xml" in text or "SmoothStreaming" in text
            )
            utils.log("probe %s -> HTTP %s ok=%s" % (url[:90], status, ok))
            if ok:
                return url
        except Exception as exc:
            utils.log("probe fail %s: %s" % (url[:90], exc))
    return first


def _scrape_la7_clear(search):
    import base64

    path = "/live-la7d" if "7d" in (search or "").lower().replace(" ", "") else "/dirette-tv"
    try:
        html = _get("https://www.la7.it" + path).text
    except Exception as exc:
        utils.log("La7 scrape pagina: %s" % exc)
        return ""
    url = ""
    match = re.search(r'var la7cln\s*=\s*"([^"]+)"', html)
    if match:
        url = match.group(1)
    if not url:
        match = re.search(r'var l7cln\s*=\s*"([^"]+)"', html)
        if match:
            try:
                url = base64.b64decode(match.group(1)).decode("utf-8")
            except Exception:
                url = ""
    if not url:
        match = re.search(r"""["']?hls["']?\s*:\s*["']([^"']+)["']""", html)
        if match and "DRM" not in match.group(1).upper():
            url = match.group(1)
    if url and "DRM" in url.upper():
        return ""
    return url


def _resolve_mediaset(search):
    """Flussi HLS/DASH clear Mediaset (Tundrak/IPTV-Italia), niente Widevine."""
    callsign = _mediaset_callsign(search)
    slug = MEDIASET_CLR.get(callsign) or MEDIASET_CLR.get(callsign.upper())
    if not slug:
        slug = (callsign or "").lower()
    # HLS prima: issue Tundrak #165, i MPD clr vanno in loop su Kodi.
    urls = [
        "https://live02-seg.msf.cdn.mediaset.net/live/ch-%s/%s-clr.isml/index.m3u8" % (slug, slug),
        "https://live03-col.msf.cdn.mediaset.net/live/ch-%s/%s-clr.isml/index.m3u8" % (slug, slug),
        "https://live2.msf.cdn.mediaset.net/content/hls_h0_clr_vos/live/channel(%s)/index.m3u8" % slug,
        "https://live03-col.msf.cdn.mediaset.net/live/ch-%s/%s-clr.isml/manifest.mpd" % (slug, slug),
    ]
    headers = {
        "User-Agent": HBBTV_UA,
        "Referer": "https://www.mediasetplay.mediaset.it/",
        "Origin": "https://www.mediasetplay.mediaset.it",
        "Accept": "*/*",
    }
    url = _first_reachable(urls, headers)
    utils.log("Mediaset %s/%s -> %s" % (callsign, slug, (url or "")[:90]))
    return {
        "url": url,
        "drm": False,
        "use_isa": True,
        "user_agent": HBBTV_UA,
        "referer": "https://www.mediasetplay.mediaset.it/",
    }


def _resolve_la7(search):
    """HLS in chiaro: URL CDN, IPTV-Italia, Akamai, scrape firmato."""
    is_la7d = "7d" in (search or "").lower().replace(" ", "")
    if is_la7d:
        candidates = [LA7D_CLEAR, LA7D_CLEAR_AKAMAI]
    else:
        candidates = [LA7_CLEAR, LA7_CLEAR_ALT, LA7_CLEAR_AKAMAI, LA7_CLEAR_AKAMAI_ALT]
    scraped = _scrape_la7_clear(search)
    if scraped:
        candidates.append(scraped)
    headers = {
        "User-Agent": utils.SKY_UA,
        "Referer": "https://www.la7.it/dirette-tv",
        "Origin": "https://www.la7.it",
        "Accept": "*/*",
    }
    url = _first_reachable(candidates, headers)
    if not url:
        utils.log("La7: nessuno stream clear (fallback Vavoo)")
        return None
    utils.log("La7 scelta: %s" % url[:100])
    return {
        "url": url,
        "drm": False,
        "use_isa": True,
        "user_agent": utils.SKY_UA,
        "referer": "https://www.la7.it/dirette-tv",
    }


def _resolve_discovery(search):
    cfg = None
    for name, data in DISCOVERY_HOSTS.items():
        if utils.normalize_name(name) == utils.normalize_name(search):
            cfg = data
            break
    if not cfg:
        return None
    headers = dict(BROWSER_HEADERS)
    headers["Referer"] = "https://%s/" % cfg["host"]
    headers["Origin"] = "https://%s" % cfg["host"]
    cfg_url = (
        "https://public.aurora.enhanced.live/site/configurations"
        "?include=default&filter[environment]=%s&v=2" % cfg["code"]
    )
    try:
        site = _get(cfg_url, headers=headers).json()
        simulcast = site["settings"]["site"]["simulcast"]
        base = simulcast["sonicEndpoint"]
        realm = simulcast["sonicRealm"]
    except Exception:
        base = "https://public.aurora.enhanced.live"
        realm = "it"
    headers["X-Device-Info"] = "STONEJS/1 (Unknown/Unknown; Windows/NT 10.0; Unknown)"
    headers["X-disco-params"] = "realm=it"
    headers["X-disco-client"] = "WEB:UNKNOWN:wbdatv:2.1.9"
    token = _get("%s/token?realm=%s" % (base, realm), headers=headers).json()["data"]["attributes"]["token"]
    headers["Authorization"] = "Bearer %s" % token
    headers["Content-Type"] = "application/json"
    body = (
        '{"deviceInfo":{"adBlocker":false,"drmSupported":false,"hdrCapabilities":["SDR"],'
        '"hwDecodingCapabilities":[],"soundCapabilities":["STEREO"]},'
        '"wisteriaProperties":{"platform":"desktop"},"channelId":"%s"}' % cfg["id"]
    )
    data = requests.post(
        "%s/playback/v3/channelPlaybackInfo" % base,
        headers=headers,
        data=body,
        timeout=20,
    ).json()
    streams = (((data.get("data") or {}).get("attributes") or {}).get("streaming")) or []
    url = ""
    for stream in streams:
        if stream.get("type") == "hls" and stream.get("url"):
            url = stream["url"]
            break
    if not url and streams:
        url = streams[0].get("url") or ""
    if not url:
        return None
    return {"url": url, "drm": False, "user_agent": utils.SKY_UA, "headers": headers}


def _resolve_http(url):
    if not url.startswith("http"):
        return None
    low = url.lower()
    use_isa = ".mpd" in low or ".m3u8" in low or "hls" in low or "relinker" in low
    return {"url": url, "drm": False, "use_isa": use_isa, "user_agent": utils.SKY_UA}


def infer_play_ref(ch):
    wid = (ch.get("wltv_id") or "").lower()
    name = ch.get("name") or ""
    if wid in RAI_BY_ID or utils.normalize_name(name).startswith("RAI"):
        return "rai:%s" % (RAI_BY_ID.get(wid) or name)
    if wid in MEDIASET_CALLSIGNS:
        return "mediaset:$%s" % MEDIASET_CALLSIGNS[wid]
    cs = _mediaset_callsign(name)
    if cs in MEDIASET_CLR:
        return "mediaset:$%s" % cs
    norm = utils.normalize_name(name)
    if wid == "la7" or norm in ("LA7", "LA7HD"):
        return "la7:La7"
    if wid in ("la7d", "la7cinema") or norm in ("LA7D", "LA7CINEMA"):
        return "la7:La7d"
    if norm in [utils.normalize_name(n) for n in DISCOVERY_HOSTS]:
        return "discovery:%s" % name
    return ""


def _unwrap_identifier(ref):
    """Converte URL WLTV helper / HTTP scaduti in un play_ref stabile."""
    ref = (ref or "").strip()
    if ref.startswith("plugin://plugin.video.wltvhelper/play/"):
        rest = ref.split("/play/", 1)[1]
        parts = rest.split("/", 1)
        if len(parts) == 2:
            return "%s:%s" % (parts[0], requests.utils.unquote(parts[1]))
        return rest
    if ref.startswith("http"):
        low = ref.lower()
        if "mediaset.net" in low or "msf.cdn" in low or "-clr.isml" in low:
            slug = ""
            match = re.search(r"ch-([a-z0-9]+)/", low) or re.search(r"channel\(([a-z0-9]+)\)", low)
            if match:
                slug = match.group(1)
            return "mediaset:$%s" % (slug.upper() if slug else "C5")
        if "d3749synfikwkv" in low or "/la7/" in low or "la7cln" in low:
            return "la7:La7"
        if "la7d" in low or "/la7d/" in low:
            return "la7:La7d"
        if "raiplay" in low or "mediapolis.rai.it" in low or "relinker" in low:
            return ref
    return ref


def resolve(identifier, channel=None):
    """Risolve un canale WLTV. identifier = play_ref oppure URL oppure wltv_id."""
    ref = identifier or ""
    if channel and not ref:
        ref = channel.get("play_ref") or infer_play_ref(channel)
    if not ref and channel:
        ref = infer_play_ref(channel)
    ref = _unwrap_identifier(ref)
    utils.log("WLTV resolve ref=%s" % ref)

    if ref.startswith("http"):
        return _resolve_http(ref)

    if ":" not in ref:
        compact = re.sub(r"[^a-z0-9]+", "", ref.lower())
        if compact in RAI_BY_ID:
            return _resolve_rai(RAI_BY_ID[compact])
        if compact in MEDIASET_CALLSIGNS or compact.upper() in MEDIASET_CLR:
            return _resolve_mediaset(ref)
        guessed = infer_play_ref({"wltv_id": ref, "name": ref})
        if guessed and guessed != ref:
            return resolve(guessed, channel)

    broadcaster, _, search = ref.partition(":")
    broadcaster = (broadcaster or "").lower()
    search = search or ref
    try:
        if broadcaster == "rai":
            return _resolve_rai(search)
        if broadcaster == "mediaset":
            return _resolve_mediaset(search)
        if broadcaster == "la7":
            return _resolve_la7(search)
        if broadcaster == "discovery":
            return _resolve_discovery(search)
        if broadcaster == "sky":
            sky_ids = {"SKYTG24": "1", "CIELO": "2", "TV8": "7"}
            sky_id = sky_ids.get(utils.normalize_name(search))
            if not sky_id:
                return None
            from . import resolver as core
            return core.resolve_sky_free(sky_id)
        if channel:
            guessed = infer_play_ref(channel)
            if guessed and guessed != ref:
                return resolve(guessed, channel)
            wid = channel.get("wltv_id") or ""
            if wid in RAI_BY_ID:
                return _resolve_rai(RAI_BY_ID[wid])
    except Exception as exc:
        utils.log("WLTV resolve error (%s): %s" % (ref, exc))
    return None
