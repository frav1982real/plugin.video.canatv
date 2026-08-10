import xbmc
import xbmcaddon
import xbmcgui
import os
import sys
import xbmcplugin
import json as _json
import re
import xbmcvfs

from . import utils

PVR_ID = utils.PVR_ID

def _translate(path):
    try:
        return xbmcvfs.translatePath(path)
    except Exception:
        return xbmc.translatePath(path)

def _safe_delete(path):
    try:
        if xbmcvfs.exists(path):
            xbmcvfs.delete(path)
            return True
    except Exception:
        pass
    return False

def is_addon_installed(addon_id):
    return xbmc.getCondVisibility("System.HasAddon(%s)" % addon_id)

def set_addon_enabled(addon_id, enabled):
    try:
        xbmc.executeJSONRPC(
            '{"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "%s", "enabled": %s}}' % (addon_id, "true" if enabled else "false")
        )
    except Exception as exc:
        utils.log("SetAddonEnabled errore: %s" % exc)

def is_addon_enabled(addon_id):
    try:
        resp = xbmc.executeJSONRPC(
            '{"jsonrpc": "2.0", "id":1, "method": "Addons.GetAddonDetails",'
            ' "params": { "addonid": "%s", "properties": ["enabled"] } }' % addon_id
        )
        data = _json.loads(resp)
        return bool(data.get("result", {}).get("addon", {}).get("enabled", False))
    except Exception:
        return True

def ensure_enabled():
    """Garantisce che il client PVR sia attivo."""
    try:
        if not is_addon_installed(PVR_ID):
            return False
        if not is_addon_enabled(PVR_ID):
            set_addon_enabled(PVR_ID, True)
            xbmc.sleep(1500)
        return is_addon_enabled(PVR_ID)
    except Exception as exc:
        utils.log("ensure_enabled errore: %s" % exc)
        return False

def ensure_pvr_installed():
    """Installare/attivare pvr.iptvsimple se assente."""
    if not is_addon_installed(PVR_ID):
        try:
            xbmc.executebuiltin("InstallAddon(%s)" % PVR_ID, True)
        except TypeError:
            xbmc.executebuiltin("InstallAddon(%s)" % PVR_ID)
        xbmc.sleep(3000)
    if not is_addon_installed(PVR_ID):
        return False
    try:
        xbmcaddon.Addon(id=PVR_ID)
        return True
    except RuntimeError:
        set_addon_enabled(PVR_ID, True)
        xbmc.sleep(1500)
        return True

def _pvr_profile():
    simple_client = xbmcaddon.Addon(PVR_ID)
    return _translate(simple_client.getAddonInfo("profile"))

def _list_files(folder, prefix="instance-settings", suffix=".xml"):
    found = []
    try:
        dirs, files = xbmcvfs.listdir(folder)
        for f in files:
            if f.startswith(prefix) and f.endswith(suffix):
                found.append(os.path.join(folder, f))
    except Exception as exc:
        utils.log("list_files errore: %s" % exc)
    return found

def _read_xml_setting(file_path, setting_id):
    """Legge <setting id="...">valore</setting> da un file xml."""
    try:
        f = xbmcvfs.File(file_path, "r")
        try:
            content = f.read()
        finally:
            f.close()
        if isinstance(content, bytes):
            content = content.decode("utf-8", "ignore")
        m = re.search(
            r'<setting\s+id="%s"[^>]*>(.*?)</setting>' % re.escape(setting_id),
            content,
            re.DOTALL,
        )
        if m:
            return m.group(1).strip()
        return ""
    except Exception:
        return ""

def get_pvr_instances(instance_name=None):
    """Metadati delle istanze esistenti di pvr.iptvsimple."""
    try:
        pvr_path = _pvr_profile()
    except Exception:
        return []
    instances = []
    for file_path in _list_files(pvr_path):
        m = re.search(r"instance-settings-(\d+)\.xml", os.path.basename(file_path))
        if not m:
            continue
        instances.append(
            {
                "instanceId": int(m.group(1)),
                "name": _read_xml_setting(file_path, "kodi_addon_instance_name"),
                "enabled": _read_xml_setting(file_path, "kodi_addon_instance_enabled"),
                "m3u": _read_xml_setting(file_path, "m3uPath"),
                "epg": _read_xml_setting(file_path, "epgUrl"),
            }
        )
    return instances

def get_or_create_instance_id(instance_name):
    instances = get_pvr_instances(instance_name)
    existing = [i for i in instances if i["name"] == instance_name]
    if existing:
        return sorted(existing, key=lambda i: i["instanceId"])[0]["instanceId"]
    used = set(i["instanceId"] for i in instances)
    iid = 1
    while iid in used:
        iid += 1
    return iid


def export_list_to_pvr(m3u_path, epg_url, instance_name):
    """Scrive M3U (file locale) ed EPG (URL remoto) nell'istanza dedicata."""
    if not ensure_pvr_installed():
        return False

    try:
        simple_client = xbmcaddon.Addon(PVR_ID)
        pvr_path = _pvr_profile()
    except Exception as exc:
        utils.log("export: impossibile accedere a pvr.iptvsimple: %s" % exc)
        return False

    settings_path = _translate(os.path.join(pvr_path, "settings.xml"))
    instance_id = get_or_create_instance_id(instance_name)
    instance_settings_path = _translate(
        os.path.join(pvr_path, "instance-settings-%d.xml" % instance_id)
    )

    try:
        # --- M3U: file locale ---
        simple_client.setSetting("m3uPathType", "0")
        simple_client.setSetting("m3uPath", m3u_path)
        simple_client.setSetting("m3uUrl", "")
        simple_client.setSetting("m3uCache", "true")

        # --- EPG: URL remoto (lo scarica e aggiorna il client PVR) ---
        simple_client.setSetting("epgPathType", "1")
        simple_client.setSetting("epgUrl", epg_url)
        simple_client.setSetting("epgPath", "")
        simple_client.setSetting("epgCache", "true")

        # loghi canale dall'EPG quando mancano nell'M3U
        simple_client.setSetting("logoFromEpg", "2")

        # --- Metadati dell'istanza ---
        simple_client.setSetting("kodi_addon_instance_name", instance_name)
        simple_client.setSetting("kodi_addon_instance_enabled", "true")
    except Exception as exc:
        utils.log("export: setSetting fallito: %s" % exc)
        return False

    # da' il tempo a Kodi di scrivere settings.xml, poi copialo sull'istanza
    xbmc.sleep(500)
    try:
        if xbmcvfs.exists(settings_path):
            xbmcvfs.copy(settings_path, instance_settings_path)
    except Exception as exc:
        utils.log("export: copia settings.xml fallita: %s" % exc)
    _safe_delete(settings_path)

    utils.log(
        "Istanza %d configurata: m3u=%s epg=%s" % (instance_id, m3u_path, epg_url)
    )
    return True


def cleanup_pvr_cache():
    """Forza Kodi a rileggere lista ed EPG: disattiva il client, ripulisce
    cache e database, poi lo riattiva (riattivazione garantita)."""
    pvr_path = None
    try:
        pvr_path = _pvr_profile()
    except Exception as exc:
        utils.log("cleanup: profilo pvr non accessibile: %s" % exc)

    try:
        set_addon_enabled(PVR_ID, False)
        xbmc.sleep(1500)

        if pvr_path:
            # eventuali cache locali di M3U/XMLTV
            for pattern in ("iptv.m3u.cache", "xmltv.xml.cache"):
                for f in _list_files(pvr_path, prefix=pattern, suffix=""):
                    _safe_delete(f)
            # settings.xml residuo dello spegnimento
            _safe_delete(os.path.join(pvr_path, "settings.xml"))

        # database canali/EPG di Kodi (special://database)
        try:
            import sqlite3

            db_folder = _translate("special://database")
            _, db_files = xbmcvfs.listdir(db_folder)
            tv_dbs = sorted([f for f in db_files if re.match(r"TV.*\.db$", f)])
            epg_dbs = sorted([f for f in db_files if re.match(r"Epg.*\.db$", f)])
            if tv_dbs:
                try:
                    conn = sqlite3.connect(os.path.join(db_folder, tv_dbs[-1]))
                    conn.execute("UPDATE channels SET idEpg = NULL")
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    utils.log("cleanup TV db: %s" % exc)
            if epg_dbs:
                try:
                    conn = sqlite3.connect(os.path.join(db_folder, epg_dbs[-1]))
                    conn.execute("DELETE FROM lastepgscan")
                    conn.execute("DELETE FROM epgtags")
                    conn.execute("DELETE FROM epg")
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    utils.log("cleanup EPG db: %s" % exc)
        except Exception as exc:
            utils.log("cleanup db: %s" % exc)
    except Exception as exc:
        utils.log("cleanup_pvr_cache errore: %s" % exc)
    finally:
        # RIATTIVAZIONE GARANTITA del client PVR
        xbmc.sleep(500)
        set_addon_enabled(PVR_ID, True)
        xbmc.sleep(2000)
        if not ensure_enabled():
            utils.log("cleanup: il client PVR non risulta ancora attivo")


def remove_instance(instance_name):
    """Elimina l'istanza gestita dall'addon."""
    try:
        pvr_path = _pvr_profile()
    except Exception:
        return False
    targets = []
    for file_path in _list_files(pvr_path):
        if _read_xml_setting(file_path, "kodi_addon_instance_name") == instance_name:
            targets.append(file_path)
    if not targets:
        return False
    try:
        set_addon_enabled(PVR_ID, False)
        xbmc.sleep(1500)
        for file_path in targets:
            _safe_delete(file_path)
        _safe_delete(os.path.join(pvr_path, "settings.xml"))
    finally:
        xbmc.sleep(500)
        set_addon_enabled(PVR_ID, True)
    return True