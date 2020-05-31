#!/usr/bin/env python
# coding: utf-8

# Copyright 2020 John Hurley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# # weather_summary.py

# # Description
# 
# Produce a basic weather report for the day for a given geolocation. Designed to be used as part of the "Automating the Christmas Bird Count" project.

# ## Library Imports

import pandas as pd
import numpy as np
from pathlib import Path
import re
import json
import requests

import geog
from datetime import tzinfo, timedelta, datetime, date

# ## Constants and Globals

# Constants and Globals
KM_PER_MILE = 1.60934
MILES_PER_KILOMETER = 0.62137119


# # Code

def meters_to_miles(xmeters: float):
    return (xmeters / 1000) * MILES_PER_KILOMETER


# https://openweathermap.org/api/one-call-api
# https://api.openweathermap.org/data/2.5/onecall?lat=33.441792&lon=-94.037689&exclude=hourly,daily&appid={YOUR API KEY}

def weather_at_location(latitude, longitude, api_key) -> pd.DataFrame:
    results = pd.DataFrame()
    try:
        api_url_base = 'https://api.openweathermap.org/data/2.5/onecall'
        exclusions = ','.join(['minutely'])
        url = api_url_base
        # For temperature in Fahrenheit use units=imperial
        params = {
            'lat': str(latitude),
            'lon': str(longitude),
            'units': 'imperial',
            'exclude': exclusions,
            'appid': str(api_key)
        }
        rr = requests.get(url, params=params, headers=None, stream=True)  # headers=api_auth_header
        if rr.status_code == requests.codes.ok:
            results = rr.json()
        rr.raise_for_status()

    except Exception as ee:
        print(ee)

    return results


# http://api.openweathermap.org/data/2.5/onecall/timemachine?lat=60.99&lon=30.9&dt=1586468027&appid={YOUR API KEY}

def weather_at_location_history(latitude, longitude, timestamp, api_key) -> pd.DataFrame:
    results = pd.DataFrame()
    try:
        api_url_base = 'https://api.openweathermap.org/data/2.5/onecall/timemachine'
        exclusions = ','.join(['minutely'])
        url = api_url_base
        # For temperature in Fahrenheit use units=imperial
        params = {
            'lat': str(latitude),
            'lon': str(longitude),
            'dt': int(timestamp),

            'units': 'imperial',
            'exclude': exclusions,

            'appid': str(api_key)
        }
        rr = requests.get(url, params=params, headers=None, stream=True)  # headers=api_auth_header
        if rr.status_code == requests.codes.ok:
            results = rr.json()
        rr.raise_for_status()

    except Exception as ee:
        print(ee)

    return results


def weather_at_location_x(latitude, longitude, api_key):
    results = weather_at_location(latitude, longitude, api_key)
    return transform_weather_results(results)


def weather_at_location_history_x(latitude, longitude, timestamp, api_key):
    results = weather_at_location_history(latitude, longitude, timestamp, api_key)
    return transform_weather_results(results)


def transform_weather_results(results):
    daily = pd.DataFrame()
    hourly = pd.DataFrame()
    current = pd.DataFrame()

    # -------------------- Daily --------------------
    daily_json = results.get('daily', None)
    if daily_json:
        daily = pd.json_normalize(daily_json).fillna('')
        # For some reason, sunrise & sunset already are in local time?
        for col, tz_offset in [('dt', results['timezone_offset']), ('sunrise', 0), ('sunset', 0)]:
            daily[col] = daily[col].apply(convert_timestamp_to_local_str, tz_offset=tz_offset)

    # -------------------- Hourly --------------------
    hourly_json = results.get('hourly', None)
    if hourly_json:
        hourly = pd.json_normalize(hourly_json).fillna('')
        hourly['dt'] = hourly['dt'].apply(convert_timestamp_to_local_str, tz_offset=0)

    # -------------------- Current --------------------
    current_json = results.get('current')
    if current_json:
        current = pd.json_normalize(current_json).fillna('')
        # For some reason, dt, sunrise & sunset already are in local time?
        for col in ['dt', 'sunrise', 'sunset']:
            current[col] = current[col].apply(convert_timestamp_to_local_str, tz_offset=0)

    return results, current, daily, hourly

def convert_timestamp_to_local_str(ts, tz_offset) -> str:
    return datetime.fromtimestamp(ts + tz_offset).strftime('%Y-%m-%d %H:%M:%S')


def wind_direction_degrees_to_text(wind_direction: float) -> str:
    # See http://snowfence.umn.edu/Components/winddirectionanddegrees.htm
    section_degrees = (360 / 16)
    half_bin = (section_degrees / 2)
    north_bin_start = 360 - (section_degrees / 2)

    # We rotate by a half_bin to make bins monotonically increasing
    wbins = [(north_bin_start + ix * section_degrees + half_bin) % 360 for ix in range(17)]
    # to make cut work
    wbins[-1] = 360

    dir_labels = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    rx = pd.cut([(wind_direction + half_bin) % 360], wbins, labels=dir_labels)
    return rx[0]


# Glyph for ℉ looks too compressed, use °F instead
def conditions_summary(cond: dict) -> str:
    conditions = ''

    temp = cond.get("temp")
    if temp:
        conditions += f'Temperature: {temp} °F\n'

    temp_min = cond.get("temp_min")
    if temp_min:
        conditions += f'Low temperature: {temp_min} °F\n'

    temp_max = cond.get("temp_max")
    if temp_max:
        conditions += f'High temperature: {temp_max} °F\n'

    wind_deg = cond.get('wind_deg', None)
    wind_dir_str = f' from {wind_direction_degrees_to_text(wind_deg)}' if wind_deg else ''
    conditions += f'Wind: {cond["wind_speed"]} mph{wind_dir_str}\n'

    rain = cond.get("rain", 0)
    if rain == '':
        rain = 0
    if rain > 0:
        conditions += f'Rain: {rain} mm\n'

    snow = cond.get("snow", 0)
    if snow == '':
        snow = 0
    if snow > 0:
        conditions += f'Snow: {snow} mm\n'

    humidity = cond.get("humidity", 0)
    if humidity == '':
        humidity = 0
    if humidity > 0:
        conditions += f'Humidity: {humidity} %\n'

    pct_cloudy = cond["clouds"]
    weather_description = ', '.join([w["description"] for w in cond["weather"]])
    conditions += f'Description: {weather_description}, {pct_cloudy:.0f}% cloudy\n'

    sunrise = cond.get("sunrise")
    if sunrise:
        conditions += f'Sunrise: {sunrise}\n'

    sunset = cond.get("sunset")
    if sunrise:
        conditions += f'Sunset : {sunset}\n'

    return conditions


def summary_weather_report(results, daily_df, current_df, reporting_location, actual_hourly) -> str:
    summary = ''
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    utoday = datetime.timestamp(today)

    current = current_df.iloc[0].to_dict()
    daily = daily_df.iloc[0].to_dict()
    del daily["sunrise"]
    del daily["sunset"]

    summary += f'Current Conditions {current["dt"]}\n{conditions_summary(current)}\n'
    summary += f'Forecast {current["dt"]}\n{conditions_summary(daily)}\n'

    for hr in [7, 10, 13, 16]:  # 7,8,11,12,15,16
        dt_str = today.replace(hour=hr, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        df = actual_hourly[actual_hourly.dt == dt_str]
        if df.shape[0] > 0:
            summary += f'Conditions at {dt_str}\n'
            summary += conditions_summary(df.iloc[0].to_dict())
            summary += '\n'

    weather_station_location = (results["lat"], results["lon"])  # 1.0001*lat to move a bit

    summary += f'Weather station location: {weather_station_location}\n'
    summary += f'Reporting location      : {reporting_location}\n'

    # distance in meters
    dist_to_station_m = geog.distance(weather_station_location, reporting_location)
    dist_to_station = meters_to_miles(dist_to_station_m)
    summary += f'Reporting location is {dist_to_station:.2f} miles from weather station\n'

    return summary


def create_weather_summary(reporting_location: tuple, openweather_api_key) -> str:
    # reporting_location is a tuple: (latitude, longitude)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    utoday = datetime.timestamp(today)

    results, current, daily, hourly = weather_at_location_x(*reporting_location, api_key=openweather_api_key)
    hist_results, actual_current, actual_daily, actual_hourly = weather_at_location_history_x(*reporting_location,
                                                                                              timestamp=utoday,
                                                                                              api_key=openweather_api_key)

    summary = summary_weather_report(results, daily, current, reporting_location, actual_hourly)

    return summary
