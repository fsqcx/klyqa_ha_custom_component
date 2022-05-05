import argparse
import asyncio
import datetime
import json
import pickle
import select
import socket
import sys
import time
import traceback
import os
import errno
import threading

import uuid
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
import functools as ft

# pycryptodome
try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Random import get_random_bytes
except:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes

from .const import LOGGER

STATE_CONNECTED = "CONNECTED"
STATE_WAIT_IV = "WAIT_IV"

SCENES = [
    {
        "id": 100,
        "colors": ["#FFECD8", "#FFAA5B"],
        "label": "Warm White",
        "commands": "5ch 0 0 0 0 65535 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 101,
        "colors": ["#FCF4DD", "#FED07A"],
        "label": "Daylight",
        "commands": "5ch 0 0 0 24903 40631 65535 500;p 1000;",
    },
    {
        "id": 102,
        "colors": ["#FFFFFF", "#B6DAFF"],
        "label": "Cold White",
        "commands": "5ch 0 0 0 65535 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 103,
        "colors": ["#E06004", "#55230D"],
        "label": "Night Light",
        "commands": "5ch 9830 3276 0 1310 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 106,
        "colors": ["#FDCB78", "#FCDA60"],
        "label": "Relax",
        "commands": "5ch 26214 26214 0 0 13107 65535 500;p 1000;",
    },
    {
        "id": 109,
        "colors": ["#090064", "#2E2A5A"],
        "label": "TV Time",
        "commands": "5ch 655 0 6553 1310 0 65535 500;p 1000;",
    },
    {
        "id": 107,
        "colors": ["#FFD1A2", "#FFEDDA"],
        "label": "Comfort",
        "commands": "5ch 47185 0 0 18349 0 65535 500;p 1000;",
    },
    {
        "id": 108,
        "colors": ["#EAFCFF", "#81DFF0"],
        "label": "Focused",
        "commands": "5ch 0 0 26214 5000 0 65535 500;p 1000;",
        "cwww": True,
    },
    {
        "id": 110,
        "colors": ["#CD3700", "#CD0000", "#CD6600"],
        "label": "Fireplace",
        "commands": "5ch 32767 0 0 0 1500 65535 500;p 500;5ch 55535 200 0 0 2000 65535 500;p 500;",
        # '5ch 32767 0 0 0 1500 65535 500;p 500;5ch 55535 200 0 0 2000 65535 500;p 500;5ch 32767 30000 0 0 1500 65535 500;p 500;5ch 25535 20000 0 0 2000 65535 500;p 500;5ch 62767 0 0 0 1500 65535 500;p 500;5ch 65535 200 0 0 2000 65535 500;p 500;5ch 32767 30000 0 0 1500 65535 500;p 500;5ch 25535 30000 0 0 2000 65535 500;p 500;',
    },
    {
        "id": 122,
        "colors": ["#12126C", "#B22222", "#D02090"],
        "label": "Jazz Club",
        "commands": "5ch 45746 8738 8738 0 0 65535 6100;p 5100;5ch 45232 12336 24672 0 0 65535 6100;p 5000;5ch 53436 8224 37008 0 0 65535 6100;p 5000;5ch 0 0 33896 0 0 65535 6000;p 5000;5ch 18504 15677 35728 0 0 65535 6100;p 5000;5ch 38036 0 52428 0 0 65535 6600;p 5000;5ch 45232 12336 24672 0 0 65535 6100;p 5000;",
    },
    {
        "id": 104,
        "colors": ["#B20C26", "#CC1933", "#EE6AA7"],
        "label": "Romantic",
        "commands": "5ch 58981 6553 16383 0 0 65535 1000;p 7400;5ch 45874 3276 9830 0 0 65535 4400;p 6600;5ch 52428 6553 13107 0 0 65535 8800;p 15200;5ch 41287 0 0 0 0 65535 4400;p 13200;",
    },
    {
        "id": 112,
        "colors": ["#FFDCE8", "#D2FFD2", "#CCFFFF"],
        "label": "Gentle",
        "commands": "5ch 51117 0 0 13107 0 65535 26000;p 56000;5ch 26214 26214 0 8519 0 65535 26000;p 56000;5ch 0 51117 0 13107 0 65535 26000;p 56000;5ch 0 26214 26214 8519 0 65535 26000;p 56000;5ch 0 0 51117 13107 0 65535 26000;p 56000;5ch 26214 0 26214 8519 0 65535 26000;p 56000;",
    },
    {
        "id": 113,
        "colors": ["#EEAD0E", "#FF7F24", "#CD0000"],
        "label": "Summer",
        "commands": "5ch 17039 25558 0 13762 0 65535 8000;p 14000;5ch 39321 7864 0 15728 0 65535 8000;p 14000;5ch 28180 17694 0 11140 0 65535 8000;p 14000;",
    },
    {
        "id": 114,
        "colors": ["#00BA0C", "#008400", "#0C4400"],
        "label": "Jungle",
        "commands": "5ch 0 47840 3276 0 0 65535 2600;p 2100;5ch 5898 10485 1310 0 0 65535 2300;p 4200;5ch 0 34078 0 0 0 65535 2100;p 2500;5ch 3276 17694 0 0 0 65535 4600;p 4000;5ch 9174 46529 0 0 0 65535 5500;p 6900;5ch 9830 43908 1966 0 0 65535 2700;p 4700;5ch 0 55704 0 0 0 65535 2000;p 3800;",
    },
    {
        "id": 105,
        "colors": ["#00008B", "#0000FF", "#1874ED"],
        "label": "Ocean",
        "commands": "5ch 1310 17694 36044 0 0 65535 2400;p 5400;5ch 655 15073 39321 0 0 65535 2100;p 5100;5ch 1310 36044 17039 0 0 65535 4200;p 5100;5ch 1966 22281 29490 0 0 65535 2800;p 5700;5ch 655 19005 34733 0 0 65535 2100;p 4900;5ch 655 26869 27524 0 0 65535 2600;p 3400;5ch 655 26869 27524 0 0 65535 2700;p 3600;5ch 1310 38010 15728 0 0 65535 4200;p 5000;",
    },
    # {
    #   "id": 111,
    #   "colors": ['#A31900', '#A52300', '#B71933', '#A5237F', '#B71900'],
    #   "label": 'Club',
    #   "commands":
    #     '5ch 41942 6553 0 1310 0 65535 600;p 800;5ch 42597 9174 0 1310 0 65535 8700;p 12000;5ch 47185 6553 13107 1310 0 65535 8700;p 12000;5ch 42597 9174 32767 1310 0 65535 300;p 400;5ch 47185 6553 0 1310 0 65535 300;p 1300;',
    # },
    {
        "id": 115,
        "colors": ["#EE4000", "#CD6600", "#FFA500"],
        "label": "Fall",
        "commands": "5ch 49151 1966 0 9830 0 65535 8400;p 8610;5ch 35388 13107 0 6553 0 65535 8400;p 8750;5ch 52428 0 0 10485 0 65535 8400;p 8740;5ch 39321 9174 0 12451 0 65535 500;p 840;",
    },
    {
        "id": 116,
        "colors": ["#FFF0F5", "#FF6EB4", "#FF4500"],
        "label": "Sunset",
        "commands": "5ch 39321 0 15073 2621 0 65535 5680;p 5880;5ch 51117 0 0 13107 0 65535 5680;p 5880;5ch 43253 11796 0 2621 0 65535 5680;p 5880;5ch 38010 0 15073 7208 0 65535 5680;p 5880;5ch 46529 0 0 3932 0 65535 5680;p 5880;5ch 41287 11140 0 7864 0 65535 5680;p 5880;",
    },
    {
        "id": 117,
        "colors": ["#FF0000", "#0000FF", "#00FF00"],
        "label": "Party",
        "commands": "5ch 55704 0 0 0 0 65535 132;p 272;5ch 55704 0 0 0 0 65535 132;p 272;5ch 0 55704 0 0 0 65535 132;p 272;5ch 0 55704 0 0 0 65535 132;p 272;5ch 0 0 55704 0 0 65535 132;p 272;5ch 0 0 55704 0 0 65535 132;p 272;5ch 28180 0 27524 0 0 65535 132;p 272;5ch 0 28180 27524 0 0 65535 132;p 272;",
    },
    {
        "id": 118,
        "colors": ["#F0FFF0", "#C1FFC1", "#FFE4E1"],
        "label": "Spring",
        "commands": "5ch 19660 15728 19660 0 0 65535 8000;p 11000;5ch 20315 26214 13107 0 0 65535 8000;p 11000;5ch 17039 19005 19005 0 0 65535 8000;p 11000;5ch 20315 14417 14417 0 0 65535 8000;p 11000;5ch 19005 18349 17694 0 0 65535 8000;p 11000;5ch 11796 30146 6553 0 0 65535 8000;p 11000;",
    },
    {
        "id": 119,
        "colors": ["#C1FFC1", "#C0FF3E", "#CAFF70"],
        "label": "Forest",
        "commands": "5ch 23592 22937 0 3932 0 65535 6000;p 8000;5ch 19005 23592 0 7864 0 65535 6200;p 10100;5ch 22281 21626 0 12451 0 65535 6000;p 10000;5ch 23592 22281 0 4587 0 65535 5800;p 10400;5ch 18349 27524 0 1966 0 65535 6200;p 7000;5ch 8519 25558 0 23592 0 65535 6200;p 9400;",
    },
    {
        "id": 120,
        "colors": ["#104E8B", "#00008B", "#4876FF"],
        "label": "Deep Sea",
        "commands": "5ch 3932 3276 59636 0 0 65535 4100;p 5100;5ch 3276 6553 53738 0 0 65535 4100;p 5000;5ch 0 0 43908 0 0 65535 4100;p 5000;5ch 655 1310 53083 0 0 65535 3600;p 5000;5ch 1310 0 53738 0 0 65535 4000;p 5000;",
    },
    {
        "id": 121,
        "colors": ["#90ee90", "#8DEEEE", "#008B45"],
        "label": "Tropical",
        "commands": "5ch 0 43253 0 0 36044 65535 3000;p 4000;5ch 0 0 0 0 65535 65535 2400;p 5400;5ch 0 38010 0 0 48495 65535 2600;p 3600;5ch 0 32767 0 0 0 65535 2000;p 3400;5ch 0 46529 0 0 26869 65535 3100;p 4100;5ch 0 43908 0 0 0 65535 4000;p 7000;5ch 0 49806 0 0 16383 65535 2000;p 5000;",
    },
    {
        "id": 123,
        "colors": ["#FF6AD0", "#8BFFC7", "#96A0FF"],
        "label": "Magic Mood",
        "commands": "5ch 65535 27242 53456 0 0 35535 2400;p 1180;5ch 30326 33924 65535 0 0 35535 2200;p 1110;5ch 65535 21331 21331 0 0 35535 2800;p 1200;5ch 35723 55535 31143 0 0 35535 2800;p 1200;5ch 38550 41120 65535 0 0 35535 2400;p 1040;5ch 65535 61423 29041 0 0 35535 2400;p 1000;",
    },
    {
        "id": 124,
        "colors": ["#FF0000", "#B953FF", "#DBFF96"],
        "label": "Mystic Mountain",
        "commands": "5ch 65535 0 0 0 0 35535 1400;p 980;5ch 65535 30326 52685 0 0 35535 1200;p 910;5ch 47543 21331 65535 0 0 35535 1800;p 1200;5ch 35723 65535 44461 0 0 35535 1800;p 1200;5ch 56283 65535 38550 0 0 35535 1400;p 1040;5ch 65535 29041 53456 0 0 35535 1400;p 1000;",
    },
    {
        "id": 125,
        "colors": ["#FB0000", "#FFF748", "#B97FFF"],
        "label": "Cotton Candy",
        "commands": "5ch 65535 0 52428 0 0 35535 1400;p 980;5ch 47545 32639 655350 0 0 35535 1200;p 910;5ch 65535 33410 33410 0 0 35535 1800;p 1200;5ch 65535 63479 18504 0 0 35535 1800;p 1200;5ch 65535 63222 16448 0 0 35535 1400;p 1040;5ch 64507 0 0 0 0 35535 1400;p 1000;",
    },
    {
        "id": 126,
        "colors": ["#8BFFE1", "#D8FA97", "#FF927F"],
        "label": "Ice Cream",
        "commands": "5ch 65535 0 0 0 0 35535 1400;p 980;5ch 65535 37522 32639 0 0 35535 1200;p 910;5ch 61166 54741 65535 0 0 35535 1800;p 1200;5ch 35723 65535 57825 0 0 35535 1800;p 1200;5ch 55512 64250 38807 0 0 35535 1400;p 1040;5ch 65535 56796 62709 0 0 35535 1400;p 1000;",
    },
]


class Connection:
    sending_aes = None
    receiving_aes = None
    state = ""
    socket: socket.SocketType
    address = ""
    local_iv = ""
    remote_iv = ""
    u_id = ""


def send_msg(socket, message, sending_aes) -> bool:
    LOGGER.debug("Sending: " + message)
    message_encoded = message.encode("utf-8")
    while len(message_encoded) % 16:
        message_encoded = message_encoded + bytes([0x20])

    message_encrypted = sending_aes.encrypt(message_encoded)
    retry_counter = 0

    while retry_counter < 10:
        try:
            socket.send(
                bytes(
                    [len(message_encrypted) // 256, len(message_encrypted) % 256, 0, 2]
                )
                + message_encrypted
            )
            return True
        except socket.timeout:
            LOGGER.debug("Send timed out, retrying...")
        except Exception as excp:
            LOGGER.error("Could not send message on tcp connection...")
            LOGGER.error(traceback.format_exc())
        time.sleep(0.3)
        retry_counter += 1

    return False


def color_message(red, green, blue, transition, skip_wait=False):
    wait_time = transition if not skip_wait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                },
                "transitionTime": transition,
            }
        ),
        wait_time,
    )


def temperature_message(temperature, transition, skip_wait=False):
    wait_time = transition if not skip_wait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "temperature": temperature,
                "transitionTime": transition,
            }
        ),
        wait_time,
    )


def percent_color_message(red, green, blue, warm, cold, transition, skip_wait):
    wait_time = transition if not skip_wait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "p_color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                    "warm": warm,
                    "cold": cold,
                    # "brightness" : brightness
                },
                "transitionTime": transition,
            }
        ),
        wait_time,
    )


def brightness_message(brightness, transition):
    return (
        json.dumps(
            {
                "type": "request",
                "brightness": {
                    "percentage": brightness,
                },
                "transitionTime": transition,
            }
        ),
        transition,
    )


class KlyqaLightDevice:
    state = {}
    connection: Connection = None

    def __init__(self, state={}, connection=None):
        self.state = state
        self.connection = connection


from threading import Thread


class Klyqa:
    """Klyqa Manager Module"""

    lights = {}
    _access_token = ""
    _account_token = ""
    _bearer = {}
    _settings = {}

    __search_lights_mutex = threading.Lock()
    # __sending_mutex = threading.Lock() """exclude searching from multiple sending threads"""
    __send_search_mutex = threading.Lock()
    __send_workers = []
    __search_worker: Thread = None

    def set_send_search_worker(
        self, search_worker: Thread = None, send_worker: Thread = None
    ) -> bool:
        # with threadLock:
        # global_counter += 1
        got_mutex = False
        while True:
            got_mutex = self.__send_search_mutex.acquire(blocking=False)
            if got_mutex:
                if search_worker:
                    if len(self.__send_workers) == 0:
                        if not self.__search_worker:
                            self.__search_worker = search_worker
                            break
                elif send_worker:
                    if not self.__search_worker:
                        if len(self.__send_workers) < 10:
                            self.__send_workers.append(send_worker)
                            break

            time.sleep(0.05)

        if got_mutex:
            self.__send_search_mutex.release()

    def remove_send_search_worker(self, search_worker=None, send_worker=None) -> bool:
        # with threadLock:
        # global_counter += 1
        got_mutex = False
        while True:
            got_mutex = self.__send_search_mutex.acquire(blocking=False)
            if got_mutex:
                if search_worker:
                    if len(self.__send_workers) == 0:
                        if not self.__search_worker == -1:
                            self.__search_worker = search_worker
                            break
                elif send_worker:
                    if self.__search_worker == -1:
                        self.__send_workers.append(send_worker)
                        break

            time.sleep(0.05)

        if got_mutex:
            self.__send_search_mutex.release()

    def __init__(
        self,
        username,
        password,
        host,
        hass: HomeAssistant = None,
        sync_rooms=True,
    ):
        self._username = username
        self._password = password
        self.sync_rooms: bool = sync_rooms
        self._host = host
        self.hass = hass

    def login(self) -> bool:
        """Login to klyqa account."""
        self._access_token = ""
        self._account_token = ""

        login_data = {"email": self._username, "password": self._password}
        try:
            login_response = requests.post(self._host + "/auth/login", json=login_data)
        except Exception as err:
            LOGGER.error("Login to Klyqa failed: " + str(err))
            return False

        if login_response.status_code != 200 and login_response.status_code != 201:
            print(str(login_response.status_code) + ", " + str(login_response.text))
            return False

        login_json = json.loads(login_response.text)

        self._access_token = login_json.get("accessToken")
        self._account_token = login_json.get("accountToken")

        self._bearer = {
            "Authorization": "Bearer " + self._access_token,
            "X-Request-Id": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "accept-encoding": "gzip, deflate, utf-8",
        }
        return True

    def request_get(self, url, params=None, **kwargs):
        """Send request get and if logged out login again and request again."""
        response = requests.get(self._host + url, params, **kwargs)
        if response.status_code == 401 and (not self.login() or not self._access_token):
            return response
        response = requests.get(self._host + url, params, **kwargs)
        return response

    def request_get_beared(self, url, params=None, **kwargs):
        """Send request get and if logged out login again."""
        response_object = self.request_get(url, params, headers=self._bearer, **kwargs)
        return response_object

    def load_settings(self) -> bool:
        """Load settings from klyqa account."""
        settings_response = self.request_get_beared("/settings")
        if settings_response.status_code != 200:
            return False
        if settings_response.text:
            try:
                self._settings = json.loads(settings_response.text)

                if self.sync_rooms and len(self._settings.get("rooms")) > 0:
                    LOGGER.debug("Applying rooms from klyqa accounts to Home Assistant")
                    area_reg = ar.async_get(self.hass)
                    for room in self._settings.get("rooms"):
                        if not area_reg.async_get_area_by_name(
                            room.get("name")
                        ) and area_reg.async_create(room.get("name")):
                            LOGGER.info("New room created: %s", room.get("name"))
            except:
                LOGGER.debug("Couldn't load settings")
                return False

        return True

    def shutdown(self):
        """Load settings from klyqa account."""
        response = requests.post(self._host + "/auth/logout", headers=self._bearer)
        for light in self.lights:
            if self.lights.get(light).connection.socket:
                try:
                    self.lights.get(light).connection.socket.close()
                except:
                    pass

    async def search_missing_bulbs(self):
        """TODO: this function is crap. we look if any bulb connection is missing and search then for it. therefore make a list of bulbs missing connection and then look for them."""
        if len(self.lights) < len(
            self._settings.get("devices")
        ):  # self._settings.devices
            await self.search_lights()

    async def search_lights(self, seconds_to_discover=10, u_id=None):
        """Get a thread lock safe light searching broadcast of the klyqa bulbs."""

        while True:
            got_mutex = self.__search_lights_mutex.acquire(blocking=False)
            if not got_mutex and not u_id:
                """another thread is already searching for all lights"""
                return None
            if (
                u_id
                and u_id in self.lights
                and not self.lights[u_id].connection.socket._closed
            ):
                """Found a connection of unit_id. Ping it to check it's working."""
                state = await self._send_to_bulb(
                    "--ping",
                    connection=self.lights[u_id].connection,
                    reconnect=False,
                )

                if state and state.get("type") == "pong":
                    return self.lights[u_id].connection
                try:
                    self.lights[u_id].connection.socket.close()
                    self.lights[u_id].connection.socket._closed = True
                except Exception:
                    pass
            if got_mutex:
                # self.__search_lights_mutex_type = MUTEX_SEARCHING
                break
            if self.__search_lights_mutex.acquire(blocking=True, timeout=100):
                break
            # time.sleep(0.2)

            await asyncio.sleep(0.2)

        return_connection = await self.__search_lights(seconds_to_discover, u_id)

        LOGGER.info(
            "Search for bulbs finished. " + str(threading.current_thread().ident),
        )
        self.__search_lights_mutex.release()
        return return_connection

    async def __search_lights(self, seconds_to_discover=10, u_id=None):
        """
        If the local device id u_id is given, the function will search for lights
        and return the connection if the light with the u_id is found
        and a connection could be estasblished.
        Args:
            u_id: Local device id.
            seconds_to_discover: Time to look for the lights from the account devices.
        returns:
            connection: If u_id is given and new connection could be established.

        It keeps searching by broadcasting for devices as long as the seconds to discover
        are not reached and when we are looking for a specific connection to device.
        """
        LOGGER.info(
            "Search for bulbs ... " + str(threading.current_thread().ident),
        )

        return_connection = None
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_address = ("0.0.0.0", 2222)
        udp.bind(server_address)

        tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_address = ("0.0.0.0", 3333)
        tcp.bind(server_address)
        tcp.listen()

        time_started = datetime.datetime.now()
        seconds_left = datetime.timedelta(milliseconds=0)

        lights_found_num = 0
        # settings_lights_num = len(self._settings.get("devices"))
        while (
            not return_connection
            # and
            # lights_found_num < settings_lights_num and
            # seconds_left.seconds < seconds_to_discover
        ):
            LOGGER.debug("Broadcasting QCX-SYN Burst\n")
            read_burst_response = True
            try:
                udp.sendto(b"QCX-SYN", ("255.255.255.255", 2222))
            except Exception as exception:
                read_burst_response = False
            while read_burst_response:
                readable, _, _ = select.select([tcp], [], [], 0.1)
                if tcp in readable:
                    connection = Connection()
                    connection.socket, connection.address = tcp.accept()

                    # almost disable blocking socket
                    connection.socket.settimeout(0.001)
                    lights_found_num = lights_found_num + 1

                    # finish the handshake in the send bulb function
                    # Get there the local device id (u_id)
                    state = await self.__send_to_bulb(
                        "--request", connection=connection, reconnect=False
                    )
                    if state and (
                        not connection.u_id in self.lights
                        or not self.lights[connection.u_id].connection
                        or not self.lights[connection.u_id].connection.socket
                        or self.lights[connection.u_id].connection.socket._closed
                    ):
                        if (
                            connection.u_id in self.lights
                            and self.lights[connection.u_id].connection.socket
                            is not None
                        ):
                            # if not self.lights[
                            #     connection.u_id
                            # ].connection.socket._closed:
                            #     connection.socket.close()
                            #     continue

                            # always replace new connections with old once. (TODO: Is it the standard behaviour in the firmware?)
                            # if there is still an open connection try to close it
                            try:
                                self.lights[connection.u_id].connection.socket.close()
                            except Exception as ex:
                                pass

                        self.lights[connection.u_id] = KlyqaLightDevice(
                            state=state, connection=connection
                        )
                        #
                        if connection.u_id == u_id:
                            return_connection = connection

                    LOGGER.debug("TCP layer connected")
                else:
                    break
            if seconds_to_discover == 0:
                break
            # time.sleep(0.2)
            await asyncio.sleep(0.2)
            seconds_left = datetime.datetime.now() - time_started
            if seconds_left.seconds >= seconds_to_discover:
                break

        tcp.close()
        if return_connection is not None:
            return return_connection

        return

    async def send_to_bulb(self, *argv, u_id=None, **kwargs) -> dict:
        """
        Sending commands to the bulb. Put the local device id (u_id) of the bulb
        in the kwargs arguments. It finds the connection to the bulb by the local device
        id and sends the command.

        Argv:
            described in code (see parser)

        Kwargs:
            connection (Connection): Tcp connection to the bulb.
            reconnect (bool): Reconnect if tcp connection fails.

        Returns:
            Json object: The answer of the bulb if successful.
            None: Else.
        """
        if u_id not in self.lights:
            self.search_lights(u_id=u_id, seconds_to_discover=0)
            return None

        response = None
        TRY_MAX = 2
        attempt_num = 1
        while (
            not (
                response := await self._send_to_bulb(
                    *argv,
                    connection=self.lights[u_id].connection,
                    retry=attempt_num > 1,
                )
            )
            and attempt_num <= TRY_MAX
        ):
            LOGGER.warning("No answer from lamp %s. Try resend", str(u_id))
            attempt_num = attempt_num + 1
            if attempt_num > TRY_MAX:
                LOGGER.error("No answer from lamp %s.", str(u_id))
                break

        return response

    async def _send_to_bulb(self, *argv, **kwargs) -> dict:

        started = datetime.datetime.now()

        while True:
            got_mutex = self.__search_lights_mutex.acquire(blocking=False)

            if got_mutex:
                # self.__search_lights_mutex_type = MUTEX_SENDING
                break
            # time.sleep(0.2)
            await asyncio.sleep(0.2)
            elapsed = datetime.datetime.now() - started
            if elapsed > datetime.timedelta(seconds=10):
                return

        return_value = await self.__send_to_bulb(*argv, **kwargs)

        if got_mutex:
            self.__search_lights_mutex.release()

        return return_value

    async def __send_to_bulb(
        self, *argv, connection, reconnect=True, retry=False, **kwargs
    ) -> dict:
        """
        Sending commands to the bulb. Put the connection object to the bulb
        in the kwargs arguments.

        Argv:
            described in code (see parser)

        Args:
            retry (bool): On retry send (True) read tcp socket for data (answers) first, if there is return it.
                          If not retry resend and try to read again.
                          On False just send and read for response normal.

        Kwargs:
            connection (Connection): Tcp connection to the bulb.
            reconnect (bool): Reconnect if tcp connection fails.

        Returns:
            Json object: The answer of the bulb if successful.
            None: Else.
        """
        # if not "connection" in kwargs:
        #     return

        # connection: Connection = kwargs["connection"]

        # reconnect = True
        # if "reconnect" in kwargs:
        #     reconnect = kwargs["reconnect"]

        if not connection.local_iv:
            connection.state = STATE_WAIT_IV
            connection.local_iv = get_random_bytes(8)
        else:
            connection.state = STATE_CONNECTED

        parser = argparse.ArgumentParser(description="virtual App interface")

        parser.add_argument("--color", nargs=3, help="set color command (r,g,b) 0-255")
        parser.add_argument(
            "--temperature",
            nargs=1,
            help="set temperature command (kelvin 1000-12000) (1000:warm, 12000:cold)",
        )
        parser.add_argument(
            "--brightness", nargs=1, help="set brightness in percent 0-100"
        )
        parser.add_argument(
            "--percent_color",
            nargs=5,
            metavar=("RED", "GREEN", "BLUE", "WARM", "COLD"),
            help="set colors and white tones in percent 0 - 100",
        )
        parser.add_argument(
            "--transitionTime",
            nargs=1,
            help="transition time in milliseconds",
            default=[0],
        )
        parser.add_argument(
            "--power", nargs=1, metavar='"on"/"off"', help="turns the bulb on/off"
        )
        parser.add_argument(
            "--party",
            help="blink fast and furious",
            action="store_const",
            const=True,
            default=False,
        )

        parser.add_argument(
            "--myip", nargs=1, help="specify own IP for broadcast sender"
        )
        parser.add_argument("--ota", nargs=1, help="specify http URL for ota")
        parser.add_argument(
            "--ping", help="send ping", action="store_const", const=True, default=False
        )
        parser.add_argument(
            "--request",
            help="send status request",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--factory_reset",
            help="trigger a factory reset on the device (Warning: device has to be onboarded again afterwards)",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--routine_list",
            help="lists stored routines",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--routine_put",
            help="store new routine",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--routine_delete",
            help="delete routine",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--routine_start",
            help="start routine",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--routine_id", help="specify routine id to act on (for put, start, delete)"
        )
        parser.add_argument(
            "--routine_scene", help="specify routine scene label (for put)"
        )
        parser.add_argument(
            "--routine_commands", help="specify routine program (for put)"
        )
        parser.add_argument(
            "--reboot",
            help="trigger a reboot",
            action="store_const",
            const=True,
            default=False,
        )

        parser.add_argument(
            "--passive",
            help="vApp will passively listen vor UDP SYN from devices",
            action="store_const",
            const=True,
            default=False,
        )
        parser.add_argument(
            "--enable_tb", nargs=1, help="enable thingsboard connection (yes/no)"
        )

        if len(argv) < 1:
            parser.print_help()
            return

        args = parser.parse_args(argv)

        message_queue_tx = []

        if args.ota is not None:
            message_queue_tx.append(
                (json.dumps({"type": "fw_update", "url": args.ota}), 3000)
            )

        if args.ping:
            message_queue_tx.append((json.dumps({"type": "ping"}), 10000))

        if args.request:
            message_queue_tx.append((json.dumps({"type": "request"}), 1000))

        if args.enable_tb is not None:
            answer = args.enable_tb[0]
            if answer != "yes" and answer != "no":
                print("ERROR --enable_tb needs to be yes or no")
                sys.exit(1)

            message_queue_tx.append(
                (json.dumps({"type": "backend", "link_enabled": answer}), 1000)
            )

        if args.passive:
            pass

        if args.color is not None:
            r, g, b = args.color
            transition_time = args.transitionTime[0]
            message_queue_tx.append(
                color_message(
                    r, g, b, int(transition_time), skip_wait=args.brightness is not None
                )
            )

        if args.temperature is not None:
            kelvin = args.temperature[0]
            transition_time = args.transitionTime[0]
            message_queue_tx.append(
                temperature_message(
                    kelvin, int(transition_time), skip_wait=args.brightness is not None
                )
            )

        if args.brightness is not None:
            brightness = args.brightness[0]
            transition_time = args.transitionTime[0]
            message_queue_tx.append(
                brightness_message(brightness, int(transition_time))
            )

        if args.percent_color is not None:
            r, g, b, w, c = args.percent_color
            transition_time = args.transitionTime[0]
            message_queue_tx.append(
                percent_color_message(
                    r,
                    g,
                    b,
                    w,
                    c,
                    int(transition_time),
                    skip_wait=args.brightness is not None,
                )
            )

        if args.factory_reset:
            message_queue_tx.append((json.dumps({"type": "factory_reset"}), 500))

        if args.routine_list:
            message_queue_tx.append(
                (json.dumps({"type": "routine", "action": "list"}), 500)
            )

        if args.routine_put:
            message_queue_tx.append(
                (
                    json.dumps(
                        {
                            "type": "routine",
                            "action": "put",
                            "id": args.routine_id,
                            "scene": args.routine_scene,
                            "commands": args.routine_commands,
                        }
                    ),
                    1000,
                )
            )

        if args.routine_delete:
            message_queue_tx.append(
                (
                    json.dumps(
                        {"type": "routine", "action": "delete", "id": args.routine_id}
                    ),
                    500,
                )
            )
        if args.routine_start:
            message_queue_tx.append(
                (
                    json.dumps(
                        {"type": "routine", "action": "start", "id": args.routine_id}
                    ),
                    500,
                )
            )

        if args.power:
            message_queue_tx.append(
                (json.dumps({"type": "request", "status": args.power[0]}), 500)
            )

        if args.reboot:
            message_queue_tx.append((json.dumps({"type": "reboot"}), 500))

        data = []

        message_queue_tx.reverse()
        last_send = datetime.datetime.now()

        async def do_reconnect():
            """Try reconnect only once per send."""
            nonlocal reconnect, self
            reconnect = False
            return await self.__search_lights(u_id=connection.u_id)

        if connection.socket._closed:
            connection = do_reconnect()

        pause = datetime.timedelta(milliseconds=0)
        elapsed = datetime.datetime.now() - last_send
        aes_key = ""
        while len(message_queue_tx) > 0 or elapsed < pause or args.party:
            try:
                data = connection.socket.recv(4096)
                if len(data) == 0:
                    LOGGER.debug("EOF")
                    if reconnect:
                        connection = await do_reconnect()
                        continue
                    else:
                        return
            except socket.timeout:
                pass
            except Exception as exception:
                if reconnect:
                    connection = await do_reconnect()
                    if connection:
                        continue
                    else:
                        return
                else:
                    return

            elapsed = datetime.datetime.now() - last_send

            """Resend message to lamp when retrying and no message has come yet to read.
            Else read message below."""
            if connection.state == STATE_CONNECTED and (not retry or len(data) == 0):
                send_next = elapsed >= pause
                if len(message_queue_tx) > 0 and send_next:
                    msg, ts = message_queue_tx.pop()
                    # pause = datetime.timedelta(milliseconds=ts)
                    pause = datetime.timedelta(milliseconds=10000)  # 10secs max timeout
                    if not send_msg(connection.socket, msg, connection.sending_aes):
                        """Upon send error, try reconnect to the lamps and append message for transmission again."""
                        try:
                            connection.socket.close()
                        except Exception as exception:
                            pass
                        if reconnect:
                            connection = await do_reconnect()
                            if connection and retry:
                                message_queue_tx.append((msg, ts))
                            else:
                                return None
                        else:
                            return None
                    last_send = datetime.datetime.now()

            if args.party and len(message_queue_tx) < 2:
                r, g, b = get_random_bytes(3)

                brightness = 50
                if args.brightness is not None:
                    brightness = int(args.brightness[0])
                transition_time = 300
                if args.transitionTime is not None:
                    transition_time = int(args.transitionTime[0])
                message_queue_tx.append(
                    color_message(r, g, b, transition_time, brightness)
                )
                pause = datetime.timedelta(milliseconds=transition_time)

            while len(data):
                LOGGER.debug(
                    "TCP server received "
                    + str(len(data))
                    + " bytes from "
                    + str(connection.address)
                )

                pkg_len = data[0] * 256 + data[1]
                pkg_type = data[3]

                pkg = data[4 : 4 + pkg_len]
                if len(pkg) < pkg_len:
                    LOGGER.debug("Incomplete packet, waiting for more...")
                    break

                data = data[4 + pkg_len :]

                if connection.state == STATE_WAIT_IV and pkg_type == 0:
                    LOGGER.debug("Plain: " + str(pkg))
                    response_object = json.loads(pkg)
                    connection.u_id = response_object["ident"]["unit_id"]
                    for device in self._settings.get("devices"):
                        if device["localDeviceId"] == connection.u_id:
                            aes_key = bytes.fromhex(device["aesKey"])
                            break

                    connection.socket.send(bytes([0, 8, 0, 1]) + connection.local_iv)

                if connection.state == STATE_WAIT_IV and pkg_type == 1:
                    connection.remote_iv = pkg

                    connection.sending_aes = AES.new(
                        aes_key,
                        AES.MODE_CBC,
                        iv=connection.local_iv + connection.remote_iv,
                    )
                    connection.receiving_aes = AES.new(
                        aes_key,
                        AES.MODE_CBC,
                        iv=connection.remote_iv + connection.local_iv,
                    )

                    connection.state = STATE_CONNECTED

                elif connection.state == STATE_CONNECTED and pkg_type == 2:
                    cipher = pkg

                    response_plain = connection.receiving_aes.decrypt(cipher)
                    response_decoded = ""
                    try:
                        response_decoded = response_plain.decode("utf-8", "ignore")
                    except Exception as exception:
                        response_decoded = str(response_plain)
                        LOGGER.warning("Couldn't decode lamp TCP response (not utf-8?)")
                        LOGGER.debug("Respone plain: " + response_decoded)
                    uid = connection.u_id + " " if connection.u_id else ""
                    LOGGER.debug("Decrypted: " + uid + response_decoded)
                    try:
                        response = json.loads(response_decoded)
                    except Exception as exception:
                        return
                    if connection.u_id and connection.u_id in self.lights:
                        self.lights[connection.u_id].state = response
                    return response
            if not (len(message_queue_tx) > 0 or elapsed < pause or args.party):
                LOGGER.warning("TCP receive pause exceeded, stop receiving... ")

        LOGGER.warning("Something in sending went wrong...")
