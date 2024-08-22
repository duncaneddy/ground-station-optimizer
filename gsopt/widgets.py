import os
import pathlib
import datetime
import json
import io
import logging

import brahe as bh
import polars as pl
import streamlit as st

from gsopt import utils
from gsopt.ephemeris import get_satcat_df
from gsopt.models import GroundStationNetwork, GroundStation, Satellite, Contact, OptimizationWindow
import gsopt.plots as plots

from gsopt.milp_optimizer import MilpOptimizer

logger = logging.getLogger()

# Constants of interest
ALL_FREQUENCIES = ['uhf', 'l', 's', 'x', 'ka']
CONSTELLATIONS = sorted(['YAM', 'UMBRA', 'SKYSAT', 'ICEYE', 'FLOCK', 'HAWK', 'CAPELLA', 'LEGION', 'WORLDVIEW', 'GEOEYE',
                  'NUSAT'])


# Get provider names as file names from ./data/groundstations
def get_providers():
    providers = []

    for file in os.listdir('./data/groundstations'):
        if file.endswith('.json'):
            providers.append(file.replace('.json', ''))

    return providers


def freq_enabled(freq_list: list[str]):
    # Get list of required frequencies
    required_freq = set(freq for freq in ALL_FREQUENCIES if st.session_state[f'{freq.lower()}_enabled'])

    # Check that the required frequencies are a subset of the frequencies supported by the station
    return required_freq <= set([f.lower() for f in freq_list])


def add_provider_selector(provider: str):
    # Create Markdown
    provider_enabled = st.checkbox(f'**{provider.capitalize()}**', value=True)

    # Load Station File
    geojson = json.load(open(pathlib.Path(f'./data/groundstations/{provider}.json'), 'r'))

    stations = []

    cols = st.columns(5)

    if 'features' not in geojson:
        st.error('GeoJSON file must contain a "features" key.')
    else:
        for idx, feature in enumerate(geojson['features']):

            # We'll do some optimistic parsing here because we control the schema
            try:
                name = feature['properties']['name']
                provider = feature['properties']['provider']
                lon, lat = feature['geometry']['coordinates'][:2]
                alt = feature['geometry']['coordinates'][2] if len(feature['geometry']['coordinates']) > 2 else 0.0
                frequency_bands = feature['properties']['frequency_bands']
            except KeyError:
                st.error(f'Feature {idx} does not contain the required fields.')
                continue

            stations.append((
                cols[idx % 5].checkbox(f'{name.capitalize()}', key=f'checkbox_{provider}_{name}',
                                       value=freq_enabled(frequency_bands) and provider_enabled,
                                       disabled=not (freq_enabled(frequency_bands)) and provider_enabled),
                name,
                provider,
                lon,
                lat,
                alt
            ))

    return stations


def contact_list_to_dataframe(contacts: list[Contact]):
    # Create a list of  dictionaries to hold the contact data
    contact_dicts = []

    # Iterate over the contacts and extract the relevant data
    for contact in contacts:
        contact_dicts.append({
            "id": contact.id,
            "location_id": contact.station_id,
            "location_name": contact.name,
            "satellite_id": contact.satellite_id,
            "sattellite_name": contact.satellite_name,
            'longitude': contact.lon,
            'latitude': contact.lat,
            'altitude': contact.alt,
            "t_start": contact.t_start.to_datetime(),
            "t_end": contact.t_end.to_datetime(),
            "t_duration": contact.t_duration,
        })

    # Convert the list of dictionaries to a Polars DataFrame
    return contact_dicts


def ground_stations_from_dataframe(df: pl.DataFrame) -> list[GroundStation]:
    """
    Create a list of GroundStation objects from a Polars DataFrame
    """
    stations = []
    for sta in df.iter_rows(named=True):
        stations.append(GroundStation(
            name=sta['name'],
            provider=sta['provider'],
            longitude=sta['longitude'],
            latitude=sta['latitude'],
            altitude=sta['altitude']
        ))

    return stations

def satellites_from_dataframe(df: pl.DataFrame) -> list[Satellite]:
    """
    Create a list of Satellite objects from a Polars DataFrame
    """
    satellites = []
    for idx, sat in enumerate(df.iter_rows(named=True)):
        satellites.append(Satellite(
            id=idx,
            satcat_id=sat['satcat_id'],
            name=sat['object_name'],
            tle_line1=sat['tle_line1'],
            tle_line2=sat['tle_line2']
        ))

    return satellites


def station_selector():
    st.markdown('## Ground Station Selection')

    st.markdown('''
    This section allows the user to select the ground stations providers and ground stations to consider in the 
    optimization problem. The user can also upload a GeoJSON file with ground station locations or define a custom
    ground station.
    ''')

    if 'stations_df' not in st.session_state:
        st.session_state['stations_df'] = pl.DataFrame({}, schema={
            'name': str,
            'provider': str,
            'longitude': float,
            'latitude': float,
            'altitude': float,
        })

    # Predefined providers

    st.markdown('### Add Stations by Provider')

    st.markdown('This section allows you to select ground stations from predefined providers. The providers are defined'
                'based on current major station providers.')

    st.markdown('**Frequency Bands**')

    st.markdown('Required frequency bands. Enable the checkbox to only consider stations that support the given '
                'frequency bands. If no boxes are checked all stations will be considered (if enabled).')

    freq_columns = st.columns(5)

    st.session_state['uhf_enabled'] = freq_columns[0].checkbox('UHF', value=False)
    st.session_state['l_enabled'] = freq_columns[1].checkbox('L', value=False)
    st.session_state['s_enabled'] = freq_columns[2].checkbox('S', value=False)
    st.session_state['x_enabled'] = freq_columns[3].checkbox('X', value=False)
    st.session_state['ka_enabled'] = freq_columns[4].checkbox('Ka', value=False)

    station_buttons = []
    for provider in sorted(get_providers()):
        station_buttons.extend(add_provider_selector(provider))

    if st.button('Add Stations'):
        for station in station_buttons:
            if station[0]:
                new_loc = pl.DataFrame({
                    'name': station[1],
                    'provider': station[2],
                    'longitude': station[3],
                    'latitude': station[4],
                    'altitude': station[5]
                })

                st.session_state['stations_df'] = pl.concat([st.session_state['stations_df'], new_loc]).unique()

    # Custom Ground Station

    st.markdown('### Add Station by Coordinates')

    st.markdown('This section allows you to define a custom ground station by providing the coordinates and metadata.'
                'The provider name is required to enable optimization of provider selection.')

    name = st.text_input('Station Name')
    provider = st.text_input('Provider Name')
    lon = st.number_input('Longitude (deg)', min_value=-180.0, max_value=180.0, value=0.0, format='%.3f')
    lat = st.number_input('Latitude (deg)', min_value=-90.0, max_value=90.0, value=0.0, format='%.3f')
    alt = st.number_input('Altitude (m)', value=0.0, format='%.3f')

    if st.button('Add Location'):
        if name == '':
            st.error('Please provide a name for the station')

        if provider == '':
            st.error('Please provide a provider name for the station')

        else:
            new_loc = pl.DataFrame({
                'name': name,
                'provider': provider,
                'longitude': lon,
                'latitude': lat,
                'altitude': alt
            })

            st.session_state['stations_df'] = pl.concat([st.session_state['stations_df'], new_loc]).unique()

    # Add button to load locations from GeoJSON
    st.markdown('### Add Stations from GeoJSON')

    st.markdown('Here you can upload a GeoJSON file to define a set of ground stations. The GeoJSON file must adhere to'
                'a predefined schema. An example schema is provided below:')
    with st.expander("GeoJSON Schema"):
        st.code("""
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {
                "type": "Point",
                "coordinates": [
                  -0.3, # Longitude [deg]
                  5.6,  # Latitude [deg]
                  0.0   # Altitude [m], Optional
                ]
              },
              "properties": {
                "name": "MyAwesomeStation",
                "provider": "MyAwesomeProvider"
              }
            }
          ]
        }
    """)

    st_geojson_cols = st.columns(2)

    with st_geojson_cols[0]:
        name_property_field = st.text_input('Station Name Property Field', value='',
                                                    help='The field in the GeoJSON file that contains the station name, if any')

    with st_geojson_cols[1]:
        provider_property_field = st.text_input('Provider Name Property Field', value='',
                                                     help='The field in the GeoJSON file that container the provider name, if any')
    geojson_file = st.file_uploader('Upload GeoJSON File', accept_multiple_files=False)

    if st.button('Add Locations from GeoJSON FeatureCollection'):
        if geojson_file is None:
            st.error('Please upload a GeoJSON file.')
        else:
            geojson = json.load(geojson_file)
            if 'features' not in geojson:
                st.error('GeoJSON file must contain a "features" key.')
            else:
                for idx, feature in enumerate(geojson['features']):
                    if 'geometry' in feature and 'coordinates' in feature['geometry']:
                        lon, lat = feature['geometry']['coordinates'][:2]

                        if 'properties' not in feature:
                            st.error(f'Feature {idx} does not contain a "properties" field.')
                            break

                        if 'provider' in feature['properties']:
                            st.error(f'Feature {idx} does not contain a "provider" field.')

                        if 'properties' in feature and name_property_field in feature['properties']:
                            name = feature['properties'][name_property_field]
                        else:
                            name = f"GeoJSON Point ({lon:.3f}, {lat:.3f})"

                        if 'properties' in feature and provider_property_field in feature['properties']:
                            provider = feature['properties'][provider_property_field]
                        else:
                            provider = f"GeoJSON File"

                        alt = feature['geometry']['coordinates'][2] if len(
                            feature['geometry']['coordinates']) > 2 else 0.0

                        new_loc = pl.DataFrame({
                            'name': name,
                            'provider': provider,
                            'longitude': float(lon),
                            'latitude': float(lat),
                            'altitude': float(alt)
                        })

                        st.session_state['stations_df'] = pl.concat([st.session_state['stations_df'], new_loc]).unique()

    # Show all selected locations
    st.markdown('### Selected Stations')

    selected_loc_count = st.empty()
    selected_loc_count.markdown(f"**Number of Locations:** {st.session_state['stations_df'].height}")
    selected_locs = st.empty()
    selected_locs.dataframe(st.session_state['stations_df'].to_pandas())

    selected_loc_row = st.number_input('Selected location index', min_value=0)
    if st.button('Remove Selected Station'):
        if selected_loc_row >= st.session_state['stations_df'].height:
            st.error(f"Selected row {selected_loc_row} out of range.")

        # Remove selected location by adding a new index column
        st.session_state['stations_df'] = st.session_state['stations_df'].with_row_index().filter(
            ~pl.col("index").is_in([selected_loc_row]))

        # Drop the column so you can keep deleting rows
        st.session_state['stations_df'].drop_in_place("index")

        # Force a refresh of the selected locations dataframe - for some reason this doesn't happen automatically
        selected_locs.dataframe(st.session_state['stations_df'].to_pandas())
        selected_loc_count.markdown(f"**Number of Stations:** {st.session_state['stations_df'].height}")

    if st.button('Clear All Stations'):
        st.session_state['stations_df'] = pl.DataFrame({}, schema={
            'name': str,
            'provider': str,
            'longitude': float,
            'latitude': float,
            'altitude': float,
        })

        # Force a refresh of the selected locations dataframe - for some reason this doesn't happen automatically
        selected_locs.dataframe(st.session_state['stations_df'].to_pandas())
        selected_loc_count.markdown(f"**Number of Locations:** {st.session_state['stations_df'].height}")

    # Show Stations

    st_plot = st.empty()

    st_plot_cols = st.columns(4)
    with st_plot_cols[0]:
        plot_ele = st.number_input('Minimum Elevation (deg)', min_value=0.0, max_value=90.0, value=10.0, step=0.1,
                                   format='%.3f')
    with st_plot_cols[1]:
        plot_alt = st.number_input('Plot Altitude (km)', min_value=200.0, value=500.0, format='%.3f')
    with st_plot_cols[2]:
        plot_opacity = st.slider('Plot Opacity', min_value=0.0, max_value=1.0, value=0.5, step=0.01)

    plot_stations = [(row['longitude'], row['latitude'], row['provider']) for row in
                     st.session_state['stations_df'].iter_rows(named=True)]
    gs_fig, gs_ax = plots.plot_stations(plot_stations, elevation_min=plot_ele, alt=plot_alt * 1e3, opacity=plot_opacity)

    st_plot.pyplot(gs_fig)

    with st_plot_cols[3]:
        img = io.BytesIO()
        gs_fig.savefig(img, format='png')

        st.download_button(
            label="Download image",
            data=img,
            file_name='groundstations.png',
            mime="image/png"
        )


def satellite_selector():
    # Get current (or update) TLE data
    satcat_df = get_satcat_df()

    # Render Widget
    st.markdown('## Satellte Selection')

    if 'satellites_df' not in st.session_state:
        st.session_state['satellites_df'] = pl.DataFrame({}, schema={
            'object_name': str,
            'satcat_id': str,
            'epoch': datetime.datetime,
            'altitude': float,
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

    # Add satellites by elements

    st.markdown('### Add Satellte by Elements')

    sat_ele_cols = st.columns(2)

    object_name = sat_ele_cols[0].text_input('Object Name')
    satcat_id = sat_ele_cols[1].text_input('SATCAT ID')

    sat_date = sat_ele_cols[0].date_input('Ephemeris Epoch Day')
    sat_time = sat_ele_cols[1].time_input('Ephemeris Epoch Time (UTC)')

    # Add input fields for the TLE elements

    altitude = sat_ele_cols[0].number_input('Altitude (km)', min_value=200.0, value=500.0, format='%.3f')
    semi_major_axis = bh.R_EARTH + altitude * 1e3
    eccentricity = sat_ele_cols[1].number_input('Eccentricity', min_value=0.0, max_value=1.0, format='%.3f')

    sat_ele_cols[1].text('')  # Fake linebreak for formatting
    sat_sso = sat_ele_cols[1].checkbox('Sun-Synchronous Orbit', value=False, key="sun_sync_orbit")
    inclination = sat_ele_cols[0].number_input('Inclination (deg)', min_value=0.0, max_value=180.0,
                                               value=bh.sun_sync_inclination(semi_major_axis, eccentricity,
                                                                             use_degrees=True) if 'sun_sync_orbit' in st.session_state and st.session_state.sun_sync_orbit else 0.0,
                                               disabled=st.session_state.sun_sync_orbit if 'sun_sync_orbit' in st.session_state else False,
                                               format='%.3f')
    right_ascension = sat_ele_cols[0].number_input('Right Ascension (deg)', min_value=0.0, max_value=360.0,
                                                   format='%.3f')
    arg_of_perigee = sat_ele_cols[1].number_input('Argument of Perigee (deg)', min_value=0.0, max_value=360.0,
                                                  format='%.3f')
    mean_anomaly = sat_ele_cols[0].number_input('Mean Anomaly (deg)', min_value=0.0, max_value=360.0, format='%.3f')

    if st.button('Add Satellite', key='add_satellite_by_elements'):
        if satcat_id in st.session_state['satellites_df']['satcat_id']:
            st.error(f"Satellite with SATCAT ID {satcat_id} already selected.")

        elif object_name == '':
            st.error('Please provide a name for the satellite')
        elif satcat_id == '':
            st.error('Please provide a SATCAT ID for the satellite')
        elif len(satcat_id) != 5:
            st.error('SATCAT ID must be 5 digits long')

        else:
            tle_line1, tle_line2 = bh.tle_string_from_elements(
                bh.Epoch(sat_date.year, sat_date.month, sat_date.day, sat_time.hour, sat_time.minute, sat_time.second,
                         tsys='UTC'),
                [
                    bh.mean_motion(semi_major_axis, use_degrees=True) * 86400 / 360,
                    # Convert sma into mean motion rev/day
                    eccentricity, inclination, right_ascension, arg_of_perigee, mean_anomaly, 0.0, 0.0, 0.0],
                norad_id=int(satcat_id),
            )

            new_sat = pl.DataFrame({
                'object_name': object_name,
                'satcat_id': satcat_id,
                'epoch': datetime.datetime.now(),
                'altitude': (semi_major_axis - bh.R_EARTH)/1e3,
                'semi_major_axis': semi_major_axis,
                'eccentricity': eccentricity,
                'inclination': inclination,
                'right_ascension': right_ascension,
                'arg_of_perigee': arg_of_perigee,
                'mean_anomaly': mean_anomaly,
                'tle_line0': object_name,
                'tle_line1': tle_line1,
                'tle_line2': tle_line2
            })

            st.session_state['satellites_df'] = pl.concat([st.session_state['satellites_df'], new_sat]).unique()

    st.markdown('### Add Satellites by Constellation')
    constellations = st.multiselect('**Select Constellations:**', CONSTELLATIONS)

    if st.button('Add Constellations'):
        # Filter constellation data by name and add to existing data
        con_sats = satcat_df.filter(pl.col('object_name').str.contains_any(constellations))
        logger.info(f'Found {con_sats.height} satellites in constellations {constellations}')
        st.session_state['satellites_df'] = pl.concat([st.session_state['satellites_df'], con_sats]).unique()

    st.markdown('### Add Satellite by NORAD ID')

    # Get the min and max SATCAT ID numbers from the full TLE datafarme
    min_satcat_id = satcat_df['satcat_id'].min()
    max_satcat_id = satcat_df['satcat_id'].max()

    # SATCAT ID number input
    satcat_id = st.text_input(f'**SATCAT ID - Min: {min_satcat_id}, Max: {max_satcat_id}**')

    if satcat_id != None:
        pass
        satcat_df = satcat_df.filter(pl.col('satcat_id') == satcat_id)

        if satcat_df.height > 0:
            record = satcat_df.row(0, named=True)

            satcat_col1, satcat_col2 = st.columns(2)
            with satcat_col1:
                st.markdown(f"**Object Name:** {record['object_name']}")
                st.markdown(f"**Semi-Major Axis:** {record['semi_major_axis'] / 1e3:.3f} km")
                st.markdown(f"**Eccentricity:** {record['eccentricity']:.3f}")
                st.markdown(f"**Right Ascension:** {record['right_ascension']:.3f} deg")
                st.markdown(f"**Mean Anomaly:** {record['mean_anomaly']:.3f} deg")
            with satcat_col2:
                st.markdown(f"**TLE Epoch:** {record['epoch']}")
                st.markdown(f"**Altitude:** {(record['semi_major_axis'] - bh.R_EARTH) / 1e3:.3f} km")
                st.markdown(f"**Inclination:** {record['inclination']:.3f} deg")
                st.markdown(f"**Argument of Perigee:** {record['arg_of_perigee']:.3f} deg")

    else:
        st.error(f"No satellite with SATCAT ID {satcat_id} found.")

    if st.button('Add Satellite', key='add_satellite_by_satcat_id'):
        st.session_state['satellites_df'] = pl.concat([st.session_state['satellites_df'], satcat_df]).unique()

    # Show all selected satellites
    st.markdown('### Selected Satellites')

    # Create the dataframe of selected satellites
    satellites_count = st.empty()
    satellites_count.markdown(
        f"**Number of Selected Satellites:** {st.session_state['satellites_df'].height}")
    st_satellites = st.empty()
    st_satellites.dataframe(st.session_state['satellites_df'].drop(['tle_line0', 'tle_line1', 'tle_line2']).to_pandas())

    selected_sat_row = st.number_input('Selected satellite index', min_value=0)
    if st.button('Remove Selected Satellite'):
        if selected_sat_row >= st.session_state['satellites_df'].height:
            st.error(f"Selected satellite row {selected_sat_row} out of range.")

        # Remove selected satellite by adding a new index column
        st.session_state['satellites_df'] = st.session_state['satellites_df'].with_row_index().filter(
            ~pl.col("index").is_in([selected_sat_row]))

        # Drop the column so you can keep deleting rows
        st.session_state['satellites_df'].drop_in_place("index")

        # Force a refresh of the selected satellites dataframe - for some reason this doesn't happen automatically
        st_satellites.dataframe(st.session_state['satellites_df'].to_pandas())
        satellites_count.markdown(
            f"**Number of Selected Satellites:** {st.session_state['satellites_df'].height}")

    if st.button('Clear All Selected Satellites'):
        st.session_state['satellites_df'] = pl.DataFrame({}, schema={
            'object_name': str,
            'satcat_id': str,
            'epoch': datetime.datetime,
            'altitude': float,
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

        # Force a refresh of the selected satellites dataframe - for some reason this doesn't happen automatically
        st_satellites.dataframe(
            st.session_state['satellites_df'].drop(['tle_line0', 'tle_line1', 'tle_line2']).to_pandas())
        satellites_count.markdown(
            f"**Number of Selected Satellites:** {st.session_state['satellites_df'].height}")


def provider_cost_selector(provider: str):
    st.session_state.provider_costs[provider] = {}

    st.markdown(f'**{provider.capitalize()}**')

    default_cost_cols = st.columns(5)
    st.session_state['default_setup_cost'] = default_cost_cols[0].number_input('Default First Time Use Cost ($)', min_value=0.0, value=50000.0, format='%.2f', key=f'{provider}_setup_cost')
    st.session_state['default_per_satellite_license_cost'] = default_cost_cols[1].number_input('Default Per Satellite License Cost ($)', min_value=0.0, value=5000.0, format='%.2f', key=f'{provider}_per_satellite_license_cost')
    st.session_state['default_monthly_cost'] = default_cost_cols[2].number_input('Default Monthly ($)',
                                                                                  min_value=0.0, value=0.0,
                                                                                  format='%.2f',
                                                                                  key=f'{provider}_monthly_cost')
    st.session_state['default_cost_per_pass'] = default_cost_cols[2].number_input('Default Cost per Pass ($)', min_value=0.0, value=0.0, format='%.2f', key=f'{provider}_cost_per_pass')
    st.session_state['default_cost_per_minute'] = default_cost_cols[3].number_input('Default Cost per Minute ($)', min_value=0.0, value=0.0, format='%.2f', key=f'{provider}_cost_per_minute')

    st.session_state.provider_costs[provider]['integration_cost'] = st.number_input(
        f'{provider.capitalize()} Integration Cost ($)', min_value=0.0, value=st.session_state.default_integration_cost, format='%.2f', key=f'{provider}_integration_cost')

    with st.expander(f'{provider.capitalize()} Ground Station Costs'):
        cols = st.columns(5)

        for station in st.session_state['stations_df'].filter(pl.col('provider') == provider)['name'].to_list():
            st.session_state.provider_costs[provider][station] = {}

            st.session_state.provider_costs[provider][station]['setup_cost'] = cols[0].number_input(
                f'{station.capitalize()} Setup Cost ($)', min_value=0.0, value=st.session_state.default_setup_cost, format='%.2f', key=f'{provider}_{station}_setup_cost')
            st.session_state.provider_costs[provider][station]['per_satellite_license_cost'] = cols[1].number_input(
                f'{station.capitalize()} Per Satellite License Cost ($)', min_value=0.0, value=st.session_state.default_per_satellite_license_cost, format='%.2f', key=f'{provider}_{station}_per_satellite_license_cost')
            st.session_state.provider_costs[provider][station]['monthly_cost'] = cols[1].number_input(
                f'{station.capitalize()} Per Satellite License Cost ($)', min_value=0.0,
                value=st.session_state.default_monthly_cost, format='%.2f',
                key=f'{provider}_{station}_montly_cost')
            st.session_state.provider_costs[provider][station]['cost_per_pass'] = cols[3].number_input(
                f'{station.capitalize()} Cost per Pass ($)', min_value=0.0, value=st.session_state.default_cost_per_pass, format='%.2f', key=f'{provider}_{station}_cost_per_pass')
            st.session_state.provider_costs[provider][station]['cost_per_minute'] = cols[4].number_input(
                f'{station.capitalize()} Cost per Minute ($)', min_value=0.0, value=st.session_state.default_cost_per_minute, format='%.2f', key=f'{provider}_{station}_cost_per_minute')

def cost_model_selector():
    """
    Create widget to allow the user to define the cost model for the ground station optimization problem.
    """

    st.markdown('### Cost Model')
    st.markdown("""
    This section allows the user to define the costs associated with the use of different ground stations and providers.
    These costs are the primary drivers of the selection of ground stations and providers. There are multiple potential
    costs associated with the use of a ground station. These include:
      - **Integration Cost**: The cost for the operator to integrate the ground station into their network. This is typically a one-time cost. It can conver both engineering time to integrate the station into the network, as well as any hardware or software costs.
      - **Setup Cost**: The cost to setup a ground station for first use. This can include costs for setting up the station for use, such as provisioning operator-specific hardware at the station.
      - **Per Satellite License Cost**: The the one-time cost of any regulatory, licensing, or legal fees associated with using the station for a specific satellite.
      - **Monthly Cost**: The monthly fix cost of using the station. This cost is charged regardless of the number of passes or the duration of the passes. It is typically driven by monthly backhaul (internet) costs, power costs, or other fixed costs.
      - **Cost per Pass**: The cost of using the station for a single pass of a satellite. This is charged each time the station is used to communicate with a satellite, it is independent of the duration of the pass.
      - **Cost per Minute**: The cost of using the station for a single minute of communication with a satellite. This is charged based on the duration of the pass.
      
    Note a provider will typically charge either a cost per pass or a cost per minute, but not both.
    """)

    st.markdown('#### Cost Definition')

    st.session_state['default_integration_cost'] = st.number_input('Default Integration Cost ($)', min_value=0.0, value=100000.0, format='%.2f')


    st.session_state['provider_costs'] = {}

    for provider in sorted(st.session_state['stations_df']['provider'].unique().to_list()):
        provider_cost_selector(provider)

def create_satellite_datarate_selector():

    st.markdown('This section allows the user to define the data rates for the satellites in the optimization problem.')

    datarate_unit = st.selectbox('Data Rate Unit', ['bps', 'kbps', 'Mbps', 'Gbps'], index=3)
    default_datarate = st.number_input(f'Default Data Rate {datarate_unit}', min_value=0.0, value=1.2, format='%.2f')

    cols = st.columns(5)

    st.session_state['satellite_datarates'] = {}

    for idx, sat in enumerate(st.session_state['satellites_df'].iter_rows(named=True)):
        st.session_state['satellite_datarates'][sat['satcat_id']] = cols[idx % 5].number_input(
            f'{sat["object_name"]} Data Rate ({datarate_unit})', min_value=0.0, value=default_datarate, format='%.3f')

def create_groundstation_datarate_selector(provider: str, datarate_unit: str):

    st.markdown('This section allows the user to define the data rates for the ground stations in the optimization problem.')

    st.markdown(f'**{provider.capitalize()}**')

    default_datarate = st.number_input(f'{provider.capitalize()} Default Data Rate ({datarate_unit})', min_value=0.0, value=2.0, format='%.2f', key=f'{provider}_default_datarate')

    st.session_state['groundstation_datarates'][provider] = {}

    with st.expander(f'{provider.capitalize()} Ground Station Data Rates'):
        cols = st.columns(5)

        for idx, station in enumerate(st.session_state['stations_df'].filter(pl.col('provider') == provider).iter_rows(named=True)):
            st.session_state['groundstation_datarates'][provider][station['name']] = cols[idx % 5].number_input(
                f'{station["name"]} Data Rate ({datarate_unit})', min_value=0.0, value=default_datarate, format='%.3f', key=f'{provider}_{station["name"]}_datarate')


def downlink_model_selector():
    """
    Create widget to allow the user to define the downlink model for the ground station optimization problem.

    This model defines the downlink capabilities of the ground stations and the satellites.
    """

    st.markdown('### Data Model')
    st.markdown("""
    This section allows the user to define the data downlink model for the ground station optimization problem.
    The downlink model defines the capabilities of the ground stations and the satellites to communicate with each other.
    This model determines the effective amount of data that can be downlinked from the satellite to the ground station
    over a given contact. This section allows the user to define the datarate for each ground station and satellite.
    The datarate for a given contact is the minimum of the datarates of the satellite and the ground station.
    """)

    st.markdown('#### Satellite Data Rates')

    create_satellite_datarate_selector()

    st.markdown('#### Ground Station Data Rates')

    st.session_state['groundstation_datarates'] = {}

    datarate_unit = st.selectbox('Data Rate Unit', ['bps', 'kbps', 'Mbps', 'Gbps'], index=3, key='groundstation_datarate_unit')

    for provider in sorted(st.session_state['stations_df']['provider'].unique().to_list()):
        create_groundstation_datarate_selector(provider, datarate_unit)


def optimization_window_selector():
    """
    Allows the user to select the optimization window for the ground station optimization problem.
    """

    st.markdown('### Optimization Window Selection')

    st.markdown("""
    Here we can define the _optimization window_ and the _simulation window_ for the ground station optimization problem.
    The _optimization window_ is the period over which the problem is solved. This is the horizon over which 
    the problem of location and provider selection is considered. In most cases this should match the expected mission
    duration. 
    
    The _simulation window_ is the period over which the simulation is run. This is the period over which the optimizer
    calculates potential ground contacts and determines the best ground station to use. This window should be less than
    or equal to the _optimization window_. Normally, due to orbit progation uncertainties (primarily driven by 
    the solar cycle and atmospheric drag), it is not possible to accurately predict the exact satellite contact times
    over the entire life of the mission. Therefore, we use a shorter simulation window to simulate contacts for a shorter
    period (typically 7 days), and use that number as an approximation of the expected number of contacts
    over the mission lifetime for different ground station locations and providers.
    """)


    # Optimization Window
    st.markdown('#### Optimization Window')
    opt_cols = st.columns(2)
    with opt_cols[0]:
        opt_start = st.date_input('Optimization Window Start Date', value=datetime.datetime.now())
    with opt_cols[1]:
        opt_end = st.date_input('Optimization Window End Date', value=datetime.datetime.now() + datetime.timedelta(days=365))

    # Simulation Window
    st.markdown('#### Simulation Window')
    sim_cols = st.columns(2)
    with sim_cols[0]:
        sim_start = st.date_input('Simulation Window Start Date')
    with sim_cols[1]:
        sim_duration = st.number_input('Simulation Window Duration (days)', min_value=1, value=7)

    if sim_duration > (opt_end - opt_start).days:
        st.error('Simulation window duration must be less than or equal to the optimization window duration.')

    # Create and store an OptimizationWindow object
    opt_window = OptimizationWindow(
        opt_start=datetime.datetime.fromisoformat(opt_start.isoformat()),
        opt_end=datetime.datetime.fromisoformat(opt_end.isoformat()),
        sim_start=datetime.datetime.fromisoformat(sim_start.isoformat()),
        sim_end=datetime.datetime.fromisoformat((sim_start + datetime.timedelta(days=sim_duration)).isoformat())
    )

    st.session_state['opt_window'] = opt_window



def opt_problem_creator_widget():
    optimization_window_selector()

    st.markdown('### Optimization Problem Creation')

    st.markdown("""
    This section allows the user to define the optimization
    """)

    opt_type = st.selectbox('Optimization Type', ['MILP'], index=0)

    if st.button('Create Optimization Problem'):
        # Create the MILP optimizer
        st.session_state['gsopt'] = MilpOptimizer(opt_window=st.session_state['opt_window'])

        # Convert the selected satellites to Satellite objects and add to problem
        satellites = satellites_from_dataframe(st.session_state['satellites_df'])

        for sat in satellites:
            # Set datarate for satellite from inputs
            sat.datarate = st.session_state['satellite_datarates'][sat.satcat_id]

            # Add the satellite to the optimizer
            st.session_state['gsopt'].add_satellite(sat)

        # Convert the selected Ground Stations to networks and stations

        # Add provider stations to the optimizer
        for provider in st.session_state['stations_df']['provider'].unique().to_list():
            provider_stations = st.session_state['stations_df'].filter(pl.col('provider') == provider)
            stations = ground_stations_from_dataframe(provider_stations)

            # Create a network for the provider
            network = GroundStationNetwork(stations)

            # Set the integration cost for the network
            network.integration_cost = st.session_state.provider_costs[provider]['integration_cost']

            # Set cost and datarate for each station
            for station in stations:
                station.datarate = st.session_state['groundstation_datarates'][provider][station.name]
                station.setup_cost = st.session_state.provider_costs[provider][station.name]['setup_cost']
                station.per_satellite_license_cost = st.session_state.provider_costs[provider][station.name]['per_satellite_license_cost']
                station.cost_per_pass = st.session_state.provider_costs[provider][station.name]['monthly_cost']
                station.cost_per_pass = st.session_state.provider_costs[provider][station.name]['cost_per_pass']
                station.cost_per_minute = st.session_state.provider_costs[provider][station.name]['cost_per_minute']

            # Add the network to the optimizer
            st.session_state.gsopt.add_network(network)

        st.markdown(f"""
        Created optimization problem with:
        - Optimization Window: {st.session_state.gsopt.opt_window.opt_start} to {st.session_state.gsopt.opt_window.opt_end}
        - Simulation Window: {st.session_state.gsopt.opt_window.sim_start} to {st.session_state.gsopt.opt_window.sim_end}
        - {len(st.session_state.gsopt.satellites)} satellites
        - {len(st.session_state.gsopt.networks)} ground station networks
        - {len(st.session_state.gsopt.stations)} ground stations
        """)


    # Compute contact windows
    elevation_min = st.number_input('Minimum Elevation (deg)', min_value=0.0, max_value=90.0, value=10.0, step=0.1,)

    if st.button('Compute Contact Windows'):
        if 'gsopt' not in st.session_state:
            st.error('Please create the optimization problem before computing contacts.')
        else:
            # st.session_state['gsopt'].set_access_constraints(elevation_min)
            st.session_state.gsopt.compute_contacts()

            # st.markdown(f'Number of Contacts: {len(st.session_state.gsopt.contacts)}')
            st.success(f"Found {len(st.session_state.gsopt.contacts)} contacts. Contact computation took {utils.get_time_string(st.session_state.gsopt.contact_compute_time)}.")

    # Define Constraints and Objective

    # Solve Optimization problem
    if st.button('Solve Optimization Problem'):
        if 'gsopt' not in st.session_state:
            st.error('Please create the optimization problem before solving.')
        else:
            st.session_state.gsopt.solve()

            st.success(f'Optimization problem solved in {st.session_state.gsopt.solve_time:.2f} seconds')


