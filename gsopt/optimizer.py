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

logger = logging.getLogger()


# Enumeration of available optimizers
class OptimizerType(Enum):
    Gurobi = 'gurobi'
    Cbc = 'cbc'


class MilpGSOptimizer(pk.block):

    def __init__(self,
                 opt_window: OptimizationWindow | None,
                 stations: list[GroundStation] | None = None,
                 satellites: list[Satellite] | None = None,
                 optimizer: OptimizerType = OptimizerType.Gurobi,
                 ):
        super().__init__()

        # Default initializations
        self.solve_time = 0.0
        self.contact_compute_time = 0.0
        self.opt_window = opt_window
        self.stations   = stations
        self.satellites = satellites
        self.elevation_min = 0.0
        self.contacts = None

        # Set the optimizer
        self.optimizer = optimizer

        # MILP Model Initialization
        self.constraints = pk.constraint_list()


    def set_optimization_window(self, opt_window):
        self.opt_window = opt_window

    def set_satellites(self, satellites):
        self.satellites = satellites

    def set_stations(self, stations):
        self.stations = stations

    def set_access_constraints(self, elevation_min):
        self.elevation_min = elevation_min

    def compute_contacts(self):
        precompute_time = time.perf_counter()

        t_start = bh.Epoch(self.opt_window.sim_start)
        t_end   = bh.Epoch(self.opt_window.sim_end)

        self.contacts = utils.compute_all_contacts(
            self.satellites,
            self.stations,
            t_start,
            t_end,
            self.elevation_min,
            show_streamlit=True
        )

        completion_time = time.perf_counter()

        self.contact_compute_time = completion_time - precompute_time

    def solve(self):

        # Create the solver
        if self.optimizer == OptimizerType.Gurobi:
            solver = po.SolverFactory("gurobi")
        else:
            logger.info("Using backup COIN-OR CBC solver")
            solver = po.SolverFactory("cbc")

        # try to solve with chosen optimizer
        presolve_time = time.perf_counter()
        # self.solution = solver.solve(self)
        completion_time = time.perf_counter()

        self.solve_time = completion_time - presolve_time
