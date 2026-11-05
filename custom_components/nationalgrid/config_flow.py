"""The setup form: asks for the National Grid website sign-in and checks it works.

The same form is shown again (as re-authentication) when National Grid stops accepting the saved password.
"""

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from py_nationalgrid import InvalidAuthError, NationalGridClient, NationalGridConfig, create_cookie_jar
import voluptuous as vol

from .const import DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str})


class NationalGridConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a National Grid login (one entry per login; it covers every account linked to it)."""

    async def async_step_user(self, user_input=None):
        """Show the form, then try to sign in with what was entered."""
        errors = {}
        if user_input:
            session = async_create_clientsession(self.hass, cookie_jar=create_cookie_jar())
            try:
                client = NationalGridClient(NationalGridConfig(**user_input), session=session)
                await client.get_linked_accounts()  # signs in; fails on a wrong email or password
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - any other failure means National Grid couldn't be reached
                errors["base"] = "cannot_connect"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=user_input)
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
            finally:
                await session.close()  # this session was only for the sign-in check
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data):
        """National Grid rejected the saved sign-in: ask for it again with the same form."""
        return await self.async_step_user()
