'''
Functions for managing ephemeris data
'''

import os
import logging
import datetime
import httpx

import streamlit as st
import polars as pl
import brahe as bh

from gsopt.utils import get_last_modified_time_as_datetime


logger = logging.getLogger()

def get_latest_celestrak_tles(output_dir='./data'):
    CELESTRAK_URL = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=ACTIVE&FORMAT=TLE'

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Extract filename from URL
    filename = os.path.join(output_dir, 'celestrak_tles.txt')

    # Use httpx to get the content from the URL
    response = httpx.get(CELESTRAK_URL, follow_redirects=True)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Open a file and write the content
        with open(filename, 'w') as fp:
            fp.write(response.text)
        logger.info(f"Saved latest TLE information to {filename}")
    else:
        logger.error(f"Failed to download TLE data from Celestrak. Status code: {response.status_code}")

def get_tles():

    # Check on time of last update
    last_update = get_last_modified_time_as_datetime('./data/celestrak_tles.txt')

    logger.info(f'Last TLE update: {last_update.isoformat()}')

    # If the file is older than 1 day, download the latest TLE data
    if (datetime.datetime.now() - last_update).days > 1:
        logger.info(f'TLE data is {(datetime.datetime.now() - last_update).days} days old. Updating...')
        get_latest_celestrak_tles()
    else:
        logger.info(f'TLE data is {(datetime.datetime.now() - last_update).days} days old. TLE data is up to date.')

    # Parse the TLE file and return the records
    return parse_tle_file('./data/celestrak_tles.txt')


@st.cache_resource(ttl=3600*12) # Expire cache every 12 hours
def get_satcat_df():
    # Load the TLE data
    tle_data = get_tles()

    # Create a DataFrame from the TLE data
    satcat_df = pl.DataFrame(tle_data, schema={
        'object_name': str,
        'satcat_id': str,
        'epoch': datetime.datetime,
        'semi_major_axis': float,
        'eccentricity': float,
        'inclination': float,
        'right_ascension': float,
        'arg_of_perigee': float,
        'mean_anomaly': float,
        'tle_line0': str,
        'tle_line1': str,
        'tle_line2': str
    })

    return satcat_df

def parse_tle_file(filepath):

    # Create an empty list to store parsed TLE records
    tle_records = []

    with open(filepath, 'r') as file:

        # Read all lines from the file
        lines = file.readlines()

        # Iterate over the lines in the file in groups of 3
        i = 0
        while i < len(lines):
            tle_line0 = lines[i].strip()
            tle_line1 = lines[i + 1].strip()
            tle_line2 = lines[i + 2].strip()

            # Get Information
            object_name = tle_line0.rstrip()

            # Extract TLE data
            tle = bh.TLE(tle_line1, tle_line2)

            satcat_id = tle_line1[2:7]
            tle_epoch = tle.epoch.to_datetime(tsys='UTC')
            semi_major_axis = tle.a
            eccentricity = tle.e
            inclination = tle.i
            right_ascension = tle.RAAN
            arg_of_perigee = tle.w
            mean_anomaly = tle.M

            # Append parsed information to the list
            tle_records.append({
                'object_name': object_name,
                'satcat_id': satcat_id,
                'epoch': tle_epoch,
                'semi_major_axis': semi_major_axis,
                'eccentricity': eccentricity,
                'inclination': inclination,
                'right_ascension': right_ascension,
                'arg_of_perigee': arg_of_perigee,
                'mean_anomaly': mean_anomaly,
                'tle_line0': tle_line0,
                'tle_line1': tle_line1,
                'tle_line2': tle_line2
            })

            # Move to the next 3-line record
            i += 3

    return tle_records