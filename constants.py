LOCAL_SENSOR = '7198'

LOCAL_REGION = 'MC'
#           SW lon / lat            NE lon / lat
#           nwlng, selat, selng, nwlat   
BBOX_DICT = {
    'MC': (('-122.557726', '37.896530', '-122.468719', '37.945280'), 'MC', 'Target Region')
    }

# Durations in seconds
STATUS_INTERVAL_DURATION: int = 42
LOCAL_INTERVAL_DURATION: int = 30
REGIONAL_INTERVAL_DURATION: int = 12500


RECIPIENT_LIST = ['wawzat@gmail.com', 'jslshop@att.net']
SUBJECT = 'pa.notify.alert - PurpleAir Sensor Air Quality Alert'
BODY_INTRO = 'Test from pa.notify.alert'
PA_MAP_LINK = '<a href="https://map.purpleair.com/1/mPM25/a10/p604800/cC0#11.64/33.7686/-117.4475">PurpleAir Map</a>'
DISCLAIMER_PT1 = 'The information provided in this message is for notification purposes only. ' \
            'Prior to making any decisions, please independently verify the information ' \
            'is accurate through official sources.'
DISCLAIMER_PT2 = 'PM 2.5 AQI is based on EPA conversion (more accurate for wood smoke). ' \
            ' PM 2.5 AQI 10 minute average is based on PurpleAir ATM conversion (more suited for mineral dust). '
DISCLAIMER_PT3 = 'AQI provided in this notification is based on PM 2.5 particulates only. ' \
            ' Other pollutants regulated by the Clean Air Act including ' \
            'ground-level ozone, carbon monoxide, sulfur dioxide, and nitrogen dioxide ' \
            'may also be present but are not included in this notification.'


cols_1 = ['time_stamp', 'time_stamp_pacific']
cols_2 = ['sensor_index', 'name', 'latitude', 'longitude']
cols_3 = ['altitude']
cols_4 = ['rssi']
cols_5 = ['uptime']
cols_6 = ['humidity', 'temperature', 'pressure', 'voc']
cols_7 = ['pm1.0_atm_a', 'pm1.0_atm_b', 'pm2.5_atm_a', 'pm2.5_atm_b', 'pm10.0_atm_a', 'pm10.0_atm_b',
          'pm1.0_cf_1_a', 'pm1.0_cf_1_b', 'pm2.5_cf_1_a', 'pm2.5_cf_1_b', 'pm10.0_cf_1_a', 'pm10.0_cf_1_b',
          '0.3_um_count', '0.5_um_count', '1.0_um_count', '2.5_um_count', '5.0_um_count', '10.0_um_count']
cols_8 = ['pm25_epa']
cols_9 = ['Ipm25']

cols = cols_1 + cols_2 + cols_3 + cols_4 + cols_5 + cols_6 + cols_7 + cols_8 + cols_9