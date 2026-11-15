"""The setup form: asks for the National Grid website sign-in and checks it works.

When National Grid stops accepting the saved password, Home Assistant asks for the new one (re-authentication),
for the same login.
"""

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from probatio import Required, Schema
from py_nationalgrid import InvalidAuthError, NationalGridClient, NationalGridConfig, create_cookie_jar

from .const import DOMAIN

USER_SCHEMA = Schema({Required(CONF_USERNAME): str, Required(CONF_PASSWORD): str})
REAUTH_SCHEMA = Schema({Required(CONF_PASSWORD): str})


async def _sign_in_error(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Try signing in to National Grid. Returns None when it works, otherwise the form's error key."""
    session = async_create_clientsession(hass, cookie_jar=create_cookie_jar())
    try:
        client = NationalGridClient(NationalGridConfig(**data), session=session)
        await client.get_linked_accounts()  # signs in; fails on a wrong email or password
    except InvalidAuthError:
        return "invalid_auth"
    except Exception:  # noqa: BLE001 - any other failure means National Grid couldn't be reached
        return "cannot_connect"
    finally:
        await session.close()  # this session was only for the sign-in check
    return None


class NationalGridConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a National Grid login (one entry per login; it covers every account linked to it)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the form, then try to sign in with what was entered."""
        errors = {}
        if user_input:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()  # before signing in: no need to check a login that's already added
            if not (error := await _sign_in_error(self.hass, user_input)):
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
            errors["base"] = error
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """National Grid rejected the saved password: ask for the new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask only for the password, so the entry keeps its login (and its meters and statistics)."""
        entry = self._get_reauth_entry()
        errors = {}
        if user_input:
            data = {CONF_USERNAME: entry.data[CONF_USERNAME], CONF_PASSWORD: user_input[CONF_PASSWORD]}
            if not (error := await _sign_in_error(self.hass, data)):
                return self.async_update_reload_and_abort(entry, data_updates=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
