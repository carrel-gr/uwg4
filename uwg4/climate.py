"""Platform for sensor integration."""


import datetime
import time
import requests
import json

HOST = "https://mythermostat.info:443"
USER = "your_usernname"
PASSWORD = "your_password"

# Time that comfort setting should last (in minutes)
COMFORT_TIME=90

# Update frequency is secured to no spam the servers
# and then get the account blacklisted.
UPDATE_RATE_SEC = 1 * 60

class UWG4(object):

    REGMODE_AUTO = 1
    REGMODE_COMFORT = 2
    REGMODE_MANUAL = 3
    REGMODE_VACATION = 4

    REGMODETXT = [
        "ERROR",
        "AUTO",
        "COMFORT",
        "MANUAL",
        "VACATION",
    ]

    def __init__(self):
        self.sessionId = "Not_a_real_sessionId--"
        self.stateJson = None
        self.list_of_thermos = []
        self.last_update = None
        self.update_budget = 1

        account = self
        account.login()
        account.getData()  # actual data gathering
        pass

    def log(self, msg):
        # print(msg)
        pass

    def logerr(self, msg):
        print(msg)

    def login(self, user=USER, psw=PASSWORD):
        path = "/api/authenticate/user"

        data = {
            "Application": 2,
            "Confirm": "",
            "Email": user,
            "Password": psw,
        }
        r = requests.post(HOST + path, json=data)
        if r.ok:
            res = r.json()
            if res["ErrorCode"] == 0:
                self.log(f"Logged in with username {user}")
                self.sessionId = res["SessionId"]
                print(f"Session ID: {self.sessionId}")
            else:
                self.logerr(f"Failed to login, error code { res['ErrorCode']}")
        else:
            self.logerr("Failed to execute login request")

    def setThermoTemperature(self, thermo_sn, mode, temp):

        path = "/api/thermostat"
        params = {"sessionid": self.sessionId, "serialnumber": thermo_sn}
        if mode == self.REGMODE_MANUAL:
            data = {
                "RegulationMode": mode,
                "ManualTemperature": temp,
            }
        elif mode == self.REGMODE_COMFORT:
            td = datetime.timedelta(minutes=COMFORT_TIME)
            d = datetime.datetime.utcnow()
            e = d + td
            comfort_end = e.strftime("%d/%m/%Y %H:%M:00 +00:00")
            data = {
                "RegulationMode": mode,
                "ComfortTemperature": temp,
                "ComfortEndTime": comfort_end,
            }
        elif mode == self.REGMODE_VACATION:
            # For now, vacation is not implemented.
            is_vacation = False
            vacation_begin = "01/01/1970 00:00:00"
            vacation_end = "01/01/1970 00:00:00"
            data = {
                "RegulationMode": mode,
                "VacationEnabled": is_vacation,
                "VacationTemperature": temp,
                "VacationBeginDay": vacation_begin,
                "VacationEndDay": vacation_end,
            }
        else:
            # For everything else (including AUTO), just set AUTO.
            data = {
                "RegulationMode": self.REGMODE_AUTO,
            }

        r = requests.post(HOST + path, json=data, params=params)
        res = r.json()
        if res["Success"] != True:
            self.login()
            r = requests.post(HOST + path, json=data, params=params)
            res = r.json()
            if res["Success"] != True:
                self.logerr("Operation failed")
        self.allow_next_update()

    def update_allowed(self):
        now = time.time()
        if (self.last_update == None) or (
            int(now - self.last_update) > UPDATE_RATE_SEC
        ):
            dt = datetime.datetime.now()
            dt = dt.strftime("%Y-%m-%d %H:%M:%S")
            self.logerr(f"{dt} - Update allowed")
            self.last_update = now
            return True
        return False

    def allow_next_update(self):
        self.update_budget = self.update_budget + 1

    def getData(self, force=False):
        if self.update_budget > 0:
            self.update_budget = self.update_budget - 1
        elif not self.update_allowed():
            return

        path = "/api/thermostats"
        data = {"sessionid": self.sessionId}

        r = requests.get(HOST + path, params=data)
        if not r.ok:
            self.login()
            r = requests.get(HOST + path, params=data)
            if not r.ok:
                self.logerr("Failed to execute request ")
                return
        res = r.json()

        if "Groups" in res:
            found = 0
            for group in res["Groups"]:
                if "Thermostats" in group:
                    found = found + 1
            if found == 0:
                self.logerr("Failed to retrieve any thermostats")
                return
        else:
            self.logerr("Failed to get group information")
            return

        self.stateJson = res
        with open("data.json", "w") as outfile:
            json.dump(res, outfile)

    def getThermoInfo(self, data=None):
        if data == None:
            data = self.stateJson
        for group in data["Groups"]:
            gname = group["GroupName"]

            for thermo in group["Thermostats"]:
                regmode = int(thermo["RegulationMode"])
                actualTemp = thermo["Temperature"]
                actualTemp = actualTemp / 100
                if regmode == self.REGMODE_AUTO:
                    setpointTemp = thermo["SetPointTemp"]
                elif regmode == self.REGMODE_COMFORT:
                    setpointTemp = thermo["ComfortTemperature"]
                elif regmode == self.REGMODE_MANUAL:
                    setpointTemp = thermo["ManualTemperature"]
                elif regmode == self.REGMODE_VACATION:
                    setpointTemp = thermo["VacationTemperature"]

                setpointTemp = setpointTemp / 100
                heatingOn = thermo["Heating"]
                name = thermo["Room"]
                online = thermo["Online"]
                sn = thermo["SerialNumber"]

                therm = None
                for e in self.list_of_thermos:
                    if e.name == name:
                        therm = e
                if not therm:
                    therm = UWG4_Hvac()
                    # print(f"Adding {name}")
                    self.list_of_thermos.append(therm)
                therm.set_props(
                    name,
                    actualTemp,
                    setpointTemp,
                    heatingOn,
                    regmode,
                    online,
                    sn,
                    self,
                )

        return self.list_of_thermos


#############################################################################
from abc import abstractmethod
from datetime import timedelta
import functools as ft
import logging
from typing import Any, Dict, List, Optional
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType
from homeassistant.util.unit_conversion import TemperatureConverter 

from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.climate.const import *
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
)
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity


DEFAULT_MAX_TEMP = 25.0
DEFAULT_MIN_TEMP = 5.0


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    t = UWG4()
    thermos = t.getThermoInfo()
    add_entities(thermos)


class UWG4_Hvac(ClimateEntity):

    PRESETMODE_AUTO = "Run Schedule"
    PRESETMODE_COMFORT = "{} Minute Hold".format(COMFORT_TIME)
    PRESETMODE_MANUAL = "Permanent Hold"
    PRESETMODE_VACATION = "Vacation Hold"

    def set_props(
            self, name, temp_act, temp_setpoint, heatingOn, regmode,
            online, sn, parent
    ):
        self._name = name
        self._temp_act = temp_act
        self._temp_setpoint = temp_setpoint
        self._isOnline = online
        self._isHeating = heatingOn
        self._regmode = regmode
        self._parent = parent
        self._thermoSN = sn

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._thermoSN

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        HVAC_MODE_OFF	The device is turned off.
        HVAC_MODE_HEAT	The device is set to heat to a target temperature.
        HVAC_MODE_AUTO	The device is set to a schedule, learned behavior, AI.
        """
        if not self._isOnline:
            return HVAC_MODE_OFF
        if self._regmode == UWG4.REGMODE_AUTO:
            return HVAC_MODE_AUTO
        else:
            return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_AUTO]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        CURRENT_HVAC_OFF	Device is turned off.
        CURRENT_HVAC_HEAT	Device is heating.
        CURRENT_HVAC_IDLE	Device is idle.
        """
        if not self._isOnline:
            return CURRENT_HVAC_OFF
        if self._isHeating:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_IDLE

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._temp_act

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._temp_setpoint

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        # for key, value in kwargs.items():
        #     print("{0} = {1}".format(key, value))
        temp = float(kwargs["temperature"])
        if self._regmode == UWG4.REGMODE_AUTO:
            regmode = UWG4.REGMODE_COMFORT
        else:
            regmode = self._regmode
        self._parent.setThermoTemperature(
            self._thermoSN,
            regmode,
            int(temp * 100),
        )
        self._temp_setpoint = temp
        # print(f"Setting temperature: {int(temp * 100)}")

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        # No function to turn OFF/ON/IDLE

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        preset = self.PRESETMODE_AUTO
        if self._regmode == UWG4.REGMODE_COMFORT:
            preset = self.PRESETMODE_COMFORT
        elif self._regmode == UWG4.REGMODE_MANUAL:
            preset = self.PRESETMODE_MANUAL
        elif self._regmode == UWG4.REGMODE_VACATION:
            preset = self.PRESETMODE_VACATION
        return preset

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        # this does not match the parent class because it can arrive
        # as input from the user
        PRESET_MODES = [
            self.PRESETMODE_AUTO,
            self.PRESETMODE_COMFORT,
            self.PRESETMODE_MANUAL,
            # self.PRESETMODE_VACATION,
        ]
        return PRESET_MODES

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # self.preset_mode = preset_mode
        regmode = UWG4.REGMODE_AUTO
        if preset_mode == self.PRESETMODE_AUTO:
            regmode = UWG4.REGMODE_AUTO
        if preset_mode == self.PRESETMODE_COMFORT:
            regmode = UWG4.REGMODE_COMFORT
        if preset_mode == self.PRESETMODE_MANUAL:
            regmode = UWG4.REGMODE_MANUAL
        if preset_mode == self.PRESETMODE_VACATION:
            regmode = UWG4.REGMODE_VACATION
        self._parent.setThermoTemperature(
            self._thermoSN,
            regmode,
            int(self._temp_setpoint * 100),
        )
        self._regmode = regmode

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return TemperatureConverter.convert(
            DEFAULT_MIN_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return TemperatureConverter.convert(
            DEFAULT_MAX_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._parent.getData()
        self._parent.getThermoInfo()
