"""The Klyqa integration."""
from __future__ import annotations


from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from collections.abc import Callable


from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, EVENT_KLYQA_NEW_SETTINGS

# from .light import KlyqaLight
from .api import Klyqa
from datetime import timedelta
from async_timeout import timeout
from typing import Any


class KlyqaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Klyqa data API."""

    # add_entities: Callable[[], None] = None

    def __init__(
        self,
        hass: HomeAssistant,
        klyqa_api: Klyqa,
        update_interval: timedelta = timedelta(seconds=3),
    ) -> None:
        self.klyqa_api = klyqa_api
        LOGGER.debug("Data will be update every %s", update_interval)

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            async with timeout(10):
                if not await self.hass.async_add_executor_job(
                    self.klyqa_api.load_settings
                ):
                    raise Exception()
                # if self.add_entities:
                #     self.add_entities()
            for d in self.klyqa_api._settings["devices"]:
                u_id = d["localDeviceId"]
                light = [
                    e
                    for e in self.hass.data["light"].entities
                    if hasattr(e, "u_id") and e.u_id == u_id
                ]
                if len(light) == 0:
                    # await self.hass.data["light"].async_add_entities()
                    self.hass.bus.async_fire(
                        EVENT_KLYQA_NEW_SETTINGS, self.klyqa_api._settings
                    )

            return self.klyqa_api._settings

        except Exception as error:
            LOGGER.debug("Error updating data")
            raise UpdateFailed(error) from error
