import os
import pathlib
import datetime
import json
import io

import brahe as bh
import polars as pl
import streamlit as st

import gsopt.plots as plots

ALL_FREQUENCIES = ['uhf', 'l', 's', 'x', 'ka']

CONSTELLATIONS = ['YAM', 'UMBRA', 'SKYSAT', 'ICEYE', 'FLOCK', 'HAWK', 'CAPELLA', 'LEGION', 'WORLDVIEW', 'GEOEYE', 'NUSAT']

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

def add_provider_selector(provider_name:str):

    # Create Markdown
    provider_enabled = st.checkbox(f'**{provider_name.capitalize()}**', value=True)

    # Load Station File
    geojson = json.load(open(pathlib.Path(f'./data/groundstations/{provider_name}.json'), 'r'))

    stations = []

    cols = st.columns(5)

    if 'features' not in geojson:
        st.error('GeoJSON file must contain a "features" key.')
    else:
        for idx, feature in enumerate(geojson['features']):

            # We'll do some optimistic parsing here because we control the schema
            try:
                station_name  = feature['properties']['station_name']
                provider_name = feature['properties']['provider_name']
                lon, lat = feature['geometry']['coordinates'][:2]
                alt = feature['geometry']['coordinates'][2] if len(feature['geometry']['coordinates']) > 2 else 0.0
                frequency_bands = feature['properties']['frequency_bands']
            except KeyError:
                st.error(f'Feature {idx} does not contain the required fields.')
                continue


            stations.append((
                cols[idx % 5].checkbox(f'{station_name.capitalize()}', key=f'checkbox_{provider_name}_{station_name}',
                                       value=freq_enabled(frequency_bands) and provider_enabled, disabled=not (freq_enabled(frequency_bands)) and provider_enabled),
                station_name,
                provider_name,
                lon,
                lat,
                alt
            ))

    return stations


def station_selector():
    st.markdown('## Ground Station Selection')

    st.markdown('''
    This section allows the user to select the ground stations providers and ground stations to consider in the 
    optimization problem. The user can also upload a GeoJSON file with ground station locations or define a custom
    ground station.
    ''')

    if 'stations_df' not in st.session_state:
        st.session_state['stations_df'] = pl.DataFrame({}, schema={
            'station_name': str,
            'provider_name': str,
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
    for provider in get_providers():
        station_buttons.extend(add_provider_selector(provider))

    if st.button('Add Stations'):
        for station in station_buttons:
            if station[0]:
                new_loc = pl.DataFrame({
                    'station_name': station[1],
                    'provider_name': station[2],
                    'longitude': station[3],
                    'latitude': station[4],
                    'altitude': station[5]
                })

                st.session_state['stations_df'] = pl.concat([st.session_state['stations_df'], new_loc]).unique()

    # Custom Ground Station

    st.markdown('### Add Station by Coordinates')

    st.markdown('This section allows you to define a custom ground station by providing the coordinates and metadata.'
                'The provider name is required to enable optimization of provider selection.')

    station_name = st.text_input('Station Name')
    provider_name = st.text_input('Provider Name')
    lon = st.number_input('Longitude (deg)', min_value=-180.0, max_value=180.0, value=0.0, format='%.3f')
    lat = st.number_input('Latitude (deg)', min_value=-90.0, max_value=90.0, value=0.0, format='%.3f')
    alt = st.number_input('Altitude (m)', value=0.0, format='%.3f')

    if st.button('Add Location'):
        if station_name == '':
            st.error('Please provide a name for the station')

        if provider_name == '':
            st.error('Please provide a provider name for the station')

        else:
            new_loc = pl.DataFrame({
                'station_name': station_name,
                'provider_name': provider_name,
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
                "station_name": "MyAwesomeStation",
                "provider_name": "MyAwesomeProvider"
              }
            }
          ]
        }
    """)

    station_name_property_field = st.text_input('Station Name Property Field', value='', help='The field in the GeoJSON file that contains the station name, if any')
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

                        if 'provider_name' in feature['properties']:
                            st.error(f'Feature {idx} does not contain a "provider_name" field.')

                        if 'properties' in feature and station_name_property_field in feature['properties']:
                            station_name = feature['properties'][station_name_property_field]
                        else:
                            station_name = f"GeoJSON Point ({lon:.3f}, {lat:.3f})"

                        alt = feature['geometry']['coordinates'][2] if len(feature['geometry']['coordinates']) > 2 else 0.0

                        new_loc = pl.DataFrame({
                            'station_name': station_name,
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
            'station_name': str,
            'provider_name': str,
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
        plot_ele = st.number_input('Minimum Elevation (deg)', min_value=0.0, max_value=90.0, value=10.0, step=0.1, format='%.3f')
    with st_plot_cols[1]:
        plot_alt = st.number_input('Plot Altitude (km)', min_value=200.0, value=500.0, format='%.3f')
    with st_plot_cols[2]:
        plot_opacity = st.slider('Plot Opacity', min_value=0.0, max_value=1.0, value=0.5, step=0.01)


    plot_stations = [(row['longitude'], row['latitude'], row['provider_name']) for row in
                     st.session_state['stations_df'].iter_rows(named=True)]
    gs_fig, gs_ax = plots.plot_stations(plot_stations, elevation_min=plot_ele, alt=plot_alt*1e3, opacity=plot_opacity)


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
    st.markdown('## Satellte Selection')

    if 'satellites_df' not in st.session_state:
        st.session_state['satellites_df'] = pl.DataFrame({}, schema={
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
                                                                              use_degrees=True) if st.session_state.sun_sync_orbit else 0.0,
                                                disabled=st.session_state.sun_sync_orbit,
                                                format='%.3f')
    right_ascension = sat_ele_cols[0].number_input('Right Ascension (deg)', min_value=0.0, max_value=360.0, format='%.3f')
    arg_of_perigee = sat_ele_cols[1].number_input('Argument of Perigee (deg)', min_value=0.0, max_value=360.0, format='%.3f')
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
        st_satellites.dataframe(st.session_state['satellites_df'].drop(['tle_line0', 'tle_line1', 'tle_line2']).to_pandas())
        satellites_count.markdown(
            f"**Number of Selected Satellites:** {st.session_state['satellites_df'].height}")