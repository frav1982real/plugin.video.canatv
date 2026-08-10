import sys
import os
import logging
import xbmcgui
import xbmc
import xbmcplugin
import xbmcaddon
import json
import string
import random
import re
import time
import xbmcvfs

# Get the plugin url in plugin:// notation. 
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])
addon_id = 'plugin.video.canatv'
#selfAddon = xbmcaddon.Addon(id=addon_id)
xbmcaddon.Addon(id=addon_id).setSetting("debug", "on")

debug = xbmcaddon.Addon(id=addon_id).getSetting("debug")

PY3 = sys.version_info[0] == 3
if PY3:
    from urllib.parse import urlencode, parse_qsl
else:
    from urlparse import urlparse, parse_qsl
    from urllib import urlencode, quote

# Compat: genera un ID dispositivo a 6 caratteri usato per l'UA/headers.
def id_generator(size=6, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
	
def logga(mess):
    global testoLog
    if debug == "on":
        logging.warning("CANA_LOG: \n"+mess)
        testoLog += mess+"\n";

def makeRequest(url, hdr=None):
    html = ""
    if PY3:
        import urllib.request as myRequest
    else:
        import urllib2 as myRequest
    pwd = xbmcaddon.Addon(id=addon_id).getSetting("password")
    deviceId = xbmcaddon.Addon(id=addon_id).getSetting("urlAppo2")
    if (deviceId == "Not in use" or deviceId == "" or len(deviceId) != 6):
        #generate id
        deviceId = id_generator()
        xbmcaddon.Addon(id=addon_id).setSetting("urlAppo2", deviceId)
    version = xbmcaddon.Addon(id=addon_id).getAddonInfo("version")
    if hdr is None:
        ua = "MandraKodi2@@"+version+"@@"+pwd+"@@"+deviceId
        hdr = {"User-Agent" : ua}
    try:
        req = myRequest.Request(url, headers=hdr)
        response = myRequest.urlopen(req, timeout=45)
        html = response.read().decode('utf-8')
        response.close()
    except:
        logging.warning('Error to open url: '+url)
        pass
    return html

def jsonrpcRequest(method, params=None):
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else {},
        "id": 1
    }

    response = xbmc.executeJSONRPC(json.dumps(request))
    return json.loads(response)
