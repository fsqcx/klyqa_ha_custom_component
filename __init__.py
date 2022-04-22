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

from .const import DOMAIN, CONF_POLLING, CONF_SYNC_ROOMS
from .light import KlyqaLight
from .api import Klyqa

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

    """Set up or change Klyqa integration from a config entry."""

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    host = entry.data.get(CONF_HOST)
    # scan_interval = entry.data.get(CONF_SCAN_INTERVAL)
    sync_rooms = (
        entry.data.get(CONF_SYNC_ROOMS) if entry.data.get(CONF_SYNC_ROOMS) else False
    )
    klyqa_api: Klyqa
    if DOMAIN in hass.data:
        klyqa_api = hass.data[DOMAIN]
        await hass.async_add_executor_job(klyqa_api.shutdown)

        klyqa_api._username = username
        klyqa_api._password = password
        klyqa_api._host = host
        klyqa_api.sync_rooms = sync_rooms
    else:
        klyqa_api: Klyqa = await hass.async_add_executor_job(
            Klyqa,
            username,
            password,
            host,
            hass,
            False,
            sync_rooms,
        )
        hass.data[DOMAIN] = klyqa_api

    if not await hass.async_add_executor_job(
        klyqa_api.login,
    ):
        return False

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, klyqa_api.shutdown)
    await hass.async_add_executor_job(klyqa_api.load_settings)
    # await hass.async_add_executor_job(klyqa.search_lights)

    # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = co

    # For previous config entries where unique_id is None
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

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
