"""Platform for light integration."""
from __future__ import annotations

import json
import socket

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import area_registry as ar
import voluptuous as vol


from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)


from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBWW,
    ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_OK,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity, generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util
from homeassistant.config_entries import ConfigEntry

from .api import SCENES, Klyqa, KlyqaLightDevice
from .const import DOMAIN, LOGGER, CONF_SYNC_ROOMS

# all deprecated, still here for testing, color_mode is the modern way to go ...
SUPPORT_KLYQA = (
    SUPPORT_BRIGHTNESS
    | SUPPORT_COLOR
    | SUPPORT_COLOR_TEMP
    | SUPPORT_TRANSITION
    | SUPPORT_EFFECT
)

from datetime import timedelta
import functools as ft

from homeassistant.helpers.area_registry import AreaEntry, AreaRegistry
import homeassistant.helpers.area_registry as area_registry

SCAN_INTERVAL = timedelta(seconds=3)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    await async_setup_klyqa(
        hass,
        entry.data,
        async_add_entities,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    await async_setup_klyqa(
        hass,
        config,
        add_entities,
        discovery_info,
    )


async def async_setup_klyqa(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Klyqa Light platform."""

    if not DOMAIN in hass.data:
        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        host = config.get(CONF_HOST)
        sync_rooms = (
            config.get(CONF_SYNC_ROOMS) if config.get(CONF_SYNC_ROOMS) else False
        )
        hass.data[DOMAIN] = Klyqa(username, password, host, hass, sync_rooms=sync_rooms)
        if not await hass.async_add_executor_job(hass.data[DOMAIN].login):
            return

    klyqa: Klyqa = hass.data[DOMAIN]

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, klyqa.shutdown)
    await hass.async_add_executor_job(klyqa.load_settings)
    await hass.async_add_executor_job(
        ft.partial(klyqa.search_lights, seconds_to_discover=1)
    )

    entities = []

    for device_settings in klyqa._settings["devices"]:
        entity_id = generate_entity_id(
            ENTITY_ID_FORMAT,
            device_settings["localDeviceId"],
            hass=hass,
        )
        u_id = device_settings["localDeviceId"]

        light_state = klyqa.lights[u_id] if u_id in klyqa.lights else KlyqaLightDevice()
        rooms = []
        for room in klyqa._settings["rooms"]:
            for device in room["devices"]:
                if device["localDeviceId"] == u_id:
                    rooms.append(room)
        # TODO: perhaps the routines can be put into automations or scenes in HA
        routines = []
        for routine in klyqa._settings["routines"]:
            for task in routine["tasks"]:
                for device in task["devices"]:
                    if device == u_id:
                        routines.append(routine)
        # TODO: same for timers.
        timers = []
        for timer in klyqa._settings["timers"]:
            for task in timer["tasks"]:
                for device in task["devices"]:
                    if device == u_id:
                        timers.append(timer)

        entities.append(
            KlyqaLight(
                device_settings,
                light_state,
                klyqa,
                entity_id,
                should_poll=True,
                rooms=rooms,
                timers=timers,
                routines=routines,
            )
        )

    add_entities(entities, True)


class KlyqaLight(LightEntity):
    """Representation of a Klyqa Light."""

    _attr_supported_features = SUPPORT_KLYQA
    _attr_transition_time = 500

    _klyqa_api: Klyqa
    _klyqa_device: KlyqaLightDevice
    settings = {}
    """synchrononise rooms to HA"""
    sync_rooms: bool = True

    def __init__(
        self,
        settings,
        device: KlyqaLightDevice,
        klyqa_api,
        entity_id,
        should_poll=True,
        rooms=None,
        timers=None,
        routines=None,
    ):
        """Initialize a Klyqa Light Bulb."""
        self._klyqa_api = klyqa_api
        self.u_id = settings["localDeviceId"]
        self._klyqa_device = device
        self.entity_id = entity_id
        self._attr_should_poll = should_poll
        self._attr_device_class = "light"
        self._attr_icon = "mdi:lightbulb"
        self.rooms = rooms
        self.timers = timers
        self.routines = routines
        self._attr_supported_color_modes = {
            COLOR_MODE_BRIGHTNESS,
            COLOR_MODE_COLOR_TEMP,
            COLOR_MODE_RGB,
            # COLOR_MODE_RGBWW
        }
        self._attr_effect_list = [x["label"] for x in SCENES]
        """Entity state will be updated after adding the entity."""

    async def async_update_settings(self):
        """Set device specific settings from the klyqa settings cloud."""
        devices_settings = self._klyqa_api._settings["devices"]

        device_result = [
            x for x in devices_settings if str(x["localDeviceId"]) == self.u_id
        ]
        if len(device_result) < 1:
            return

        response_object = await self.hass.async_add_executor_job(
            self._klyqa_api.request_get_beared,
            "/config/product/" + device_result[0]["productId"],
        )

        self.device_config = json.loads(response_object.text)

        self.settings = device_result[0]
        self._attr_name = self.settings["name"]
        self._attr_unique_id = self.settings["localDeviceId"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self.name,
            manufacturer="QConnex GmbH",
            model=self.settings["productId"],  # TODO: Maybe exclude.
            sw_version=self.settings["firmwareVersion"],
            hw_version=self.settings["hardwareRevision"],  # TODO: Maybe exclude.
            configuration_url="https://www.klyqa.de/produkte/e27-color-lampe",  # TODO: Maybe exclude. Or make rest call for device url.
        )
        if len(self.rooms) > 0:
            area_reg = ar.async_get(self.hass)
            area = area_reg.async_get_area_by_name(self.rooms[0]["name"])
            if area:
                self._attr_device_info["suggested_area"] = area.name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn off."""

        entity_registry = er.async_get(self.hass)

        await self.async_update_klyqa()
        args = ["--power", "on"]

        if ATTR_HS_COLOR in kwargs:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self._attr_rgb_color = (rgb[0], rgb[1], rgb[2])
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]

        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGB_COLOR in kwargs or ATTR_HS_COLOR in kwargs:
            args.extend(["--color", *([str(rgb) for rgb in self._attr_rgb_color])])

        if ATTR_RGBWW_COLOR in kwargs:
            self._attr_rgbww_color = kwargs[ATTR_RGBWW_COLOR]
            args.extend(
                ["--percent_color", *([str(rgb) for rgb in self._attr_rgbww_color])]
            )

        if ATTR_EFFECT in kwargs:
            scene_result = [x for x in SCENES if x["label"] == kwargs[ATTR_EFFECT]]
            if len(scene_result) > 0:
                scene = scene_result[0]
                self._attr_effect = kwargs[ATTR_EFFECT]
                commands = scene["commands"]
                if len(commands.split(";")) > 2:
                    commands += "l 0;"

                ret = self._klyqa_api.send_to_bulb(
                    "--routine_id",
                    "0",
                    "--routine_scene",
                    str(scene["id"]),
                    "--routine_put",
                    "--routine_command",
                    commands,
                    u_id=self.u_id,
                )
                if ret:
                    args.extend(
                        [
                            "--routine_id",
                            "0",
                            "--routine_start",
                        ]
                    )

        if ATTR_COLOR_TEMP in kwargs:
            self._attr_color_temp = kwargs[ATTR_COLOR_TEMP]
            args.extend(
                [
                    "--temperature",
                    str(
                        color_temperature_mired_to_kelvin(self._attr_color_temp)
                        if self._attr_color_temp
                        else 0
                    ),
                ]
            )

        if ATTR_TRANSITION in kwargs:
            self._attr_transition_time = kwargs[ATTR_TRANSITION]

        if self._attr_transition_time:
            args.extend(["--transitionTime", str(self._attr_transition_time)])

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            args.extend(
                ["--brightness", str(round((self._attr_brightness / 255.0) * 100.0))]
            )

        if ATTR_BRIGHTNESS_PCT in kwargs:
            self._attr_brightness = int(
                round((kwargs[ATTR_BRIGHTNESS_PCT] / 100) * 255)
            )
            args.extend(["--brightness", str(ATTR_BRIGHTNESS_PCT)])

        LOGGER.info(
            "Send to bulb " + str(self.entity_id) + "%s: %s",
            " (" + self.name + ")" if self.name else "",
            " ".join(args),
        )
        ret = self._klyqa_api.send_to_bulb(*(args), u_id=self.u_id)
        await self.async_update()

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        args = ["--power", "off"]
        if self._attr_transition_time:
            args.extend(["--transitionTime", str(self._attr_transition_time)])
        await self.async_update_klyqa()
        LOGGER.info(
            "Send to bulb " + str(self.entity_id) + "%s: %s",
            " (" + self.name + ")" if self.name else "",
            " ".join(args),
        )
        ret = self._klyqa_api.send_to_bulb(*(args), u_id=self.u_id)
        await self.async_update()

    async def async_update_klyqa(self):
        """Fetch settings from klyqa cloud account."""
        await self.hass.async_add_executor_job(self._klyqa_api.load_settings)
        await self.async_update_settings()
        # if self._attr_state == STATE_UNAVAILABLE:
        #     await self.hass.async_add_executor_job(self._klyqa_api.search_missing_bulbs)

    async def async_update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        await self.async_update_klyqa()
        ret = self._klyqa_api.send_to_bulb("--request", u_id=self.u_id)
        self._update_state(ret)

    def _update_state(self, state_complete):
        """Process state request response from the bulb to the entity state."""
        # self.state = STATE_OK if state_complete else STATE_UNAVAILABLE
        self._attr_state = STATE_OK if state_complete else STATE_UNAVAILABLE
        if self._attr_state == STATE_UNAVAILABLE:
            self._attr_is_on = False
            # self._attr_available = False
        else:
            self._attr_available = True

        if not self._attr_state:
            LOGGER.info(
                "Bulb " + str(self.entity_id) + "%s unavailable.",
                " (" + self.name + ")" if self.name else "",
            )

        if not state_complete or not isinstance(state_complete, dict):
            return

        LOGGER.info(
            "Update bulb " + str(self.entity_id) + "%s.",
            " (" + self.name + ")" if self.name else "",
        )

        if "error" in state_complete:
            LOGGER.error(state_complete["error"])
            return

        if state_complete.get("type") == "error":
            LOGGER.error(state_complete["type"])
            return

        state_type = state_complete.get("type")
        if not state_type or state_type != "status":
            return

        self._klyqa_device.state = state_complete
        self._attr_color_temp = (
            color_temperature_kelvin_to_mired(state_complete["temperature"])
            if state_complete["temperature"]
            else 0
        )

        self._attr_rgb_color = (
            state_complete["color"]["red"],
            state_complete["color"]["green"],
            state_complete["color"]["blue"],
        )
        self._attr_hs_color = color_util.color_RGB_to_hs(*self._attr_rgb_color)
        # interpolate brightness from klyqa bulb 0 - 100 percent to homeassistant 0 - 255 points
        self._attr_brightness = (
            float(state_complete["brightness"]["percentage"]) / 100
        ) * 255
        self._attr_is_on = state_complete["status"] == "on"

        self._attr_color_mode = (
            COLOR_MODE_COLOR_TEMP
            if state_complete["mode"] == "cct"
            else "effect"
            if state_complete["mode"] == "cmd"
            else state_complete["mode"]
        )
        self._attr_effect = ""
        if "active_scene" in state_complete and state_complete["mode"] == "cmd":
            scene_result = [
                x for x in SCENES if str(x["id"]) == state_complete["active_scene"]
            ]
            if len(scene_result) > 0:
                self._attr_effect = scene_result[0]["label"]
