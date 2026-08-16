# -*- coding: utf-8 -*-
"""Client per la piattaforma vavoo.to.

Logica ripresa da myResolver.py dell'addon Mandrakodi
(plugin.video.mandrakodi - https://mandrakodi.github.io):
  - VavooResolver.getAuthSignature  -> ping https://www.vavoo.tv/api/app/ping
  - get_channels                    -> catalogo https://vavoo.to/mediahubmx-catalog.json
  - VavooResolver.resolve_link      -> https://vavoo.to/mediahubmx-resolve.json
  - fallback streammode=0           -> ping2 + vavoo_auth (.ts)

Come richiesto, la funzione koolto() di Mandrakodi NON e' utilizzata.
"""
import json
import time
import uuid

import requests

from . import utils

VYPN_PING_URL = "https://www.vypn.net/api/app/ping"
VAVOO_PING_URL = "https://www.vavoo.tv/api/app/ping"
VAVOO_PING2_URL = "https://www.vavoo.tv/api/box/ping2"
VAVOO_CATALOG_URL = "https://vavoo.to/mediahubmx-catalog.json"
VAVOO_RESOLVE_URL = "https://vavoo.to/mediahubmx-resolve.json"

# User-agent usati dalle app correnti della piattaforma (vypn/vavoo)
UA_PING = "electron-fetch/1.0 electron (+https://github.com/arantes555/electron-fetch)"
UA_API = "okhttp/4.11.0"
UA_RESOLVE = "MediaHubMX/2"
CLIENT_VERSION = "3.1.0"


def vypn_ping_data():
    """Payload del ping alla piattaforma VYPN (identita' net.vypn.app).

    IMPORTANTE: vavoo e' migrata sulla piattaforma VYPN. Il vecchio ping a
    vavoo.tv con l'identita' "tv.vavoo.app" restituisce una sessione
    degradata che fa servire lo stream promo "VYPN Vavoo" al posto dei
    canali. Questo payload replica quello delle implementazioni funzionanti
    attuali (token vuoto, reason app-focus, timestamps dinamici, uniqueId
    casuale).
    """
    now_ms = int(time.time() * 1000)
    return {
        "token": "",
        "reason": "app-focus",
        "locale": "de",
        "theme": "dark",
        "metadata": {
            "device": {"type": "phone", "uniqueId": uuid.uuid4().hex[:16]},
            "os": {"name": "android", "version": "14", "abis": ["arm64-v8a"], "host": "android"},
            "app": {"platform": "android"},
            "version": {"package": "net.vypn.app", "binary": "1.4.1", "js": "1.4.1"},
        },
        "appFocusTime": 0,
        "playerActive": False,
        "playDuration": 0,
        "devMode": False,
        "hasAddon": True,
        "castConnected": False,
        "package": "net.vypn.app",
        "version": "1.4.1",
        "process": "app",
        "firstAppStart": now_ms - 86400000,
        "lastAppStart": now_ms,
        "ipLocation": None,
        "adblockEnabled": True,
        "migrationApplied": False,
        "migrationTargetInstalled": False,
        "proxy": {
            "supported": ["ss"],
            "engine": "Mu",
            "ssVersion": "2022",
            "enabled": False,
            "autoServer": True,
            "id": "",
        },
        "iap": {"supported": False, "error": ""},
    }


# payload del ping "legacy" vavoo.tv (identico a Mandrakodi) - solo fallback
PING_DATA = {
    "token": "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g",
    "reason": "app-blur",
    "locale": "de",
    "theme": "dark",
    "metadata": {
        "device": {
            "type": "Handset",
            "brand": "google",
            "model": "Nexus",
            "name": "21081111RG",
            "uniqueId": "d10e5d99ab665233",
        },
        "os": {
            "name": "android",
            "version": "7.1.2",
            "abis": ["arm64-v8a", "armeabi-v7a", "armeabi"],
            "host": "android",
        },
        "app": {
            "platform": "android",
            "version": "3.1.20",
            "buildId": "289515000",
            "engine": "hbc85",
            "signatures": ["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"],
            "installer": "app.revanced.manager.flutter",
        },
        "version": {"package": "tv.vavoo.app", "binary": "3.1.20", "js": "3.1.20"},
    },
    "appFocusTime": 0,
    "playerActive": False,
    "playDuration": 0,
    "devMode": False,
    "hasAddon": True,
    "castConnected": False,
    "package": "tv.vavoo.app",
    "version": "3.1.20",
    "process": "app",
    "firstAppStart": 1743962904623,
    "lastAppStart": 1743962904623,
    "ipLocation": "",
    "adblockEnabled": True,
    "proxy": {
        "supported": ["ss", "openvpn"],
        "engine": "ss",
        "ssVersion": 1,
        "enabled": True,
        "autoServer": True,
        "id": "pl-waw",
    },
    "iap": {"supported": False},
}

# payload per la firma .ts (ping2) - da Mandrakodi gettsSignature()
VEC_DATA = {"vec": "9frjpxPjxSNilxJPCJ0XGYs6scej3dW/h/VWlnKUiLSG8IP7mfyDU7NirOlld+VtCKGj03XjetfliDMhIev7wcARo+YTU8KPFuVQP9E2DVXzY2BFo1NhE6qEmPfNDnm74eyl/7iFJ0EETm6XbYyz8IKBkAqPN/Spp3PZ2ulKg3QBSDxcVN4R5zRn7OsgLJ2CNTuWkd/h451lDCp+TtTuvnAEhcQckdsydFhTZCK5IiWrrTIC/d4qDXEd+GtOP4hPdoIuCaNzYfX3lLCwFENC6RZoTBYLrcKVVgbqyQZ7DnLqfLqvf3z0FVUWx9H21liGFpByzdnoxyFkue3NzrFtkRL37xkx9ITucepSYKzUVEfyBh+/3mtzKY26VIRkJFkpf8KVcCRNrTRQn47Wuq4gC7sSwT7eHCAydKSACcUMMdpPSvbvfOmIqeBNA83osX8FPFYUMZsjvYNEE3arbFiGsQlggBKgg1V3oN+5ni3Vjc5InHg/xv476LHDFnNdAJx448ph3DoAiJjr2g4ZTNynfSxdzA68qSuJY8UjyzgDjG0RIMv2h7DlQNjkAXv4k1BrPpfOiOqH67yIarNmkPIwrIV+W9TTV/yRyE1LEgOr4DK8uW2AUtHOPA2gn6P5sgFyi68w55MZBPepddfYTQ+E1N6R/hWnMYPt/i0xSUeMPekX47iucfpFBEv9Uh9zdGiEB+0P3LVMP+q+pbBU4o1NkKyY1V8wH1Wilr0a+q87kEnQ1LWYMMBhaP9yFseGSbYwdeLsX9uR1uPaN+u4woO2g8sw9Y5ze5XMgOVpFCZaut02I5k0U4WPyN5adQjG8sAzxsI3KsV04DEVymj224iqg2Lzz53Xz9yEy+7/85ILQpJ6llCyqpHLFyHq/kJxYPhDUF755WaHJEaFRPxUqbparNX+mCE9Xzy7Q/KTgAPiRS41FHXXv+7XSPp4cy9jli0BVnYf13Xsp28OGs/D8Nl3NgEn3/eUcMN80JRdsOrV62fnBVMBNf36+LbISdvsFAFr0xyuPGmlIETcFyxJkrGZnhHAxwzsvZ+Uwf8lffBfZFPRrNv+tgeeLpatVcHLHZGeTgWWml6tIHwWUqv2TVJeMkAEL5PPS4Gtbscau5HM+FEjtGS+KClfX1CNKvgYJl7mLDEf5ZYQv5kHaoQ6RcPaR6vUNn02zpq5/X3EPIgUKF0r/0ctmoT84B2J1BKfCbctdFY9br7JSJ6DvUxyde68jB+Il6qNcQwTFj4cNErk4x719Y42NoAnnQYC2/qfL/gAhJl8TKMvBt3Bno+va8ve8E0z8yEuMLUqe8OXLce6nCa+L5LYK1aBdb60BYbMeWk1qmG6Nk9OnYLhzDyrd9iHDd7X95OM6X5wiMVZRn5ebw4askTTc50xmrg4eic2U1w1JpSEjdH/u/hXrWKSMWAxaj34uQnMuWxPZEXoVxzGyuUbroXRfkhzpqmqqqOcypjsWPdq5BOUGL/Riwjm6yMI0x9kbO8+VoQ6RYfjAbxNriZ1cQ+AW1fqEgnRWXmjt4Z1M0ygUBi8w71bDML1YG6UHeC2cJ2CCCxSrfycKQhpSdI1QIuwd2eyIpd4LgwrMiY3xNWreAF+qobNxvE7ypKTISNrz0iYIhU0aKNlcGwYd0FXIRfKVBzSBe4MRK2pGLDNO6ytoHxvJweZ8h1XG8RWc4aB5gTnB7Tjiqym4b64lRdj1DPHJnzD4aqRixpXhzYzWVDN2kONCR5i2quYbnVFN4sSfLiKeOwKX4JdmzpYixNZXjLkG14seS6KR0Wl8Itp5IMIWFpnNokjRH76RYRZAcx0jP0V5/GfNNTi5QsEU98en0SiXHQGXnROiHpRUDXTl8FmJORjwXc0AjrEMuQ2FDJDmAIlKUSLhjbIiKw3iaqp5TVyXuz0ZMYBhnqhcwqULqtFSuIKpaW8FgF8QJfP2frADf4kKZG1bQ99MrRrb2A="}

TIMEOUT = 20

# La addonSig restituita dal ping ha una finestra di validita' molto breve
# (campo "validUntil" della firma: circa 18 minuti) e incorpora l'IP del
# client. Se si riusa una firma scaduta, vavoo.to serve lo stream PROMO
# ("VYPN Vavoo") invece del canale. Mandrakodi infatti NON cachera' la firma:
# fa un ping fresco a ogni riproduzione. Lo replichiamo: la cache qui sotto
# serve SOLO a non duplicare i ping dentro la stessa riproduzione (retry),
# non a riusare la firma tra riproduzioni diverse.
SIG_CACHE_TTL = 8  # secondi


class VavooClient(object):
    """Client vavoo.to.

    La firma (addonSig) viene rifatta fresca a ogni riproduzione, come fa
    Mandrakodi: riutilizzare una firma piu' vecchia di qualche minuto fa
    servire la promo "VYPN Vavoo" al posto del canale.
    """

    def __init__(self, cache_file=None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MediaHubMX/2"})
        self._signature = None
        self._signature_ts = 0
        self._cache_file = cache_file
        if cache_file:
            self._load_cached_signature()

    # ------------------------------------------------------ cache signature
    def _load_cached_signature(self):
        try:
            with open(self._cache_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            sig = data.get("sig")
            ts = float(data.get("ts", 0))
            # riusa la firma solo se molto recente (entro SIG_CACHE_TTL)
            if sig and time.time() - ts < SIG_CACHE_TTL:
                self._signature = sig
                self._signature_ts = ts
        except Exception:
            pass

    def _store_cached_signature(self):
        if not self._cache_file:
            return
        try:
            with open(self._cache_file, "w", encoding="utf-8") as fh:
                json.dump({"sig": self._signature, "ts": self._signature_ts}, fh)
        except Exception:
            pass

    # ------------------------------------------------------------------ ping
    def get_auth_signature(self, force=False):
        """addonSig dal ping (VavooResolver.getAuthSignature di Mandrakodi,
        aggiornato alla piattaforma VYPN).

        Ping fresco a ogni chiamata, salvo riuso entro SIG_CACHE_TTL secondi
        (solo per non duplicare i ping nei retry della stessa riproduzione).
        Prova prima vypn.net (identita' net.vypn.app, quella che fa ottenere
        i canali veri), poi il vecchio ping vavoo.tv come fallback.
        """
        now = time.time()
        if not force and self._signature and now - self._signature_ts < SIG_CACHE_TTL:
            return self._signature
        signature = self._ping(VYPN_PING_URL, vypn_ping_data(), UA_PING)
        if not signature:
            utils.log("Ping vypn.net fallito, provo vavoo.tv (legacy)")
            signature = self._ping(VAVOO_PING_URL, PING_DATA, UA_API)
        if signature:
            self._signature = signature
            self._signature_ts = time.time()
            self._store_cached_signature()
        return self._signature or signature

    def _ping(self, url, data, user_agent):
        headers = {
            "user-agent": user_agent,
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "accept-encoding": "gzip",
            "Accept-Language": "de",
        }
        try:
            resp = self.session.post(url, json=data, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("addonSig")
        except Exception as exc:
            utils.log("Errore ping %s: %s" % (url, exc))
            return None

    def get_ts_signature(self):
        """Firma per i flussi .ts (Mandrakodi VavooResolver.gettsSignature)."""
        try:
            req = self.session.post(VAVOO_PING2_URL, data=VEC_DATA, timeout=TIMEOUT)
            return req.json()["response"].get("signed")
        except Exception as exc:
            utils.log("Errore ping2 vavoo: %s" % exc)
            return None

    # --------------------------------------------------------------- catalogo
    def get_channels(self, group="Italy", progress_callback=None):
        """Scarica l'intero catalogo di un gruppo (paginando con nextCursor)."""
        signature = self.get_auth_signature()
        headers = {
            "user-agent": UA_API,
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "accept-encoding": "gzip",
            "mediahubmx-signature": signature or "",
        }
        all_channels = []
        cursor = 0
        while True:
            data = {
                "language": "de",
                "region": "AT",
                "catalogId": "iptv",
                "id": "iptv",
                "adult": False,
                "search": "",
                "sort": "name",
                "filter": {"group": group},
                "cursor": cursor,
                "clientVersion": CLIENT_VERSION,
            }
            resp = self.session.post(VAVOO_CATALOG_URL, json=data, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            result = resp.json()
            items = result.get("items", [])
            all_channels.extend(items)
            if progress_callback:
                progress_callback(len(all_channels))
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return all_channels

    # --------------------------------------------------------------- resolve
    def resolve_link(self, link, streammode=1):
        """Risolve l'url di un canale (Mandrakodi VavooResolver.resolve_link)."""
        if not link or "vavoo" not in link:
            return None
        if streammode == 1:
            signature = self.get_auth_signature()
            if not signature:
                return self.resolve_link(link, streammode=0)
            headers = {
                "user-agent": UA_RESOLVE,
                "accept": "application/json",
                "content-type": "application/json; charset=utf-8",
                "accept-encoding": "gzip",
                "mediahubmx-signature": signature,
            }
            data = {"language": "de", "region": "AT", "url": link, "clientVersion": CLIENT_VERSION}
            try:
                resp = self.session.post(VAVOO_RESOLVE_URL, json=data, headers=headers, timeout=TIMEOUT)
                resp.raise_for_status()
                result = resp.json()
                if isinstance(result, list) and result and result[0].get("url"):
                    return result[0]["url"]
                if isinstance(result, dict) and result.get("url"):
                    return result["url"]
                return None
            except Exception as exc:
                utils.log("Errore resolve vavoo: %s" % exc)
                return None
        else:
            try:
                ts_signature = self.get_ts_signature()
                if not ts_signature:
                    return None
                ts_url = "%s.ts?n=1&b=5&vavoo_auth=%s" % (
                    link.replace("vavoo-iptv", "live2")[0:-12],
                    ts_signature,
                )
                return ts_url
            except Exception as exc:
                utils.log("Errore resolve ts vavoo: %s" % exc)
                return None

    def resolve_with_fallback(self, link):
        """Prima streammode=1; se fallisce rigioca con firma nuova;
        infine fallback streammode=0 (.ts)."""
        resolved = self.resolve_link(link, streammode=1)
        if resolved:
            return resolved, "principale"

        # la firma in cache potrebbe essere scaduta: riprova con un ping nuovo
        self.get_auth_signature(force=True)
        resolved = self.resolve_link(link, streammode=1)
        if resolved:
            return resolved, "principale"

        resolved = self.resolve_link(link, streammode=0)
        if resolved:
            return resolved, "fallback"
        return None, None
