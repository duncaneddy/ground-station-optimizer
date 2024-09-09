"""
Functions to analyze contact opportunities and optimization outputs
"""

import json
import statistics
from dataclasses import dataclass
from itertools import groupby

from brahe import Epoch

from gsopt.models import GroundStationProvider, Satellite, Contact, GroundStation, OptimizationWindow, DataUnits
from gsopt.plots import plot_stations

import matplotlib.pyplot as plt
import plotly.graph_objs as go


@dataclass
class SolutionContact:
    """
    Dataclass to store information about a contact in a solution
    """
    id: str
    provider_id: str
    satellite_id: str
    station_id: str

    t_start: Epoch
    t_end: Epoch
    t_duration: float

    cost: float
    cost_per_minute: float
    cost_per_pass: float
    datavolume: float

    def __post_init__(self):
        # Ensure that t_start and t_end are Epoch objects
        if not isinstance(self.t_start, Epoch):
            self.t_start = Epoch(self.t_start)

        if not isinstance(self.t_end, Epoch):
            self.t_end = Epoch(self.t_end)

@dataclass
class Solution:
    """
    Dataclass to store information about an optimization solution
    """

    runtime: dict[str, float]
    opt_window: OptimizationWindow
    satellite_dict: dict[str, Satellite]
    provider_dict: dict[str, GroundStationProvider]
    station_dict: dict[str, GroundStation]
    contact_dict: dict[str, SolutionContact]
    selected_provider_dict: dict[str, GroundStationProvider]
    selected_station_dict: dict[str, GroundStation]
    stattions_by_satellite: dict[str: list[str]]

    @property
    def satellites(self):
        return list(self.satellite_dict.values())

    @property
    def providers(self):
        return list(self.provider_dict.values())

    @property
    def stations(self):
        return list(self.station_dict.values())

    @property
    def contacts(self):
        return list(self.contact_dict.values())

    @property
    def selected_stations(self):
        return list(self.selected_station_dict.values())


def load_solution(filepath: str):
    """
    Load an optimization solution from a JSON file and return the satellite, provider, station, and contact
    dictionaries. This function is useful for analyzing the results of an optimization run.

    Args:
        filepath: Path to the JSON file containing the optimization solution

    Returns:
        solution (Solution): Dataclass containing the satellites, providers, stations, and contacts in the solution
    """

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Parse Optimization Window
    opt_window = OptimizationWindow(**data["optimization_window"])



    # Parse Providers
    providers = [GroundStationProvider.load_geojson(p) for p in data["providers"]]

    # Extract provider / station dictionaries
    provider_dict = {p.id: p for p in providers}
    station_dict = {s.id: s for p in providers for s in p.stations}

    # Parse Satellites
    satellite_dict = {s['id']:Satellite(**s) for s in data["satellites"]}

    # Parse Contacts
    contact_dict = {c['id']:SolutionContact(**c) for c in data["contacts"]}

    # Extract providers that were selected in the solution
    selected_provider_ids = set([c.provider_id for c in contact_dict.values()])
    selected_provider_dict = {p_id:provider_dict[p_id] for p_id in selected_provider_ids}

    # Extract stations that were selected in the solution
    selected_station_ids = set([c.station_id for c in contact_dict.values()])
    selected_station_dict = {s_id:station_dict[s_id] for s_id in selected_station_ids}

    # Extract stations by satellite
    stations_by_satellite = data['stations_by_satellite']

    return Solution(data['runtime'], opt_window, satellite_dict, provider_dict,
                    station_dict, contact_dict, selected_provider_dict,
                    selected_station_dict, stations_by_satellite)

def plot_solution_stations(solution: Solution, selected_only: bool = False):
    """
    A convenience function to plot the locations of the ground stations in a solution. This wraps utils.plot_stations
    and computes the elevation_min and alt based on minimum of all stations and satellites.


    Args:
        solution:

    Returns:

    """

    if selected_only:
        stations = list(solution.selected_station_dict.values())
    else:
        stations = list(solution.station_dict.values())

    elevation_min = min([s.elevation_min for s in stations])
    alt = min([s.alt for s in solution.satellite_dict.values()])

    return plot_stations([(s.lon, s.lat, s.provider) for s in stations], elevation_min=elevation_min, alt=alt)

def compute_contact_gaps(contacts: list[Contact] | list[SolutionContact]):
    """
    Compute the gaps between contacts in a list of contacts. The gap is defined as the time between the end of one
    contact and the start of the next contact. The function returns a list of contact gaps.

    Args:
        contacts: List of contacts to compute gaps for

    Returns:
        contact_gaps: List of contact gaps
    """

    contact_gaps = {}
    all_gaps = []


    for sat_id, sat_contacts in groupby(contacts, lambda c: c.satellite_id):

        contact_gaps[sat_id] = []

        # Sort the contacts by start time
        sorted_contacts = sorted(sat_contacts, key=lambda c: c.t_start)

        # Compute the gaps between contacts
        for i in range(1, len(sorted_contacts)):
            gap = sorted_contacts[i].t_start - sorted_contacts[i-1].t_end
            gap_stats = {
                'satellite_id': sorted_contacts[i].satellite_id,
                'gap_start': sorted_contacts[i-1].t_end,
                'gap_end': sorted_contacts[i].t_start,
                'gap_duration_s': gap,
                'contact_before_id': sorted_contacts[i-1].id,
                'contact_after_id': sorted_contacts[i].id
            }

            all_gaps.append(gap_stats)
            contact_gaps[sat_id].append(gap_stats)

    contact_gaps['all'] = all_gaps
    return contact_gaps

def compute_gap_statistics(contact_gaps: list[dict]):

    # Compute the total number of gaps
    num_gaps = len(contact_gaps)

    # Compute the average gap duration
    mean_gap_duration = sum([g['gap_duration_s'] for g in contact_gaps]) / num_gaps

    # Compute the maximum gap duration
    max_gap_duration = max([g['gap_duration_s'] for g in contact_gaps])

    # Compute the minimum gap duration
    min_gap_duration = min([g['gap_duration_s'] for g in contact_gaps])

    # Compute 5 and 95 percentiles
    sorted_gap_durations = sorted([g['gap_duration_s'] for g in contact_gaps])
    gap_duration_s_p5bins = statistics.quantiles(sorted_gap_durations, n=20)
    gap_duration_s_p05 = gap_duration_s_p5bins[0]
    gap_duration_s_p95 = gap_duration_s_p5bins[18]

    return {
        'num_gaps': num_gaps,
        'mean_gap_duration_s': mean_gap_duration,
        'max_gap_duration_s': max_gap_duration,
        'min_gap_duration_s': min_gap_duration,
        'gap_duration_s_p05': gap_duration_s_p05,
        'gap_duration_s_p95': gap_duration_s_p95
    }

def compute_contact_statistics(contacts: list[Contact] | list[SolutionContact]):

    # Compute the total number of contacts
    num_contacts = len(contacts)

    # Compute the average contact duration
    mean_duration = sum([c.t_duration for c in contacts]) / num_contacts

    # Compute the maximum contact duration
    max_duration = max([c.t_duration for c in contacts])

    # Compute the minimum contact duration
    min_duration = min([c.t_duration for c in contacts])

    # Compute 5 and 95 percentiles
    sorted_durations = sorted([c.t_duration for c in contacts])
    contact_duration_s_p5bins = statistics.quantiles(sorted_durations, n=20)
    contact_duration_s_p05 = contact_duration_s_p5bins[0]
    contact_duration_s_p95 = contact_duration_s_p5bins[18]

    sat_contact_stats = {}
    sat_gap_stats = {}

    # Compute per-satellite contact statistics
    for sat_id, sat_contacts in groupby(contacts, lambda c: c.satellite_id):
        sat_contacts = list(sat_contacts)
        sat_mean_duration = sum([c.t_duration for c in sat_contacts]) / len(sat_contacts)
        sat_max_duration = max([c.t_duration for c in sat_contacts])
        sat_min_duration = min([c.t_duration for c in sat_contacts])
        sat_sorted_durations = sorted([c.t_duration for c in sat_contacts])
        sat_duration_s_p5bins = statistics.quantiles(sat_sorted_durations, n=20)
        sat_duration_s_p05 = sat_duration_s_p5bins[0]
        sat_duration_s_p95 = sat_duration_s_p5bins[18]

        sat_contact_stats[sat_id] = {
            'num_contacts': len(sat_contacts),
            'mean_duration_s': sat_mean_duration,
            'max_duration_s': sat_max_duration,
            'min_duration_s': sat_min_duration,
            'duration_s_p05': sat_duration_s_p05,
            'duration_s_p95': sat_duration_s_p95
        }

        # Compute contact gaps
        sat_contact_gaps = compute_contact_gaps(sat_contacts)[sat_id]
        sat_gap_stats[sat_id] = compute_gap_statistics(sat_contact_gaps)

    return {
        'num_contacts': num_contacts,
        'mean_duration_s': mean_duration,
        'max_duration_s': max_duration,
        'min_duration_s': min_duration,
        'duration_s_p05': contact_duration_s_p05,
        'duration_s_p95': contact_duration_s_p95,
        'satellite_contact_stats': sat_contact_stats
    }

def plot_contact_duration_histogram(contacts: list[Contact] | list[SolutionContact], satellite_id: str | None = None, units: str = 'minutes', x_axis_min: float = 0):

    if satellite_id is not None:
        contacts = [c for c in contacts if c.satellite_id == satellite_id]

    durations = [c.t_duration for c in contacts]

    # Change duration into minutes for better visualization
    if units == 'minutes':
        durations = [d/60 for d in durations]

    fig = go.Figure(
        data=[go.Histogram(x=durations)]  # Set bin width to 2
    )

    # Set title
    fig.update_layout(
        title_text="Contact Duration Histogram"
    )

    # Set axis labels
    fig.update_xaxes(title_text=f"Duration ({units})")
    fig.update_yaxes(title_text="Count")

    # Change color of the bars
    fig.update_traces(marker_color='blue', marker_line_color='black', marker_line_width=1)

    # Set x-axis lower limit to 0
    fig.update_xaxes(range=[x_axis_min, None])

    return fig


def plot_contact_gap_histogram(contact_gaps, satellite_id: str | None = None, units: str = 'minutes', x_axis_min: float = 0, bin_width: float = 5.0):

    # Compute contact gaps
    if satellite_id is not None:
        contact_gaps = contact_gaps[satellite_id]
    else:
        contact_gaps = contact_gaps['all']

    gap_durations = [g['gap_duration_s'] for g in contact_gaps]

    # Change duration into minutes for better visualization
    if units == 'minutes':
        gap_durations = [d/60 for d in gap_durations]

    fig = go.Figure(

        data=[go.Histogram(x=gap_durations, xbins={'size': bin_width})]
    )

    # Set title
    fig.update_layout(
        title_text="Contact Gap Histogram"
    )

    # Set axis labels
    fig.update_xaxes(title_text=f"Gap Duration ({units})")
    fig.update_yaxes(title_text="Count")

    # Change color of the bars
    fig.update_traces(marker_color='blue', marker_line_color='black', marker_line_width=1)

    # Set x-axis lower limit to 0

    fig.update_xaxes(range=[x_axis_min, None])

    return fig

def analyze_solution(solution: Solution, data_unit: DataUnits = DataUnits.b):
    """
    Analyze an optimization solution and return statistics about the contacts and gaps in the solution.

    Args:
        solution: Solution object containing the satellites, providers, stations, and contacts in the solution

    Returns:
        contact_stats: Dictionary containing statistics about the contacts in the solution
        gap_stats: Dictionary containing statistics about the gaps between contacts in the solution
    """

    # Compute contact statistics
    contact_stats = compute_contact_statistics(solution.contacts)

    # Compute contact gaps
    contact_gaps = compute_contact_gaps(solution.contacts)

    # Compute gap statistics
    gap_stats = compute_gap_statistics(contact_gaps['all'])

    # Compute Costs
    total_cost = 0.0
    total_fixed_cost = 0.0
    total_operational_cost = 0.0
    monthly_operational_cost = 0.0

    ## Provider Costs - Fixed
    for pn_id, pn in solution.selected_provider_dict.items():
        total_cost += pn.integration_cost
        total_fixed_cost += pn.integration_cost

    ## Station Costs - Fixed & Operational
    for sn_id, sn in solution.selected_station_dict.items():
        total_cost += sn.setup_cost
        total_fixed_cost += sn.setup_cost

        extr_opt_cost = (12 * solution.opt_window.T_opt) / (365.25 * 86400.0) * sn.monthly_cost
        total_cost += extr_opt_cost
        total_operational_cost += extr_opt_cost
        monthly_operational_cost += sn.monthly_cost

    ## Add Satellite Licensing Costs
    for sat_id in solution.stattions_by_satellite.keys():
        for station_id in solution.stattions_by_satellite[sat_id]:
            total_cost += solution.station_dict[station_id].per_satellite_license_cost

    ## Contact Costs - Operational
    for cn_id, cn in solution.contact_dict.items():
        total_cost += solution.opt_window.T_opt / solution.opt_window.T_sim * cn.cost
        total_operational_cost += solution.opt_window.T_opt / solution.opt_window.T_sim * cn.cost
        monthly_operational_cost += cn.cost / solution.opt_window.T_sim * (365.25 * 86400.0) / 12.0

    # Data Downlink Statistics
    total_data_downlinked = sum([c.datavolume for c in solution.contacts]) * solution.opt_window.T_opt / solution.opt_window.T_sim
    total_data_downlinked = total_data_downlinked / data_unit.value

    datavolume_by_satellite = {
        'total': {},
        'daily_avg': {},
    }

    for sat_id, sat_contacts in groupby(solution.contacts, lambda c: c.satellite_id):
        datavolume_by_satellite['total'][sat_id] = sum([c.datavolume for c in sat_contacts]) * solution.opt_window.T_opt / solution.opt_window.T_sim / data_unit.value
        datavolume_by_satellite['daily_avg'][sat_id] = datavolume_by_satellite['total'][sat_id] / (solution.opt_window.T_opt / 86400.0)

    return {
        'runtime': {
        },
        'contact_stats': contact_stats,
        'gap_stats': gap_stats,
        'costs': {
            'total_cost': total_cost,
            'total_fixed_cost': total_fixed_cost,
            'total_operational_cost': total_operational_cost,
            'monthly_operational_cost': monthly_operational_cost
        },
        'data_downlink': {
            'total_data_downlinked': total_data_downlinked,
            'datavolume_by_satellite': datavolume_by_satellite
        }
    }