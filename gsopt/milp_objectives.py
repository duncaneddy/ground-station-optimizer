"""
Module containing different objective functions for MILP optimization
"""

from abc import abstractmethod, ABCMeta
from itertools import groupby

import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow
from gsopt.utils import time_milp_generation


class GSOptObjective(metaclass=ABCMeta):
    """
    Abstract class for the objective function of the MILP optimization.

    Enforces the implementation of the _generate_objective method.
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs

        self.obj = pk.objective()

        self.obj.expr = 0

    @abstractmethod
    def _generate_objective(self):
        pass

    def dict(self):
        return {
            'type': self.__class__.__name__,
            'args': self.kwargs
        }


class MinCostObjective(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the total cost (capital and operational) of the
    ground station provider over the optimization period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptObjective.__init__(self, **kwargs)

        # Set objective direction
        self.obj.sense = pk.minimize

    @time_milp_generation
    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            station_satellite_nodes: dict[(str, str), pk.variable] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """

        # Add provider costs
        for pn_id, pn in provider_nodes.items():
            self.obj.expr += pn.model.integration_cost * provider_nodes[pn_id].var

        # Add station costs
        for sn_id, sn in station_nodes.items():
            self.obj.expr += sn.model.setup_cost * station_nodes[sn_id].var

            # Add monthly station costs, normalized to the optimization period
            self.obj.expr += (12 * opt_window.T_opt) / (365.25 * 86400.0 * opt_window.T_sim) * sn.model.monthly_cost * station_nodes[sn_id].var

            # Add satellite licensing costs for the station
            for key in filter(lambda x: x[0] == sn_id, station_satellite_nodes.keys()):
                self.obj.expr += sn.model.per_satellite_license_cost * station_satellite_nodes[key]

        # Add contact costs
        for cn_id, cn in contact_nodes.items():
            self.obj.expr += opt_window.T_opt / opt_window.T_sim * (cn.model.t_duration * cn.model.cost_per_minute + cn.model.cost_per_pass) * contact_nodes[cn_id].var


class MaxDataDownlinkObjective(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that maximizes the total data downlinked by the constellation over the
    optimization period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptObjective.__init__(self, **kwargs)

        # Set objective direction
        self.obj.sense = pk.maximize

    @time_milp_generation
    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """

        for cn in contact_nodes.values():
            self.obj.expr += cn.var * cn.model.data_volume * opt_window.T_opt / opt_window.T_sim


class MinMaxContactGapObjective(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the maximum gap between contacts across all satellites
    in the constellation over the optimization period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptObjective.__init__(self, **kwargs)

        # Set objective direction
        self.obj.sense = pk.minimize

        # Initialize constraints required to implement the objective
        self.constraints = pk.constraint_list()

    @time_milp_generation
    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """

        # Group contacts by satellite
        contact_nodes_by_satellite = sorted(contact_nodes.values(), key=lambda cn: cn.satellite.id)

        self.variable_dict = pk.variable_dict()

        # Create auxiliary variable for the max gap across all satellites and contacts
        self.variable_dict['max_gap'] = pk.variable(value=0.0, domain=pk.NonNegativeReals)

        # Set objective to minimize the maximum gap
        self.obj.expr = self.variable_dict['max_gap']

        for sat_id, sat_contacts in groupby(contact_nodes_by_satellite, lambda cn: cn.satellite.id):
            # Sort contacts by start time
            sat_contacts = list(sorted(sat_contacts, key=lambda cn: cn.model.t_start))

            # For each contact, create an auxiliary variable for the next scheduled task
            for i, cn_i in enumerate(sat_contacts[0:len(sat_contacts) - 1]):

                # Working expression for the next scheduled contact
                expr = pk.expression(0)

                for j, cn_j in enumerate(filter(lambda cn: cn.model.t_start > cn_i.model.t_end, sat_contacts)):
                    # Auxiliary variable if contact j is the next scheduled after contact i
                    self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] = pk.variable(value=0, domain=pk.Binary)

                    expr += self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)]

                    # Constraints to ensure that if the auxiliary variable is 1, then both x_i and x_j are 1
                    self.constraints.append(pk.constraint(
                        self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] <= contact_nodes[cn_i.id].var))
                    self.constraints.append(pk.constraint(
                        self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] <= contact_nodes[cn_j.id].var))

                    # Add constraint to ensure that the associated scheduled gap is less than the maximum
                    self.constraints.append(pk.constraint((cn_j.model.t_start - cn_i.model.t_end) * self.variable_dict[
                        (sat_id, cn_i.model.id, cn_j.model.id)] <= self.variable_dict['max_gap']))
                    # print(self.constraints[-1].expr)


                # Add constraint that only one of the auxiliary variables can be 1 if the contact node is scheduled
                self.constraints.append(pk.constraint(expr == contact_nodes[cn_i.id].var))
