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


# MILP Optimizer
class MilpOptimizer(pk.block, GroundStationOptimizer):
    """
    A MILP optimizer defines
    """

    def __init__(self, opt_window: OptimizationWindow):
        # Initialize parent classes
        pk.block.__init__(self)
        GroundStationOptimizer.__init__(self, opt_window)

        # Define MILP objective
        self.objective = pk.objective()

        # Variables
        self.provider_nodes = pk.block_dict()
        self.station_nodes = pk.block_dict()
        self.contact_nodes = pk.block_dict()
        self.satellite_nodes = pk.block_dict()

        # Constraints container
        self.constraints = pk.constraint_list()

        # Metadata
        self.n_vars = {
            'providers': 0,
            'stations': 0,
            'contacts': 0,
            'satellites': 0
        }
        self.n_constraints = 0

        self._problem_initialized = False

    def set_objective(self, objective):
        """
        Set the objective function for the optimization problem

        Args:
            objective (pk.objective): Objective function to set
        """

        if isinstance(objective, pk.objective):
            # Hack to ensure no previous objective exists
            if hasattr(self, "obj"):
                del self.obj

            self.obj = objective

        else:
            raise ValueError(f"Objective must be of type pk.objective. Unsupported type: {type(objective)}")

    def add_constraint(self, constraint):
        """
        Add / apply a constraint set to the model instance

        Args:
            constraint (pk.constraints): Constraint to add to the model
        """

        if isinstance(constraint, (pk.constraint, pk.constraint_list, pk.constraint_dict)):
            self.constraints.append(constraint)
        else:
            raise ValueError(f"Constraint must be of type pk.constraint, pk.constraint_list, or pk.constraint_dict")

    def generate_problem(self):
        """
        Build the underlying MILP objetive and constraints
        """

        inputs = dict(
            provider_nodes=self.provider_nodes,
            station_nodes=self.station_nodes,
            contact_nodes=self.contact_nodes,
            satellite_nodes=self.satellite_nodes
        )

        # Generate objective
        self.obj.generate_objective(**inputs)

        # Generate constraints
        for constraint in self.constraints:
            constraint.generate_constraints(**inputs)
            self.n_constraints += len(constraint)

    def solve(self):

        if not self._problem_initialized:
            self.generate_problem()
            self._problem_initialized = True

    def write_solution(self):
        pass

    def __str__(self):
        return f"<MilpOptimizer - {self.solver_status}: {len(self.satellites)} satellites, {len(self.providers)} providers, {len(self.stations)} stations, {len(self.contacts)} contacts>"
