'''
This module contains the GSOptimizer class, which is used to solve the ground station optimization problem.
'''
import json
import logging
import os
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
from rich.text import Text

from gsopt import utils
from gsopt.milp_constraints import GSOptConstraint
from gsopt.milp_core import ProviderNode, StationNode, ContactNode, SatelliteNode
from gsopt.models import GroundStation, Satellite, OptimizationWindow, DataUnits
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

    def __init__(self, opt_window: OptimizationWindow, optimizer: OptimizerType = OptimizerType.Gurobi, presolve: int | None = None):
        # Initialize parent classes
        pk.block.__init__(self)
        GroundStationOptimizer.__init__(self, opt_window)

        # Set optimizer
        self.optimizer = optimizer
        self.presolve = presolve

        # Define MILP objective
        self.obj_block = pk.block()

        # Variables
        self.provider_nodes = pk.block_dict()
        self.station_nodes = pk.block_dict()
        self.contact_nodes = pk.block_dict()
        self.satellite_nodes = pk.block_dict()
        self.station_satellite_nodes = pk.variable_dict()

        # Constraints container
        self.constraint_blocks = pk.block_list()
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

        if isinstance(objective, pk.block):

            # Always remove the old objective block
            del self.obj_block

            self.obj_block = objective

        elif isinstance(objective, pk.objective):
            raise ValueError("Objective must be a block type. Use a block with a member varible that is a pyomo.kernel.objective")

        else:
            raise ValueError(f"Objective must be of type pk.block. Unsupported type: {type(objective)}")

        self._objective_set = True

    def add_constraint(self, constraint):
        """
        Add / apply a constraint set to the model instance

        Args:
            constraint (pk.constraints): Constraint to add to the model
        """

        if isinstance(constraint, list) and len(constraint) != 1:
            raise ValueError("Input constraint must be a single constraint, not a list of constraints")

        if isinstance(constraint, pk.block):
            self.constraint_blocks.append(constraint)

        elif isinstance(constraint, (pk.constraint, pk.constraint_list, pk.constraint_dict)):
            self.constraints.append(constraint)
        else:
            raise ValueError(f"Constraint {type(constraint).__name__} is not of type pk.constraint, pk.constraint_list, or pk.constraint_dict")

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

        if not self._objective_set:
            raise RuntimeError("Objective function not set. Please set the objective function before generating the problem.")

        logger.info("Generating MILP problem...")
        ts = time.perf_counter()

        # Generate nodes to ensure variables exist
        self.generate_nodes()

        inputs = dict(
            provider_nodes=self.provider_nodes,
            station_nodes=self.station_nodes,
            contact_nodes=self.contact_nodes,
            satellite_nodes=self.satellite_nodes,
            station_satellite_nodes=self.station_satellite_nodes,
            opt_window=self.opt_window
        )

        # Generate constraints
        for constraint in self.constraint_blocks:
            if hasattr(constraint, '_generate_constraints'):
                constraint._generate_constraints(**inputs)
            self.n_constraints += len(constraint.constraints)

        for constraint in self.constraints:
            if hasattr(constraint, '_generate_constraints'):
                constraint._generate_constraints(**inputs)
            self.n_constraints += len(constraint)

        # Generate objective function
        # We do this after the constraints since some objectives (MinMaxContactGapObjective) require additional
        # constraints to be generated, and it's nicer for debugging if all user-specified constraints are generated first
        self.obj_block._generate_objective(**inputs)

        # Generate minimum variable constraints
        # This must be done after the constraints are generated for the model
        self._generate_variable_constraints()

        te = time.perf_counter()
        self.problem_setup_time = te - ts
        logger.info(f"Finished generating MILP problem with {self.n_constraints} constraints. Took: {utils.get_time_string(te - ts)}.")

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

            # logger.debug(f'Generating constraints for station {gs_id} with {num_station_contacts} contacts')

            # Ensure that station node is scheduled if at least one contact is scheduled
            self.constraints.append(pk.constraint(
                sum([self.contact_nodes[c.id].var for c in contact_node_group]) <= num_station_contacts * self.station_nodes[gs_id].var
            ))

            # Ensure at least one contact is scheduled if station is scheduled
            self.constraints.append(pk.constraint(
                sum([self.contact_nodes[c.id].var for c in contact_node_group]) >= self.station_nodes[gs_id].var
            ))

            self.n_constraints += 1

            # If a single contact for a given satellite is selected then that satellite-station indicator must be selected
            contacts_by_satellite_sorted = sorted(contact_node_group, key=lambda x: str(x.satellite.id))
            for sat_id, sat_contacts in groupby(contacts_by_satellite_sorted, key=lambda x: x.satellite.id):
                sat_contact_group = list(sat_contacts)
                num_sat_contacts = len(sat_contact_group)

                # logger.debug(f'Generating constraints for station {gs_id}, for satellite {sat_id}, with {num_sat_contacts} contacts')

                self.constraints.append(pk.constraint(
                    sum([self.contact_nodes[c.id].var for c in sat_contact_group]) <= num_sat_contacts * self.station_satellite_nodes[(gs_id, sat_id)]
                ))

                self.n_constraints += 1

        # If a single station for a given provider is selected then that provider must be selected
        station_nodes_sorted = sorted(self.station_nodes.values(), key=lambda x: x.provider.id)
        for p_id, stations in groupby(station_nodes_sorted, key=lambda x: x.provider.id):
            station_node_group = list(stations)
            num_provider_stations = len(station_node_group)

            # logger.debug(f'Generating constraints for provider {p_id} with {num_provider_stations} stations')

            self.constraints.append(pk.constraint(
                sum([self.station_nodes[s.id].var for s in station_node_group]) <= num_provider_stations * self.provider_nodes[p_id].var
            ))

            self.n_constraints += 1


    def solve(self):

        # Initialize problem
        if not self._problem_initialized:
            self.generate_problem()
            self._problem_initialized = True

        logger.info("Solving MILP problem...")
        ts = time.perf_counter()

        # Select solver
        if self.optimizer == OptimizerType.Gurobi:
            logger.debug("Using Gurobi solver")
            solver = po.SolverFactory("gurobi")

        else:
            logger.debug("Using backup COIN-OR CBC solver")
            solver = po.SolverFactory("cbc")

            # Set timeout limit on solve
            if self.time_limit is not None:
                solver.options['TimeLimit'] = self.time_limit
            if self.presolve is not None:
                if self.presolve not in [0, 1, 2]:
                    raise ValueError("Presolve must be 0, 1, or 2")
                solver.options['Presolve'] = self.presolve

        try:
            self.solution = solver.solve(self, tee=self.verbose)
        except ApplicationError as e:
            logger.error(f"Solver error: {e}")

        # Set solver status
        self.solver_status = str(self.solution.solver.termination_condition)


        te = time.perf_counter()
        self.solve_time = te - ts

        logger.info(f"Solved MILP problem in {utils.get_time_string(self.solve_time)} with status: {self.solver_status}")


    def get_solution(self):
        """
        Get the solution from the MILP solver

        Returns:
            - Solver status
            - Compute time
            - Objective value
            - Provider selection
            - Station selection
            - Contact selection
        """

        solution = {}

        # Compute statistics
        solution['runtime'] = {
            'contact_compute_time': self.contact_compute_time,
            'problem_setup_time': self.problem_setup_time,
            'solve_time': self.solve_time,
        }

        # Problem Formulation
        solution['problem'] = {
            'objective': self.obj_block.dict(),
            'constraints': [c.dict() for c in self.constraint_blocks if isinstance(c, GSOptConstraint)]
        }

        # Solution Output
        solution['solver_status'] = self.solver_status.upper()

        # Objective value
        solution['objective_value'] = self.obj_block.obj()

        # Solution Metadata
        solution['n_vars'] = self.n_vars
        solution['n_constraints'] = self.n_constraints

        # Compute Costs
        total_cost = 0.0
        total_fixed_cost = 0.0
        total_operational_cost = 0.0
        monthly_operational_cost = 0.0

        ## Provider Costs - Fixed
        for pn_id, pn in self.provider_nodes.items():
            if pn.var() > 0:
                total_cost += pn.model.integration_cost
                total_fixed_cost += pn.model.integration_cost

        ## Station Costs - Fixed & Operational
        for sn_id, sn in self.station_nodes.items():
            if sn.var() > 0:
                total_cost += sn.model.setup_cost
                total_fixed_cost += sn.model.setup_cost

                extr_opt_cost = (12 * self.opt_window.T_opt) / (365.25 * 86400.0 * self.opt_window.T_sim) * sn.model.monthly_cost
                total_cost += extr_opt_cost
                total_operational_cost += extr_opt_cost
                monthly_operational_cost += sn.model.monthly_cost

        ## Add Satellite Licensing Costs
        for (station_id, sat_id) in self.station_satellite_nodes.keys():
            if self.station_satellite_nodes[(station_id, sat_id)]() > 0:
                total_cost += self.station_nodes[station_id].model.per_satellite_license_cost

        ## Contact Costs - Operational
        for cn_id, cn in self.contact_nodes.items():
            if cn.var() > 0:
                total_cost += self.opt_window.T_opt / self.opt_window.T_sim * cn.model.cost
                total_operational_cost += self.opt_window.T_opt / self.opt_window.T_sim * cn.model.cost
                monthly_operational_cost += cn.model.cost / self.opt_window.T_sim * (365.25 * 86400.0) / 12.0

        # Data Downlink Statistics
        total_data_downlinked = sum(
            [c.model.data_volume  for c in self.contact_nodes.values() if c.var() > 0]) * self.opt_window.T_opt / self.opt_window.T_sim

        datavolume_by_satellite = {
            'total': {},
            'total_GB': {},
            'daily_avg': {},
            'daily_avg_GB': {}
        }

        for sat_id, sat_contacts in groupby(self.contact_nodes.values(), lambda c: c.model.satellite_id):
            datavolume_by_satellite['total'][sat_id] = sum([c.model.data_volume for c in
                                                            sat_contacts]) * self.opt_window.T_opt / self.opt_window.T_sim
            datavolume_by_satellite['total_GB'][sat_id] = datavolume_by_satellite['total'][sat_id] / DataUnits.GB.value
            datavolume_by_satellite['daily_avg'][sat_id] = datavolume_by_satellite['total'][sat_id] / (
                        self.opt_window.T_opt / 86400.0)
            datavolume_by_satellite['daily_avg_GB'][sat_id] = datavolume_by_satellite['daily_avg'][sat_id] / DataUnits.GB.value

        solution['statistics'] = {
            'costs': {
                'total': total_cost,
                'fixed': total_fixed_cost,
                'operational': total_operational_cost,
                'monthly_operational': monthly_operational_cost,
            },
            'data_downlinked': { # Value values in bits
                'total': total_data_downlinked,
                'total_GB': total_data_downlinked / DataUnits.GB.value,
                'by_satellite': datavolume_by_satellite,
            },
            'contact_time_s': {
                'total': sum([c.model.t_duration for c in self.contact_nodes.values() if c.var() > 0]) * self.opt_window.T_opt / self.opt_window.T_sim,
                'by_satellite': {sat_id: sum([c.model.t_duration * c.var() for c in sat_contacts]) / (self.opt_window.T_sim / 86400.0) for sat_id, sat_contacts in groupby(self.contact_nodes.values(), lambda c: c.model.satellite_id)}
            }
        }

        # Optimization Window
        solution['optimization_window'] = self.opt_window.as_dict()

        # Satellites
        solution['satellites'] = [sn.model.as_dict() for sn in self.satellite_nodes.values()]

        # Variable selection
        solution['providers'] = [pn.model.as_dict() for pn in self.provider_nodes.values()]
        solution['selected_providers'] = [pn.model.name for pn in self.provider_nodes.values() if pn.var() > 0]
        solution['selected_stations'] = [{'name': sn.model.name, 'provider': sn.model.provider} for sn in self.station_nodes.values() if sn.var() > 0]
        solution['contacts'] = [cn.model.as_dict(minimal=True) for cn in sorted(self.contact_nodes.values(), key=lambda c: c.model.t_start) if cn.var() > 0]

        # Add station-satellite indicators
        solution['stations_by_satellite'] = {}

        for sat_id, sat in self.satellites.items():
            solution['stations_by_satellite'][sat_id] = []
            for gs_id, gs in self.stations.items():
                if (gs_id, sat_id) in self.station_satellite_nodes and \
                    self.station_satellite_nodes[(gs_id, sat_id)]() > 0:
                    solution['stations_by_satellite'][sat_id].append(gs_id)

        return solution

    def write_solution(self, filename: str):
        """
        Write the solution to a file

        Args:
            filename (str): Filename to write the solution to
        """

        # Confirm problem has been solved
        if self.solver_status == 'Not Solved':
            raise RuntimeError("Problem has not been solved. Please solve the problem before writing the solution.")

        # Confirm filename is a JSON file
        if not filename.endswith('.json'):
            raise ValueError("Filename must be a JSON file (e.g. 'single_sat_solution.json')")

        json.dump(self.get_solution(), open(filename, 'w'), indent=4)

    def __str__(self):
        return f"<MilpOptimizer - {self.solver_status}: {len(self.satellites)} satellites, {len(self.providers)} providers, {len(self.stations)} stations, {len(self.contacts)} contacts>"

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        tbl = Table(title="MILP Optimizer")

        tbl.add_column("Property")
        tbl.add_column("Value")

        tbl.add_row("Optimization Objective", self.obj_block.__class__.__name__)
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
        tbl.add_row("Setup Time", str(utils.get_time_string(self.problem_setup_time)))
        tbl.add_row("Solver Status", str(self.solver_status).upper())
        tbl.add_row("Solve Time", utils.get_time_string(self.solve_time))
        tbl.add_row("Objective Value", str(self.obj_block.obj()))
        tbl.add_row("# of Selected Providers", str(sum([pn.var() for pn in self.provider_nodes.values()])))
        for provider in self.provider_nodes.values():
            if provider.var() > 0:
                text = Text("Yes")
                text.stylize("bright_green", 0, 4)
            else:
                text = Text("No")
                text.stylize("bright_red", 0, 2)

            tbl.add_row(f" - {provider.model.name}", text)

        tbl.add_row("# of Selected Stations", str(sum([sn.var() for sn in self.station_nodes.values()])))

        for _, station_groups in groupby(sorted(self.station_nodes.values(), key=lambda x: x.provider.name),
                                         lambda x: x.provider.name):
            for s in station_groups:
                if s.var() > 0:
                    text = Text("Yes")
                    text.stylize("bright_green", 0, 4)
                else:
                    text = Text("No")
                    text.stylize("bright_red", 0, 2)
                tbl.add_row(f" - {s.provider.name}-{s.model.name}", text)

        tbl.add_row("# of Selected Contacts", str(sum([cn.var() for cn in self.contact_nodes.values()])))

        yield tbl

    def set_presolve(self, presolve: int):
        """
        Set the presolve level for the solver

        Args:
            presolve (int): Presolve level (0, 1, 2)
        """
        self.presolve = presolve
