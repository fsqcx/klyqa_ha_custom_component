"""The Klyqa integration."""
from __future__ import annotations

"""
Good integrations to look at:
abode
amrest
accuweather
met.no
mobile_app
helpers/device_registry
helpers/entity_registry
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.helpers.area_registry import AreaEntry, AreaRegistry
import homeassistant.helpers.area_registry as area_registry

from .const import DOMAIN, CONF_POLLING
from .light import KlyqaLight

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Klyqa integration from a config entry."""
    # username = entry.data[CONF_USERNAME]
    # password = entry.data[CONF_PASSWORD]
    # polling = entry.data[CONF_POLLING]
    # host = entry.data[CONF_HOST]

    # For previous config entries where unique_id is None
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    area_reg: AreaRegistry = area_registry.async_get(hass)
    area_reg = await hass.helpers.area_registry.async_get_registry()
    # area_reg.areas.get(area_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    await hass.async_add_executor_job(hass.data[DOMAIN].shutdown)

    hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
