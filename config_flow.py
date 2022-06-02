"""Config flow for Klyqa."""
# import my_pypi_dependency

from typing import Any, cast
from numpy import integer

from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .api import Klyqa
from .const import DOMAIN, LOGGER
import homeassistant.helpers.config_validation as cv

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_ROOM,
    CONF_USERNAME,
)
from .const import CONF_SYNC_ROOMS
from homeassistant.data_entry_flow import FlowResult

# user_step_data_schema = {
#     vol.Required(CONF_USERNAME, default="frederick.stallmeyer1@qconnex.com"): cv.string,
#     vol.Required(CONF_PASSWORD, default="testpwd1"): cv.string,
#     vol.Required(CONF_SCAN_INTERVAL, default="60"): cv.string,
#     vol.Required(CONF_SYNC_ROOMS, default=True): cv.boolean,
#     vol.Required(CONF_HOST, default="http://localhost:3000"): cv.url,
# }


user_step_data_schema = {
    vol.Required(CONF_USERNAME, default="frederick.stallmeyer1@qconnex.com"): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_SCAN_INTERVAL, default=60): int,
    vol.Required(CONF_SYNC_ROOMS, default=True): bool,
    vol.Required(CONF_HOST, default="https://app-api.test.qconnex.io"): str,
}

# http://localhost:3000
# https://app-api.test.qconnex.io
# user_step_data_schema = {
#     vol.Required(CONF_USERNAME): str,
#     vol.Required(CONF_PASSWORD): str,
#     vol.Required(CONF_SCAN_INTERVAL, default=60): int,
#     vol.Required(CONF_SYNC_ROOMS, default=True): bool,
#     vol.Required(CONF_HOST): str,
# }


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

        self._username: str | None = None
        self._password: str | None = None
        self._scan_interval: int = 30
        self._host: str | None = None
        self._klyqa = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(user_step_data_schema),
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # return self.async_create_entry(title="", data=user_input)
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._scan_interval = user_input[CONF_SCAN_INTERVAL]
            self._sync_rooms = user_input[CONF_SYNC_ROOMS]
            self._host = user_input[CONF_HOST]

            return await self._async_klyqa_login(step_id="user")

            # return self.async_show_form(_init
            #     step_id="user", data_schema=vol.Schema(user_step_data_schema)
            # )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                user_step_data_schema
                # {
                #     vol.Required(
                #         "user",
                #         default=self.config_entry.options.get("show_things"),
                #     ): bool
                # }
            ),
        )

    async def _async_klyqa_login(self, step_id: str) -> FlowResult:
        """Handle login with Klyqa."""

        errors = {}
        # will give new config entry. doesnt need to shutdown.
        # self._klyqa = hass.data.setdefault(DOMAIN, {}).get("klyqa")
        # if DOMAIN in self.hass.data and self.hass.data[DOMAIN]:
        #     self._klyqa = self.hass.data[DOMAIN]
        #     try:
        #         await self.hass.async_add_executor_job(self._klyqa.shutdown)
        #     except Exception as e:
        #         pass

        try:

            self._klyqa: Klyqa = Klyqa(
                self._username,
                self._password,
                self._host,
                self.hass,
                sync_rooms=self._sync_rooms,
            )
            if not await self.hass.async_add_executor_job(
                self._klyqa.login,
            ):
                raise Exception("Unable to login")

            # if self._klyqa:
            #     self.hass.data[DOMAIN] = self._klyqa

        except (ConnectTimeout, HTTPError) as ex:
            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        except Exception as ex:

            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        if not self._klyqa or not self._klyqa._access_token:
            errors = {"base": "cannot_connect"}

        if errors:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema(user_step_data_schema),
                errors=errors,
            )

        return await self._async_create_entry()

    async def _async_create_entry(self) -> FlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_SCAN_INTERVAL: self._scan_interval,
            CONF_SYNC_ROOMS: self._sync_rooms,
            CONF_HOST: self._host,
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            # Reload the Klyqa config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=cast(str, self._username), data=config_data
        )


class KlyqaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""

        self._username: str | None = None
        self._password: str | None = None
        self._scan_interval: int = 30
        self._host: str | None = None
        self._klyqa = None
        pass

    def klyqa(self) -> Klyqa:
        if self._klyqa:
            return self._klyqa
        if not self.hass or not DOMAIN in self.hass.data:
            return None
        self._klyqa = self.hass.data[DOMAIN]
        return self.hass.data[DOMAIN]

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        """ already logged in from platform or other way """
        # if self.klyqa() and self._klyqa._access_token:
        #     self._username = self._klyqa._username
        #     self._password = self._klyqa._password
        #     self._host = self._klyqa._host
        #     return await self._async_create_entry()
        login_failed = False

        if user_input is None or login_failed:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(user_step_data_schema)
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._scan_interval = user_input[CONF_SCAN_INTERVAL]
        self._sync_rooms = user_input[CONF_SYNC_ROOMS]
        self._host = user_input[CONF_HOST]

        return await self._async_klyqa_login(step_id="user")

    async def _async_klyqa_login(self, step_id: str) -> FlowResult:
        """Handle login with Klyqa."""

        errors = {}
        # will give new config entry. doesnt need to shutdown.
        # self._klyqa = hass.data.setdefault(DOMAIN, {}).get("klyqa")
        # if DOMAIN in self.hass.data and self.hass.data[DOMAIN]:
        #     self._klyqa = self.hass.data[DOMAIN]
        #     try:
        #         await self.hass.async_add_executor_job(self._klyqa.shutdown)
        #     except Exception as e:
        #         pass

        try:

            self._klyqa: Klyqa = Klyqa(
                self._username,
                self._password,
                self._host,
                self.hass,
                sync_rooms=self._sync_rooms,
            )
            if not await self.hass.async_add_executor_job(
                self._klyqa.login,
            ):
                raise Exception("Unable to login")

            # if self._klyqa:
            #     self.hass.data[DOMAIN] = self._klyqa

        except (ConnectTimeout, HTTPError) as ex:
            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        except Exception as ex:

            LOGGER.error("Unable to connect to Klyqa: %s", ex)
            errors = {"base": "cannot_connect"}

        if not self._klyqa or not self._klyqa._access_token:
            errors = {"base": "cannot_connect"}

        if errors:
            return self.async_show_form(
                step_id=step_id,
                data_schema=vol.Schema(user_step_data_schema),
                errors=errors,
            )

        return await self._async_create_entry()

    async def _async_create_entry(self) -> FlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_SCAN_INTERVAL: self._scan_interval,
            CONF_SYNC_ROOMS: self._sync_rooms,
            CONF_HOST: self._host,
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            # Reload the Klyqa config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=cast(str, self._username), data=config_data
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


# async def _async_has_devices(hass: HomeAssistant) -> bool:
#     """Return if there are devices that can be discovered."""
#     # TODO Check if there are any devices that can be discovered in the network.
#     devices = []
#     # await hass.async_add_executor_job(my_pypi_dependency.discover)
#     device_unique_id = "AABBCCDD"  # e. g. mac address using homeassistant.helpers.device_registry.format_mac

#     # api.send("--request")
#     LOGGER.info("okkkk")
#     return True  # len(devices) > 0


# config_entry_flow.register_discovery_flow(DOMAIN, "Klyqa", _async_has_devices)
