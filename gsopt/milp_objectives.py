"""
Module containing different objective functions for MILP optimization
"""

from abc import abstractmethod, ABCMeta
import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow


class GSOptObjective(metaclass=ABCMeta):
    """
    Abstract class for the objective function of the MILP optimization.

    Enforces the implementation of the generate_objective method.
    """
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def generate_objective(self):
        pass


class MinCostObjective(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the total cost (capital and operational) of the
    ground station network over the optimization period.
    """
    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)


    def generate_objective(self, provider_nodes: list[ProviderNode] | None = None,
                           station_nodes: list[StationNode] | None = None,
                           contact_nodes: list[ContactNode] | None = None,
                           opt_window: OptimizationWindow | None = None):
        """
        Generate the objective function.
        """
        pass


class MaxDataDownlink(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that maximizes the total data downlinked by the constellation over the
    optimization period.
    """
    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)


    def generate_objective(self, provider_nodes: list[ProviderNode] | None = None,
                           station_nodes: list[StationNode] | None = None,
                           contact_nodes: list[ContactNode] | None = None,
                           opt_window: OptimizationWindow | None = None):
        """
        Generate the objective function.
        """
        pass


class MinMaxContactGap(pk.block, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the maximum gap between contacts across all satellites
    in the constellation over the optimization period.
    """
    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)


    def generate_objective(self, provider_nodes: list[ProviderNode] | None = None,
                           station_nodes: list[StationNode] | None = None,
                           contact_nodes: list[ContactNode] | None = None,
                           opt_window: OptimizationWindow | None = None):
        """
        Generate the objective function.
        """
        pass