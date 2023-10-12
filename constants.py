TEST_MODE = False

#  0  |   1   |   2   |   3   |   4   |   5   |   6  |
# Mon |  Tue  |  Wed  |  Thu  |  Fri  |  Sat  |  Sun |
MAX_DAY_OF_WEEK = 4

REPORTING_TIME_ZONE = 'America/Los_Angeles'

# Durations in seconds
STATUS_INTERVAL: int = 30
POLLING_INTERVAL: int = 120
NOTIFICATION_INTERVAL: int = 28800     # 8 hours

# Duration in minutes
READINGS_STORAGE_DURATION: int = 30    # For ROC and Average calculations

# Times in UTC
POLLING_START_TIME = '11:50:00'        # 4:50 AM PDT
POLLING_END_TIME = '23:00:00'          # 4:00 PM PDT

PRE_OPEN_ALERT_START_TIME = '12:30:00' # 5:30 AM PDT
PRE_OPEN_ALERT_END_TIME = '14:59:59'   # 7:59:59 AM PDT

OPEN_ALERT_START_TIME = '15:00:00'     # 8:00 AM PDT
OPEN_ALERT_END_TIME = '23:00:00'       # 4:00 PM PDT

# Values in AQI
PRE_OPEN_AQI_ALERT_THRESHOLD = 125
OPEN_AQI_ALERT_THRESHOLD = 140

SUBJECT = 'pa.notify.alert - PurpleAir Sensor Air Quality Alert'
EMAIL_BODY_INTRO = 'High AQI Notification From pa.notify.alert'
PA_MAP_EMAIL_LINK = '<a href="https://map.purpleair.com/1/i/mAQI/a0/p604800/cC5?select=70745#14.28/38.01731/-122.55343">PurpleAir Map</a>'
EMAIL_DISCLAIMER_PT1 = 'The information provided in this message is for notification purposes only. ' \
            'Prior to making any decisions, please independently verify the information ' \
            'is accurate through official sources.'
EMAIL_DISCLAIMER_PT2 = 'PM 2.5 AQI and PM 2.5 Average AQI values are based on EPA conversion. ' \
            ' (more accurate for wood smoke, reads low for mineral dust). '
EMAIL_DISCLAIMER_PT3 = 'AQI provided in this notification is based on PM 2.5 particulates only. ' \
            ' Other pollutants regulated by the Clean Air Act including ' \
            'ground-level ozone, carbon monoxide, sulfur dioxide, and nitrogen dioxide ' \
            'may also be present but are not included in this notification.'

PA_MAP_TEXT_LINK = 'https://map.purpleair.com/1/i/mAQI/a0/p604800/cC5?select=70745#14.28/38.01731/-122.55343'

FILE_PATHS = {'last_text_notification.txt':'',
                'last_email_notification.txt':'',
                'last_daily_text_notification.txt':'',
                'last_daily_email_notification.txt':''}