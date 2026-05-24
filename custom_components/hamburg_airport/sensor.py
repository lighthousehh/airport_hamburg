"""Sensor-Plattform für Hamburg Airport."""
from __future__ import annotations

import json
import logging
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(key="total_arrivals",     name="Landungen gesamt",                   icon="mdi:airplane-landing", native_unit_of_measurement="Flüge"),
    SensorEntityDescription(key="next_flight_number", name="Nächste Landung Flugnummer",          icon="mdi:airplane"),
    SensorEntityDescription(key="next_origin",        name="Nächste Landung Herkunft",            icon="mdi:map-marker"),
    SensorEntityDescription(key="next_origin_iata",   name="Nächste Landung IATA-Code",           icon="mdi:airport"),
    SensorEntityDescription(key="next_planned_time",  name="Nächste Landung Planzeit",            icon="mdi:clock-outline"),
    SensorEntityDescription(key="next_expected_time", name="Nächste Landung Erwartete Zeit",      icon="mdi:clock-alert-outline"),
    SensorEntityDescription(key="next_terminal",      name="Nächste Landung Terminal",            icon="mdi:gate"),
    SensorEntityDescription(key="next_status",        name="Nächste Landung Status",              icon="mdi:information-outline"),
    SensorEntityDescription(key="next_via",           name="Nächste Landung Via-Flughafen",       icon="mdi:transit-connection"),
    SensorEntityDescription(key="arrivals_json",      name="Alle Landungen JSON",                 icon="mdi:format-list-bulleted"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HamburgAirportSensor(coordinator, description, entry.entry_id)
         for description in SENSOR_DESCRIPTIONS],
        True,
    )


class HamburgAirportSensor(CoordinatorEntity, SensorEntity):
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
        d = self.coordinator.data
        n = d.get("next_arrival", {})
        return {
            "total_arrivals":     d.get("total_count", 0),
            "next_flight_number": n.get("flight_number"),
            "next_origin":        n.get("origin_name_int") or n.get("origin_name"),
            "next_origin_iata":   n.get("origin_iata"),
            "next_planned_time":  self._fmt(n.get("planned_arrival")),
            "next_expected_time": self._fmt(n.get("expected_arrival")),
            "next_terminal":      n.get("terminal"),
            "next_status":        n.get("status"),
            "next_via":           n.get("via_airport"),
            "arrivals_json":      json.dumps(d.get("arrivals", [])[:20], ensure_ascii=False),
        }.get(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "arrivals_json":
            return None
        if not self.coordinator.data:
            return None
        arrivals = self.coordinator.data.get("arrivals", [])
        attrs = {"total_count": len(arrivals)}
        for i, f in enumerate(arrivals[:10]):
            p = f"flight_{i+1}"
            attrs.update({
                f"{p}_number":   f.get("flight_number", ""),
                f"{p}_origin":   f.get("origin_name_int") or f.get("origin_name", ""),
                f"{p}_iata":     f.get("origin_iata", ""),
                f"{p}_planned":  self._fmt(f.get("planned_arrival")),
                f"{p}_expected": self._fmt(f.get("expected_arrival")),
                f"{p}_terminal": f.get("terminal", ""),
                f"{p}_status":   f.get("status") or "scheduled",
            })
        return attrs

    @staticmethod
    def _fmt(t):
        if not t:
            return None
        try:
            return t.split("[")[0][11:16]
        except Exception:
            return t
