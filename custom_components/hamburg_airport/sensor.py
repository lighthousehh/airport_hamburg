"""Sensor-Plattform für Hamburg Airport."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NEXT_SENSORS = (
    SensorEntityDescription(key="next_flight_number", name="Nächste Landung Flugnummer",     icon="mdi:airplane"),
    SensorEntityDescription(key="next_origin",        name="Nächste Landung Herkunft",       icon="mdi:map-marker"),
    SensorEntityDescription(key="next_origin_iata",   name="Nächste Landung IATA",           icon="mdi:airport"),
    SensorEntityDescription(key="next_planned_time",  name="Nächste Landung Planzeit",       icon="mdi:clock-outline"),
    SensorEntityDescription(key="next_expected_time", name="Nächste Landung Erwartete Zeit", icon="mdi:clock-alert-outline"),
    SensorEntityDescription(key="next_terminal",      name="Nächste Landung Terminal",       icon="mdi:gate"),
    SensorEntityDescription(key="next_status",        name="Nächste Landung Status",         icon="mdi:information-outline"),
    SensorEntityDescription(key="next_via",           name="Nächste Landung Via",            icon="mdi:transit-connection"),
)

WINDOW_SENSOR = SensorEntityDescription(
    key="window",
    name="Landungen Zeitfenster",
    icon="mdi:airplane-clock",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [HamburgAirportNextSensor(coordinator, d, entry.entry_id)
                for d in NEXT_SENSORS]
    entities.append(HamburgAirportWindowSensor(coordinator, WINDOW_SENSOR, entry.entry_id))
    async_add_entities(entities, True)


class HamburgAirportNextSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, description, entry_id):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Hamburg Airport",
            "manufacturer": "Flughafen Hamburg GmbH",
            "model": "Open API v2",
            "configuration_url": "https://portal.api.hamburg-airport.de",
        }

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        n = self.coordinator.data.get("next_arrival", {})
        return {
            "next_flight_number": n.get("flight_number"),
            "next_origin":        n.get("origin_name_int") or n.get("origin_name"),
            "next_origin_iata":   n.get("origin_iata"),
            "next_planned_time":  n.get("planned_arrival"),
            "next_expected_time": n.get("expected_arrival"),
            "next_terminal":      n.get("terminal"),
            "next_status":        n.get("status"),
            "next_via":           n.get("via_airport"),
        }.get(self.entity_description.key)


class HamburgAirportWindowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, description, entry_id):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_window"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Hamburg Airport",
            "manufacturer": "Flughafen Hamburg GmbH",
            "model": "Open API v2",
            "configuration_url": "https://portal.api.hamburg-airport.de",
        }

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("future_count", 0)

    @property
    def native_unit_of_measurement(self):
        return "Flüge"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return None
        d = self.coordinator.data
        window       = d.get("window", [])
        window_past  = d.get("window_past", 0)
        window_future= d.get("window_future", 2)

        attrs = {
            "past_count":    d.get("past_count", 0),
            "future_count":  d.get("future_count", 0),
            "window_past":   window_past,
            "window_future": window_future,
        }

        # Dynamische Labels: past_N (ältester zuerst) → future_N
        for i, flight in enumerate(window):
            past_slots = min(window_past, len([f for f in window]))
            if i < window_past:
                # vergangene: past_2, past_1 (past_1 = zuletzt gelandet)
                slot_num = window_past - i
                label = f"past_{slot_num}"
            else:
                # zukünftige: future_1, future_2, ...
                label = f"future_{i - window_past + 1}"

            attrs.update({
                f"{label}_number":   flight.get("flight_number", ""),
                f"{label}_origin":   flight.get("origin_name_int") or flight.get("origin_name", ""),
                f"{label}_iata":     flight.get("origin_iata", ""),
                f"{label}_planned":  flight.get("planned_arrival"),
                f"{label}_expected": flight.get("expected_arrival"),
                f"{label}_terminal": flight.get("terminal", ""),
                f"{label}_status":   flight.get("status") or "scheduled",
                f"{label}_via":      flight.get("via_airport"),
            })
        return attrs
