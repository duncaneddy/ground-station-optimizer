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
from pyomo.common.errors import ApplicationError
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from gsopt import utils
from gsopt.milp_core import ProviderNode, StationNode, ContactNode, SatelliteNode
from gsopt.models import GroundStation, Satellite, OptimizationWindow
from gsopt.optimizer import GroundStationOptimizer
from gsopt.utils import APPLIED_FILTER_WARNINGS

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

    def __init__(self, opt_window: OptimizationWindow, optimizer: OptimizerType = OptimizerType.Gurobi):
        # Initialize parent classes
        pk.block.__init__(self)
        GroundStationOptimizer.__init__(self, opt_window)

        # Set optimizer
        self.optimizer = optimizer

        # Define MILP objective
        self.obj = pk.objective()

        # Variables
        self.provider_nodes = pk.block_dict()
        self.station_nodes = pk.block_dict()
        self.contact_nodes = pk.block_dict()
        self.satellite_nodes = pk.block_dict()
        self.station_satellite_nodes = pk.variable_dict()

        # Constraints container
        self.constraints = pk.constraint_list()

        # Metadata
        self.n_vars = {
            'providers': 0,
            'stations': 0,
            'contacts': 0,
            'satellites': 0,
            'station_sat_indicators': 0
        }
        self.n_constraints = 0

        self._problem_initialized = False
        self._objective_set = False

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

        self._objective_set = True

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

    def add_constraints(self, constraints: list):
        """
        Add / apply a list of constraints to the model instance

        Args:
            constraints (list[pk.constraint]): List of constraints to add to the model
        """

        for constraint in constraints:
            self.add_constraint(constraint)

    def generate_nodes(self):
        """
        Create the nodes for the MILP model
        """

        # Generate provider nodes
        for id, provider in self.providers.items():
            self.provider_nodes[id] = ProviderNode(**{'obj': provider})
            self.n_vars['providers'] += 1

        for id, station in self.stations.items():
            self.station_nodes[id] = StationNode(**{'obj': station, 'provider': self.providers[station.provider_id]})
            self.n_vars['stations'] += 1

        for id, satellite in self.satellites.items():
            self.satellite_nodes[id] = SatelliteNode(**{'obj': satellite})
            self.n_vars['satellites'] += 1

        for id, contact in self.contacts.items():
            self.contact_nodes[id] = ContactNode(**{'obj': contact,
                                                            'provider': self.providers[contact.provider_id],
                                                            'station': self.stations[contact.station_id],
                                                            'satellite': self.satellites[contact.satellite_id]})
            self.n_vars['contacts'] += 1

        # Generate station_statellite individuals
        for station_id in self.stations:

            # Get all statellites that had a contact with the station
            sat_ids = set([c.satellite_id for c in self.contacts.values() if c.station_id == station_id])

            for s in sat_ids:
                self.station_satellite_nodes[(station_id, s)] = pk.variable(value=0, domain=pk.Binary)

                self.n_vars['station_sat_indicators'] += 1


    def generate_problem(self):
        """
        Build the underlying MILP objetive and constraints
        """

        # Generate nodes to ensure variables exist
        self.generate_nodes()

        inputs = dict(
            provider_nodes=self.provider_nodes,
            station_nodes=self.station_nodes,
            contact_nodes=self.contact_nodes,
            satellite_nodes=self.satellite_nodes,
            opt_window=self.opt_window
        )

        # Generate objective
        if not self._objective_set:
            raise RuntimeError("Objective function not set. Please set the objective function before generating the problem.")

        self.obj._generate_objective(**inputs)

        # Generate constraints
        for constraint in self.constraints:
            constraint._generate_constraints(**inputs)
            self.n_constraints += len(constraint)

    def solve(self):

        ts = time.perf_counter()

        # Initialize problem
        if not self._problem_initialized:
            self.generate_problem()
            self._problem_initialized = True

        # Select solver
        if self.optimizer == OptimizerType.Gurobi:
            logger.debug("Using Gurobi solver")
            solver = po.SolverFactory("gurobi")

        else:
            logger.debug("Using backup COIN-OR CBC solver")
            solver = po.SolverFactory("cbc")

        try:
            self.solution = solver.solve(self)
        except ApplicationError as e:
            logger.error(f"Solver error: {e}")

        # Set solver status
        self.solver_status = str(self.solution.solver.termination_condition)


        te = time.perf_counter()
        self.solve_time = te - ts


    def write_solution(self):
        pass

    def __str__(self):
        return f"<MilpOptimizer - {self.solver_status}: {len(self.satellites)} satellites, {len(self.providers)} providers, {len(self.stations)} stations, {len(self.contacts)} contacts>"

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        tbl = Table(title="MILP Optimizer")

        tbl.add_column("Property")
        tbl.add_column("Value")

        tbl.add_row("Contact Compute Time", utils.get_time_string(self.contact_compute_time))
        tbl.add_row("# of Satellites", str(len(self.satellites)))
        tbl.add_row("# of Providers", str(len(self.providers)))
        tbl.add_row("# of Stations", str(len(self.stations)))
        tbl.add_row("# of Contacts", str(len(self.contacts)))
        tbl.add_row("# of Variables:", str(sum(self.n_vars.values())))
        tbl.add_row("- Satellites", str(self.n_vars['satellites']))
        tbl.add_row("- Satellite Station Indicators", str(self.n_vars['station_sat_indicators']))
        tbl.add_row("- Providers", str(self.n_vars['providers']))
        tbl.add_row("- Stations", str(self.n_vars['stations']))
        tbl.add_row("- Contacts", str(self.n_vars['contacts']))
        tbl.add_row("Number of Constraints", str(self.n_constraints))
        tbl.add_row("Solver Status", self.solver_status)
        tbl.add_row("Solve Time", utils.get_time_string(self.solve_time))
        tbl.add_row("Objective Value", str(self.obj()))
        tbl.add_row("# of Selected Providers", str(sum([pn.var() for pn in self.provider_nodes.values()])))
        tbl.add_row("# of Selected Stations", str(sum([sn.var() for sn in self.station_nodes.values()])))
        tbl.add_row("# of Selected Contacts", str(sum([cn.var() for cn in self.contact_nodes.values()])))
        tbl.add_row("Station Use By # Of Satellite", "")

        sats_by_station = { k: 0 for k in self.station_ids }

        for sta in sats_by_station.keys():
            for k, v in self.station_satellite_nodes.items():
                if k[0] == sta:
                    sats_by_station[sta] += v()

        # Ensure display is in consistent alphabetical order
        l = {}
        for sta in self.stations.values():
            l[(sta.provider, sta.name)] = f"- {sta.provider} - {sta.name}", str(sats_by_station[sta.id])

        for k in sorted(l.keys()):
            tbl.add_row(l[k][0], l[k][1])

        yield tbl

