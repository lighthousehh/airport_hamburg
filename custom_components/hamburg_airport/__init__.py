from __future__ import annotations
import json, logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN, API_BASE_URL,
    DEFAULT_SCAN_INTERVAL, DEFAULT_PAST_COUNT, DEFAULT_FUTURE_COUNT,
    CONF_SCAN_INTERVAL, CONF_PAST_COUNT, CONF_FUTURE_COUNT,
    FLIGHT_TYPE_ARRIVALS, FLIGHT_TYPE_DEPARTURES,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
HAM_TZ = ZoneInfo("Europe/Berlin")

def _parse_time(t):
    if not t: return None
    try: return datetime.fromisoformat(t.split("[")[0])
    except: return None

def _fmt(t):
    if not t: return None
    try: return t.split("[")[0][11:16]
    except: return t

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    past_count    = entry.options.get(CONF_PAST_COUNT,    DEFAULT_PAST_COUNT)
    future_count  = entry.options.get(CONF_FUTURE_COUNT,  DEFAULT_FUTURE_COUNT)
    api_key       = entry.data["api_key"]
    arr = HamburgAirportCoordinator(hass, api_key, scan_interval, past_count, future_count, FLIGHT_TYPE_ARRIVALS)
    dep = HamburgAirportCoordinator(hass, api_key, scan_interval, past_count, future_count, FLIGHT_TYPE_DEPARTURES)
    await arr.async_config_entry_first_refresh()
    await dep.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {FLIGHT_TYPE_ARRIVALS: arr, FLIGHT_TYPE_DEPARTURES: dep}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

class HamburgAirportCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api_key, scan_interval, past_count, future_count, flight_type):
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{flight_type}",
                         update_interval=timedelta(minutes=scan_interval))
        self.api_key = api_key
        self.past_count = past_count
        self.future_count = future_count
        self.flight_type = flight_type

    async def _async_update_data(self) -> dict:
        endpoint = "arrivals" if self.flight_type == FLIGHT_TYPE_ARRIVALS else "departures"
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{API_BASE_URL}/flights/{endpoint}",
                headers={"Ocp-Apim-Subscription-Key": self.api_key, "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as r:
                if r.status == 401: raise UpdateFailed("Ungültiger API-Schlüssel (401)")
                if r.status == 403: raise UpdateFailed("Zugriff verweigert (403)")
                if r.status != 200: raise UpdateFailed(f"HTTP {r.status}")
                data = json.loads(await r.text())
        except json.JSONDecodeError as e: raise UpdateFailed(f"Ungültiges JSON: {e}") from e
        except aiohttp.ClientError as e:  raise UpdateFailed(f"Verbindungsfehler: {e}") from e
        return self._process(data)

    def _process(self, raw) -> dict:
        now = datetime.now(tz=HAM_TZ)
        is_arr = self.flight_type == FLIGHT_TYPE_ARRIVALS
        key_list = "arrivals" if is_arr else "departures"
        flights_raw = raw if isinstance(raw, list) else raw.get(key_list, [])
        all_flights = []
        for f in flights_raw:
            if is_arr:
                ref = _parse_time(f.get("expectedArrivalTime")) or _parse_time(f.get("plannedArrivalTime"))
                if not ref: continue
                all_flights.append({
                    "flight_number":  f.get("flightnumber", ""),
                    "origin_iata":    f.get("originAirport3LCode", ""),
                    "origin_name":    f.get("originAirportNameInt") or f.get("originAirportName", ""),
                    "planned_time":   _fmt(f.get("plannedArrivalTime")),
                    "expected_time":  _fmt(f.get("expectedArrivalTime")),
                    "terminal":       f.get("arrivalTerminal", ""),
                    "status":         f.get("flightStatusArrival", ""),
                    "_ref":           ref.astimezone(HAM_TZ),
                })
            else:
                ref = _parse_time(f.get("expectedDepartureTime")) or _parse_time(f.get("plannedDepartureTime"))
                if not ref: continue
                all_flights.append({
                    "flight_number":    f.get("flightnumber", ""),
                    "destination_iata": f.get("destinationAirport3LCode", ""),
                    "destination_name": f.get("destinationAirportNameInt") or f.get("destinationAirportName", ""),
                    "planned_time":     _fmt(f.get("plannedDepartureTime")),
                    "expected_time":    _fmt(f.get("expectedDepartureTime")),
                    "terminal":         f.get("departureTerminal", ""),
                    "gate":             f.get("gate", ""),
                    "status":           f.get("flightStatusDeparture", ""),
                    "_ref":             ref.astimezone(HAM_TZ),
                })
        all_flights.sort(key=lambda x: x["_ref"])
        past   = [f for f in all_flights if f["_ref"] < now]
        future = [f for f in all_flights if f["_ref"] >= now]
        window = (past[-self.past_count:] if self.past_count > 0 else []) + future[:self.future_count]
        next_flight = dict(future[0]) if future else {}
        for f in window + ([next_flight] if next_flight else []):
            f.pop("_ref", None)
        return {
            "window": window, "next_flight": next_flight,
            "past_count": len(past), "future_count": len(future),
            "window_past": self.past_count, "window_future": self.future_count,
            "flight_type": self.flight_type,
        }