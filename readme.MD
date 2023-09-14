# A collection of Python programs for logging and processing PurpleAir sensor data.
  
# pa_log_data.py
 
## Python program to periodically log PurpleAir sensor data to Google Sheets from the PurpleAir API for sensors within a defined rectangular area.

### Notes:
 
- There are two files you need to edit before running the program: config.ini and constants.py.
- Rename config_template.ini to config.ini.
- Edit config.ini with your API keys and credentials
- Edit constants.py document names, file paths and preferences.
- Edit constants.py BBOX_DICT with your region abbreviations and coordinates. 
- bbox finder is handy for getting rectangular coordinates: http://bboxfinder.com/#0.000000,0.000000,0.000000,0.000000 
- Name the Google Sheets worksheet document with the name you provided for DOCUMENT_NAME in constants.py 
- Manually create empty Google Sheets sheets with names corresponding to regions.
  - For example, for the BBOX_DICT below:
    - BBOX_DICT = {
        'DT': (('-118.5298', '35.7180', '-118.4166', '35.8188'), 'DT', 'Delta Transit'),  
        'QC': (('-118.455864', '35.855306', '-118.185326', '35.018518'), 'Qual College'),  
        'YB': (('-118.877808', '35.650065', '-118.628899', '35.776579'), 'YB', 'Yucatan Borrego'),  
        'CP': (('-118.807770', '35.901766', '-118.550964', '35.079394'), 'CP', 'Cirrus Park')  
        }
    - You would manually create Google sheets with the following names:
        - DT
        - QC
        - YB
        - CP
        - DT Proc
        - QC Proc
        - YB Proc
        - CP Proc
        - Health
        - Regional
        - Current
 
    - The two character sheets will contain raw logged data and the sheets with a "Proc" suffix will contain processed data for each corresponding region.

- Setup an application and API keys for Google Sheets. https://developers.google.com/workspace/guides/create-credentials 
- Read the gspread documentation for authentication instructions. https://docs.gspread.org/en/v5.7.2/oauth2.html 
- PurpleAir API keys may be obtained from PurpleAir. https://community.purpleair.com/t/creating-api-keys/3951 
- Sensor data are gathered for a "local" region and other regions as defined in constants.py.
- Sensor Confidence is calculated as the percentage of data discarded after cleaning with EPA criteria and may not match displayed PurpleAir Confidence percentages.
- requirements.txt is included for installing the required non-standard Python libraries (i.e., pip: -r requirements.txt)
- To prevent the Google Sheets document from becoming too large you should periodically archive data to another worksheet and delete data from the master document.
- You can use the Google Sheets worksheet as source data for a Google Looker Studio dashboard. https://lookerstudio.google.com/ 
  
  
 
# sheet_size_reduce.py  

## Python program to trim the earliest rows from a specified Google Sheets sheet.  

### Notes:  

- Edit the code to change defaults in the argparse section.
- For performance reasons I typically only keep three to four weeks of data in my raw logged data sheets.
- This program automates deleting old data.
  
  
# pa_get_history.py
  
## Python program to get PurpleAir historical sensor data and save to Google Sheets, CSV, Excel or all three.
  
### Notes:
  
- Default Sensor names are stored in the sensors_current dictionary in cofig.py  
  
    
# gsheets_to_xl.py  
  
## Python program to download Google Sheets data to Excel.  
  
### Notes:  
  
- Consolidates data from all sheets in a Google Sheets document into a single Excel workbook.  
  

# gsheets_mgmt.py  
  
## Python program to manage Google Sheets documents.  
  
### Notes:  
  
- Google Sheets spreadsheets created by gsheets are owned by the Google Service Account.
- As such they are not manageable from the Google Sheets Web UI.
- This program lists all Google Sheets documents prefixed with "pa_history" that are owned by or shared with the Google Service Account and optionally deletes the documents owned by the Google Service Account.
- I typically "Make a copy" from the Google Sheets Web UI and share it with the Google Sheets Account before deleting the original from the Google Service Account.
  
  
# xl_merge.py  
    
## Python program to merge Excel files.  
  
### Notes:  
  
- This program merges all Excel files in a directory into a single Excel workbook.
- The program assumes the file structure begins with the path defined in constants.py followed by a folder in yyyy-mm format.
- Files to be excluded are hard coded in exclude_list.
  

# aqmd_get_data.py  
    
## Python program to scrape pollution data from the SCAQMD AQ Details - HistoricalData website for a given month and year.
  
### Notes:  
  
- The station to get data from is named in constants.py.