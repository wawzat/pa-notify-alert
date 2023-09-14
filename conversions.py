
"""
This module contains classes for converting air quality data from one unit to another. 

Classes:
- AQI: Converts PM2.5 concentration to Air Quality Index (AQI) value.
- EPA: Converts PM2.5 concentration and relative humidity to EPA concentration value.

Functions:
- None

Exceptions:
- None

Usage:
- Import the module and use the AQI and EPA classes to convert air quality data.

Dependencies:
- logging module
"""
import logging

class AQI:
    @staticmethod
    def calculate(PM, *args):
        # Calculate average of the arguments
        total = PM
        count = 1
        for arg in args:
            total += arg
            count += 1
        PM2_5 = total / count
        PM2_5 = max(int(PM2_5 * 10) / 10.0, 0)
        #AQI breakpoints (0,    1,     2,    3    )
        #                (Ilow, Ihigh, Clow, Chigh)
        pm25_aqi = (
                    [0, 50, 0, 12],
                    [51, 100, 12.1, 35.4],
                    [101, 150, 35.5, 55.4],
                    [151, 200, 55.5, 150.4],
                    [201, 300, 150.5, 250.4],
                    [301, 500, 250.5, 500.4],
                    [301, 500, 250.5, 500.4]
        )
        for values in pm25_aqi:
            Ilow, Ihigh, Clow, Chigh = values
            if Clow <= PM2_5 <= Chigh:
                Ipm25 = int(round(((Ihigh - Ilow) / (Chigh - Clow) * (PM2_5 - Clow) + Ilow)))
                return Ipm25

class EPA:
    @staticmethod
    def calculate(RH, PM, *args):
        # If either PM2_5 or RH is a string, the EPA conversion value will be set to 0.
        if any(isinstance(x, str) for x in (RH, PM)):
            PM = 0
            RH = 0
        if PM < 0:
            PM = 0
        if RH < 0:
            RH = 0
        # Calculate average of the arguments
        total = PM
        count = 1
        for arg in args:
            if arg < 0:
                arg = 0
            elif isinstance(arg, str):
                arg = 0
            else:
                total += arg
                count += 1
        PM2_5 = total / count
        try: 
            if PM2_5 <= 343:
                PM2_5_epa = round((0.52 * PM2_5 - 0.086 * RH + 5.75), 3)
            elif PM2_5 > 343:
                PM2_5_epa = round((0.46 * PM2_5 + 3.93 * 10 ** -4 * PM2_5 ** 2 + 2.97), 3)
            else:
                PM2_5_epa = 0
            return PM2_5_epa
        except Exception as e:
            logging.exception('calc_epa() error')

