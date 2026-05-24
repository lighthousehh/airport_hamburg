"""Config Flow für die Hamburg Airport Integration."""
from __future__ import annotations

import json
import logging
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, API_BASE_URL,
    DEFAULT_SCAN_INTERVAL, DEFAULT_PAST_COUNT, DEFAULT_FUTURE_COUNT,
    CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_PAST_COUNT, CONF_FUTURE_COUNT,
)

_LOGGER = logging.getLogger(__name__)


class HamburgAirportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if await self._test_api_key(user_input[CONF_API_KEY]):
                await self.async_set_unique_id(
                    f"hamburg_airport_{user_input[CONF_API_KEY][:8]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Hamburg Airport Arrivals", data=user_input)
            errors["base"] = "invalid_api_key"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _test_api_key(self, key: str) -> bool:
        headers = {"Ocp-Apim-Subscription-Key": key, "Accept": "application/json"}
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"{API_BASE_URL}/flights/arrivals",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    return False
                text = await r.text()
                json.loads(text)
                return True
        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HamburgAirportOptionsFlow()


class HamburgAirportOptionsFlow(config_entries.OptionsFlow):
    """Kein __init__ nötig – config_entry ist Read-only Property der Basisklasse."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                vol.Required(CONF_PAST_COUNT,
                    default=opts.get(CONF_PAST_COUNT, DEFAULT_PAST_COUNT)):
                    vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
                vol.Required(CONF_FUTURE_COUNT,
                    default=opts.get(CONF_FUTURE_COUNT, DEFAULT_FUTURE_COUNT)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            }),
        )
