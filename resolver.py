import re, requests, sys, logging, uuid
import os
import string
import random
import traceback
from urllib.parse import quote_plus, urlparse, parse_qsl, unquote
from requests import Response

import xbmcgui
import xbmc
import xbmcaddon
import xbmcplugin
import launcher

from urllib.request import Request, urlopen

def xor_decrypt(data_b64, key):
    import base64

    data = base64.b64decode(data_b64)
    key_bytes = key.encode()

    out = bytearray()
    for i in range(len(data)):
        out.append(data[i] ^ key_bytes[i % len(key_bytes)])

    return out.decode("utf-8")

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

def sky(parIn=None):
    import json
    import launcher
    from datetime import datetime, timedelta

    SECRET = "my_secret_key"

    apiUrl="https://test34344.herokuapp.com/filter.php?numTest=A1A159&id="+parIn
    resp = launcher.makeRequest(apiUrl)
    res=json.loads(resp)
    decrypted = xor_decrypt(res["data"], SECRET)
    data = json.loads(decrypted)

    manifest = data["manifest"]
    kid = data["kid"]
    key = data["key"]

    drmType="org.w3.clearkey"
    key64=kid+":"+key
    
    data_str = data["fine"]
    logga ("data_str ==> "+data_str)
    data_adesso = datetime.now()
    logga("ADESSO: " +data_adesso.strftime("%d/%m/%Y %H:%M:%S"))
    if "EXPIRE" not in data_str:
        
        try:
            data_roma = datetime.strptime(data_str, "%d/%m/%Y %H:%M:%S")
            data_roma = data_roma + timedelta(hours=2)
            if data_roma < data_adesso:
                data_scad=data_roma.strftime("%d/%m/%Y %H:%M:%S")
                msgBox("Link scaduto "+data_scad)
        except:
            pass
    
    liz = xbmcgui.ListItem(path=manifest, offscreen=True)
    liz.setContentLookup(False)

    liz.setProperty("inputstream", "inputstream.adaptive")
    liz.setProperty('inputstream.adaptive.drm_legacy', drmType+'|'+key64)

    ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    host="https://www.nowtv.it"
    liz.setProperty('inputstream.adaptive.stream_headers', 'User-Agent='+ua+'&Referer='+host+'/&Origin='+host+'&verifypeer=false')
    liz.setProperty('inputstream.adaptive.manifest_headers', 'User-Agent='+ua+'&Referer='+host+'/&Origin='+host+'&verifypeer=false')

    return liz