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

    Enforces the implementation of the _generate_objective method.
    """

    def __init__(self):
        pass

    @abstractmethod
    def _generate_objective(self):
        pass


class MinCostObjective(pk.objective, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the total cost (capital and operational) of the
    ground station provider over the optimization period.
    """

    def __init__(self, **kwargs):
        pk.objective.__init__(self)
        GSOptObjective.__init__(self)

    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """
        pass


class MaxDataDownlinkObjective(pk.objective, GSOptObjective):
    """
    Objective function for the MILP optimization that maximizes the total data downlinked by the constellation over the
    optimization period.
    """

    def __init__(self, **kwargs):
        pk.objective.__init__(self)
        GSOptObjective.__init__(self)

    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """
        pass


class MinMaxContactGapObjective(pk.objective, GSOptObjective):
    """
    Objective function for the MILP optimization that minimizes the maximum gap between contacts across all satellites
    in the constellation over the optimization period.
    """

    def __init__(self, **kwargs):
        pk.objective.__init__(self)
        GSOptObjective.__init__(self)

    def _generate_objective(self, provider_nodes: dict[str, ProviderNode] | None = None,
                            station_nodes: dict[str, StationNode] | None = None,
                            contact_nodes: dict[str, ContactNode] | None = None,
                            opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the objective function.
        """
        pass
