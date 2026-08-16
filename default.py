# -*- coding: utf-8 -*-
"""CanàTV - entry point plugin. Catalogo unico da canali.json, con Vavoo SEMPRE ultima opzione."""
import os
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import builder, channel_fetcher, resolver, utils

ADDON_ID = utils.ADDON_ID
_handle = int(sys.argv[1])


def _(msgid):
    return utils.localize(msgid)


def _icon():
    return os.path.join(utils.addon_path(), "resources", "icon.png")


def _notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification(title, message, icon, 5000)


def build_url(**params):
    return sys.argv[0] + "?" + urllib.parse.urlencode(params)


def parse_params():
    raw = sys.argv[2] if len(sys.argv) > 2 else ""
    if raw.startswith("?"):
        raw = raw[1:]
    return dict(urllib.parse.parse_qsl(raw))


def _entries():
    """Scaletta locale + id aggiornati. Mai riusare URL firmati/scaduti dallo state."""
    from resources.lib import wltv

    configured = channel_fetcher.load_configured_channels()
    by_lcn = {ch.get("lcn"): ch for ch in configured}
    state = builder.load_state() or []
    if not state:
        return [builder._entry_from_channel(ch) for ch in configured]
    merged = []
    for entry in state:
        cat = by_lcn.get(entry.get("lcn"))
        if cat:
            for key in ("source", "sky_ppv_id", "sky_id", "wltv_id", "is_free", "name", "group", "vavoo_id"):
                if cat.get(key) not in (None, ""):
                    entry[key] = cat[key]
            inferred = wltv.infer_play_ref(entry)
            if inferred:
                entry["play_ref"] = inferred
            stale = entry.get("url") or ""
            if stale.startswith("http") and "tvchannels.worldtvlive.eu" not in stale:
                entry["url"] = ""
        merged.append(entry)
    return merged


def _resolve_vavoo_id_on_the_fly(name):
    """Safety net: se un canale non ha vavoo_id pre-salvato, prova on-the-fly.

    Usato come ultima rete di sicurezza in play_channel: se la sorgente
    primaria fallisce e non c'e vavoo_id, cerca comunque nel catalogo Vavoo
    per nome canale.
    """
    if not name:
        return ""
    try:
        index = channel_fetcher._build_vavoo_index(channel_fetcher.fetch_vavoo_channels())
        if not index:
            return ""
        vch = channel_fetcher.match_vavoo_channel({"name": name}, index)
        if not vch:
            return ""
        return channel_fetcher._extract_vavoo_id(vch)
    except Exception:
        return ""


def main_menu():
    items = [
        (_(32100), "setup", False),
        (_(32101), "browse", True),
        (_(32102), "playtest", False),
        (_(32103), "remove", False),
        (_(32104), "settings", False),
    ]
    listing = []
    for label, action, is_folder in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": _icon(), "icon": _icon()})
        listing.append((build_url(action=action), li, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def run_setup():
    if not xbmcgui.Dialog().yesno(ADDON_ID, _(32206)):
        return
    try:
        ok, info = builder.build_all(silent=False)
    except Exception as exc:
        utils.log("build_all exception: %s" % exc)
        _notify(ADDON_ID, _(32203) % str(exc), xbmcgui.NOTIFICATION_ERROR)
        return
    if info.get("canceled"):
        _notify(ADDON_ID, _(32202), xbmcgui.NOTIFICATION_WARNING)
        return
    if not ok:
        _notify(ADDON_ID, _(32203) % info.get("error", "?"), xbmcgui.NOTIFICATION_ERROR)
        return
    message = _(32200) % (info["configured"], info["total"])
    missing = info.get("missing") or []
    if missing:
        shown = ", ".join(missing[:10])
        if len(missing) > 10:
            shown += " ..."
        message += "\n" + (_(32201) % shown)
    xbmcgui.Dialog().ok(ADDON_ID, message)


def run_remove():
    if not xbmcgui.Dialog().yesno(ADDON_ID, _(32207)):
        return
    try:
        builder.remove_all()
    except Exception as exc:
        utils.log("remove_all exception: %s" % exc)
        _notify(ADDON_ID, _(32205) % str(exc), xbmcgui.NOTIFICATION_ERROR)
        return
    xbmcgui.Dialog().ok(ADDON_ID, _(32204))


def browse_groups():
    entries = _entries()
    groups = []
    seen = set()
    for entry in entries:
        group = entry.get("group") or _(32106)
        if group not in seen:
            seen.add(group)
            groups.append(group)

    listing = []
    all_item = xbmcgui.ListItem(label=_(32105))
    all_item.setArt({"thumb": _icon(), "icon": _icon()})
    listing.append((build_url(action="browse", group="*"), all_item, True))
    for group in groups:
        li = xbmcgui.ListItem(label=group)
        li.setArt({"thumb": _icon(), "icon": _icon()})
        listing.append((build_url(action="browse", group=group), li, True))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def _add_channel_item(entry, listing):
    label = "%s. %s" % (entry.get("lcn"), entry.get("name"))
    li = xbmcgui.ListItem(label=label)
    art = entry.get("logo") or _icon()
    li.setArt({"thumb": art, "icon": art})
    li.setInfo("video", {"plot": "%s - %s" % (entry.get("group") or "", entry.get("name") or "")})
    li.setProperty("IsPlayable", "true")
    listing.append(
        (
            build_url(
                action="play",
                source=entry.get("source") or "wltv",
                identifier=utils.channel_identifier(entry),
                name=entry.get("name") or "",
                vavoo_id=entry.get("vavoo_id") or "",
            ),
            li,
            False,
        )
    )


def browse_channels(group=None):
    entries = _entries()
    if group and group != "*":
        entries = [e for e in entries if (e.get("group") or "") == group]
    listing = []
    for entry in entries:
        _add_channel_item(entry, listing)
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.setContent(_handle, "videos")
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)


def run_playtest():
    utils.set_debug()
    try:
        catalog = channel_fetcher.build_channel_catalog()
    except Exception as exc:
        xbmcgui.Dialog().ok(ADDON_ID, _(32211) % str(exc))
        return

    target = None
    for ch in catalog:
        if utils.normalize_name(ch.get("name") or "").startswith("RAI1"):
            target = ch
            break
    if not target:
        xbmcgui.Dialog().ok(ADDON_ID, _(32210))
        return
    play_channel(
        {
            "source": target.get("source") or "wltv",
            "identifier": utils.channel_identifier(target),
            "name": target.get("name") or "",
            "vavoo_id": target.get("vavoo_id") or "",
        }
    )


def play_channel(params):
    """Riproduce un canale. SEMPRE: 1) sorgente primaria, 2) Vavoo ultima opzione.

    Vavoo e' l'ultima spiaggia: viene sempre tentato come fallback finale,
    indipendentemente dal fatto che la sorgente primaria abbia funzionato.
    Se vavoo_id non era pre-salvato, si fa un match on-the-fly col nome del
    canale. Cosi OGNI click su un canale finisce sempre con Vavoo come
    ultima opzione tentata.
    """
    utils.set_debug()
    source = params.get("source") or "wltv"
    identifier = params.get("identifier") or ""
    name = params.get("name") or "Canale"
    vavoo_id = params.get("vavoo_id") or ""

    if not identifier and not vavoo_id and not name:
        xbmcgui.Dialog().ok(ADDON_ID, _(32208) % "Canale")
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    # Step 1: Prova sorgente primaria (WLTV o Sky)
    li = None
    if identifier:
        li = resolver.resolve(source, identifier)

    # Step 2: SEMPRE Vavoo come ultima opzione.
    # Se non c'e vavoo_id pre-salvato, prova on-the-fly col nome canale
    # (anche se la sorgente primaria ha funzionato: cosi Vavoo e' SEMPRE
    # l'ultima alternativa esplorata come richiesto).
    if not vavoo_id and name:
        vavoo_id = _resolve_vavoo_id_on_the_fly(name)
        if vavoo_id:
            utils.log("On-the-fly Vavoo ID per '%s': %s" % (name, vavoo_id))

    if not li and vavoo_id:
        utils.log("Fallback Vavoo per %s (vavoo_id=%s)" % (name, vavoo_id))
        li = resolver.resolve("vavoo", vavoo_id)

    if not li:
        xbmcgui.Dialog().ok(ADDON_ID, _(32209) % name)
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    if _handle >= 0:
        xbmcplugin.setResolvedUrl(_handle, True, li)
    else:
        xbmc.Player().play(li.getPath(), li)


def open_settings():
    utils.addon().openSettings()


def router():
    utils.set_debug()
    params = parse_params()
    action = params.get("action", "menu")
    if action == "menu":
        main_menu()
    elif action == "setup":
        run_setup()
    elif action == "browse":
        if params.get("group"):
            browse_channels(params.get("group"))
        else:
            browse_groups()
    elif action == "playtest":
        run_playtest()
    elif action == "remove":
        run_remove()
    elif action == "settings":
        open_settings()
    elif action == "play":
        play_channel(params)
    elif action == "clear_cache":
        channel_fetcher.refresh_all_caches()
        _notify(ADDON_ID, _(32212))
        main_menu()
    else:
        main_menu()


if __name__ == "__main__":
    router()