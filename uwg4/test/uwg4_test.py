"""Platform for sensor integration."""


import datetime
import time
import requests
import json

#import logging
#import contextlib


HOST = "https://mythermostat.info:443"
USER = "your_username"
PASSWORD = "your_password"

# Time that comfort setting should last (in minutes)
COMFORT_TIME=2

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
        self.sessionId = "zaXn5iUDH0Wos-5b_f-NzA"
        self.stateJson = None
        self.list_of_thermos = []
        self.last_update = None
        self.update_budget = 1

        account = self
        account.login()
        account.getData()  # actual data gathering
        pass

    def log(self, msg):
        print(msg)
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
        if mode == self.REGMODE_AUTO:
            data = {
                "RegulationMode": mode,
            }
        elif mode == self.REGMODE_MANUAL:
            data = {
                "RegulationMode": mode,
                "ManualTemperature": temp,
            }
        elif mode == self.REGMODE_COMFORT:
            td = datetime.timedelta(minutes=COMFORT_TIME)
            d = datetime.datetime.utcnow()
            e = d + td
            comfort_end = e.strftime("%d/%m/%Y %H:%M:00 +00:00")
            print(f"{comfort_end} - {temp}")
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
                "ManualTemperature": temp,
                "VacationEnabled": is_vacation,
                "VacationTemperature": temp,
                "VacationBeginDay": vacation_begin,
                "VacationEndDay": vacation_end,
            }
        else:
            print("Bad mode.")
            return

        r = requests.post(HOST + path, json=data, params=params)
        res = r.json()
        if res["Success"] != True:
            self.login()
            r = requests.post(HOST + path, json=data, params=params)
            res = r.json()
            if res["Success"] != True:
                self.logerr("Operation failed")
                print("Failed.")
                return
        print("Success.")
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

    def getScheduleSetpoint(self, schedule):
        weekday = datetime.datetime.today().weekday()
        days = schedule["Days"]
        day = days[weekday]
        day_evt = day["Events"]
        sch_setpoint = -1
        for evt in day_evt:
            if evt["Active"] == True:
                # print(f"Clk: {evt['Clock']} : {evt['Temperature']}")
                now = datetime.datetime.now()
                now_mins = now.hour * 60 + now.minute
                h, m, s = evt["Clock"].split(":")
                sch_mins = int(h) * 60 + int(m)
                # print(f"Min now/setpoint: {now_mins}/{sch_mins}")
                if sch_mins >= now_mins:
                    # schedule was not yer reached
                    pass
                else:
                    # schedule time was passed
                    sch_setpoint = float(evt["Temperature"])
                last_setpoint = float(evt["Temperature"])
        if sch_setpoint == -1:
            sch_setpoint = last_setpoint
        return sch_setpoint

    def getData(self, force=False):
        if self.update_budget > 0:
            self.update_budget = self.update_budget - 1
        elif not self.update_allowed():
            return

        path = "/api/thermostats"
        data = {"sessionId": self.sessionId}

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
            self.logerr("Failed to retrieve any thermostats")
            return

        self.stateJson = res
        with open("data.json", "w") as outfile:
            json.dump(res, outfile)

    def getThermoInfo(self, data=None):
        if data == None:
            data = self.stateJson
        for group in data["Groups"]:
            gname = group["GroupName"]

            print(
                f"\nG: {gname:<20}"
            )

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

                if heatingOn:
                    heatStatus = "Heating ON"
                else:
                    heatStatus = "Heating OFF"

                online = thermo["Online"]

                if online:
                    isOnline = "ONLINE"
                else:
                    isOnline = "OFFLINE"

                sn = thermo["SerialNumber"]
                actualTemp = round((1.8*actualTemp)+32, 2)
                setpointTemp = round((1.8*setpointTemp)+32, 2)
                comfortTemp = thermo["ComfortTemperature"]
                comfortTemp = comfortTemp / 100
                comfortTemp = round((1.8*comfortTemp)+32, 2)
                comEnd = thermo["ComfortEndTime"]
                manTemp = thermo["ManualTemperature"]
                manTemp = manTemp / 100
                manTemp = round((1.8*manTemp)+32, 2)
                vacTemp = thermo["VacationTemperature"]
                vacTemp = vacTemp / 100
                vacTemp = round((1.8*vacTemp)+32, 2)
                print(f"   {name:<20}/{sn:<8} : {heatStatus:<12} : {actualTemp:<4}/{setpointTemp:<4} : {self.REGMODETXT[regmode]} : {isOnline}")
                print(f"                  set={setpointTemp}  comfort={comfortTemp}  manual={manTemp}  vacation={vacTemp}")
                print(f"                  comEnd={comEnd}")


if __name__ == "__main__":
   uwg4 = UWG4()
   uwg4.getThermoInfo()
   uwg4.setThermoTemperature(1281255, uwg4.REGMODE_COMFORT, 17 * 100)
   uwg4.getData()
   uwg4.getThermoInfo()
