"""National Grid (US) electric usage and cost for Home Assistant.

Home Assistant calls these two functions when the integration is added, reloaded or removed. Everything else
lives in coordinator.py (talking to National Grid and writing statistics) and sensor.py (the entities).
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import NationalGridCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Sign in, run the first update (which imports history on a new install) and create the sensors."""
    coordinator = NationalGridCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove the sensors. Statistics stay in the database so the Energy dashboard keeps its history."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
