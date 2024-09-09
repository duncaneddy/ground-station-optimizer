#!/usr/bin/env python
"""
Ground station optimization with minimization of the maximum gap between contacts as the objective function.

This example demonstrates how to create a ground station optimization problem with the objective of minimizing the
maximum gap between contacts. The optimization problem is formulated as a mixed-integer linear programming (MILP)
problem and solved using either the Gurobi or CBC solver.
"""

import logging
import datetime
from rich.console import Console

from gsopt.milp_objectives import *
from gsopt.milp_constraints import *
from gsopt.milp_optimizer import MilpOptimizer
from gsopt.models import OptimizationWindow
from gsopt.scenarios import ScenarioGenerator

# Set up logging
logging.basicConfig(
    datefmt='%Y-%m-%dT%H:%M:%S',
    format='%(asctime)s.%(msecs)03dZ %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Rich console for pretty printing
console = Console()

# Define the optimization window
opt_start = datetime.datetime.utcnow()
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
# scengen.add_constellation('CAPELLA')
scengen.add_satellite(25544)

# Consider all providers
scengen.add_all_providers()

# Generate a problem instance
scen = scengen.sample_scenario()

# Display the randomly generate scenario
console.print(scen)

# Create a MILP optimizer from the scenario
optimizer = MilpOptimizer.from_scenario(scen)

# Compute contacts
optimizer.compute_contacts()

# Setup the optimization problem
optimizer.set_objective(
    MinMaxContactGapObjective()
)

# Add Constraints
optimizer.add_constraints([
    MaxProvidersConstraint(num_providers=3), # At most 3 providers
    MinContactDurationConstraint(min_duration=180.0), # Minimum 3 minute contact duration
    MinSatelliteDataDownlinkConstraint(value=100.0e9, period=86400, step=3600), # Ensure at least 100 Gb of data downlinked per day
                                                                                # This constraint is key for a MaxGap optimization
                                                                                # because otherwise the solver will just not
                                                                                # schedule any contacts to minimize the gap
    StationContactExclusionConstraint(),
    SatelliteContactExclusionConstraint(), # This constraint should always be added to avoid self-interference
])

# Solve the optimization problem
optimizer.solve()

# Display results
console.print(optimizer)
