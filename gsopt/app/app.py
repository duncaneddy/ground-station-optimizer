import streamlit as st
from gsopt.app.widgets import station_selector, satellite_selector

import gsopt.plots as plots

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

# Compute contact windows
# contacts = compute_contact_windows(stations, spacecraft)

# Define Constraints and Objective


# Show results