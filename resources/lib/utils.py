# -*- coding: utf-8 -*-
"""Costanti e helper condivisi per CanàTV."""
import logging
import os
import re
import unicodedata

ADDON_ID = "plugin.video.canatv"
PVR_ADDON_ID = "pvr.iptvsimple"
PVR_ID = PVR_ADDON_ID

# apid.sky.it/vdp è morto (streaming_url vuoto). API attuale del player web Sky.
SKY_FREE_API = "https://video.sky.it/api/v1/getLivestream?id={}"
SKY_FREE_CHANNELS = {
    "1": "Sky TG24",
    "2": "Cielo",
    "7": "TV8",
}
SKY_FREE_REFERER = {
    "1": "https://video.sky.it/",
    "2": "https://www.cielo.it/",
    "7": "https://www.tv8.it/streaming",
}
SKY_PAY_API_DEFAULT = "https://test34344.herokuapp.com/filter.php?numTest=A1A159&id={}"
SKY_PAY_SECRET_DEFAULT = "my_secret_key"

# ID sky_ppv_id equivalenti (bidirezionali).
# Se l'API Sky pay restituisce 404 sull'ID "ufficiale", proviamo
# l'equivalente "vecchio" (e viceversa).
SKY_PPV_ALIASES = {
    "skysportfootball": "skysportcalcio",
    "skysportcalcio": "skysportfootball",
    "skysportnba": "skysportbasket",
    "skysportbasket": "skysportnba",
    "nickjr": "nickjunior",
    "nickjunior": "nickjr",
}
SKY_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
HBBTV_UA = "HbbTV/1.6.1"
NOWTV_HOST = "https://www.nowtv.it"
DEFAULT_EPG_URL = "http://epg-guide.com/wltv.xz"
DEFAULT_CACHE_TTL = 3600

_DEBUG = False


def addon():
    import xbmcaddon
    return xbmcaddon.Addon(ADDON_ID)


def setting(key, default=""):
    try:
        value = addon().getSetting(key)
        return value if value not in (None, "") else default
    except Exception:
        return default


def setting_bool(key, default=False):
    value = setting(key, "true" if default else "false")
    return str(value).lower() == "true"


def setting_int(key, default=0):
    try:
        return int(setting(key, str(default)))
    except (TypeError, ValueError):
        return default


def set_debug(enabled=None):
    global _DEBUG
    if enabled is None:
        enabled = setting_bool("debug", False)
    _DEBUG = bool(enabled)
    return _DEBUG


def log(msg):
    """Scrive sempre su kodi.log con prefisso [CANATTV]."""
    text = "[CANATTV] %s" % msg
    try:
        import xbmc
        xbmc.log(text, xbmc.LOGINFO)
    except Exception:
        try:
            logging.info(text)
        except Exception:
            pass


def kodi_major():
    try:
        import xbmc
        ver = xbmc.getInfoLabel("System.BuildVersion") or "20"
        digits = "".join(ch if ch.isdigit() else " " for ch in ver[:4]).split()
        return int(digits[0]) if digits else 20
    except Exception:
        return 20


def translate_path(path):
    try:
        import xbmcvfs
        return xbmcvfs.translatePath(path)
    except Exception:
        import xbmc
        return xbmc.translatePath(path)


def addon_path():
    return addon().getAddonInfo("path")


def profile_dir():
    import xbmcvfs
    path = translate_path(addon().getAddonInfo("profile"))
    if not xbmcvfs.exists(path):
        try:
            xbmcvfs.mkdirs(path)
        except Exception:
            pass
    return path


def data_path(*parts):
    return os.path.join(addon_path(), "resources", "data", *parts)


def strip_accents(text):
    try:
        nfkd = unicodedata.normalize("NFKD", text or "")
        return "".join(c for c in nfkd if not unicodedata.combining(c))
    except Exception:
        return text or ""


def normalize_name(name):
    """Normalizza un nome di canale per il confronto (HD ignorato, +1 distinto)."""
    s = strip_accents(name or "").upper().replace("È", "E")
    s = re.sub(r"\s*\+24\s*", "PLUS24", s)
    s = re.sub(r"\s*\+1\s*", "PLUS1", s)
    s = re.sub(r"\s*\.(C|S)\s*$", "", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\bHD\b", " ", s)
    s = re.sub(r"\b4K\b", " ", s)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s


def slugify(name):
    s = strip_accents(name or "").lower()
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "canale"


def xml_escape(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def m3u_escape(text):
    if text is None:
        return ""
    return str(text).replace('"', "'").replace("\n", " ").replace("\r", " ").strip()


def channel_identifier(ch):
    """Identificatore STABILE (mai URL firmati/scaduti)."""
    source = ch.get("source") or "wltv"
    if source == "sky_pay":
        return ch.get("sky_ppv_id") or ""
    if source == "sky_free":
        return str(ch.get("sky_id") or "")
    pref = ch.get("play_ref") or ""
    if pref.startswith("http") or pref.startswith("plugin://"):
        pref = ""
    if pref:
        return pref
    try:
        from . import wltv
        inferred = wltv.infer_play_ref(ch)
        if inferred:
            return inferred
    except Exception:
        pass
    return ch.get("wltv_id") or ""


def plugin_play_url(ch):
    from urllib.parse import urlencode
    return "plugin://%s/?%s" % (
        ADDON_ID,
        urlencode(
            {
                "action": "play",
                "source": ch.get("source") or "wltv",
                "identifier": channel_identifier(ch),
                "name": ch.get("name") or "",
            }
        ),
    )


def localize(msgid, fallback=""):
    try:
        text = addon().getLocalizedString(int(msgid))
        return text if text else (fallback or str(msgid))
    except Exception:
        return fallback or str(msgid)