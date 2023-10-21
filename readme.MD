# pa_notify_alert.py
## Python program for sending notifications about air quality as measured by PurpleAir sensors.
- Times and AQI thresholds are adjustable parameters stored in cnstants.py.
- Time ranges, durations and thresholds noted below are initital settings and are ajustable in constants.py
- Samples PA data for a "local" sensor and region with a default of every 2 minutes on weekdays from 4:50 AM to 4:00 PM PT
- Up to the last 30 minutes of local sensor data is stored and used to calculate the average over that period and the rate of change which is reported in the notification.
- Readings are converted with the US EPA conversion (more accurate for wood smoke, under estimates "normal dust").
- If the local sensor or regional average AQI is >= 125 between 5:30AM and 7:59:59 AM PT on a weekday a notification will be sent.  
- If the local sensor or regional average AQI is >= 140 between 8:00AM and 4:00 PM PT on a weekday a notification will be sent
- Notifications can be via text, email or both.
- Notifications are limited by the program to one per user per 8 hours during the notification window. 
- Text notification received status is logged 
- Sends a daily text notification on weekdays to a select list of software "administrators". This is to help monitor if the system is on-line and functioning.
- System corrects for standard and daylight savings time
 
 
### Notes:

- Edit config.ini with text and email contact info. PurpleAir, Twilio, Gmail API keys and regional bounding box.
- Information on obtaining API keys and setting up services for Twilio, Gmail and PurpleAir
    - Requires Twilio account for text messaging.   
        - [Twilio Programmable Messaging Quickstart - Python](https://www.twilio.com/docs/sms/quickstart/python)
    - Requires a Google developer Gmail app to be setup.   
        - [EZGmail Setup](https://pypi.org/project/EZGmail/)
        - EZGmail requires two JSON files in its program folder: "credentials.json" and "token.json."  
           - To obtain "credentials.json," follow the provided instructions.
           - For "token.json," also follow the instructions, but if you're running the program on a non-graphical or non-web browser-enabled server, run "get_gmail_credentials.py." It will display a URL in your terminal. Copy the URL to a machine with a web browser, authenticate with Google, and then transfer "token.json" to your server using FTP or another method.
    - Requires read key from PurpleAir.   
        - [Creating PurpleAir API Keys](https://community.purpleair.com/t/creating-api-keys/3951)