'''
This module contains the GSOptimizer class, which is used to solve the ground station optimization problem.
'''
import logging
import time
import copy
from enum import Enum
from itertools import groupby

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

    @property
    def opt_start(self):
        return copy.deepcopy(self.opt_window.opt_start)

    @property
    def opt_end(self):
        return copy.deepcopy(self.opt_window.opt_end)

    @property
    def sim_start(self):
        return copy.deepcopy(self.opt_window.sim_start)

    @property
    def sim_end(self):
        return copy.deepcopy(self.opt_window.sim_end)

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

        # Generate minimum variable constraints
        # This must be done after the constraints are generated for the model
        self._generate_variable_constraints()

    def _generate_variable_constraints(self):
        """
        Generate variable relationship constraints for indicator variables. This enforces that
        if any station is selected, the corresponding satellite-station indicator variable is set.
        It also enforces that the indicator that if a station is used that station and provider are also indicated as
        used.
        """

        # If a single contact for a given station is selected then that station must be selected
        contact_nodes_sorted = sorted(self.contact_nodes.values(), key=lambda x: x.station.id)
        for gs_id, contacts in groupby(contact_nodes_sorted, key=lambda x: x.station.id):
            contact_node_group = list(contacts)
            num_station_contacts = len(contact_node_group)

            logger.debug(f'Generating constraints for station {gs_id} with {num_station_contacts} contacts')

            self.constraints.append(pk.constraint(
                sum([self.contact_nodes[c.id].var for c in contact_node_group]) <= num_station_contacts * self.station_nodes[gs_id].var
            ))

            self.n_constraints += 1

            # If a single contact for a given satellite is selected then that satellite-station indicator must be selected
            contacts_by_satellite_sorted = sorted(contact_node_group, key=lambda x: x.satellite.id)
            for sat_id, sat_contacts in groupby(contacts_by_satellite_sorted, key=lambda x: x.satellite.id):
                sat_contact_group = list(sat_contacts)
                num_sat_contacts = len(sat_contact_group)

                logger.debug(f'Generating constraints for station {gs_id}, for satellite {sat_id}, with {num_sat_contacts} contacts')

                self.constraints.append(pk.constraint(
                    sum([self.contact_nodes[c.id].var for c in sat_contact_group]) <= num_sat_contacts * self.station_satellite_nodes[(gs_id, sat_id)]
                ))

                self.n_constraints += 1

        # If a single station for a given provider is selected then that provider must be selected
        station_nodes_sorted = sorted(self.station_nodes.values(), key=lambda x: x.provider.id)
        for p_id, stations in groupby(station_nodes_sorted, key=lambda x: x.provider.id):
            station_node_group = list(stations)
            num_provider_stations = len(station_node_group)

            logger.debug(f'Generating constraints for provider {p_id} with {num_provider_stations} stations')

            self.constraints.append(pk.constraint(
                sum([self.station_nodes[s.id].var for s in station_node_group]) <= num_provider_stations * self.provider_nodes[p_id].var
            ))

            self.n_constraints += 1


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
        tbl.add_row("Solver Status", str(self.solver_status).upper())
        tbl.add_row("Solve Time", utils.get_time_string(self.solve_time))
        tbl.add_row("Objective Value", str(self.obj()))
        tbl.add_row("# of Selected Providers", str(sum([pn.var() for pn in self.provider_nodes.values()])))
        for provider in self.provider_nodes.values():
            tbl.add_row(f" - {provider.model.name}", str(provider.var()))

        tbl.add_row("# of Selected Stations", str(sum([sn.var() for sn in self.station_nodes.values()])))

        for _, station_groups in groupby(sorted(self.station_nodes.values(), key=lambda x: x.provider.name),
                                         lambda x: x.provider.name):
            for s in station_groups:
                tbl.add_row(f" - {s.provider.name}-{s.model.name}", str(s.var()))

        tbl.add_row("# of Selected Contacts", str(sum([cn.var() for cn in self.contact_nodes.values()])))

        # tbl.add_row("Visible Sats By Station", "")
        #
        # sats_by_station = { k: 0 for k in self.station_ids }
        #
        # for sta in sats_by_station.keys():
        #     for k, v in self.station_satellite_nodes.items():
        #         if k[0] == sta:
        #             sats_by_station[sta] += v()
        #
        # # Ensure display is in consistent alphabetical order
        # l = {}
        # for sta in self.stations.values():
        #     l[(sta.provider, sta.name)] = f"- {sta.provider} - {sta.name}", str(sats_by_station[sta.id])
        #
        # for k in sorted(l.keys()):
        #     tbl.add_row(l[k][0], l[k][1])

        yield tbl
