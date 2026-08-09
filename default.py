# -*- coding: utf-8 -*-
import os
import sys
import re
import xbmc
import xbmcaddon
import xbmcgui
import logging

addon_id = "plugin.video.canatv"
xbmcaddon.Addon(id=addon_id).getSetting("debug")

def test():
    info = xbmcaddon.Addon(id=addon_id).getAddonInfo()

    def log():
        dialog = xbmcgui.Dialog()
        dialog.ok(info)

    log()

test()