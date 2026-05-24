"""Hamburg Airport Arrivals – Home Assistant Integration."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, API_BASE_URL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
HAM_TZ = ZoneInfo("Europe/Berlin")


def _parse_time(t: str | None) -> datetime | None:
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.split("[")[0])
    except Exception:
        return None


def _fmt(t: str | None) -> str | None:
    if not t:
        return None
    try:
        return t.split("[")[0][11:16]
    except Exception:
        return t


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api_key = entry.data["api_key"]
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    coordinator = HamburgAirportDataCoordinator(hass, api_key, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


class HamburgAirportDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_key, scan_interval):
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(minutes=scan_interval))
        self.api_key = api_key

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Accept": "application/json",
        }
        try:
            async with session.get(
                f"{API_BASE_URL}/flights/arrivals",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise UpdateFailed("Ungültiger API-Schlüssel (401)")
                if response.status == 403:
                    raise UpdateFailed("Zugriff verweigert (403)")
                if response.status != 200:
                    raise UpdateFailed(f"HTTP {response.status}")
                text = await response.text()
                data = json.loads(text)
        except json.JSONDecodeError as err:
            raise UpdateFailed(f"Ungültiges JSON: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Verbindungsfehler: {err}") from err
        return self._process_arrivals(data)

    def _process_arrivals(self, raw_data) -> dict:
        arrivals = raw_data if isinstance(raw_data, list) else raw_data.get("arrivals", [])
        now = datetime.now(tz=HAM_TZ)

        # Alle Flüge parsen und mit Referenzzeit versehen
        all_flights = []
        for f in arrivals:
            ref_time = _parse_time(f.get("expectedArrivalTime")) or \
                       _parse_time(f.get("plannedArrivalTime"))
            if ref_time is None:
                continue
            all_flights.append({
                "flight_number":    f.get("flightnumber", ""),
                "origin_iata":      f.get("originAirport3LCode", ""),
                "origin_name":      f.get("originAirportName", ""),
                "origin_name_int":  f.get("originAirportNameInt", ""),
                "planned_arrival":  _fmt(f.get("plannedArrivalTime")),
                "expected_arrival": _fmt(f.get("expectedArrivalTime")),
                "terminal":         f.get("arrivalTerminal", ""),
                "status":           f.get("flightStatusArrival", ""),
                "via_airport":      f.get("viaAirportName"),
                "_ref_time":        ref_time.astimezone(HAM_TZ),
            })

        # Nach Referenzzeit sortieren
        all_flights.sort(key=lambda x: x["_ref_time"])

        # In vergangene und zukünftige aufteilen
        past    = [f for f in all_flights if f["_ref_time"] < now]
        future  = [f for f in all_flights if f["_ref_time"] >= now]

        # Letzte 2 vergangene + nächste 2 kommende
        window = past[-2:] + future[:2]

        # Internes Sortierfeld entfernen
        for f in window:
            del f["_ref_time"]

        next_arrival = future[0] if future else {}
        if next_arrival:
            next_arrival = dict(next_arrival)

        _LOGGER.debug(
            "HAM: %d vergangen, %d kommend – Fenster: %s",
            len(past), len(future),
            [f["flight_number"] for f in window]
        )

        return {
            "window":       window,       # 2 vergangene + 2 kommende
            "next_arrival": next_arrival, # nächster Flug für Einzel-Sensoren
            "past_count":   len(past),
            "future_count": len(future),
        }