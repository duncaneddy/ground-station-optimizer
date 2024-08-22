'''
General utilities and helper functions
'''

import os
import math
import pathlib
import time
import datetime
import warnings

import polars as pl
import multiprocessing as mp

from typing import Dict, Any

import brahe as bh
import brahe.data_models as bdm
from brahe.access.access import find_location_accesses

import streamlit as st
from stqdm import stqdm as stqdm

from gsopt.models import Satellite, GroundStation, Contact

# Set up logging
# change asc time to
LOG_FORMAT_VERBOSE = '%(asctime)s.%(msecs)03d:%(levelname)8s [%(filename)20s:%(lineno)4d] %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'

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

def compute_contacts(station: GroundStation, satellite: Satellite, t_start: bh.Epoch, t_end: bh.Epoch):
    # Convert Spacecraft and Station objects to Brahe objects
    sc = satellite.as_brahe_model()
    loc = station.as_brahe_model()

    contacts = find_location_accesses(sc, loc, t_start, t_end)

    # Create contact object from Brahe Contact objects and return
    return [Contact(c, station, satellite) for c in contacts]

def get_time_string(t: float) -> str:
    """
    Convert a time in seconds to a human-readable string
    """

    if t < 60:
        return f"{t:.2f} seconds"
    elif t < 3600:
        return f"{math.floor(t / 60)} minutes and {t % 60:.2f} seconds"
    else:
        return f"{math.floor(t / 3600)} hours, {math.floor(t / 60) % 60} minutes, and {t % 60:.2f} seconds"

def initialize_eop():
    """
    Helper function to initialize the Earth Orientation Parameters (EOP) data for Brahe.
    Some functions in this application require the EOP data to be loaded, namely checking
    Returns:

    """
    if not bh.EOP._initialized:
        if pathlib.Path("data/iau2000A_finals_ab.txt").exists():
            bh.EOP.load("data/iau2000A_finals_ab.txt")
        else:
            bh.EOP._initialize()


def ground_stations_from_geojson(geojson: Dict[str, Any]) -> list[GroundStation]:
    """
    Create a list of GroundStation objects from a GeoJSON dictionary
    """
    stations = []
    for feature in geojson['features']:
        properties = feature['properties']
        geometry = feature['geometry']

        if geometry['type'] != 'Point':
            raise ValueError("Only Point geometries are supported")

        if 'provider' not in properties:
            raise ValueError("Missing 'provider' property")

        if 'name' not in properties:
            raise ValueError("Missing 'name' property")

        stations.append(GroundStation(
            name=properties['name'],
            provider=properties['provider'],
            longitude=geometry['coordinates'][0],
            latitude=geometry['coordinates'][1],
            altitude=geometry['coordinates'][2] if len(geometry['coordinates']) > 2 else 0.0
        ))

    return stations
