# -*- coding: utf-8 -*-
"""Service per CanàTV - aggiornamento automatico canali all'avvio di Kodi."""
import xbmc
import xbmcaddon

from resources.lib import utils

ADDON_ID = utils.ADDON_ID


class AutoUpdater(xbmc.Monitor):
    """Monitor Kodi per triggerare aggiornamento all'avvio e al risveglio."""

    def __init__(self):
        xbmc.Monitor.__init__(self)
        self.addon = xbmcaddon.Addon(ADDON_ID)

    def trigger_update(self, reason="manual"):
        xbmc.log("[CANATTV] Trigger update (%s)" % reason, xbmc.LOGINFO)
        _run_update(silent=True)

    def onSettingsChanged(self):
        try:
            self.addon = xbmcaddon.Addon(ADDON_ID)
        except Exception:
            pass

    def onNotification(self, sender, method, data):
        if method == "System.OnWake" and self.addon.getSetting("auto_update_wake") == "true":
            self.trigger_update("wake")

    def onWakeUp(self, reason=None):
        if self.addon.getSetting("auto_update_wake") == "true":
            self.trigger_update("wake")


def _run_update(silent=True):
    """Esegue l'aggiornamento completo (catalogo -> M3U -> PVR)."""
    try:
        from resources.lib import builder

        ok, info = builder.build_all(silent=silent)
        if ok:
            xbmc.log(
                "[CANATTV] Auto-update completed: %d channels configured"
                % info.get("configured", 0),
                xbmc.LOGINFO,
            )
        else:
            xbmc.log(
                "[CANATTV] Auto-update failed: %s" % info.get("error", "unknown"),
                xbmc.LOGERROR,
            )
    except Exception as exc:
        xbmc.log("[CANATTV] Auto-update exception: %s" % exc, xbmc.LOGERROR)


def service_entry():
    """Entry point per service.py (chiamato da Kodi all'avvio)."""
    addon = xbmcaddon.Addon(ADDON_ID)
    monitor = AutoUpdater()

    if addon.getSetting("auto_update") == "true":
        if monitor.waitForAbort(5):
            return

        online = False
        for _ in range(30):
            if xbmc.getCondVisibility("System.InternetState"):
                online = True
                break
            if monitor.waitForAbort(1):
                return

        if not online:
            xbmc.log("[CANATTV] No network, skipping auto-update", xbmc.LOGWARNING)
        else:
            xbmc.log("[CANATTV] Starting auto-update...", xbmc.LOGINFO)
            _run_update(silent=True)

    while not monitor.abortRequested():
        if monitor.waitForAbort(3600):
            break
        if addon.getSetting("auto_update_periodic") == "true":
            _run_update(silent=True)


if __name__ == "__main__":
    service_entry()
