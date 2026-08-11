# -*- coding: utf-8 -*-
import os
import sys
import re
import xbmc
import xbmcaddon
import xbmcplugin
import xbmcgui
import logging
import urllib.parse
import resolver

addon_id = "plugin.video.canatv"
addon = xbmcaddon.Addon(id=addon_id)
xbmcaddon.Addon(id=addon_id).getSetting("debug")
addon_path = xbmcaddon.Addon().getAddonInfo('path')
addon_handle = int(sys.argv[1])

def build_url(action):
    return sys.argv[0] + '?' + urllib.parse.urlencode({'action': action})

params = urllib.parse.parse_qs(sys.argv[2][1:])
action = params.get('action', [None])[0]
testpath = resolver.sky(parIn="skysport24")  # Ottieni il flusso di prova da resolver.py

if action == 'play_videotest':
    # Riproduci un video
    path="https://file-examples.com/wp-content/storage/2018/04/file_example_AVI_1920_2_3MG.avi"
    item = xbmcgui.ListItem(offscreen=True)
    item.setPath(path)
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem=item)

elif action == 'open_settings_pvr':
    # Apri le impostazioni dell'addon
    addon.openSettings()

elif action == 'run_script':
    # Esegui uno script
    xbmc.executebuiltin('RunScript(%s/launcher.py)' % addon.getAddonInfo('path'))

elif action == 'show_notification':
    # Mostra una notifica
    xbmcgui.Dialog().notification('Titolo', 'Ciao!', xbmcgui.NOTIFICATION_INFO, 3000)

elif action == 'ask_user':
    # Chiedi conferma all'utente
    ok = xbmcgui.Dialog().yesno('Conferma', 'Vuoi procedere?')
    if ok:
        xbmc.log('Utente ha confermato', xbmc.LOGINFO)

elif action == 'builtin':
    # Esegui un comando built-in di Kodi
    xbmc.executebuiltin('UpdateLibrary(video)')

elif action == 'subfolder':
    # Mostra un sottomenu
    li = xbmcgui.ListItem('Voce secondaria')
    url = build_url('play_video')
    xbmcplugin.addDirectoryItem(addon_handle, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)

# =====================
# MENU PRINCIPALE
# =====================
else:
    items = [
        ('Riproduci Flusso di Prova (skysport24)',    'play_videotest',        'DefaultMovies.png',    False),
        ('Apri impostazioni PVR IPTV Simple Client',  'open_settings_pvr',      'DefaultAddon.png',     False),
        ('Avvia Script',       'run_script',         'DefaultProgram.png',   False),
        ('Mostra Notifica',    'show_notification',  'DefaultAddon.png',     False),
        ('Conferma Azione',    'ask_user',           'DefaultAddon.png',     False),
        ('Aggiorna Libreria',  'builtin',            'DefaultFolder.png',    False),
        ('Sottomenu',          'subfolder',          'DefaultFolder.png',    True),
    ]

    for label, act, icon, is_folder in items:
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(addon_handle, build_url(act), li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(addon_handle)