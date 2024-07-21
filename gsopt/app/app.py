import logging
import streamlit as st

from gsopt.models import ground_stations_from_dataframe, satellites_from_dataframe
from gsopt.optimizer import MilpGSOptimizer
from gsopt.plots import filter_cartopy_warnings
from gsopt.app.widgets import *

# Filter warnings
filter_cartopy_warnings()

# Enforce log-level and set log format to include timestamp
logging.basicConfig(
    datefmt='%Y-%m-%dT%H:%M:%S',
    format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
    level=logging.INFO
)

st.set_page_config(layout="wide")

st.markdown('''
# Ground Station Optimization

This application allows a user to optimize the selection of ground stations providers and locations for a given
satellite or set of satellites. The application walks the user through defining the stations to consider, the
spacecraft to consider, and the constraints and objectives of the optimization problem. The user can then run the
optimization and view the results.
''')

# Define Ground Stations
station_selector()

# Define spacecraft
spacecraft = satellite_selector()

# Create Problem
# problem = GSOpt(stations, spacecraft)

st.markdown('## Optimization')

"""
This section allows the user to define the optimization problem by selecting the constraints and objectives for the
problem as well as setting other parameters for the optimization.
"""

opt_problem_creator_widget()

# Show results