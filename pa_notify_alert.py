#!/usr/bin/env python3
# Regularly Polls Purpleair api for outdoor sensor data and sends email notofications when air quality exceeds threshold.
# James S. Lucas - 20230913

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

# Read config file
config = ConfigParser()
config.read('config.ini')

# Gets or creates a logger
logger = logging.getLogger(__name__)  
# set log level
logger.setLevel(logging.WARNING)
# define file handler and set formatter
file_handler = logging.FileHandler('pa_log_data_error.log')
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


def retry(max_attempts=3, delay=2, escalation=10, exception=(Exception,)):
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


def status_update(local_et, regional_et, process_et):
    """
    A function that calculates the time remaining for each interval and prints it in a table format.

    Args:
        local_et (int): The elapsed time for the local interval in seconds.
        regional_et (int): The elapsed time for the regional interval in seconds.
        process_et (int): The elapsed time for the process interval in seconds.

    Returns:
        A datetime object representing the current time.
    """
    local_minutes = int((constants.LOCAL_INTERVAL_DURATION - local_et) / 60)
    local_seconds = int((constants.LOCAL_INTERVAL_DURATION - local_et) % 60)
    regional_minutes = int((constants.REGIONAL_INTERVAL_DURATION - regional_et) / 60)
    regional_seconds = int((constants.REGIONAL_INTERVAL_DURATION - regional_et) % 60)
    process_minutes = int((constants.PROCESS_INTERVAL_DURATION - process_et) / 60)
    process_seconds = int((constants.PROCESS_INTERVAL_DURATION - process_et) % 60)
    table_data = [
        ['Local:', f"{local_minutes:02d}:{local_seconds:02d}"],
        ['Regional:', f"{regional_minutes:02d}:{regional_seconds:02d}"],
        ['Process:', f"{process_minutes:02d}:{process_seconds:02d}"]
    ]
    print(tabulate(table_data, headers=['Interval', 'Time Remaining (MM:SS)'], tablefmt='orgtbl'))
    print("\033c", end="")
    return datetime.now()


def elapsed_time(local_start, regional_start, process_start, status_start):
    """
    Calculates the elapsed time for each interval since the start time.

    Args:
        local_start (datetime): The start time for the local interval.
        regional_start (datetime): The start time for the regional interval.
        process_start (datetime): The start time for the process interval.
        status_start (datetime): The start time for the status interval.

    Returns:
        A tuple containing the elapsed time for each interval in seconds.
    """
    local_et: int = (datetime.now() - local_start).total_seconds()
    regional_et: int = (datetime.now() - regional_start).total_seconds()
    process_et: int = (datetime.now() - process_start).total_seconds()
    status_et: int = (datetime.now() - status_start).total_seconds()
    return local_et, regional_et, process_et, status_et


def get_pa_data(previous_time, bbox: List[float]) -> pd.DataFrame:
    """
    A function that queries the PurpleAir API for sensor data within a given bounding box and time frame.

    Args:
        previous_time (datetime): A datetime object representing the time of the last query.
        bbox (List[float]): A list of four floats representing the bounding box of the area of interest.
            The order is [northwest longitude, southeast latitude, southeast longitude, northwest latitude].

    Returns:
        A pandas DataFrame containing sensor data for the specified area and time frame. The DataFrame will contain columns
        for the timestamp of the data, the index of the sensor, and various sensor measurements such as temperature,
        humidity, and PM2.5 readings.
    """
    et_since = int((datetime.now() - previous_time + timedelta(seconds=20)).total_seconds())
    root_url: str = 'https://api.purpleair.com/v1/sensors/?fields={fields}&max_age={et}&location_type=0&nwlng={nwlng}&nwlat={nwlat}&selng={selng}&selat={selat}'
    params = {
        'fields': "name,latitude,longitude,altitude,rssi,uptime,humidity,temperature,pressure,voc,"
                "pm1.0_atm_a,pm1.0_atm_b,pm2.5_atm_a,pm2.5_atm_b,pm10.0_atm_a,pm10.0_atm_b,"
                "pm1.0_cf_1_a,pm1.0_cf_1_b,pm2.5_cf_1_a,pm2.5_cf_1_b,pm10.0_cf_1_a,pm10.0_cf_1_b,"
                "0.3_um_count,0.5_um_count,1.0_um_count,2.5_um_count,5.0_um_count,10.0_um_count",
        'nwlng': bbox[0],
        'selat': bbox[1],
        'selng': bbox[2],
        'nwlat': bbox[3],
        'et': et_since
    }
    url: str = root_url.format(**params)
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
        # convert the lat and lon values to strings
        df['latitude'] = df['latitude'].astype(str)
        df['longitude'] = df['longitude'].astype(str)
        df = df[cols]
    else:
        df = pd.DataFrame()
        logger.exception('get_pa_data() response not ok')
    return df


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

def notify():
    #
    pass
    

def current_process(df):
    """
    This function takes a pandas DataFrame as input, performs some processing on it and saves it as a Google Sheet.
    The sheet will contain only the most recent data from each sensor
    
    Args:
        df (pandas.DataFrame): The DataFrame to be processed.
        
    Returns:
        df (pandas.DataFrame): The processed DataFrame.
    
    Notes:
        - This function modifies the input DataFrame in place.
        - The following columns are added to the DataFrame:
            - Ipm25 (AQI)
            - pm25_epa
            - time_stamp_pacific
        - Data is cleaned according to EPA criteria.
    """
    df['Ipm25'] = df.apply(
        lambda x: AQI.calculate(x['pm2.5_atm_a'], x['pm2.5_atm_b']),
        axis=1
        )
    df['pm25_epa'] = df.apply(
                lambda x: EPA.calculate(x['humidity'], x['pm2.5_cf_1_a'], x['pm2.5_cf_1_b']),
                axis=1
                )
    df['time_stamp'] = pd.to_datetime(
        df['time_stamp'],
        format='%m/%d/%Y %H:%M:%S'
    )
    df['time_stamp_pacific'] = df['time_stamp'].dt.tz_localize('UTC').dt.tz_convert('US/Pacific')
    df['time_stamp'] = df['time_stamp'].dt.strftime('%m/%d/%Y %H:%M:%S')
    df['time_stamp_pacific'] = df['time_stamp_pacific'].dt.strftime('%m/%d/%Y %H:%M:%S')
    df = clean_data(df)
    df = format_data(df)
    return df


def process_data(DOCUMENT_NAME, client):
    """
    Process data from Google Sheets sheets for each region. Data is cleaned, summarized and various values are calculated. Data are saved to
    different worksheets in the same Google Sheets document.

    Args:
        DOCUMENT_NAME (str): The name of the Google Sheets document to be processed.
        client: The Google Sheets client object.

    Returns:
        A cleaned and summarized pandas DataFrame with the following columns:
        'time_stamp', 'sensor_index', 'name', 'latitude', 'longitude', 'altitude', 'rssi',
        'uptime', 'humidity', 'temperature', 'pressure', 'voc', 'pm1.0_atm_a',
        'pm1.0_atm_b', 'pm2.5_atm_a', 'pm2.5_atm_b', 'pm10.0_atm_a', 'pm10.0_atm_b',
        'pm1.0_cf_1_a', 'pm1.0_cf_1_b', 'pm2.5_cf_1_a', 'pm2.5_cf_1_b', 'pm10.0_cf_1_a',
        'pm10.0_cf_1_b', '0.3_um_count', '0.5_um_count', '1.0_um_count', '2.5_um_count',
        '5.0_um_count', '10.0_um_count', 'pm25_epa', 'Ipm25'.
    """
    write_mode: str = 'update'
    for k, v in constants.BBOX_DICT.items():
        # open the Google Sheets input worksheet and read in the data
        in_worksheet_name: str = k
        out_worksheet_name: str = k + ' Proc'
        df = get_gsheet_data(client, DOCUMENT_NAME, in_worksheet_name)
        if constants.LOCAL_REGION == k:
            # Save the dataframe for later use by the regional_stats() and sensor_health() functions
            df_local = df.copy()
        df['Ipm25'] = df.apply(
            lambda x: AQI.calculate(x['pm2.5_atm_a'], x['pm2.5_atm_b']),
            axis=1
            )
        df['pm25_epa'] = df.apply(
                    lambda x: EPA.calculate(x['humidity'], x['pm2.5_cf_1_a'], x['pm2.5_cf_1_b']),
                    axis=1
                    )
        df['time_stamp'] = pd.to_datetime(
            df['time_stamp'],
            format='%m/%d/%Y %H:%M:%S'
            )
        df = df.set_index('time_stamp')
        df[constants.cols_6] = df[constants.cols_6].replace('', 0)
        df[constants.cols_6] = df[constants.cols_6].astype(float)
        df_summarized = df.groupby('name').resample(constants.PROCESS_RESAMPLE_RULE).mean(numeric_only=True)
        df_summarized = df_summarized.reset_index()
        df_summarized['time_stamp_pacific'] = df_summarized['time_stamp'].dt.tz_localize('UTC').dt.tz_convert('US/Pacific')
        df_summarized['time_stamp'] = df_summarized['time_stamp'].dt.strftime('%m/%d/%Y %H:%M:%S')
        df_summarized['time_stamp_pacific'] = df_summarized['time_stamp_pacific'].dt.strftime('%m/%d/%Y %H:%M:%S')
        df_summarized['pm2.5_atm_a'] = pd.to_numeric(df_summarized['pm2.5_atm_a'], errors='coerce').astype(float)
        df_summarized['pm2.5_atm_b'] = pd.to_numeric(df_summarized['pm2.5_atm_b'], errors='coerce').astype(float)
        df_summarized = df_summarized.dropna(subset=['pm2.5_atm_a', 'pm2.5_atm_b'])
        df_summarized.replace('', 0, inplace=True)
        df_summarized = clean_data(df_summarized)
        df_summarized = format_data(df_summarized)
        write_data(df_summarized, client, DOCUMENT_NAME, out_worksheet_name, write_mode)
        sleep(90)
    return df_local


def regional_stats(client, DOCUMENT_NAME):
    """
    Retrieves air quality data from a Google Sheets document and calculates the mean and maximum values for each region.

    Args:
        client (object): A client object used to access a Google Sheets API.
        DOCUMENT_NAME (str): The name of the Google Sheets document to retrieve data from.

    Returns:
        None

    This function retrieves air quality data from a Google Sheets document for each region specified in the BBOX_DICT dictionary.
    It calculates the mean and maximum values for each region and writes the output to a specified worksheet in the same Google Sheets document.
    """
    write_mode: str = 'update'
    out_worksheet_regional_name: str = 'Regional'
    df_regional_stats = pd.DataFrame(columns=['Region', 'Mean', 'Max'])
    for k, v in constants.BBOX_DICT.items():
        worksheet_name = v[1] + ' Proc'
        df = get_gsheet_data(client, DOCUMENT_NAME, worksheet_name)
        if len(df) > 0:
            df['Ipm25'] = pd.to_numeric(df['Ipm25'], errors='coerce')
            df = df.dropna(subset=['Ipm25'])
            df['Ipm25'] = df['Ipm25'].astype(float)
            mean_value = df['Ipm25'].mean().round(2)
            max_value = df['Ipm25'].max().round(2)
            df_regional_stats.loc[len(df_regional_stats)] = [v[2], mean_value, max_value]
            df = pd.DataFrame()
            sleep(90)
        write_data(df_regional_stats, client, DOCUMENT_NAME, out_worksheet_regional_name, write_mode)


def main():
    five_min_ago: datetime = datetime.now() - timedelta(minutes=5)
    for k, v in constants.BBOX_DICT.items():
        df = get_pa_data(five_min_ago, constants.BBOX_DICT.get(k)[0])
        if len(df.index) > 0:
            write_mode = 'append'
            write_data(df, client, constants.DOCUMENT_NAME, constants.BBOX_DICT.get(k)[1], write_mode)
        else:
            pass
    local_start, regional_start, process_start, status_start = datetime.now(), datetime.now(), datetime.now(), datetime.now()
    while True:
        try:
            sleep(.1)
            local_et, regional_et, process_et, status_et = elapsed_time(local_start, regional_start, process_start, status_start)
            if status_et >= constants.STATUS_INTERVAL_DURATION:
                status_start = status_update(local_et, regional_et, process_et)
            if local_et >= constants.LOCAL_INTERVAL_DURATION:
                df_local = get_pa_data(local_start, constants.BBOX_DICT.get(constants.LOCAL_REGION)[0])
                if len (df_local.index) > 0:
                    write_mode: str = 'append'
                    write_data(df_local, client, constants.DOCUMENT_NAME, constants.LOCAL_WORKSHEET_NAME, write_mode)
                    sleep(10)
                    df_current = current_process(df_local)
                    write_mode: str = 'update'
                    write_data(df_current, client, constants.DOCUMENT_NAME, constants.CURRENT_WORKSHEET_NAME, write_mode)
                local_start: datetime = datetime.now()
            if regional_et > constants.REGIONAL_INTERVAL_DURATION:
                for regional_key in constants.REGIONAL_KEYS:
                    df = get_pa_data(regional_start, constants.BBOX_DICT.get(regional_key)[0]) 
                    if len(df.index) > 0:
                        write_mode: str = 'append'
                        write_data(df, client, constants.DOCUMENT_NAME, constants.BBOX_DICT.get(regional_key)[1], write_mode)
                    sleep(10)
                regional_start: datetime = datetime.now()
            if process_et > constants.PROCESS_INTERVAL_DURATION:
                df = process_data(constants.DOCUMENT_NAME, client)
                process_start: datetime = datetime.now()
                if len(df.index) > 0:
                    sensor_health(client, df, constants.DOCUMENT_NAME, constants.OUT_WORKSHEET_HEALTH_NAME)
                    regional_stats(client, constants.DOCUMENT_NAME)
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()