#!/usr/bin/env python3
# Regularly Polls Purpleair api for outdoor sensor data and sends email notofications when air quality exceeds threshold.
# James S. Lucas - 20230916

import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from time import sleep
from tabulate import tabulate
import logging
from typing import List
from conversions import AQI, EPA
import constants
from configparser import ConfigParser
from urllib3.exceptions import ReadTimeoutError
from google.auth.exceptions import TransportError
import ezgmail

# Read config file
config = ConfigParser()
config.read('config.ini')

# Gets or creates a logger
logger = logging.getLogger(__name__)  
# set log level
logger.setLevel(logging.WARNING)
# define file handler and set formatter
file_handler = logging.FileHandler('pa_notify_alert_error.log')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
# add file handler to logger
logger.addHandler(file_handler)

# Setup requests session with retry
session = requests.Session()
retry = Retry(total=10, backoff_factor=1.0)
adapter = HTTPAdapter(max_retries=retry)
PURPLEAIR_READ_KEY = config.get('purpleair', 'PURPLEAIR_READ_KEY')
if PURPLEAIR_READ_KEY == '':
    logger.error('Error: PURPLEAIR_READ_KEY not set in config.ini')
    print('ERROR: PURPLEAIR_READ_KEY not set in config.ini')
    sys.exit(1)
session.headers.update({'X-API-Key': PURPLEAIR_READ_KEY})
session.mount('http://', adapter)
session.mount('https://', adapter)


GMAIL_API_CREDENTIALS = config.get('google', 'GMAIL_API_CREDENTIAL_JSON_PATH')
EZGMAIL_API_TOKEN = config.get('google', 'EZGMAIL_API_TOKEN_JSON_PATH')
ezgmail.init(tokenFile=EZGMAIL_API_TOKEN, credentialsFile=GMAIL_API_CREDENTIALS)

previous_timestamp = None
previous_aqi_value = None


def status_update(local_et, regional_et, local_time_stamp, local_pm25_aqi, confidence, local_30minute_aqi, rate_of_change):
    """
    A function that calculates the time remaining for each interval and prints it in a table format.

    Args:
        local_et (int): The elapsed time for the local interval in seconds.
        regional_et (int): The elapsed time for the regional interval in seconds.

    Returns:
        A datetime object representing the current time.
    """
    local_minutes = int((constants.LOCAL_INTERVAL_DURATION - local_et) / 60)
    local_seconds = int((constants.LOCAL_INTERVAL_DURATION - local_et) % 60)
    regional_minutes = int((constants.REGIONAL_INTERVAL_DURATION - regional_et) / 60)
    regional_seconds = int((constants.REGIONAL_INTERVAL_DURATION - regional_et) % 60)
    time_stamp = local_time_stamp.strftime('%m/%d/%Y %H:%M:%S')
    table_data = [
        ['Local:', f"{local_minutes:02d}:{local_seconds:02d}"],
        ['Regional:', f"{regional_minutes:02d}:{regional_seconds:02d}"],
        ['Timestamp:', time_stamp],
        ['PM 2.5 AQI:', local_pm25_aqi],
        ['Confidence:', confidence],
        ['PM 2.5 AQI Rate of Change:', rate_of_change],
        ['PM 2.5 AQI 10 Minute Average:', local_30minute_aqi]
    ]
    print(tabulate(table_data, headers=['Interval', 'Time Remaining (MM:SS)'], tablefmt='orgtbl'))
    print("\033c", end="")
    return datetime.now()


def elapsed_time(local_start, regional_start, status_start):
    """
    Calculates the elapsed time for each interval since the start time.

    Args:
        local_start (datetime): The start time for the local interval.
        regional_start (datetime): The start time for the regional interval.
        status_start (datetime): The start time for the status interval.

    Returns:
        A tuple containing the elapsed time for each interval in seconds.
    """
    local_et: int = (datetime.now() - local_start).total_seconds()
    regional_et: int = (datetime.now() - regional_start).total_seconds()
    status_et: int = (datetime.now() - status_start).total_seconds()
    return local_et, regional_et, status_et


def get_local_pa_data(sensor_id) -> float:
    """
    A function that queries the PurpleAir API for sensor data for a given sensor.

    Args:
        sensor_id (float): The id of a sensor.

    Returns:
        local_aqi (float): The PM 2.5 AQI.
        time_stamp (datetime): The timestamp of the data.
        confidence (str): The confidence of the sensor data.
    """
    root_url: str = 'https://api.purpleair.com/v1/sensors/{sensor_id}?fields={fields}'
    params = {
        'sensor_id': sensor_id,
        'fields': "name,humidity,pm2.5_atm_a,pm2.5_atm_b,pm2.5_cf_1_a,pm2.5_cf_1_b,pm2.5_30minute"
    }
    url: str = root_url.format(**params)
    try:
        response = session.get(url)
    except requests.exceptions.RequestException as e:
        logger.exception(f'get_pa_data() error: {e}')
        return 0
    if response.ok:
        url_data = response.content
        json_data = json.loads(url_data)
        sensor_data = json_data['sensor']
        sensor_name = sensor_data['name']
        pm25_atm_a = sensor_data['pm2.5_atm_a']
        pm25_atm_b = sensor_data['pm2.5_atm_b']
        pm25_cf1_a = sensor_data['pm2.5_cf_1_a']
        pm25_cf1_b = sensor_data['pm2.5_cf_1_b']
        pm25_30minute = sensor_data['stats']['pm2.5_30minute']
        humidity = sensor_data['humidity']
        # Calculate sensor confidence
        pm_dif_pct = abs(pm25_atm_a - pm25_atm_b) / ((pm25_atm_a + pm25_atm_b + 1e-6) / 2)
        pm_dif_abs = abs(pm25_atm_a - pm25_atm_b)
        if pm_dif_pct >= 0.7 or pm_dif_abs >= 5:
            confidence = 'LOW'
            pm_cf1 = max(pm25_cf1_a, pm25_cf1_b)
        else:
            confidence = 'GOOD'
            pm_cf1 = (pm25_cf1_a + pm25_cf1_b) / 2
        local_aqi = AQI.calculate(EPA.calculate(humidity, pm_cf1))
        local_30minute_aqi = AQI.calculate(pm25_30minute)
    else:
        local_aqi = 'ERROR'
        confidence = 'ERROR'
        sensor_name = 'ERROR'
        local_30minute_aqi = 'ERROR'
        logger.exception('get_pa_data() response not ok')
    time_stamp = datetime.now()
    return sensor_id, sensor_name, local_aqi, confidence, time_stamp, local_30minute_aqi


def get_regional_pa_data(previous_time, bbox: List[float]) -> pd.DataFrame:
    """
    A function that queries the PurpleAir API for outdoor sensor data within a given bounding box and time frame.

    Args:
        previous_time (datetime): A datetime object representing the time of the last query.
        bbox (List[float]): A list of four floats representing the bounding box of the area of interest.
            The order is [northwest longitude, southeast latitude, southeast longitude, northwest latitude].

    Returns:
        Ipm25 (float) - Float of the pseudo PM 2.5 AQI with EPA correction.
    """
    et_since = int((datetime.now() - previous_time + timedelta(seconds=20)).total_seconds())
    root_url: str = 'https://api.purpleair.com/v1/sensors/?fields={fields}&max_age={et}&location_type=0&nwlng={nwlng}&nwlat={nwlat}&selng={selng}&selat={selat}'
    params = {
        'fields': "name,humidity,pm2.5_atm_a,pm2.5_atm_b,pm2.5_cf_1_a,pm2.5_cf_1_b",
        'nwlng': bbox[0],
        'selat': bbox[1],
        'selng': bbox[2],
        'nwlat': bbox[3],
        'et': et_since
    }
    url: str = root_url.format(**params)
    print(url)
    cols: List[str] = ['time_stamp', 'sensor_index'] + [col for col in params['fields'].split(',')]
    try:
        response = session.get(url)
    except requests.exceptions.RequestException as e:
        logger.exception(f'get_pa_data() error: {e}')
        df = pd.DataFrame()
        return df
    if response.ok:
        url_data = response.content
        json_data = json.loads(url_data)
        df = pd.DataFrame(json_data['data'], columns=json_data['fields'])
        df = df.fillna('')
        df['time_stamp'] = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        df = df[cols]
        df = clean_data(df)
        df['pm25_epa'] = df.apply(
                    lambda x: EPA.calculate(x['humidity'], x['pm2.5_cf_1_a'], x['pm2.5_cf_1_b']),
                    axis=1
                    )        
        df['Ipm25'] = df.apply(
            lambda x: AQI.calculate(x['pm2.5_atm_a'], x['pm2.5_atm_b']),
            axis=1
            )
        mean_ipm25 = df['Ipm25'].mean()
    else:
        df = pd.DataFrame()
        logger.exception('get_pa_data() response not ok')
    return round(mean_ipm25, 1) 


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes rows from the input DataFrame where the difference between the PM2.5 atmospheric concentration readings
    from two sensors is either greater than or equal to 5 or greater than or equal to 70% of the average of the two readings,
    or greater than 2000.

    Args:
        df (pd.DataFrame): The input DataFrame containing the PM2.5 atmospheric concentration readings from two sensors.

    Returns:
        A new DataFrame with the rows removed where the difference between the PM2.5 atmospheric concentration readings
        from two sensors is either greater than or equal to 5 or greater than or equal to 70% of the average of the two readings,
        or greater than 2000.
    """
    df = df.drop(df[df['pm2.5_atm_a'] > 2000].index)
    df = df.drop(df[df['pm2.5_atm_b'] > 2000].index)
    df = df.drop(df[abs(df['pm2.5_atm_a'] - df['pm2.5_atm_b']) >= 5].index)
    df = df.drop(
        df[abs(df['pm2.5_atm_a'] - df['pm2.5_atm_b']) /
            ((df['pm2.5_atm_a'] + df['pm2.5_atm_b'] + 1e-6) / 2) >= 0.7
        ].index
    )
    df = df.drop(df[df['pm2.5_cf_1_a'] > 2000].index)
    df = df.drop(df[df['pm2.5_cf_1_b'] > 2000].index)
    df = df.drop(df[abs(df['pm2.5_cf_1_a'] - df['pm2.5_cf_1_b']) >= 5].index)
    df = df.drop(
        df[abs(df['pm2.5_cf_1_a'] - df['pm2.5_cf_1_b']) /
            ((df['pm2.5_cf_1_a'] + df['pm2.5_cf_1_b'] + 1e-6) / 2) >= 0.7
        ].index
    )
    return df


def aqi_rate_of_change(timestamp, aqi_value):
    global previous_timestamp, previous_aqi_value
    
    if previous_timestamp is None or previous_aqi_value is None:
        # First call, no previous data available
        previous_timestamp = timestamp
        previous_aqi_value = aqi_value
        return 0
    
    time_delta = (timestamp - previous_timestamp).total_seconds() / 60
    aqi_delta = aqi_value - previous_aqi_value
    aqi_rate_of_change = round(aqi_delta / time_delta, 2)
    
    # Remember current values for next call
    previous_timestamp = timestamp
    previous_aqi_value = aqi_value
    
    return aqi_rate_of_change


def notification_check():
    pass



def notify(recipient_list, subject, body_intro, pa_map_link, local_time_stamp, sensor_id, sensor_name, local_pm25_aqi, local_30minute_aqi, confidence, rate_of_change, regional_aqi_mean, disclaimer_pt1, disclaimer_pt2, disclaimer_pt3):
    if rate_of_change < 0:
        rate_of_change_text = f'Air quality has decreased by {abs(rate_of_change)} AQI points per minute since the previous reading'
    elif rate_of_change > 0:
        rate_of_change_text = f'Air quality has increased by {abs(rate_of_change)} AQI points per minute since the previous reading'
    else:
        rate_of_change_text = f'Air quality has not changed since the previous reading'
    if confidence == 'LOW':
        confidence_text = 'Sensor accuracy is low, the sensor may need cleaning. Please obtain accurate data through official sources.'
    else:
        confidence_text = ''
    local_time_stamp = local_time_stamp.strftime('%m/%d/%Y %H:%M:%S')
    email_body = (
                f'{body_intro} <br>'
                f'Air quality for PurpleAir Sensor "{sensor_id} - {sensor_name}" information as of {local_time_stamp} <br>'
                f'PM 2.5 AQI: {local_pm25_aqi} <br>'
                f'PM 2.5 AQI 30 Minute Average: {local_30minute_aqi} <br>' 
                f'{rate_of_change_text} <br>'
                f'Regional average PM 2.5 AQI: {regional_aqi_mean} <br>'
                f'{pa_map_link} <br><br>'
                f'{disclaimer_pt1} <br><br>'
                f'{confidence_text}'
                f'{disclaimer_pt2} <br>'
                f'{disclaimer_pt3} <br>'
    )
    for recipient in recipient_list:
        ezgmail.send(recipient, subject, email_body, mimeSubtype='html')
    notification_time_stamp = datetime.now()
    with open('last_notification.txt', 'w') as f:
        f.write(str(notification_time_stamp))


def notify_test(recipient_list, subject, body_intro, pa_map_link, local_time_stamp, sensor_id, sensor_name, local_pm25_aqi, local_30minute_aqi, confidence, rate_of_change, regional_aqi_mean, elapsed_time, disclaimer_pt1, disclaimer_pt2, disclaimer_pt3):
    if rate_of_change < 0:
        rate_of_change_text = f'Air quality has decreased by {abs(rate_of_change)} AQI points per minute since the previous reading'
    elif rate_of_change > 0:
        rate_of_change_text = f'Air quality has increased by {abs(rate_of_change)} AQI points per minute since the previous reading'
    else:
        rate_of_change_text = f'Air quality has not changed since the previous reading'
    if confidence == 'LOW':
        confidence_text = 'Sensor accuracy is low, the sensor may need cleaning. Please obtain accurate data through official sources.'
    else:
        confidence_text = ''
    local_time_stamp = local_time_stamp.strftime('%m/%d/%Y %H:%M:%S')
    print()
    print(f'Subject: {subject}')
    print(f'To: {recipient_list[0]}')
    print()
    print(f'{body_intro}')
    print()
    print(f'Air quality information for PurpleAir Sensor "{sensor_id} - {sensor_name}" as of {local_time_stamp}')
    print(f'PM 2.5 AQI: {local_pm25_aqi}')
    print(f'PM 2.5 AQI 30 Minute Average: {local_30minute_aqi}')
    print(f'{rate_of_change_text}')
    print(f'{confidence_text}')
    print(f'Regional average PM 2.5 AQI: {regional_aqi_mean}')
    print(f"Elapsed time since last notification: {int(elapsed_time.total_seconds())} seconds")
    print(f'{pa_map_link}')
    print()
    print()
    print(f'{disclaimer_pt1}')
    print()
    print(f'{disclaimer_pt2}')
    print()
    print(f'{disclaimer_pt3}')
    print()
    notification_time_stamp = datetime.now()
    with open('last_notification.txt', 'w') as f:
        f.write(str(notification_time_stamp))


def main():
    five_min_ago: datetime = datetime.now() - timedelta(minutes=5)
    local_start, regional_start, process_start, status_start = datetime.now(), datetime.now(), datetime.now(), datetime.now()
    sensor_id = ''
    sensor_name = ''
    local_pm25_aqi = 0
    confidence = ''
    local_time_stamp = datetime.now()
    local_30minute_aqi = 0
    rate_of_change = 0
    regional_aqi_mean = 0
    notification_elapsed_time = 0
    while True:
        try:
            sleep(.1)
            local_et, regional_et, status_et = elapsed_time(local_start, regional_start, status_start)
            if status_et >= constants.STATUS_INTERVAL_DURATION:
                #status_start = status_update(local_et, regional_et, local_time_stamp, local_pm25_aqi, confidence, local_30minute_aqi, rate_of_change)
                with open('last_notification.txt', 'r') as f:
                    last_notification_str = f.read().strip()
                last_notification = datetime.strptime(last_notification_str, '%Y-%m-%d %H:%M:%S.%f')
                # Calculate the elapsed time since the last notification
                notification_elapsed_time = datetime.now() - last_notification
                notify_test(constants.RECIPIENT_LIST, constants.SUBJECT, constants.BODY_INTRO, constants.PA_MAP_LINK, local_time_stamp, sensor_id, sensor_name, local_pm25_aqi, local_30minute_aqi, confidence, rate_of_change, regional_aqi_mean, notification_elapsed_time, constants.DISCLAIMER_PT1, constants.DISCLAIMER_PT2, constants.DISCLAIMER_PT3)
                # Read the last notification timestamp from file
                status_start = datetime.now()
            if local_et >= constants.LOCAL_INTERVAL_DURATION:
                sensor_id, sensor_name, local_pm25_aqi, confidence, local_time_stamp, local_30minute_aqi = get_local_pa_data(constants.LOCAL_SENSOR)
                if local_pm25_aqi != 'ERROR':
                    rate_of_change = aqi_rate_of_change(local_time_stamp, local_pm25_aqi)
                #sleep(20)
                #egional_aqi_mean = get_regional_pa_data(local_start, constants.BBOX_DICT.get(constants.LOCAL_REGION)[0])
                local_start: datetime = datetime.now()
            if regional_et > constants.REGIONAL_INTERVAL_DURATION:
                #for regional_key in constants.REGIONAL_KEYS:
                    #df = get_pa_data(regional_start, constants.BBOX_DICT.get(regional_key)[0]) 
                    #sleep(10)
                regional_start: datetime = datetime.now()

        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()