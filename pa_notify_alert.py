#!/usr/bin/env python3
# Regularly polls Purpleair api for outdoor sensor data and sends notifications via text or email when air quality exceeds threshold.
# James S. Lucas - 20240411

import os
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json
import pandas as pd
from numpy import arange, array, polyfit
from math import ceil
import datetime
from time import sleep
import pytz
from tabulate import tabulate
import logging
from conversions import AQI, EPA
import constants
from configparser import ConfigParser
import ezgmail
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Read config file
config = ConfigParser()
config.read('config.ini')

# Create a logger for manual logging
logger = logging.getLogger(__name__)  
# set log level
logger.setLevel(logging.WARNING)
# define file handler and set formatter
file_handler = logging.FileHandler('pa_notify_alert_error_log.txt')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
# add file handler to logger
logger.addHandler(file_handler)

# Create a logger for urllib3
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)
file_handler = logging.FileHandler('pa_notify_alert_urllib3_log.txt')
formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
file_handler.setFormatter(formatter)
urllib3_logger.addHandler(file_handler)

# Setup requests session with retry for PurpleAir API
PURPLEAIR_READ_KEY = config.get('purpleair', 'PURPLEAIR_READ_KEY')
if PURPLEAIR_READ_KEY == '':
    logger.error('Error: PURPLEAIR_READ_KEY not set in config.ini')
    print('ERROR: PURPLEAIR_READ_KEY not set in config.ini')
    sys.exit(1)
session = requests.Session()
retry = Retry(total=10, backoff_factor=1.0, status_forcelist=tuple(range(401, 600)))
adapter = HTTPAdapter(max_retries=retry)
session.headers.update({'X-API-Key': PURPLEAIR_READ_KEY})
session.mount('http://', adapter)
session.mount('https://', adapter)

GMAIL_API_CREDENTIALS = config.get('google', 'GMAIL_API_CREDENTIAL_JSON_PATH')
if GMAIL_API_CREDENTIALS == '':
    logger.error('Error: GMAIL_API_CREDENTIALS not set in config.ini')
    print('ERROR: GMAIL_API_CREDENTIALS not set in config.ini')
    sys.exit(1)

EZGMAIL_API_TOKEN = config.get('google', 'EZGMAIL_API_TOKEN_JSON_PATH')
if EZGMAIL_API_TOKEN == '':
    logger.error('Error: EZGMAIL_API_TOKEN not set in config.ini')
    print('ERROR: EZGMAIL_API_TOKEN not set in config.ini')
    sys.exit(1)

ezgmail.init(tokenFile=EZGMAIL_API_TOKEN, credentialsFile=GMAIL_API_CREDENTIALS)
twilio_client = Client(config.get('twilio', 'ACCOUNT_SID'), config.get('twilio', 'AUTH_TOKEN'))


def retry(max_attempts: int = 3, delay: int = 2, escalation: int = 10, exception=(Exception,)):
    """
    A decorator function that retries a function call a specified number of times if it raises a specified exception.

    Args:
        max_attempts (int): The maximum number of attempts to retry the function call.
        delay (int): The initial delay in seconds before the first retry.
        escalation (int): The amount of time in seconds to increase the delay by for each subsequent retry.
        exception (tuple): A tuple of exceptions to catch and retry on.

    Returns:
        The decorated function.

    Raises:
        The same exception that the decorated function raises if the maximum number of attempts is reached.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exception as e:
                    adjusted_delay = delay + escalation * attempts
                    attempts += 1
                    logger.exception(f'Error in {func.__name__}(): attempt #{attempts} of {max_attempts}')
                    if attempts < max_attempts:
                        sleep(adjusted_delay)
            logger.exception(f'Error in {func.__name__}: max of {max_attempts} attempts reached')
            print(f'Error in {func.__name__}(): max of {max_attempts} attempts reached')
            sys.exit(1)
        return wrapper
    return decorator


def status_update(sensor_name: str,
                  polling_et: int,
                  text_notification_et: int,
                  email_notification_et: int,
                  local_time_stamp: datetime,
                  local_pm25_aqi: float,
                  local_pm25_aqi_avg: float,
                  confidence: str,
                  pm_aqi_roc: float,
                  regional_aqi_mean: float,
                  max_data_points: int,
                  local_pm25_aqi_list: list[float]) -> datetime:
    """
    Prints a table of program status information.

    Args:
        polling_et (int): The elapsed time since the last polling.
        text_notification_et (int): The elapsed time since the last text notification.
        email_notification_et (int): The elapsed time since the last email notification.
        local_time_stamp (datetime): The local timestamp.
        local_pm25_aqi (float): The local PM 2.5 AQI.
        local_pm25_aqi_avg (float): The local PM 2.5 AQI average.
        confidence (float): The Gan sensor confidence.
        pm_aqi_roc (float): The PM 2.5 AQI rate of change.
        regional_aqi_mean (float): The regional AQI mean.
        max_data_points (int): The maximum number of data points.
        local_pm25_aqi_list (list[float]): The current list of PM2.5 AQI data points.

    Returns:
        datetime: The current datetime.
    """
    polling_minutes = int((constants.POLLING_INTERVAL - polling_et) / 60)
    polling_seconds = int((constants.POLLING_INTERVAL - polling_et) % 60)
    text_notification_hours = int((constants.NOTIFICATION_INTERVAL - text_notification_et) / 3600)
    text_notification_minutes = int((constants.NOTIFICATION_INTERVAL - text_notification_et) / 60) % 60
    text_notification_seconds = int((constants.NOTIFICATION_INTERVAL - text_notification_et) % 60)
    email_notification_hours = int((constants.NOTIFICATION_INTERVAL - email_notification_et) / 3600)
    email_notification_minutes = int((constants.NOTIFICATION_INTERVAL - email_notification_et) / 60) % 60
    email_notification_seconds = int((constants.NOTIFICATION_INTERVAL - email_notification_et) % 60)
    time_stamp = local_time_stamp.strftime('%m/%d/%Y %H:%M:%S')
    #aqi_string = ' '
    #for point in local_pm25_aqi_list:
        #aqi_string = f' {aqi_string} | {str(point)}'
    #if len(aqi_string) > 0:
        #aqi_string = aqi_string[9:]
    pad = ' '
    table_data = [
        ['Polling', f'{polling_minutes:02d}:{polling_seconds:02d}'],
        ['Text / Email Notification', f'{text_notification_hours:02d}:{text_notification_minutes:02d}:{text_notification_seconds:02d} / {email_notification_hours:02d}:{email_notification_minutes:02d}:{email_notification_seconds:02d}'],
        ['Num / Max Data Points', f'{len(local_pm25_aqi_list)} / {max_data_points}'],
        [' ', ' '],
        ['Time Now', f'__Start__| {datetime.datetime.utcnow().strftime("%H:%M:%S")} |___End___'],
        ['Polling', f'{constants.POLLING_START_TIME} |{pad:^10}| {constants.POLLING_END_TIME}'],
        ['Pre-Open Alert', f'{constants.PRE_OPEN_ALERT_START_TIME} |{pad:^10}| {constants.PRE_OPEN_ALERT_END_TIME}'],
        ['Open Alert', f'{constants.OPEN_ALERT_START_TIME} |{pad:^10}| {constants.OPEN_ALERT_END_TIME}'],
        [' ', ' '],
        ['PM 2.5 AQI', f'{local_pm25_aqi:.0f}'],
        ['PM 2.5 AQI Average', f'{local_pm25_aqi_avg:.0f}'],
        #['PM 2.5 AQI List', f'{aqi_string}'],
        ['Regional AQI', f'{regional_aqi_mean:.0f}'],
        [f'{sensor_name} Sensor Confidence', f'{confidence}'],
        ['PM 2.5 AQI Rate of Change', f'{pm_aqi_roc:.1f}'],
        ['Timestamp', f'{time_stamp}']
    ]
    print(tabulate(table_data, headers=['Description', 'Status'], tablefmt='orgtbl'))
    print("\033c", end="")
    return datetime.datetime.now()


def elapsed_time(polling_start: datetime,
                 status_start: datetime,
                 last_text_notification: datetime,
                 last_email_notification: datetime) -> tuple:
    """
    Calculates the elapsed time in seconds since the given timestamps.

    Args:
        polling_start (datetime.datetime): The timestamp when the polling started.
        status_start (datetime.datetime): The timestamp when the status started.
        last_text_notification (datetime.datetime): The timestamp of the last text notification.
        last_email_notification (datetime.datetime): The timestamp of the last email notification.

    Returns:
        Tuple[int, int, int, int]: A tuple containing the elapsed time in seconds for polling, status, text notification, and email notification.
    """
    polling_et: int = (datetime.datetime.now() - polling_start).total_seconds()
    status_et: int = (datetime.datetime.now() - status_start).total_seconds()
    text_notification_et: int = (datetime.datetime.now(datetime.timezone.utc) - last_text_notification).total_seconds()
    email_notification_et: int = (datetime.datetime.now(datetime.timezone.utc) - last_email_notification).total_seconds()
    return polling_et, status_et, text_notification_et, email_notification_et


def write_timestamp(time_stamp: datetime, com_mode: str) -> None:
    """
    Writes the current timestamp to a text file in the specified communication mode file.
    Args:
        time_stamp (datetime): The current timestamp to be written to the file.
        com_mode (str): The communication mode filename to write the timestamp to ('email' or 'text').
    Returns:
        None
    """
    file_paths = {
        'email': 'last_email_notification.txt',
        'text': 'last_text_notification.txt',
        'daily_text': 'last_daily_text_notification.txt',
        'daily_email': 'last_daily_email_notification.txt'
    }
    try:
        file_path = file_paths[com_mode]
    except KeyError:
        logger.exception(f'Error in write_timestamp(): invalid com_mode: {com_mode}')
        print(f'Error in write_timestamp(): invalid com_mode: {com_mode}')
        sys.exit(1)
    # Store the UTC datetime in a text file
    with open(file_path, 'w') as file:
        file.write(time_stamp.strftime('%Y-%m-%d %H:%M:%S%z'))


def read_timestamp(file_paths: dict[str,str]) -> tuple:
    """
    Reads the datetime from several text files and returns them as a tuple.
    If the text file does not exist, it creates a new file with the current datetime minus 24 hours.

    Returns:
    tuple: A tuple containing the datetime values read from the text files.
    """
    for file_path, v in file_paths.items():
        # Read the datetime from the text file
        try:
            with open(file_path, 'r') as file:
                datetime_str = file.read().strip()
        except FileNotFoundError:
            logger.exception(f'Error in read_timestamp(): {file_path} not found')
            print(f'Error in read_timestamp(): {file_path} not found')
            with open(file_path, 'w') as file:
                # Create a new file with the current datetime minus 24 hours
                current_datetime = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S%z')
                file.write(current_datetime)
            datetime_str = current_datetime
        loaded_datetime = datetime.datetime.fromisoformat(datetime_str).replace(tzinfo=datetime.timezone.utc)
        file_paths[file_path] = loaded_datetime
    keys_order = ['last_text_notification.txt',
                  'last_email_notification.txt',
                  'last_daily_text_notification.txt',
                  'last_daily_email_notification.txt']
    return [file_paths[key] for key in keys_order]


def is_pdt() -> bool:
    """
    Determines if it is currently Pacific Daylight Time (PDT) or Pacific Standard Time (PST).

    Returns:
        bool: True if it is currently PDT, False if it is currently PST.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if now.astimezone(datetime.timezone(datetime.timedelta(hours=-7))).dst() != datetime.timedelta(0):
        return True
    else:
        return False


def get_local_pa_data(sensor_id: int) -> tuple:
    """
    Retrieves data from a PurpleAir sensor with the given sensor ID and calculates the AQI.

    Args:
        sensor_id (int): The ID of the PurpleAir sensor to retrieve data from.

    Returns:
        tuple: A tuple containing the sensor ID, sensor name, local AQI, confidence level, and timestamp of the data retrieval.
    """
    root_url: str = 'https://api.purpleair.com/v1/sensors/{sensor_id}?fields={fields}'
    params = {
        'sensor_id': sensor_id,
        'fields': "humidity,pm2.5_cf_1_a,pm2.5_cf_1_b"
    }
    url: str = root_url.format(**params)
    try:
        response = session.get(url)
    except requests.exceptions.RequestException as e:
        logger.exception(f'get_local_pa_data() error: {e}')
        return 0
    if response.ok:
        url_data = response.content
        json_data = json.loads(url_data)
        sensor_data = json_data.get('sensor', 0.0)
        pm25_cf1_a = sensor_data.get('pm2.5_cf_1_a', 0.0)
        pm25_cf1_b = sensor_data.get('pm2.5_cf_1_b', 0.0)
        humidity = sensor_data.get('humidity', 0.0)
        # Calculate sensor confidence
        pm_dif_pct = abs(pm25_cf1_a - pm25_cf1_b) / ((pm25_cf1_a + pm25_cf1_b + 1e-6) / 2)
        pm_dif_abs = abs(pm25_cf1_a - pm25_cf1_b)
        if pm_dif_pct >= 0.7 or pm_dif_abs >= 5:
            confidence = 'LOW'
            pm_cf1 = max(pm25_cf1_a, pm25_cf1_b)
        else:
            confidence = 'GOOD'
            pm_cf1 = (pm25_cf1_a + pm25_cf1_b) / 2
        local_aqi = AQI.calculate(EPA.calculate(humidity, pm_cf1))
    else:
        local_aqi = 'ERROR'
        confidence = 'ERROR'
        logger.exception('get_local_pa_data() response not ok')
        logger.exception(f'get_local_pa_data() response: {response}')
    time_zone = pytz.timezone(constants.REPORTING_TIME_ZONE)
    time_stamp = datetime.datetime.now(time_zone)
    return sensor_id, local_aqi, confidence, time_stamp


def get_regional_pa_data(bbox: list[float], local_aqi: float) -> pd.DataFrame:
    """
    A function that queries the PurpleAir API for outdoor sensor data within a given bounding box and time frame.

    Args:
        bbox (list[float]): A list of four floats representing the bounding box of the area of interest.
            The order is [northwest longitude, southeast latitude, southeast longitude, northwest latitude].

    Returns:
        Mean Ipm25 (float) - Float of the pseudo PM 2.5 AQI with US EPA correction.
    """
    root_url: str = 'https://api.purpleair.com/v1/sensors/?fields={fields}&location_type={location_type}&max_age={max_age}&nwlng={nwlng}&nwlat={nwlat}&selng={selng}&selat={selat}'
    params = {
        'fields': "humidity,pm2.5_cf_1_a,pm2.5_cf_1_b",
        'location_type': "0",
        'max_age': f"{constants.POLLING_INTERVAL * 3}",
        'nwlng': bbox[0],
        'selat': bbox[1],
        'selng': bbox[2],
        'nwlat': bbox[3]
    }
    url: str = root_url.format(**params)
    cols: list[str] = ['time_stamp', 'sensor_index'] + [col for col in params['fields'].split(',')]
    try:
        response = session.get(url)
    except requests.exceptions.RequestException as e:
        logger.exception(f'get_regional_pa_data() error: {e}')
        df = pd.DataFrame()
        return df
    if response.ok:
        url_data = response.content
        json_data = json.loads(url_data)
        df = pd.DataFrame(json_data['data'], columns=json_data['fields'])
        df = df.fillna('')
        df['time_stamp'] = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        df = df[cols]
        df = clean_data(df)
        if not df.empty:
            df['pm25_epa'] = df.apply(
                        lambda x: EPA.calculate(x['humidity'], x['pm2.5_cf_1_a'], x['pm2.5_cf_1_b']),
                        axis=1
                        )
            df['Ipm25'] = df.apply(
                lambda x: AQI.calculate(x['pm25_epa']),
                axis=1
                )
            mean_ipm25 = df['Ipm25'].mean()
        else:
            # All of the sensors had low confidence so df was empty.
            mean_ipm25 = local_aqi

    else:
        df = pd.DataFrame()
        logger.exception('get_regional_pa_data() response not ok')
    return round(mean_ipm25, 1) 


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes rows from the input DataFrame where the difference between the PM2.5 readings
    from two sensors is either greater than or equal to 5 or greater than or equal to 70% of the average of the two readings,
    or greater than 2000.

    Args:
        df (pd.DataFrame): The input DataFrame containing the PM2.5 readings from two sensors.

    Returns:
        A new DataFrame with the rows removed where the difference between the PM2.5 readings
        from two sensors is either greater than or equal to 5 or greater than or equal to 70% of the average of the two readings 
        (US EPA Conversion data cleaning criteria), or greater than 2000.
    """
    df = df.drop(df[df['pm2.5_cf_1_a'] > 2000].index)
    df = df.drop(df[df['pm2.5_cf_1_b'] > 2000].index)
    df = df.drop(df[abs(df['pm2.5_cf_1_a'] - df['pm2.5_cf_1_b']) >= 5].index)
    df = df.drop(
        df[abs(df['pm2.5_cf_1_a'] - df['pm2.5_cf_1_b']) /
            ((df['pm2.5_cf_1_a'] + df['pm2.5_cf_1_b'] + 1e-6) / 2) >= 0.7
        ].index
    )
    return df


def aqi_rate_of_change(data_points: list[float]) -> float:
    """
    Calculates the rate of change of AQI (Air Quality Index) based on the given data points.

    Args:
        data_points (list): A list of AQI data points.

    Returns:
        float: The rate of change of AQI in AQI / min rounded to 1 decimal place.
    """
    if len(data_points) < 2:
        slope = 0
    else:
        x = arange(len(data_points)) * int(constants.POLLING_INTERVAL / 60)
        y = array(data_points)
        # Calculate the slope of the best fit line
        slope, _ = polyfit(x, y, 1)
    slope_per_hour = slope * 60
    return round(slope_per_hour, 1)


@retry(max_attempts=6, delay=90, escalation=90, exception=(TwilioRestException))
def text_notify(is_daily: bool,
                first_line: str,
                sensor_id: int,
                sensor_name: str,
                lat: str,
                lon: str,
                text_list: list[str],
                local_time_stamp: datetime,
                local_pm25_aqi: float,
                pm_aqi_roc: float,
                local_pm25_aqi_avg: float,
                local_pm25_aqi_avg_duration: int,
                confidence: str,
                regional_aqi_mean: float) -> datetime:
    """
    Sends a text notification to a list of recipients with the current air quality information.

    Args:
    - is_daily (bool): Whether the notification is a daily summary or not.
    - first_line (str): The first line of the text message.
    - sensor_id (int): The ID of the sensor.
    - sensor_name (str): The name of the sensor.
    - text_list (list[str]): A list of phone numbers to send the text message to.
    - local_time_stamp (datetime): The local timestamp of the air quality reading.
    - local_pm25_aqi (float): The local PM2.5 AQI reading.
    - pm_aqi_roc (float): The rate of change of the PM2.5 AQI reading.
    - local_pm25_aqi_avg (float): The local average PM2.5 AQI reading.
    - local_pm25_aqi_avg_duration (int): The duration of the local average PM2.5 AQI reading.
    - confidence (str): The confidence level of the sensor reading.
    - regional_aqi_mean (float): The regional average PM2.5 AQI reading.

    Returns:
    - datetime: The UTC timestamp of the text notification.
    """
    rate_of_change_text = f'Change = {pm_aqi_roc:.1f} AQI /hr.'
    if confidence == 'LOW':
        confidence_text = '\n Sensor accuracy is low and may be inaccurate. \n \n'
    else:
        confidence_text = '\n'
    text_body = (
                f'{first_line}'
                f'AQ Notification \n'
                f'PA {sensor_id} - {sensor_name} \n'
                f'Time: {local_time_stamp.strftime("%Y-%m-%d %H:%M:%S")} \n \n'
                f'PM 2.5 Based Readings: \n'
                f' AQI: {local_pm25_aqi} \n'
                f' {rate_of_change_text} \n'
                f' {local_pm25_aqi_avg_duration:.0f} Min. Avg AQI: {local_pm25_aqi_avg:.0f} \n' 
                f'\u00A0Neighborhood \n'
                f'\u00A0\u00A0\u00A0Avg AQI: {regional_aqi_mean:.0f} \n'
                f' {confidence_text} '
                f'https://map.purpleair.com/1/i/mAQI/a0/p604800/cC5?select={sensor_id}#14.28/{lat}/{lon}'
    )
    message_sid_dict = {}
    for recipient in text_list:
        status_dict = {}
        message = twilio_client.messages.create(
            body=text_body,
            from_=config.get('twilio', 'TWILIO_PHONE_NUMBER').strip("'"),
            to=recipient
        )
        message_sid_dict[recipient] = message.sid
    sleep(5)
    for recipient, message_sid in message_sid_dict.items():
        updated_message = twilio_client.messages(message_sid).fetch()
        status = updated_message.status
        status_dict[recipient] = status
    for recipient, status in status_dict.items():
        time_zone = pytz.timezone(constants.REPORTING_TIME_ZONE)
        log_text = f'{datetime.datetime.now(time_zone).strftime("%Y-%m-%d %H:%M:%S")}: {recipient} - {status}'
        with open(os.path.join(os.getcwd(), '1_text_status_log.txt'), 'a') as f:
            f.write(log_text + '\n')
    utc_now = datetime.datetime.utcnow()
    if is_daily:
        write_timestamp(utc_now, 'daily_text')
    else:
        write_timestamp(utc_now, 'text')
    return utc_now.replace(tzinfo=pytz.utc)


@retry(max_attempts=6, delay=90, escalation=90, exception=(Exception, ezgmail.EZGmailException, ezgmail.EZGmailTypeError, ezgmail.EZGmailValueError))
def email_notify(
    is_daily: bool,
    first_line: str,
    email_list: list[str],
    local_time_stamp: datetime,
    sensor_id: str,
    sensor_name: str,
    lat: str,
    lon: str,
    local_pm25_aqi: float,
    local_pm25_aqi_avg: float,
    local_pm25_aqi_avg_duration: int,
    confidence: str,
    pm_aqi_roc: float,
    regional_aqi_mean: float) -> datetime:
    """
    Sends an email notification with air quality information for a PurpleAir sensor.

    Args:
        is_daily (bool): Whether the email is a daily summary or not.
        first_line (str): The first line of the email body.
        email_list (list[str]): A list of email addresses to send the notification to.
        local_time_stamp (datetime): The local timestamp of the air quality reading.
        sensor_id (str): The ID of the PurpleAir sensor.
        sensor_name (str): The name of the PurpleAir sensor.
        local_pm25_aqi (float): The PM 2.5 AQI reading for the sensor.
        local_pm25_aqi_avg (float): The PM 2.5 AQI reading for the sensor averaged over a certain duration.
        local_pm25_aqi_avg_duration (int): The duration over which the PM 2.5 AQI reading is averaged.
        confidence (str): The confidence level of the sensor reading.
        pm_aqi_roc (float): The rate of change of the PM 2.5 AQI reading since the previous reading.
        regional_aqi_mean (float): The regional average PM 2.5 AQI reading.

    Returns:
        datetime: The UTC timestamp of when the email was sent.
    """
    attachment_list = []
    if is_daily:
        attachment_list.append('pa_notify_alert_error_log.txt')
        attachment_list.append('1_text_status_log.txt')
        attachment_list.append('1_email_status_log.txt')
        subject = f'Daily {constants.SUBJECT}'
    else:
        subject = constants.SUBJECT
    if round(pm_aqi_roc, 1) < 0:
        rate_of_change_text = f'Air quality has improved by {abs(pm_aqi_roc):.1f} AQI per hour over the last {local_pm25_aqi_avg_duration:.0f} minutes'
    elif round(pm_aqi_roc, 1) > 0:
        rate_of_change_text = f'Air quality has worsened by {abs(pm_aqi_roc):.1f} AQI per hour over the last {local_pm25_aqi_avg_duration:.0f} minutes'
    else:
        rate_of_change_text = f'Air quality has not changed in the last {local_pm25_aqi_avg_duration:.0f} minutes'
    if confidence == 'LOW':
        confidence_text = 'Sensor accuracy is low, the sensor may need cleaning. Please obtain accurate data through official sources. <br>'
    else:
        confidence_text = ''
    email_body = (
                f'{first_line}'
                f'{constants.EMAIL_BODY_INTRO} <br>'
                f'Air quality for PurpleAir Sensor "{sensor_id} - {sensor_name}" information as of {local_time_stamp.strftime("%Y-%m-%d %H:%M:%S")} <br> <br>'
                f'PM 2.5 AQI: {local_pm25_aqi} <br>'
                f'PM 2.5 AQI {local_pm25_aqi_avg_duration:.0f} minute average: {local_pm25_aqi_avg:.0f} <br>'
                f'{rate_of_change_text} <br>'
                f'{confidence_text}'
                f'Neighborhood average PM 2.5 AQI: {regional_aqi_mean:.0f} <br>'
                f'<a href="https://map.purpleair.com/1/i/mAQI/a0/p604800/cC5?select={sensor_id}#14.28/{lat}/{lon}">PurpleAir Map</a> <br> <br>'
                f'{constants.EMAIL_DISCLAIMER_PT1} <br> <br>'
                f'{constants.EMAIL_DISCLAIMER_PT2} <br> <br>'
                f'{constants.EMAIL_DISCLAIMER_PT3}'
    )
    for recipient in email_list:
        ezgmail.send(recipient, subject, email_body, attachment_list, mimeSubtype='html')
        time_zone = pytz.timezone(constants.REPORTING_TIME_ZONE)
        log_text = f'{datetime.datetime.now(time_zone).strftime("%Y-%m-%d %H:%M:%S")}: {recipient} - Sent'
        with open(os.path.join(os.getcwd(), '1_email_status_log.txt'), 'a') as f:
            f.write(log_text + '\n')
    utc_now = datetime.datetime.utcnow()
    if is_daily:
        write_timestamp(utc_now, 'daily_email')
    else:
        write_timestamp(utc_now, 'email')
    return utc_now.replace(tzinfo=pytz.utc)


def polling_criteria_met(polling_et: int) -> bool:
    """
    Determines if the polling criteria has been met based on the current time and the polling interval.

    Args:
        polling_et (int): The elapsed time since the last poll.

    Returns:
        bool: True if the polling criteria has been met, False otherwise.
    """
    # Check if the day of the week is a weekday
    if datetime.datetime.today().weekday() > constants.MAX_DAY_OF_WEEK:
        return False

    POLLING_START_TIME = constants.POLLING_START_TIME
    POLLING_END_TIME = constants.POLLING_END_TIME

    # Adjust time values for PST
    if not is_pdt():
        polling_start_time = datetime.datetime.strptime(POLLING_START_TIME, '%H:%M:%S')
        polling_start_time -= datetime.timedelta(hours=1)
        POLLING_START_TIME = polling_start_time.strftime('%H:%M:%S')

        polling_end_time = datetime.datetime.strptime(POLLING_END_TIME, '%H:%M:%S')
        polling_end_time -= datetime.timedelta(hours=1)
        POLLING_END_TIME = polling_end_time.strftime('%H:%M:%S')

    return polling_et >= constants.POLLING_INTERVAL, \
        datetime.datetime.utcnow().strftime('%H:%M:%S') >= POLLING_START_TIME and \
        datetime.datetime.utcnow().strftime('%H:%M:%S') <= POLLING_END_TIME


def notification_criteria_met(local_pm25_aqi: float,
                              regional_aqi_mean: float,
                              num_data_points: int,
                              max_data_points: int) -> bool:
    """
    Determines if the notification criteria are met based on the local PM2.5 AQI and number of data points collected.

    Args:
        local_pm25_aqi (float): The local PM2.5 AQI.
        regional_aqi_mean (float): The local PM2.5 AQI.
        num_data_points (int): The number of data points.

    Returns:
        bool: True if the notification criteria are met, False otherwise.
    """
    if datetime.datetime.today().weekday() > constants.MAX_DAY_OF_WEEK:
        return False

    PRE_OPEN_ALERT_START_TIME = constants.PRE_OPEN_ALERT_START_TIME
    PRE_OPEN_ALERT_END_TIME = constants.PRE_OPEN_ALERT_END_TIME
    OPEN_ALERT_START_TIME = constants.OPEN_ALERT_START_TIME
    OPEN_ALERT_END_TIME = constants.OPEN_ALERT_END_TIME

    # Adjust time values for PST if needed
    if not is_pdt():
        pre_open_alert_start_time = datetime.datetime.strptime(PRE_OPEN_ALERT_START_TIME, '%H:%M:%S')
        pre_open_alert_start_time -= datetime.timedelta(hours=1)
        PRE_OPEN_ALERT_START_TIME = pre_open_alert_start_time.strftime('%H:%M:%S')

        pre_open_alert_end_time = datetime.datetime.strptime(PRE_OPEN_ALERT_END_TIME, '%H:%M:%S')
        pre_open_alert_end_time -= datetime.timedelta(hours=1)
        PRE_OPEN_ALERT_END_TIME = pre_open_alert_end_time.strftime('%H:%M:%S')

        open_alert_start_time = datetime.datetime.strptime(OPEN_ALERT_START_TIME, '%H:%M:%S')
        open_alert_start_time -= datetime.timedelta(hours=1)
        OPEN_ALERT_START_TIME = open_alert_start_time.strftime('%H:%M:%S')

        open_alert_end_time = datetime.datetime.strptime(OPEN_ALERT_END_TIME, '%H:%M:%S')
        open_alert_end_time -= datetime.timedelta(hours=1)
        OPEN_ALERT_END_TIME = open_alert_end_time.strftime('%H:%M:%S')

    pre_open_notification_criteria = (
        datetime.datetime.utcnow().strftime('%H:%M:%S') >= PRE_OPEN_ALERT_START_TIME and \
        datetime.datetime.utcnow().strftime('%H:%M:%S') <= PRE_OPEN_ALERT_END_TIME and \
        (local_pm25_aqi >= constants.OPEN_AQI_ALERT_THRESHOLD  or regional_aqi_mean >= constants.PRE_OPEN_AQI_ALERT_THRESHOLD))

    open_notification_criteria = (
        datetime.datetime.utcnow().strftime('%H:%M:%S') >= OPEN_ALERT_START_TIME and \
        datetime.datetime.utcnow().strftime('%H:%M:%S') <= OPEN_ALERT_END_TIME and \
        (local_pm25_aqi >= constants.OPEN_AQI_ALERT_THRESHOLD  or regional_aqi_mean >= constants.OPEN_AQI_ALERT_THRESHOLD))
    return (pre_open_notification_criteria or open_notification_criteria) and num_data_points >= max_data_points 


def daily_text_notification_criteria_met(daily_text_notification: datetime, num_data_points: int) -> bool:
    """
    Determines if the daily text notification criteria has been met based on the current time and day of the week.

    Args:
        daily_text_notification (datetime.datetime): The last time a text notification was sent.

    Returns:
        bool: True if the criteria has been met, False otherwise.
    """
    if constants.DAILY_TEXT_NOTIFICATION:
        # Adjust time values for PST if needed
        if not is_pdt():
            daily_text_notification += datetime.timedelta(hours=1)
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        text_criteria = utc_now - daily_text_notification >= datetime.timedelta(hours=14) and \
            datetime.datetime.utcnow().strftime('%H:%M:%S') >= (datetime.datetime.strptime(constants.PRE_OPEN_ALERT_START_TIME, '%H:%M:%S') - datetime.timedelta(seconds=30)).strftime('%H:%M:%S')
        if datetime.datetime.today().weekday() <= constants.MAX_DAY_OF_WEEK:
            text_criteria = text_criteria and num_data_points >= 16
    else:
        text_criteria = False
    return text_criteria


def daily_email_notification_criteria_met(daily_email_notification: datetime, num_data_points: int) -> bool:
    """
    Determines if the daily email notification criteria has been met based on the current time and day of the week.

    Args:
        daily_email_notification (datetime.datetime): The last time an email notification was sent.

    Returns:
        bool: True if the criteria has been met, False otherwise.
    """
    if constants.DAILY_EMAIL_NOTIFICATION:
        # Adjust time values for PST if needed
        if not is_pdt():
            daily_email_notification += datetime.timedelta(hours=1)
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        email_criteria = utc_now - daily_email_notification >= datetime.timedelta(hours=14) and \
            datetime.datetime.utcnow().strftime('%H:%M:%S') >= (datetime.datetime.strptime(constants.PRE_OPEN_ALERT_START_TIME, '%H:%M:%S') - datetime.timedelta(seconds=30)).strftime('%H:%M:%S')
        if datetime.datetime.today().weekday() <= constants.MAX_DAY_OF_WEEK:
            email_criteria = email_criteria and num_data_points >= 16
    else:
        email_criteria = False
    return email_criteria


def com_lists() -> tuple:
    """
    Returns the the email and text lists from the config file.

    Args:
        None

    Returns:
        email_list (list): A list of email addresses.
        text_list (list): A list of phone numbers.
        admin_text_list (list): A list of phone numbers.
        admin_email_list (list): A list of email addresses.
    """
    admin_text_list = []
    admin_text_items = config.items('admin_text_numbers')
    admin_email_list = []
    admin_email_items = config.items('admin_email_addresses')
    for key, path in admin_text_items:
        admin_text_list.append(path)
    for key, path in admin_email_items:
        admin_email_list.append(path)
    if not constants.TEST_MODE:
        email_list = []
        email_items = config.items('email_addresses')
        for key, path in email_items:
            email_list.append(path)
        text_list = []
        text_items = config.items('text_numbers')
        for key, path in text_items:
            text_list.append(path)
    else:
        email_list = []
        email_items = config.items('admin_email_addresses')
        for key, path in email_items:
            email_list.append(path)
        text_list = []
        text_items = config.items('admin_text_numbers')
        for key, path in text_items:
            text_list.append(path)
    return email_list, text_list, admin_text_list, admin_email_list


def check_logs() -> None:
    """
    Check the status of log files and create them if they don't exist.

    Args:
        None

    Returns:
        None
    """
    # List of file names
    file_names = ['1_text_status_log.txt',
                  '1_email_status_log.txt',
                  'pa_notify_alert_error_log.txt',
                  'pa_notify_alert_urllib3_log.txt'
                  ]

    # Check each file
    for file_name in file_names:
        if not os.path.isfile(file_name):
            # If file does not exist, create it
            with open(file_name, 'w') as f:
                pass


def initialize() -> tuple:
    """
    Initializes the necessary variables for the PurpleAir notification alert system.

    Returns:
    tuple: A tuple containing the following variables:
        - bbox (list): A list of bounding box coordinates.
        - email_list (list): A list of email addresses to send notifications to.
        - text_list (list): A list of phone numbers to send text notifications to.
        - admin_text_list (list): A list of phone numbers to send administrative text notifications to.
        - admin_email_list (list): A list of email addresses to send administrative notifications to.
        - status_start (datetime): The start time of the system status.
        - polling_start (datetime): The start time of the polling.
        - sensor_id (str): The ID of the PurpleAir sensor.
        - sensor_name (str): The name of the PurpleAir sensor.
        - lat (str): The latitude of the PurpleAir sensor.
        - lon (str): The longitude of the PurpleAir sensor.
        - local_pm25_aqi (float): The local PM2.5 AQI.
        - local_pm25_aqi_avg (float): The local PM2.5 AQI average.
        - confidence (str): The confidence level of the PurpleAir sensor.
        - local_time_stamp (datetime): The local timestamp.
        - pm_aqi_roc (float): The rate of change of the PM2.5 AQI.
        - regional_aqi_mean (float): The regional AQI mean.
        - local_pm25_aqi_list (list): A list of local PM2.5 AQI values.
        - max_data_points (int): The maximum number of data points to store.
        - last_text_notification (datetime): The timestamp of the last text notification.
        - last_email_notification (datetime): The timestamp of the last email notification.
        - last_daily_text_notification (datetime): The timestamp of the last daily text notification.
        - last_daily_email_notification (datetime): The timestamp of the last daily email notification.
    """
    check_logs()
    bbox: list[float] = [] 
    bbox_items: dict[str,float] = config.items('bbox')
    for key, coord in bbox_items:
        bbox.append(coord)
    email_list, text_list, admin_text_list, admin_email_list = com_lists()
    status_start, polling_start =  datetime.datetime.now(), datetime.datetime.now()
    local_pm25_aqi_avg: float = 0
    local_pm25_aqi_avg_duration: int = 2
    pm_aqi_roc: float = 0
    regional_aqi_mean: float = 0
    local_pm25_aqi_list: list[float] = []
    max_data_points: int = ceil(constants.READINGS_STORAGE_DURATION / (constants.POLLING_INTERVAL/60)) + 1
    last_text_notification, last_email_notification, last_daily_text_notification, last_daily_email_notification = read_timestamp(constants.FILE_PATHS)
    sensor_name = config.get('purpleair', 'LOCAL_SENSOR_NAME').strip("'")
    lat = config.get('purpleair', 'LOCAL_SENSOR_LAT').strip("'")
    lon = config.get('purpleair', 'LOCAL_SENSOR_LON').strip("'")
    sensor_id, local_pm25_aqi, confidence, local_time_stamp = get_local_pa_data(config.get('purpleair', 'LOCAL_SENSOR_INDEX'))
    return (bbox, email_list, text_list, admin_text_list, admin_email_list, status_start, polling_start, 
        sensor_id, sensor_name, lat, lon, local_pm25_aqi, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, local_time_stamp, pm_aqi_roc, 
        regional_aqi_mean, local_pm25_aqi_list, max_data_points, last_text_notification, 
        last_email_notification, last_daily_text_notification, last_daily_email_notification)


def main() -> None:
    bbox, email_list, text_list, admin_text_list, admin_email_list, status_start, polling_start, sensor_id, sensor_name, lat, lon, local_pm25_aqi, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, local_time_stamp, pm_aqi_roc, regional_aqi_mean, local_pm25_aqi_list, max_data_points, last_text_notification, last_email_notification, last_daily_text_notification, last_daily_email_notification = initialize()
    while True:
        try:
            sleep(.1)
            polling_et, status_et, text_notification_et, email_notification_et = elapsed_time(polling_start, status_start, last_text_notification, last_email_notification)
            if status_et >= constants.STATUS_INTERVAL:
                status_start = status_update(sensor_name, polling_et, text_notification_et, email_notification_et, local_time_stamp, local_pm25_aqi, local_pm25_aqi_avg, confidence, pm_aqi_roc, regional_aqi_mean, max_data_points, local_pm25_aqi_list)
            if polling_criteria_met(polling_et) == (True, True):
                sensor_id, local_pm25_aqi, confidence, local_time_stamp = get_local_pa_data(config.get('purpleair', 'LOCAL_SENSOR_INDEX'))
                if local_pm25_aqi != 'ERROR':
                    local_pm25_aqi_list.append(local_pm25_aqi)
                    # Keep only the last max_data_points data points
                    local_pm25_aqi_list = local_pm25_aqi_list[-max_data_points:]
                    pm_aqi_roc = aqi_rate_of_change(local_pm25_aqi_list)
                    local_pm25_aqi_avg = sum(local_pm25_aqi_list) / len(local_pm25_aqi_list)
                    local_pm25_aqi_avg_duration = (len(local_pm25_aqi_list) -1) * (constants.POLLING_INTERVAL/60)
                regional_aqi_mean = get_regional_pa_data(bbox, local_pm25_aqi)
                polling_start: datetime = datetime.datetime.now()
                if notification_criteria_met(local_pm25_aqi, regional_aqi_mean, len(local_pm25_aqi_list), max_data_points):
                    if len(text_list) > 0 and text_notification_et >= constants.NOTIFICATION_INTERVAL:
                        last_text_notification = text_notify(False, '', sensor_id, sensor_name, lat, lon, text_list, local_time_stamp, local_pm25_aqi, pm_aqi_roc, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, regional_aqi_mean)
                    if len(email_list) > 0 and email_notification_et >= constants.NOTIFICATION_INTERVAL:
                        last_email_notification = email_notify(False, '', email_list, local_time_stamp, sensor_id, sensor_name, lat, lon, local_pm25_aqi, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, pm_aqi_roc, regional_aqi_mean)
            elif polling_criteria_met(polling_et) == (True, False):
                local_pm25_aqi_list = []
            if daily_text_notification_criteria_met(last_daily_text_notification, len(local_pm25_aqi_list)):
                if len(admin_text_list) > 0:
                    last_daily_text_notification = text_notify(True, 'Daily Notification \n', sensor_id, sensor_name, lat, lon, admin_text_list, local_time_stamp, local_pm25_aqi, pm_aqi_roc, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, regional_aqi_mean)
            if daily_email_notification_criteria_met(last_daily_email_notification, len(local_pm25_aqi_list)):
                if len(email_list) > 0:
                    last_daily_email_notification = email_notify(True, 'Daily Notification <br>', admin_email_list, local_time_stamp, sensor_id, sensor_name, lat, lon, local_pm25_aqi, local_pm25_aqi_avg, local_pm25_aqi_avg_duration, confidence, pm_aqi_roc, regional_aqi_mean)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()