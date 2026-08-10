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

def build_url(action):
    return addon + '?' + urllib.parse.urlencode({'action': action})

params = urllib.parse.parse_qs(sys.argv[2][1:])
action = params.get('action', [None])[0]
testpath = resolver.sky(parIn="skysport24")  # Ottieni il flusso di prova da resolver.py

if action == 'play_video':
    # Riproduci un video
    item = xbmcgui.ListItem(path=testpath)
    xbmcplugin.setResolvedUrl(addon, True, item)

elif action == 'open_settings':
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
    xbmcplugin.addDirectoryItem(addon, url, li, isFolder=False)
    xbmcplugin.endOfDirectory(addon)

# =====================
# MENU PRINCIPALE
# =====================
else:
    items = [
        ('Riproduci Flusso di Prova (skysport24)',    'play_video',        'DefaultMovies.png',    False),
        ('Impostazioni',       'open_settings',      'DefaultAddon.png',     False),
        ('Avvia Script',       'run_script',         'DefaultProgram.png',   False),
        ('Mostra Notifica',    'show_notification',  'DefaultAddon.png',     False),
        ('Conferma Azione',    'ask_user',           'DefaultAddon.png',     False),
        ('Aggiorna Libreria',  'builtin',            'DefaultFolder.png',    False),
        ('Sottomenu',          'subfolder',          'DefaultFolder.png',    True),
    ]

    for label, act, icon, is_folder in items:
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(addon, build_url(act), li, isFolder=is_folder)

    xbmcplugin.endOfDirectory(addon)