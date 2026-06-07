from __future__ import annotations
import logging
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, FLIGHT_TYPE_ARRIVALS, FLIGHT_TYPE_DEPARTURES


_LOGGER = logging.getLogger(__name__)


ARRIVAL_SENSORS = (
    SensorEntityDescription(key="arr_next_number",   name="Nächste Landung Flugnummer",     icon="mdi:airplane-landing"),
    SensorEntityDescription(key="arr_next_origin",   name="Nächste Landung Herkunft",       icon="mdi:map-marker"),
    SensorEntityDescription(key="arr_next_iata",     name="Nächste Landung IATA",           icon="mdi:airport"),
    SensorEntityDescription(key="arr_next_planned",  name="Nächste Landung Planzeit",       icon="mdi:clock-outline"),
    SensorEntityDescription(key="arr_next_expected", name="Nächste Landung Erwartete Zeit", icon="mdi:clock-alert-outline"),
    SensorEntityDescription(key="arr_next_terminal", name="Nächste Landung Terminal",       icon="mdi:gate"),
    SensorEntityDescription(key="arr_next_status",   name="Nächste Landung Status",         icon="mdi:information-outline"),
)
DEPARTURE_SENSORS = (
    SensorEntityDescription(key="dep_next_number",      name="Nächster Abflug Flugnummer",     icon="mdi:airplane-takeoff"),
    SensorEntityDescription(key="dep_next_destination", name="Nächster Abflug Ziel",           icon="mdi:map-marker"),
    SensorEntityDescription(key="dep_next_iata",        name="Nächster Abflug IATA",           icon="mdi:airport"),
    SensorEntityDescription(key="dep_next_planned",     name="Nächster Abflug Planzeit",       icon="mdi:clock-outline"),
    SensorEntityDescription(key="dep_next_expected",    name="Nächster Abflug Erwartete Zeit", icon="mdi:clock-alert-outline"),
    SensorEntityDescription(key="dep_next_terminal",    name="Nächster Abflug Terminal",       icon="mdi:gate"),
    SensorEntityDescription(key="dep_next_gate",        name="Nächster Abflug Gate",           icon="mdi:door"),
    SensorEntityDescription(key="dep_next_status",      name="Nächster Abflug Status",         icon="mdi:information-outline"),
)


DEVICE_INFO = {"manufacturer": "Flughafen Hamburg GmbH", "model": "Open API v2",
               "configuration_url": "https://portal.api.hamburg-airport.de"}


ARR_KEY_MAP = {
    "arr_next_number": "flight_number", "arr_next_origin": "origin_name",
    "arr_next_iata": "origin_iata",     "arr_next_planned": "planned_time",
    "arr_next_expected": "expected_time","arr_next_terminal": "terminal",
    "arr_next_status": "status",
}
DEP_KEY_MAP = {
    "dep_next_number": "flight_number",         "dep_next_destination": "destination_name",
    "dep_next_iata": "destination_iata",         "dep_next_planned": "planned_time",
    "dep_next_expected": "expected_time",        "dep_next_terminal": "terminal",
    "dep_next_gate": "gate",                     "dep_next_status": "status",
}


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinators = hass.data[DOMAIN][entry.entry_id]
    arr = coordinators[FLIGHT_TYPE_ARRIVALS]
    dep = coordinators[FLIGHT_TYPE_DEPARTURES]
    entities = []
    for desc in ARRIVAL_SENSORS:
        entities.append(HAMNextSensor(arr, desc, entry.entry_id, FLIGHT_TYPE_ARRIVALS))
    for desc in DEPARTURE_SENSORS:
        entities.append(HAMNextSensor(dep, desc, entry.entry_id, FLIGHT_TYPE_DEPARTURES))
    entities.append(HAMWindowSensor(arr, SensorEntityDescription(
        key="arr_window", name="Hamburg Airport Landungen Zeitfenster", icon="mdi:airplane-clock"), entry.entry_id))
    entities.append(HAMWindowSensor(dep, SensorEntityDescription(
        key="dep_window", name="Hamburg Airport Abflüge Zeitfenster", icon="mdi:airplane-clock"), entry.entry_id))
    async_add_entities(entities, True)


class HAMNextSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, description, entry_id, flight_type):
        super().__init__(coordinator)
        self.entity_description = description
        self._flight_type = flight_type
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {**DEVICE_INFO,
            "identifiers": {(DOMAIN, f"{entry_id}_{flight_type}")},
            "name": "Hamburg Airport Landungen" if flight_type == FLIGHT_TYPE_ARRIVALS else "Hamburg Airport Abflüge"}
    @property
    def native_value(self):
        if not self.coordinator.data: return None
        nf = self.coordinator.data.get("next_flight", {})
        km = ARR_KEY_MAP if self._flight_type == FLIGHT_TYPE_ARRIVALS else DEP_KEY_MAP
        field = km.get(self.entity_description.key)
        return nf.get(field) if field else None


class HAMWindowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False
    def __init__(self, coordinator, description, entry_id):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_name = description.name
        ft = coordinator.flight_type
        self._attr_device_info = {**DEVICE_INFO,
            "identifiers": {(DOMAIN, f"{entry_id}_{ft}")},
            "name": "Hamburg Airport Landungen" if ft == FLIGHT_TYPE_ARRIVALS else "Hamburg Airport Abflüge"}
    @property
    def native_value(self):
        if not self.coordinator.data: return None
        return len(self.coordinator.data.get("window", []))
    @property
    def extra_state_attributes(self):
        if not self.coordinator.data: return {}
        data = self.coordinator.data
        wp = data.get("window_past", 0)
        window = data.get("window", [])
        past_window   = window[:wp]
        future_window = window[wp:]
        attrs = {"window_past": data.get("window_past"), "window_future": data.get("window_future")}
        for i, f in enumerate(reversed(past_window), start=1):
            for k, v in f.items():
                attrs[f"past_{i}_{k}"] = v
        for i, f in enumerate(future_window, start=1):
            for k, v in f.items():
                attrs[f"future_{i}_{k}"] = v
        return attrs