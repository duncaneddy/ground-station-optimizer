'''
This module contains the GSOptimizer class, which is used to solve the ground station optimization problem.
'''
import logging
import time
import multiprocessing as mp
from enum import Enum

import brahe as bh
import pyomo.kernel as pk
import pyomo.opt as po

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
        self.opt_window = opt_window
        self.stations   = None
        self.satellites = None

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

    def compute_contacts(self):
        pass

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
