# core.py

import os
import json
import re
import time
import difflib
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import urllib.request

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
URL_CANAL_JSON = "https://raw.githubusercontent.com/ElBarcoDeSabeT/El-barco-de-sabeT-Online/main/canales.json"
PROXIES_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=json"


@dataclass
class Channel:
    nombre: str
    tvg_id: str
    logo: str


@dataclass
class Event:
    day: str
    time: str
    event: str
    channel: str
    sport: str


class CoreAddon:
    def __init__(self, addon_dir: str, cache_file: str):
        self.addon_dir = addon_dir
        self.cache_file = cache_file
        self.channels: List[Channel] = self.fetch_channels(URL_CANAL_JSON)
        self.tv_programs: List[Event] = self.get_tv_programs()

    def fetch_channels(self, url: str) -> List[Channel]:
        """Fetch channel list from a remote JSON URL."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            channels_data = response.json()
            channels = [Channel(**channel) for channel in channels_data]
            logger.info(f"Fetched {len(channels)} channels.")
            return channels
        except requests.RequestException as e:
            logger.error(f"Failed to load channels from {url}: {e}")
            return []

    def get_tv_programs(
        self, url: str = "https://www.marca.com/programacion-tv.html"
    ) -> List[Event]:
        """Retrieve TV programs from the specified URL, ensuring no duplicates."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            day_sections = soup.find_all("li", class_="content-item")
            events_data = []
            seen_events = set()
            day_sections = day_sections[1:]

            for day_section in day_sections:
                day_span = day_section.find("span", class_="title-section-widget")
                if not day_span:
                    continue
                day = day_span.text.strip()

                events = day_section.find_all("li", class_="dailyevent")
                for event in events:
                    time_tag = event.find("strong", class_="dailyhour")
                    event_name_tag = event.find("h4", class_="dailyteams")
                    channel_tag = event.find("span", class_="dailychannel")
                    sport_tag = event.find("span", class_="dailyday")

                    time_text = time_tag.text.strip() if time_tag else "N/A"
                    event_name = (
                        event_name_tag.text.strip() if event_name_tag else "N/A"
                    )
                    channel = channel_tag.text.strip() if channel_tag else "N/A"
                    sport = sport_tag.text.strip() if sport_tag else "N/A"

                    event_id = (day, time_text, event_name, channel)
                    if event_id not in seen_events:
                        events_data.append(
                            Event(day, time_text, event_name, channel, sport)
                        )
                        seen_events.add(event_id)

            logger.info(f"Fetched {len(events_data)} unique TV programs.")
            print(events_data)
            return events_data
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve TV programs from {url}: {e}")
            return []

    def find_closest_channel(
        self, channel_name: str, channels_names: List[str]
    ) -> Optional[str]:
        """Find the closest matching channel name using difflib."""
        closest_matches = difflib.get_close_matches(
            channel_name, [c for c in channels_names], n=1, cutoff=0.5
        )
        return closest_matches[0] if closest_matches else None

    def load_cache(self) -> Dict:
        """Load cache data from the cache file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    logger.info("Cache loaded successfully.")
                    return cache
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load cache: {e}")
        return {}

    def save_cache(self, data: Dict):
        """Save data to the cache file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                logger.info("Cache saved successfully.")
        except IOError as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")


    def export_m3u(self, links: List[str], titles: List[str], dialog_interface, m3u_path):
        """Export the provided links and titles to an M3U file."""
        if not m3u_path:
            dialog_interface.notification("Canceled", "M3U export canceled.")
            return

        try:
            with open(m3u_path, "w", encoding="utf-8") as f:
                # Write M3U header with EPG URLs
                f.write(
                    '#EXTM3U url-tvg="https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml, https://raw.githubusercontent.com/Icastresana/lista1/main/epg.xml"\n'
                )
                for title, link in zip(titles, links):
                    # Extract channel name for matching
                    channel_name = " ".join(title.split()[:-1]).strip().lower()
                    channel = next(
                        (c for c in self.channels if c.nombre.lower() == channel_name),
                        None,
                    )
                    if channel:
                        f.write(
                            f'#EXTINF:-1 tvg-id="{channel.tvg_id}" tvg-logo="{channel.logo}",{title}\n{link}\n'
                        )
                    else:
                        f.write(f"#EXTINF:-1,{title}\n{link}\n")
            dialog_interface.notification("Success", f"M3U list exported to {m3u_path}")
            logger.info(f"M3U exported successfully to {m3u_path}")
        except IOError as e:
            dialog_interface.notification("Error", f"Failed to export M3U: {e}")
            logger.error(f"Failed to export M3U to {m3u_path}: {e}")

    def fetch_proxies(self, url: str) -> List[Dict]:
        """Fetch a list of proxies from the given URL."""
        try:
            with urllib.request.urlopen(url) as response:
                proxies_json = json.loads(response.read().decode('utf-8'))
                return proxies_json['proxies']  # Assuming the JSON has a 'proxies' key
        except Exception as e:
            logger.error(f"Failed to load proxies from {url}: {e}")
            return []

    def filter_asian_proxies(self, proxies: List[Dict]) -> List[str]:
        """Filter proxies to include only those from Asia."""
        proxies_asia = []
        for proxy in proxies:
            ip_data = proxy.get('ip_data')
            if ip_data and ip_data.get('continentCode') == 'AS':
                proxies_asia.append(proxy['proxy'])
        return proxies_asia

    def get_web_content(self, url: str, proxy: Optional[str] = None) -> Optional[str]:
        """Fetch web content using an optional proxy."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/58.0.3029.110 Safari/537.3"
            )
        }
        try:
            if proxy:
                proxies = {"http": proxy, "https": proxy}
                response = requests.get(
                    url, headers=headers, proxies=proxies, timeout=10
                )
            else:
                response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info(
                f"Fetched content from {url} using {'proxy ' + proxy if proxy else 'no proxy'}."
            )
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url} with proxy {proxy}: {e}")
            return None

    def extract_program_links(self, html: str) -> Tuple[List[str], List[str]]:
        """Extract program links and titles from the HTML content."""
        enlaces = {}
        titulos = []

        patrones = re.findall(r'<a href="(acestream://[^"]+)"[^>]*>(.*?)</a>', html)
        for enlace, titulo in patrones:
            nuevo_enlace = enlace.replace(
                "acestream://", "plugin://script.module.horus?action=play&id="
            )
            titulos.append(titulo.strip())
            enlaces[titulo.strip()] = nuevo_enlace

        new_enlaces = []
        new_titulos = []
        last_date = None
        print(titulos)
        titulos_without_quality = [title.replace("720", "").replace("1080", "") for title in titulos]
        for program in self.tv_programs:
            if program.day != last_date:
                last_date = program.day
                new_enlaces.append(f"# {program.day}")  # Add the date as a comment
                new_titulos.append(f"# {program.day}")  # Add the date as a comment
            if program.channel == "Movistar Plus+":
                closest_tvg_id = "M.Plus 1080"
            else:
                closest_tvg_id = self.find_closest_channel(
                    program.channel, titulos_without_quality
                )
                print(closest_tvg_id)
            found = False
            if closest_tvg_id:
                for quality in ["720", "1080"]:
                    if f"{closest_tvg_id}{quality}" in titulos:
                        found = True
                        new_closest_tvg_id = f"{closest_tvg_id}{quality}"  
                        new_enlaces.append(enlaces[new_closest_tvg_id])
                        new_titulos.append(
                            f"{program.sport} {program.time} {program.event} ({new_closest_tvg_id})"
                        )
                if closest_tvg_id in titulos:
                    found = True
                    new_enlaces.append(enlaces[closest_tvg_id])
                    new_titulos.append(
                        f"{program.sport} {program.time} {program.event} ({closest_tvg_id})"
                    )
                if not found:
                    new_enlaces.append(f"# No matching channel for {program.event}, this was the channel: {program.channel}")
                    new_titulos.append(f"{program.sport} {program.time} {program.event} - No match for {program.channel}")

        logger.info("Extracted program links.")
        return new_enlaces, new_titulos

    def extract_channel_links(self, html: str) -> Tuple[List[str], List[str]]:
        """Extract channel links and titles from the HTML content."""
        enlaces = []
        titulos = []

        patrones = re.findall(r'<a href="(acestream://[^"]+)"[^>]*>(.*?)</a>', html)
        for enlace, titulo in patrones:
            nuevo_enlace = enlace.replace(
                "acestream://", "plugin://script.module.horus?action=play&id="
            )
            enlaces.append(nuevo_enlace)
            ultimos_digitos = enlace.split("://")[1][-4:]
            titulos.append(f"{titulo.strip()} {ultimos_digitos}")

        logger.info("Extracted channel links.")
        return enlaces, titulos

    def update_list(self, dialog_interface = None) -> Dict:
        """Update the channel and program list, handling proxies if necessary."""
        options = ["Servidor Principal", "Servidor Espejo"]
        selection = 0  # Default to "Servidor Principal"
        origin = options[selection]
        url_selected = (
            "https://elcano.top"
            if selection == 0
            else "https://viendoelfutbolporlaface.pages.dev/"
        )
        proxies = self.fetch_proxies(PROXIES_URL)

        if not proxies:
            logger.error("No proxies available.")
            if dialog_interface:
                dialog_interface.notification("Error", "No proxies found.")
            return {}

        asian_proxies = self.filter_asian_proxies(proxies)

        # Attempt to fetch content without proxy
        if dialog_interface:
            dialog_interface.notification(
                "Connection", "Attempting to connect without proxy"
            )
        content = self.get_web_content(url_selected)

        if not content:
            # Attempt with proxies
            if dialog_interface:
                dialog_interface.notification(
                    "Proxy", "Attempting to connect using proxies"
                )
            for proxy in asian_proxies:
                if dialog_interface:
                    dialog_interface.notification("Proxy", f"Trying proxy: {proxy}")
                content = self.get_web_content(url_selected, proxy)
                if content:
                    logger.info(f"Successfully fetched content using proxy: {proxy}")
                    break
            else:
                if dialog_interface:
                    dialog_interface.notification(
                        "Error", "Failed to retrieve content with all proxies."
                    )
                logger.error("Failed to retrieve content using all proxies.")
                return {}

        if not content:
            # Fallback to a secondary URL
            logger.warning("Content still not fetched. Trying secondary URL.")
            content = self.get_web_content("https://viendoelfutbolporlaface.pages.dev/")
            if not content:
                logger.error("Failed to fetch content from secondary URL.")
                if dialog_interface:
                    dialog_interface.notification(
                        "Error", "Failed to retrieve content from secondary URL."
                    )
                return {}

        enlaces_eventos, titulos_eventos = self.extract_program_links(content)
        enlaces_canal, titulos_canal = self.extract_channel_links(content)

        logger.info("List updated.")
        logger.info("Event links:")
        for title, link in zip(titulos_eventos, enlaces_eventos):
            logger.info(f"{title}: {link}")

        # Save to cache
        cache_data = {
            "enlaces_eventos": enlaces_eventos,
            "titulos_eventos": titulos_eventos,
            "enlaces_canal": enlaces_canal,
            "titulos_canal": titulos_canal,
            "origen": origin,
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.save_cache(cache_data)

        logger.info("List updated and cached.")
        return cache_data
