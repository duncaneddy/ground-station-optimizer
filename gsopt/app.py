
import os

# Optionally instrument the application with Iudex for monitoring
# See https://iudexai.com/ for more information
if os.getenv('IUDEX_API_KEY'):
    pass
    from iudex import instrument, start_trace, end_trace

    instrument(
        service_name = "GroundStationOptimizer",  # highly encouraged
        env = os.getenv('GSOPT_ENV', 'local'),  # dev, local, etc
        iudex_api_key = os.getenv('IUDEX_API_KEY'),  # only ever commit your WRITE ONLY key
        disable_print=True,
    )

    iudex_token = start_trace(name="GSOpt")

import shutil

from gsopt.utils import filter_warnings
from gsopt.widgets import *

# Filter warnings
filter_warnings()

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

st.markdown("### Earth Orientation Parameters (EOP) Data")

st.markdown("""
This application needs valid Earth Orientation Parameters (EOP) data to run. The EOP data is used to correctly transform
between different reference frames and time systems. The EOP data must be updated periodically from empirical data
sources. If the data is outdate and does not cover the time period of the optimization, you may need to update the
data by clicking the button below.
""")

# Initialize the EOP data since it normally isn't loaded until the first time it is used
# Check if an EOP file already exists and load it
utils.initialize_eop()


# The bh.EOP data object is the global EOP data object that is used globally in Brahe once loaded. We access the
# internal data object (_data) to get the keys (modified julian date), find the largest key, and then convert that
# key to a calendar date.
max_eop_caldate = bh.mjd_to_caldate(max(bh.EOP._data.keys()))

st_eop_max_date = st.empty()
st_eop_max_date.write(f"EOP Data Valid Through: {max_eop_caldate[0]}-{max_eop_caldate[1]:02d}-{max_eop_caldate[2]:02d}")

# Create a button when clicked that will update the EOP data
if st.button("Update EOP Data"):
    # Download the latest EOP data
    with st.spinner('Updating...'):
        bh.utils.download_iers_bulletin_ab()

    # Move the data to the correct location
    shutil.move("iau2000A_finals_ab.txt", "data/iau2000A_finals_ab.txt")

    # Reload the EOP data
    bh.EOP.load("data/iau2000A_finals_ab.txt")

    # Get the new max date
    max_eop_caldate = bh.mjd_to_caldate(max(bh.EOP._data.keys()))
    st_eop_max_date.write(
        f"EOP Data Valid Through: {max_eop_caldate[0]}-{max_eop_caldate[1]:02d}-{max_eop_caldate[2]:02d}")

# Define Ground Stations
station_selector()

# Define spacecraft
satellite_selector()

st.markdown('## Optimization')

"""
This section allows the user to define the optimization problem by selecting the constraints and objectives for the
problem as well as setting other parameters for the optimization.
"""

downlink_model_selector()

cost_model_selector()

opt_problem_creator_widget()

# Clean Up Iudex Logging
if os.getenv('IUDEX_API_KEY'):
    pass
    end_trace(iudex_token)