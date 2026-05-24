"""Config Flow für die Hamburg Airport Integration."""
from __future__ import annotations
import aiohttp, async_timeout, voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, API_BASE_URL, DEFAULT_SCAN_INTERVAL, CONF_API_KEY, CONF_SCAN_INTERVAL

class HamburgAirportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if await self._test_api_key(user_input[CONF_API_KEY]):
                await self.async_set_unique_id(f"hamburg_airport_{user_input[CONF_API_KEY][:8]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Hamburg Airport Arrivals", data=user_input)
            errors["base"] = "invalid_api_key"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"portal_url": "https://portal.api.hamburg-airport.de"},
        )

    async def _test_api_key(self, key: str) -> bool:
        headers = {"Ocp-Apim-Subscription-Key": key, "Accept": "application/json"}
        try:
            async with async_timeout.timeout(15):
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"{API_BASE_URL}/flights/arrivals", headers=headers) as r:
                        return r.status == 200
        except Exception:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return HamburgAirportOptionsFlow(entry)

class HamburgAirportOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.config_entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        cur = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_SCAN_INTERVAL, default=cur):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=60))}))