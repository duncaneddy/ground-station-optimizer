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
from pathlib import Path
from rich.console import Console

import brahe as bh

from gsopt.models import Satellite, GroundStation, GroundStationProvider, OptimizationWindow
from gsopt.milp_optimizer import MilpOptimizer
from gsopt.utils import LOG_FORMAT_VERBOSE, LOG_DATE_FORMAT

# Set seed to ensure consistency
random.seed(42)

# Create Rich console for pretty printing
console = Console()

# Set up logging
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT_VERBOSE, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger(__name__)

# Load the ground stations
STATION_DATA_DIR = Path('data/groundstations')

providers = [] # List of all different station providers to analyze

for provider_file in os.listdir(STATION_DATA_DIR):
    # Hack to skip unpopulated stations
    if 'ksat' not in provider_file and 'aws' not in provider_file:

        with open(STATION_DATA_DIR / provider_file, 'r') as f:
            # Load stations from file and add to existing provider
            providers.append(GroundStationProvider.load_geojson(f))

# Display Station provider
for sta_provider in providers:

    sta_provider.integration_cost = random.uniform(50000, 200000)

    # Set station one-time costs
    sta_provider.set_property('setup_cost', random.uniform(10000, 100000))
    sta_provider.set_property('per_satellite_license_cost', random.uniform(1000, 5000))

    # Set minimum cost per-pass
    sta_provider.set_property('monthly_cost', random.uniform(500, 2000))
    sta_provider.set_property('cost_per_pass', random.uniform(20, 40))
    sta_provider.set_property('per_satellite_license_cost', random.uniform(2000, 6000))

    # Station max data rate
    sta_provider.set_property('datarate', 2.0e9)  # 2.0 Gbps

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
    # console.print(provider)
    optimizer.add_provider(provider)

for satellite in satellites:
    # console.print(satellite)
    optimizer.add_satellite(satellite)

# Compute contacts
optimizer.compute_contacts()

logger.info(optimizer)