'''
This module contains the GSOptimizer class, which is used to solve the ground station optimization problem.
'''
import logging
import time
from enum import Enum

import pyomo.kernel as pk
import pyomo.opt as po

import brahe as bh

import streamlit as st

from gsopt import utils
from gsopt.models import GroundStation, Satellite, OptimizationWindow
from gsopt.optimizer import GroundStationOptimizer

logger = logging.getLogger()


# Enumeration of available optimizers
class OptimizerType(Enum):
    Gurobi = 'gurobi'
    Cbc = 'cbc'

class MilpOptimizer(pk.block, GroundStationOptimizer):
    """
    A MILP optimizer defines
    """

    def __init__(self, opt_window: OptimizationWindow):
        # Initialize parent classes
        pk.block.__init__(self)
        GroundStationOptimizer.__init__(self, opt_window)

        # Define MILP variables
        self.contact_nodes = pk.variable_dict()

        # Define MILP objective
        self.objective = pk.objective()

        # Define MILP constraints
        self.constraints = pk.constraint_list()

        self.elevation_min = 0.0

    def solve(self):
        pass

    def write_solution(self):
        pass

# class MilpGSOptimizer(pk.block):
#
#     def __init__(self,
#                  opt_window: OptimizationWindow | None,
#                  stations: list[GroundStation] | None = None,
#                  satellites: list[Satellite] | None = None,
#                  optimizer_type: OptimizerType = OptimizerType.Gurobi,
#                  ):
#         super().__init__()
#
#         # Default initializations
#         self.solve_time = 0.0
#         self.contact_compute_time = 0.0
#         self.opt_window = opt_window
#         self.stations   = stations
#         self.satellites = satellites
#         self.elevation_min = 0.0
#         self.contacts = None
#
#         # Set the optimizer_type
#         self.optimizer_type = optimizer_type
#
#         # MILP Model Initialization
#         self.constraints = pk.constraint_list()
#         self.objective = pk.objective()
#         self.contact_nodes = pk.variable_dict()
#
#
#     def set_optimization_window(self, opt_window):
#         self.opt_window = opt_window
#
#     def set_satellites(self, satellites):
#         self.satellites = satellites
#
#     def set_stations(self, stations):
#         self.stations = stations
#
#     def set_access_constraints(self, elevation_min):
#         self.elevation_min = elevation_min
#
#     def compute_contacts(self):
#         precompute_time = time.perf_counter()
#
#         t_start = bh.Epoch(self.opt_window.sim_start)
#         t_end   = bh.Epoch(self.opt_window.sim_end)
#
#         self.contacts = utils.compute_all_contacts(
#             self.satellites,
#             self.stations,
#             t_start,
#             t_end,
#             self.elevation_min,
#             show_streamlit=True
#         )
#
#         completion_time = time.perf_counter()
#
#         self.contact_compute_time = completion_time - precompute_time
#
#         # Populate the contact nodes
#         for contact in self.contacts:
#             self.contact_nodes[contact.id] = pk.variable(value=0, domain=pk.Binary)
#
#     def set_objective_maximize_contact_time(self):
#
#         if len(self.contact_nodes) == 0:
#             raise RuntimeError("No contact nodes found. Please compute contacts first.")
#
#         # Set optimization direction to maximize
#         self.objective.sense = pk.maximize
#         self.objective.expr  = 0
#
#         # Objective: Maximize the total contact time
#         for c in self.contacts:
#             self.objective.expr += c.t_duration * self.contact_nodes[c.id]
#
#     def solve(self):
#
#         # Create the solver
#         if self.optimizer_type == OptimizerType.Gurobi:
#             solver = po.SolverFactory("gurobi")
#         else:
#             logger.info("Using backup COIN-OR CBC solver")
#             solver = po.SolverFactory("cbc")
#
#         # Solve the problem
#         presolve_time = time.perf_counter()
#         self.solution = solver.solve(self)
#         completion_time = time.perf_counter()
#
#         self.solve_time = completion_time - presolve_time
#
#         if (self.solution.solver.status != po.SolverStatus.ok
#              or self.solution.solver.termination_condition != po.TerminationCondition.optimal):
#             raise RuntimeError(
#                 f"Station Optimization Error: Solver Status {self.solution.solver.status} | TerminationCondition {self.solution.solver.termination_condition}"
#             )
