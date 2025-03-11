#!/usr/bin/env python
"""
Ground station optimization for maximizing data downlink over the optimization window.

This example demonstrates how to create a ground station optimization problem maximize the total data downlinked over
a mission (optimization window). The optimization problem is formulated as a mixed-integer linear programming (MILP)
problem and solved using either the Gurobi or CBC solver.
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

optimizer = get_optimizer('gurobi') # 'scip', 'cbc', 'glpk', or 'gurobi'

# Define the optimization window
opt_start = datetime.datetime.now(datetime.timezone.utc)
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

# Create a scenario generator
# Set seed=VALUE to reproduce the same scenario
scengen = ScenarioGenerator(opt_window)

# Use the Capella constellation as the reference constellation
scengen.add_constellation('UMBRA')

# Consider all providers
scengen.add_all_providers()

# Generate a problem instance
scen = scengen.sample_scenario()

# Display the randomly generate scenario
console.print(scen)

# Create a MILP optimizer from the scenario
optimizer = MilpOptimizer.from_scenario(scen, optimizer=optimizer)

# Save all potential stations
optimizer.save_plot('max_data_opt_all_stations.png')

# Compute contacts
optimizer.compute_contacts()

# Setup the optimization problem
optimizer.set_objective(
    MaxDataDownlinkObjective()
)

# Add Constraints
optimizer.add_constraints([
    MaxProvidersConstraint(num_providers=3), # At most 3 providers
    MinContactDurationConstraint(min_duration=180.0), # Minimum 3 minute contact duration
    MaxOperationalCostConstraint(value=1e9),
    StationContactExclusionConstraint(),
    SatelliteContactExclusionConstraint(), # This constraint should always be added to avoid self-interference
])

# Solve the optimization problem
optimizer.solve()

# Display results
console.print(optimizer)

# Save the plot of the optimized contacts
optimizer.save_plot('max_data_opt_selected_stations.png')