#!/usr/bin/env python
"""
Ground station optimization for maximizing data downlink for Capella spacecraft using only KSAT ground stations.

This example demonstrates how to create a ground station optimization problem to maximize the total data downlinked over
a mission period specifically for a specific constellation and ground station provider. In this example, we use the
Capella constellation and KSAT ground station provider.
"""

import logging
import datetime
from rich.console import Console

from gsopt.milp_objectives import *
from gsopt.milp_constraints import *
from gsopt.milp_optimizer import MilpOptimizer, get_optimizer
from gsopt.models import OptimizationWindow
from gsopt.scenarios import ScenarioGenerator
from gsopt.utils import filter_warnings

filter_warnings()

# Set up logging
logging.basicConfig(
    datefmt='%Y-%m-%dT%H:%M:%S',
    format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Rich console for pretty printing
console = Console()

# OPTIMIZER SELECTION
optimizer = get_optimizer('gurobi')  # 'scip', 'cbc', 'glpk', or 'gurobi'

# Define the optimization window
opt_start = datetime.datetime.now(datetime.timezone.utc)
opt_end = opt_start + datetime.timedelta(days=7) # This is the full mission window. Normally 365+ days. Set to 7 days so that the constant is 1.

# The simulation window is the duration over which we want to simulate contacts
# This is shorter than or equal to the optimization window
sim_start = opt_start
sim_end = sim_start + datetime.timedelta(days=7)

opt_window = OptimizationWindow(
    opt_start,
    opt_end,
    sim_start,
    sim_end
)

# Create a scenario generator
scengen = ScenarioGenerator(opt_window)

# Hack to override the default scenario datarates to be fixed
scengen._sat_datarate_ranges['default'] = (1.2e9, 1.2e9)
scengen._provider_datarate['default'] = (1.2e9, 1.2e9)

# Add only Capella constellation
scengen.add_constellation('CAPELLA')

# Add only KSAT provider
scengen.add_provider('ksat.json')

# Generate a problem instance
scen = scengen.sample_scenario()

# Display the generated scenario
console.print(scen)

# Create a MILP optimizer from the scenario
optimizer = MilpOptimizer.from_scenario(scen, optimizer=optimizer)

# Save plot of all stations
optimizer.save_plot('capella_ksat_all_stations.png')

# Compute contacts
optimizer.compute_contacts()

# Setup the optimization problem to maximize data downlink
optimizer.set_objective(
    MaxDataDownlinkObjective()
)

# Add Constraints
optimizer.add_constraints([
    MinContactDurationConstraint(min_duration=180.0),  # Minimum 3 minute contact duration
    StationContactExclusionConstraint(),
    SatelliteContactExclusionConstraint(),  # This constraint should always be added to avoid self-interference
    MaxStationsConstraint(num_stations=5) # At most 5 stations
])

# Solve the optimization problem
optimizer.solve()

# Display results
console.print(optimizer)

# Optional: write the solution to a file
optimizer.write_solution('capella_ksat_optimization.json')

# Plot and save the selected ground stations
optimizer.save_plot('capella_ksat_selected_stations.png')