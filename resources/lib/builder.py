# -*- coding: utf-8 -*-
"""Builder M3U + integrazione PVR, sul catalogo unificato con Vavoo fallback."""
import json
import os

import xbmcgui
import xbmcvfs

from . import channel_fetcher, utils
from .pvr import ensure_enabled, export_list_to_pvr, remove_instance


def m3u_file():
    return os.path.join(utils.profile_dir(), "canali_italia.m3u")


def state_file():
    return os.path.join(utils.profile_dir(), "canali_state.json")


def _write_text(path, text):
    fh = xbmcvfs.File(path, "w")
    try:
        fh.write(text)
    finally:
        fh.close()


def _read_text(path):
    fh = xbmcvfs.File(path, "r")
    try:
        content = fh.read()
    finally:
        fh.close()
    if isinstance(content, bytes):
        content = content.decode("utf-8", "ignore")
    return content


def save_state(entries):
    _write_text(state_file(), json.dumps(entries, ensure_ascii=False, indent=1))


def load_state():
    try:
        return json.loads(_read_text(state_file()))
    except Exception:
        return None


class Progress(object):
    def __init__(self, title, silent=False):
        self.silent = silent
        self.dialog = None
        if not silent:
            self.dialog = xbmcgui.DialogProgress()
            self.dialog.create(title, " ")

    def update(self, percent, message=""):
        if self.silent:
            utils.log("(%d%%) %s" % (int(percent), message))
            return True
        self.dialog.update(max(0, min(100, int(percent))), message)
        return not self.dialog.iscanceled()

    def close(self):
        if self.dialog:
            try:
                self.dialog.close()
            except Exception:
                pass


def _entry_from_channel(ch):
    """Record stabile usato da M3U, browse e play."""
    return {
        "lcn": ch.get("lcn"),
        "name": ch.get("name"),
        "group": ch.get("group"),
        "source": ch.get("source") or "wltv",
        "is_free": bool(ch.get("is_free", True)),
        "tvg_id": ch.get("tvg_id") or utils.slugify(ch.get("name") or ""),
        "logo": ch.get("tvg_logo") or ch.get("logo") or "",
        "url": ch.get("url") or "",
        "wltv_id": ch.get("wltv_id") or "",
        "sky_id": ch.get("sky_id") or "",
        "sky_ppv_id": ch.get("sky_ppv_id") or "",
        "user_agent": ch.get("user_agent") or "",
        "referer": ch.get("referer") or "",
        "play_ref": ch.get("play_ref") or "",
        "vavoo_id": ch.get("vavoo_id") or "",
    }


def build_m3u(entries):
    lines = ['#EXTM3U x-tvg-url="%s"' % utils.m3u_escape(channel_fetcher.get_epg_url())]
    for entry in entries:
        # HTTP diretto solo per proxy WLTV regionali (stabili, senza header speciali).
        # Tutti gli altri passano per plugin:// cosi header/ISA si applicano al play.
        direct = entry.get("url") or ""
        if (
            direct.startswith("http")
            and entry.get("source") == "wltv"
            and "tvchannels.worldtvlive.eu" in direct
        ):
            url = direct
        else:
            url = utils.plugin_play_url(entry)

        extinf = (
            '#EXTINF:-1 tvg-id="%s" tvg-chno="%s" tvg-logo="%s" group-title="%s",%s'
            % (
                utils.m3u_escape(entry.get("tvg_id")),
                entry.get("lcn") or 0,
                utils.m3u_escape(entry.get("logo")),
                utils.m3u_escape(entry.get("group")),
                utils.m3u_escape(entry.get("name")),
            )
        )
        lines.append(extinf)
        if url.startswith("http"):
            ua = entry.get("user_agent") or utils.SKY_UA
            lines.append("#EXTVLCOPT:http-user-agent=%s" % ua)
            if entry.get("referer"):
                lines.append("#EXTVLCOPT:http-referrer=%s" % entry["referer"])
        lines.append(url)
    return "\n".join(lines) + "\n"


def build_all(silent=False):
    utils.set_debug()
    instance_name = utils.setting("instance_name", "CanàTV") or "CanàTV"
    progress = Progress(utils.ADDON_ID, silent)
    try:
        if not progress.update(10, utils.localize(32213)):
            return False, {"canceled": True}

        catalog = channel_fetcher.build_channel_catalog()
        if not catalog:
            return False, {"error": utils.localize(32214)}

        entries = []
        missing = []
        for ch in catalog:
            # Un canale ha una fonte se:
            #  - URL diretto gia' disponibile (WLTV stabile o Sky free Akamai)
            #  - play_ref risolvibile al play (Rai/Mediaset/La7/Discovery)
            #  - vavoo_id (backup Vavoo.to)
            #  - e' configurato per usare una sorgente (wltv_id/sky_id/sky_ppv_id):
            #    in quel caso la sorgente e' disponibile anche se al momento
            #    il runtime non riesce a risolvere (es. Sky Nature in Sky pay)
            has_source = bool(
                ch.get("url")
                or ch.get("play_ref")
                or ch.get("vavoo_id")
                or ch.get("wltv_id")
                or ch.get("sky_id")
                or ch.get("sky_ppv_id")
            )
            if not has_source:
                missing.append("%s (LCN %s)" % (ch.get("name", "?"), ch.get("lcn", "?")))
                utils.log("Senza fonte: %s (LCN %s)" % (ch.get("name"), ch.get("lcn")))
                continue
            entries.append(_entry_from_channel(ch))

        utils.log("Catalogo M3U: %d canali, %d senza fonte" % (len(entries), len(missing)))

        if not entries:
            return False, {"error": utils.localize(32215)}

        if not progress.update(50, utils.localize(32216)):
            return False, {"canceled": True}

        _write_text(m3u_file(), build_m3u(entries))
        save_state(entries)

        if not utils.setting_bool("pvr_enabled", True):
            progress.update(100, utils.localize(32220))
            return True, {
                "total": len(catalog),
                "configured": len(entries),
                "missing": missing,
                "pvr": False,
            }

        if not progress.update(70, utils.localize(32217)):
            return False, {"canceled": True}

        try:
            ok = export_list_to_pvr(m3u_file(), channel_fetcher.get_epg_url(), instance_name)
        except Exception as exc:
            utils.log("export_list_to_pvr eccezione: %s" % exc)
            ok = False

        if not ok:
            try:
                ensure_enabled()
            except Exception:
                pass
            return False, {"error": utils.localize(32218)}

        progress.update(100, utils.localize(32220))
        return True, {
            "total": len(catalog),
            "configured": len(entries),
            "missing": missing,
            "pvr": True,
        }
    finally:
        progress.close()


def remove_all(silent=False):
    instance_name = utils.setting("instance_name", "CanàTV") or "CanàTV"
    try:
        remove_instance(instance_name)
    except Exception as exc:
        utils.log("remove_instance: %s" % exc)
    for path in (m3u_file(), state_file()):
        try:
            xbmcvfs.delete(path)
        except Exception:
            pass
    return True