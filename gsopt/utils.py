'''
General utilities and helper functions
'''

import os
import math
import time
import datetime
import warnings


import multiprocessing as mp

import brahe as bh
import brahe.data_models as bdm
from brahe.access.access import find_location_accesses

import streamlit as st
from stqdm import stqdm as stqdm

from gsopt.models import Satellite, GroundStation

APPLIED_FILTER_WARNINGS = False
def filter_warnings():
    global APPLIED_FILTER_WARNINGS

    if not APPLIED_FILTER_WARNINGS:
        warnings.filterwarnings("ignore", message="Approximating coordinate system")
        warnings.filterwarnings("ignore", message="streamlit run")
        warnings.filterwarnings("ignore", message="Session state does")
        warnings.filterwarnings("ignore", message="Warning: to view a Streamlit app")
        APPLIED_FILTER_WARNINGS = True

def get_last_modified_time(file_path):
    return os.path.getmtime(file_path)


def get_last_modified_time_as_datetime(file_path):
    return datetime.datetime.fromtimestamp(get_last_modified_time(file_path))


def create_station_objects(stations: list[GroundStation], elevation_min=0.0):
    gs = []
    for sta in stations:
        gs.append(bdm.Station(
            **{
                "properties": {
                    "constraints": bdm.AccessConstraints(elevation_min=elevation_min),
                    "station_name": sta.name,
                    "station_id": f"{sta.provider}_{sta.name}",
                },
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [sta.longitude, sta.latitude, sta.altitude]
                },
            }
        ))

    return gs

def create_spacecraft(satellites: list[Satellite]):
    spacecraft = []
    for sat in satellites:
        spacecraft.append(bdm.Spacecraft(
            id=int(sat.satcat_id),
            name=sat.name,
            line1=sat.tle_line1,
            line2=sat.tle_line2
        ))

    return spacecraft

# def compute_contacts(work):
#     (sc, loc, t_start, t_end) = work
#     return find_location_accesses(sc, loc, t_start, t_end)

def compute_contacts(sc: bdm.Spacecraft, loc: bdm.Station, t_start: bh.Epoch, t_end: bh.Epoch):
    return find_location_accesses(sc, loc, t_start, t_end)

def compute_all_contacts(satellites, stations, t_start, t_end, elevation_min, show_streamlit:bool=False):

    if show_streamlit:
        status = st.empty()

    ts = time.time()

    if show_streamlit:
        status.markdown("Preparing data....")

    # Convert statellites to spacecraft
    spacecraft = create_spacecraft(satellites)

    # Convert locations to stations
    stations = create_station_objects(stations, elevation_min)

    # Generate work
    tasks = []
    for station in stations:
        for sc in spacecraft:
            tasks.append((sc, station, t_start, t_end))

    status.write("Computing contacts...")

    contacts = []

    # Create a multiprocessing pool to compute contacts
    mpctx = mp.get_context('spawn')
    with mpctx.Pool(mp.cpu_count()) as pool:

        if show_streamlit:
            results = pool.starmap(compute_contacts, tasks)
        else:
            results = pool.starmap(compute_contacts, tasks)

        for r in results:
            contacts.extend(r)

    te = time.time()

    dt = te - ts
    if dt > 60:
        time_string = f"{math.floor(dt/60)} minutes and {dt%60:.2f} seconds"
    elif dt > 3600:
        time_string = f"{math.floor(dt/3600)} hours, {math.floor(dt/60)%60} minutes, and {dt%60:.2f} seconds"
    else:
        time_string = f"{dt:.2f} seconds"

    if show_streamlit:
        status.success(f"Contacts computed successfully. Found {len(contacts)} contacts. Took {time_string}.")

    return contacts


def contact_list_to_dataframe(contacts: list[bdm.Contact]):
    # Create a list of dictionaries to hold the contact data
    contact_dicts = []

    # Iterate over the contacts and extract the relevant data
    for contact in contacts:
        contact_dicts.append({
            "contact_id": contact.id,
            "location_id": contact.station_id,
            "location_name": contact.station_name,
            "satcat_id": contact.spacecraft_id,
            'longitude': contact.center[0],
            'latitude': contact.center[1],
            'altitude': contact.center[2] if len(contact.center) > 2 else 0.0,
            "t_start": contact.t_start,
            "t_end": contact.t_end,
            "t_duration": contact.t_duration,
            "elevation_max": contact.access_properties.elevation_max,
            "elevation_min": contact.access_properties.elevation_max,
            "azimuth_open": contact.access_properties.azimuth_open,
            "azimuth_close": contact.access_properties.azimuth_close,
        })

    # Convert the list of dictionaries to a Polars DataFrame
    return contact_dicts
