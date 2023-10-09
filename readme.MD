# pa_notify_alert.py
## Python program for sending notifications about air quality as measured by PurpleAir sensors.
- Times and AQI thresholds are adjustable parameters stored in cnstants.py.
 
- Time ranges, durations and thresholds noted below are initital settings and are ajustable in constants.py

- Samples PA data for a "local" sensor and region with a default of every 2 minutes on weekdays from 4:50 AM to 4:00 PM PT
 
- Up to the last 30 minutes of local sensor data is stored and used to calculate the average over that period and the rate of change which is reported in the notification.
 
- Readings are converted with the US EPA conversion (more accurate for wood smoke, under estimates "normal dust").
 
- If the local sensor or regional average AQI is >= 125 between 5:30AM and 7:59:59 AM PT on a weekday a notification will be sent.  
- If the local sensor or regional average AQI is >= 140 between 8:00AM and 4:00 PM PT on a weekday a notificatin will be sent
 
- Notifications can be via text, email or both.

- Notifications are limited by the program to one per user per 8 hours during the notification window. 
 
- Text notification received status is logged 

- Sends a daily text notification on weekdays to a select list of software "administrators". This is to help monitor if the system is on-line and functioning.
 
- System corrects for standard and daylight savings time
 
 
### Notes:

- Edit config.iti with text and email contact info, API keys and regional bounding box.
- Requires twilio account for text messaging. ---PLACEHOLDER FOR LINK---
- Requires a google developer Gmail app to be setup ---PLACEHOLDER FOR LINK---
- Requires read key from PurpleAir ---PLACEHOLDER FOR LINK---