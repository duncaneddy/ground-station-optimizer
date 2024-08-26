#!/usr/bin/env python
"""
This example demonstrates the basic usage of the gsopt library to perform a MILP optimization for a ground station
provider. The example walks through the major steps of the problem: data loading, contact computation, optimization,
and results display.
"""
import datetime
import os
import random
import logging
from itertools import groupby
from pathlib import Path
from rich.console import Console

import brahe as bh

from gsopt.milp_constraints import *
from gsopt.milp_objectives import *
from gsopt.models import Satellite, GroundStation, GroundStationProvider, OptimizationWindow
from gsopt.milp_optimizer import MilpOptimizer
from gsopt.utils import LOG_FORMAT_VERBOSE, LOG_DATE_FORMAT

# Set seed to ensure consistency
random.seed(42)

# Create Rich console for pretty printing
console = Console()

# Set up logging
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT_VERBOSE, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger(__name__)

# Load the ground stations
STATION_DATA_DIR = Path('data/groundstations')

providers = [] # List of all different station providers to analyze

for provider_file in os.listdir(STATION_DATA_DIR):
    with open(STATION_DATA_DIR / provider_file, 'r') as f:
        # Load stations from file and add to existing provider
        providers.append(GroundStationProvider.load_geojson(f))

# Display Station provider
for sta_provider in providers:

    # Set minimum elevation angle
    sta_provider.set_property('elevation_min', 10.0)

    sta_provider.integration_cost = random.uniform(50000, 200000)

    # Set station one-time costs
    sta_provider.set_property('setup_cost', random.uniform(10000, 100000))
    sta_provider.set_property('per_satellite_license_cost', random.uniform(1000, 5000))

    # Set minimum cost per-pass
    sta_provider.set_property('monthly_cost', random.uniform(500, 2000))

    # Set base station pass costs
    sta_cost_per_pass = random.uniform(10, 30)
    sta_cost_per_minute = random.uniform(2, 15)

    # Randomize cost type (per pass or per minute) consistently across the provider
    cost_type = random.uniform(0, 1)

    # Station max data rate
    sta_provider.set_property('datarate', 2.0e9)  # 2.0 Gbps

    # For each station, Randomize number of antennas
    for sta in sta_provider.stations:
        sta_provider.set_property('antennas', random.randint(1, 3), key=sta.id)

        # Set slightly different costs for each station
        if cost_type >= 0.5:
            sta_provider.set_property('cost_per_pass', sta_cost_per_pass + random.uniform(0, 20), key=sta.id)
            sta_provider.set_property('cost_per_minute', 0.0, key=sta.id)
        else:
            sta_provider.set_property('cost_per_pass', 0.0, key=sta.id)
            sta_provider.set_property('cost_per_minute', sta_cost_per_minute + random.uniform(0, 10), key=sta.id)

# Create a few satellites to optimize for

# Define Optimization Problem
epc = bh.Epoch(2022, 1, 1, 0, 0, 0)

# Define approximate satellite orbit based on ISS
satellites = [
    Satellite.from_elements(
        25544,
        'ISS',
        epc,
        bh.R_EARTH + 420e3,  # 420 km altitude
        0.0005296,
        51.64,
        0.0,
        0.0,
        0.0,
        datarate=1.2e9  # 1.2 Gbps
    ),
]

# Define the optimization window

# The optimization window defines the period over which we want to optimize the ground station provider selection
opt_start = datetime.datetime(2022, 1, 1, 0, 0, 0)
opt_end = opt_start + datetime.timedelta(days=365)

# The simulation window is the duration over which we want to simulate contacts.
# This is shorter than or equal to the optimization window.
sim_start = opt_start
sim_end = sim_start + datetime.timedelta(days=7)

opt_window = OptimizationWindow(
    opt_start,
    opt_end,
    sim_start,
    sim_end
)

# Create a MILP optimizer

optimizer = MilpOptimizer(opt_window)

for provider in providers:
    console.print(provider)

    for station in provider.stations:
        console.print(station)
    optimizer.add_provider(provider)

for satellite in satellites:
    console.print(satellite)
    optimizer.add_satellite(satellite)

# Compute contacts
optimizer.compute_contacts()

# Setup the optimization problem

optimizer.set_objective(
    # MinCostObjective()
    MaxDataDownlinkObjective()
    # MinMaxContactGapObjective()
)

# Add Constraints
optimizer.add_constraints([
    ProviderLimitConstraint(num_providers=3),
    MinContactDurationConstraint(min_duration=300.0),
    ConstellationDataDownlinkConstraint(value=1.0e9, period=86400.0, step=300),
    SatelliteDataDownlinkConstraint(value=1.0e9, period=96.0*60, step=300),
    SatelliteDataDownlinkConstraint(value=1.0e9, period=86400.0, step=300, satellite_id=25544),
    # OperationalCostConstraint(),
    # StationAntennaLimitConstraint(),
    SatelliteContactExclusionConstraint(),
    # MaxContactGapConstraint(max_gap=1800.0),
    MaxContactsPerPeriodConstraint(value=50, period=86400.0, step=300),
    RequireProviderConstraint('Azure'),
    RequireStationConstraint(name='Oregon', provider='Aws')
])

# Solve the optimization problem
optimizer.solve()

# Display the results

console.print(optimizer)

# print(optimizer.constraints[2][0].expr)
# print(len(optimizer.constraints[3]))
# for i in range(2, len(optimizer.constraints)):
#     # print(optimizer.constraints[i].num_providers)
#     print(optimizer.constraints[i].expr)

# print(list(sorted(optimizer.contact_nodes.values(), key=lambda x: x.model.t_start))[0].model.t_duration)
# print(list(sorted(optimizer.contact_nodes.values(), key=lambda x: x.model.t_start))[0].model.datarate)