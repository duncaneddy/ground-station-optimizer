"""
Module containing different objective functions for MILP optimization
"""

from abc import abstractmethod, ABCMeta
import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow


class GSOptConstraint(metaclass=ABCMeta):
    """
    Abstract class for the constraint function of the MILP optimization.

    Enforces the implementation of the generate_constraints method.
    """

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def generate_constraints(self):
        pass


class ConstellationDataDownlinkConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the constellation is greater than or equal to
    the given threshold over a given period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class SatelliteDataDownlinkConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the satellite is greater than or equal to
    a given threshold over a given period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class OperationalCostConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the operational cost of the constellation is less than or equal to a given
    amount over a desired time period.

    Operational costs are monthly station use costs and contact costs.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class StationAntennaLimitConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the number of simultaneous contacts a station can have is less than or equal
    to the number of antennas at the station.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class SatelliteContactExclusionConstraint(pk.block, GSOptConstraint):
    """
    Enforces that a satellite cannot have contacts with two different stations at the same time.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class MaxContactGapConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces that the time between two contacts for any satellite is less than or equal to a given
    time period.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass


class ProviderLimitConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces the number of ground station providers that can be selected is less than or equal to
    the given number.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self, **kwargs)

    def generate_constraints(self, provider_nodes: list[ProviderNode] | None = None,
                             station_nodes: list[StationNode] | None = None,
                             contact_nodes: list[ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None):
        """
        Generate the constraint function.
        """
        pass