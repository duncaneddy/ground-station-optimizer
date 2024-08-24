"""
Module containing different objective functions for MILP optimization
"""

from abc import abstractmethod, ABCMeta
import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow


class GSOptConstraint(metaclass=ABCMeta):
    """
    Abstract class for the constraint_list function of the MILP optimization.

    Enforces the implementation of the _generate_constraints method.
    """

    def __init__(self):
        pass

    @abstractmethod
    def _generate_constraints(self):
        pass


class ConstellationDataDownlinkConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the constellation is greater than or equal to
    the given threshold over a given period.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class SatelliteDataDownlinkConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the satellite is greater than or equal to
    a given threshold over a given period.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class OperationalCostConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint function that enforces that the operational cost of the constellation is less than or equal to a given
    amount over a desired time period.

    Operational costs are monthly station use costs and contact costs.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class StationAntennaLimitConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint function that enforces that the number of simultaneous contacts a station can have is less than or equal
    to the number of antennas at the station.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class SatelliteContactExclusionConstraint(pk.constraint_list, GSOptConstraint):
    """
    Enforces that a satellite cannot have contacts with two different stations at the same time.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class MaxContactGapConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint that enforces that the time between two contacts for any satellite is less than or equal to a given
    time period.
    """

    def __init__(self, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass


class ProviderLimitConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint that enforces the number of ground station providers that can be selected is less than or equal to
    the given number.
    """

    def __init__(self, num_providers: int = 1, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        self.num_providers = num_providers

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        self.append(pk.constraint(sum(pn.var for pn in provider_nodes.values()) <= self.num_providers))


class MinContactDurationConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint that enforces the minimum duration of a contact between a satellite and a ground station is greater than
    or equal to the given time period.
    """

    def __init__(self, min_duration: float = 300, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        if min_duration <= 0:
            raise ValueError("Minimum duration must be greater than zero.")

        self.min_duration = min_duration

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        for cn in contact_nodes.values():
            if cn.obj.t_duration <= self.min_duration:
                # Force all contacts with duration less than the minimum to be zero
                self.append(pk.constraint(cn.var == 0))


class MaxContactsPerPeriodConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint that enforces that the total number of contacts in any given period is less than or equal to the given
    limit. The usual period is a day.
    """

    def __init__(self, limit: int = 16, period: float = 86400.0, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


        self.limit = limit
        self.period = period

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """
        pass