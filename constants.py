TEST_MODE = False

REPORTING_TIME_ZONE = 'America/Los_Angeles'

# Durations in seconds
STATUS_INTERVAL: int = 1
POLLING_INTERVAL: int = 120
NOTIFICATION_INTERVAL: int = 28800

# Duration in minutes
READINGS_STORAGE_DURATION: int = 30

POLLING_START_TIME = '11:00:00'
POLLING_END_TIME = '23:30:00'

ALERT_START_TIME = '13:00:00'
ALERT_END_TIME = '23:00:00'

AQI_ALERT_THRESHOLD = 140

SUBJECT = 'pa.notify.alert - PurpleAir Sensor Air Quality Alert'
EMAIL_BODY_INTRO = 'High AQI Notification From pa.notify.alert'
PA_MAP_EMAIL_LINK = '<a href="https://map.purpleair.com/1/mPM25/a10/p604800/cC0#11.64/33.7686/-117.4475">PurpleAir Map</a>'
EMAIL_DISCLAIMER_PT1 = 'The information provided in this message is for notification purposes only. ' \
            'Prior to making any decisions, please independently verify the information ' \
            'is accurate through official sources.'
EMAIL_DISCLAIMER_PT2 = 'PM 2.5 AQI is based on EPA conversion (more accurate for wood smoke). ' \
            ' PM 2.5 AQI 10 minute average is based on PurpleAir ATM conversion (more suited for mineral dust). '
EMAIL_DISCLAIMER_PT3 = 'AQI provided in this notification is based on PM 2.5 particulates only. ' \
            ' Other pollutants regulated by the Clean Air Act including ' \
            'ground-level ozone, carbon monoxide, sulfur dioxide, and nitrogen dioxide ' \
            'may also be present but are not included in this notification.'

PA_MAP_TEXT_LINK = 'https://map.purpleair.com/1/i/mAQI/a0/p604800/cC0?select=70745#14.28/38.01731/-122.55343'