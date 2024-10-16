# kodi_addon.py

import sys
import os
import json
import logging
from typing import Optional, Dict

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import urllib.parse

from core import CoreAddon, Channel, Event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
ADDON = xbmcaddon.Addon()
ADDON_DIR = ADDON.getAddonInfo("path")
LIB_PATH = os.path.join(ADDON_DIR, "lib")
sys.path.append(LIB_PATH)

PLUGIN_URL = sys.argv[0]
HANDLE = int(sys.argv[1])
CACHE_FILE = os.path.join(ADDON_DIR, "cache.json")


class KodiAddonWrapper:
    def __init__(self):
        self.handle = HANDLE
        self.plugin_url = PLUGIN_URL
        self.addon_dir = ADDON_DIR
        self.cache_file = CACHE_FILE
        self.core = CoreAddon(self.addon_dir, self.cache_file)

    def handle_action(self, action: Optional[str]):
        """Handle different actions based on user selection."""
        if action == "directos":
            self.update_list()
            self.show_directos()
        elif action == "actualizar_lista":
            self.update_list(button=True)
        elif action == "canales":
            self.update_list()
            self.show_canales()
        elif action == "exportar_m3u":
            self.update_list()
            self.export_m3u()
        elif action == "play_link":
            # Extract the link from parameters
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
            link = params.get("link")
            if link:
                self.play_link(link)
            else:
                xbmcgui.Dialog().notification("Error", "No link provided to play.")
                logger.error("Play action triggered without a link.")
        else:
            self.show_main_menu()

    def show_main_menu(self):
        """Display the main menu with options."""
        main_options = ["Directos Tebas", "Canales", "Exportar M3U", "Actualizar lista"]
        for option in main_options:
            if option == "Exportar M3U":
                # This option triggers an action, not a directory item
                list_item = xbmcgui.ListItem(label=option)
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=f"{self.plugin_url}?action=exportar_m3u",
                    listitem=list_item,
                    isFolder=False,
                )
            elif option == "Actualizar lista":
                # This option triggers an action, not a directory item
                list_item = xbmcgui.ListItem(label=option)
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=f"{self.plugin_url}?action=actualizar_lista",
                    listitem=list_item,
                    isFolder=False,
                )
            elif option == "Directos Tebas":
                # This option leads to direct events
                list_item = xbmcgui.ListItem(label=option)
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=f"{self.plugin_url}?action=directos",
                    listitem=list_item,
                    isFolder=True,
                )
            else:
                # These options lead to submenus
                list_item = xbmcgui.ListItem(label=option)
                xbmcplugin.addDirectoryItem(
                    handle=self.handle,
                    url=f"{self.plugin_url}?action={option.lower()}",
                    listitem=list_item,
                    isFolder=True,
                )
        xbmcplugin.endOfDirectory(self.handle)

    def show_directos(self):
        """Display the mapping of events and links."""
        cache = self.core.load_cache()

        if not cache:
            xbmcgui.Dialog().notification(
                "Info", "Cache is empty. Please update the list first."
            )
            logger.info("Cache is empty; prompting user to update the list.")
            return

        enlaces_eventos = cache.get("enlaces_eventos", [])
        titulos_eventos = cache.get("titulos_eventos", [])

        if not enlaces_eventos or not titulos_eventos:
            xbmcgui.Dialog().notification(
                "Info", "No direct links available. Please update the list."
            )
            logger.info("No direct links found in cache.")
            return

        # Display the list of direct events
        for title, link in zip(titulos_eventos, enlaces_eventos):
            if link.startswith("#"):
                # This is a comment (e.g., date)
                list_item = xbmcgui.ListItem(label=title)
                xbmcplugin.addDirectoryItem(
                    handle=self.handle, url=link, listitem=list_item, isFolder=False
                )
            else:
                # Option 1: Let Kodi handle playing via IsPlayable
                list_item = xbmcgui.ListItem(label=title)
                list_item.setInfo("video", {"title": title})
                list_item.setProperty("IsPlayable", "true")
                xbmcplugin.addDirectoryItem(
                    handle=self.handle, url=link, listitem=list_item, isFolder=False
                )

                # Option 2: Use explicit play_link action (uncomment to use)
                # list_item = xbmcgui.ListItem(label=title)
                # list_item.setInfo("video", {"title": title})
                # xbmcplugin.addDirectoryItem(
                #     handle=self.handle,
                #     url=f"{self.plugin_url}?action=play_link&link={urllib.parse.quote(link)}",
                #     listitem=list_item,
                #     isFolder=False,
                # )
        xbmcplugin.endOfDirectory(self.handle)

    def show_canales(self):
        """Display the list of channels."""
        cache = self.core.load_cache()

        if not cache:
            xbmcgui.Dialog().notification(
                "Info", "Cache is empty. Please update the list first."
            )
            logger.info("Cache is empty; prompting user to update the list.")
            return

        enlaces_canal = cache.get("enlaces_canal", [])
        titulos_canal = cache.get("titulos_canal", [])

        if not enlaces_canal or not titulos_canal:
            xbmcgui.Dialog().notification(
                "Info", "No channels available. Please update the list."
            )
            logger.info("No channels found in cache.")
            return

        # Display the list of channels
        for title, link in zip(titulos_canal, enlaces_canal):
            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo("video", {"title": title})
            list_item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(
                handle=self.handle, url=link, listitem=list_item, isFolder=False
            )
        xbmcplugin.endOfDirectory(self.handle)

    def select_m3u_path(self) -> Optional[str]:
        """Display a dialog to select the M3U file save location."""
        selected_path = xbmcgui.Dialog().browse(
            type=3, heading="Select folder to save", shares="files"
        )
        if selected_path:
            filename = xbmcgui.Dialog().input(
                "M3U File Name", "ElBarcoDeSabet.m3u", type=xbmcgui.INPUT_ALPHANUM
            )
            if filename:
                if not filename.endswith(".m3u"):
                    filename += ".m3u"
                full_path = os.path.join(selected_path, filename)
                logger.info(f"M3U path selected: {full_path}")
                return full_path
        logger.info("M3U path selection canceled.")
        return None

    def export_m3u(self):
        """Export the cached channels to an M3U file."""
        cache = self.core.load_cache()
        path = self.select_m3u_path()
        if cache:
            self.core.export_m3u(
                cache.get("enlaces_canal", []),
                cache.get("titulos_canal", []),
                xbmcgui.Dialog(),
                path,
            )
        else:
            xbmcgui.Dialog().notification("Error", "No cache available to export.")
            logger.error("Export attempted without available cache.")

    def update_list(self, button=False):
        """Update the channel and program list."""
        if self.core.load_cache() and not button:
            return

        cache_data = self.core.update_list(xbmcgui.Dialog())
        if cache_data:
            xbmcgui.Dialog().notification("Success", "List updated successfully.")
        else:
            xbmcgui.Dialog().notification("Error", "Failed to update the list.")

    def play_link(self, link: str):
        """Play the selected link using Kodi's player."""
        try:
            xbmc.Player().play(link)
            xbmcgui.Dialog().notification("Playing", "Starting playback...")
            logger.info(f"Playing link: {link}")
        except Exception as e:
            xbmcgui.Dialog().notification("Error", f"Failed to play link: {e}")
            logger.error(f"Failed to play link {link}: {e}")

    def run(self):
        """Run the addon by handling the current action."""
        # Parse query parameters
        params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
        action = params.get("action")
        self.handle_action(action)


def main():
    addon = KodiAddonWrapper()
    addon.run()


if __name__ == "__main__":
    main()
