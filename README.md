# uwg4
UWG4 / AWG4 Microline thermostat custom component for Home Assistant

Features:
- Auto detection of thermostats associated with your account
- Supports Permanant/90 Minute/Auto settings (as presets)
  - "Permanent" sets the temp and it stays until you change it.
  - "90 Minutes" sets the temp for 90 minutes (see below to change this duration)
  - "Auto" returns you to your pre-programmed schedules
  - Changing the temperature when in Auto mode defaults to 90 Minute mode
- Uses cloud data from mythermostat.info

# Limitations
 - Energy download not supported
 - Reading/setting schedules is not supported
   - But AUTO mode returns to existing schedules
 - The code polls the server for thermostat status once a minute
 

# How to use
- Copy the uwg4 folder to your home assistant `custom_components` folder
  - example: /opt/home-assistant/custom_components/uwg4
- Edit `climate.py` and set your username/password
   - I use the same user/pass in the OJ Microline UWG4 app by OJ Electronics
   - https://play.google.com/store/apps/details?id=com.ojelectronics.microline
   
- Add the following in your `configuration.yaml` file:
```yaml
climate:
   platform: uwg4
   # scan_interval default is 30 (internal code protects against server bashing)
   scan_interval: 20
