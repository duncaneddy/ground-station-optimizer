"""
Module containing different objective functions for MILP optimization
"""

import logging

from abc import abstractmethod, ABCMeta
import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow

logger = logging.getLogger(__name__)


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

    def _generate_constraints(self, data_min: float = 0.0,
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

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None, **kwargs):
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

    def _generate_constraints(self, contact_nodes: dict[str, ContactNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        for cn in contact_nodes.values():
            if cn.model.t_duration <= self.min_duration:
                # Force all contacts with duration less than the minimum to be zero
                self.append(pk.constraint(cn.var == 0))


class MaxContactsPerPeriodConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint that enforces that the total number of contacts in any given period is less than or equal to the given
    limit. The usual period is a day.

    Args:
        limit (int): The maximum number of contacts allowed in the period.
        period (float): The period over which the limit is enforced in seconds.
        step (int): The interval at which the constraint is enforced in seconds.
    """

    def __init__(self, limit: int = 16, period: float = 86400.0, step: float = 300, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")

        if step <= 0:
            raise ValueError("Step must be greater than zero.")

        self.limit = limit
        self.period = period
        self.step = step

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        ts = opt_window.sim_start  # Working variable for the start of the current period
        te = ts + self.period    # Working variable for the end of the current period

        t_max = opt_window.sim_end  # The end of the constraint period

        # Get contacts in the current period, sorted by start time
        contacts = sorted(contact_nodes.values(), key=lambda cn: cn.model.t_start)

        while te <= t_max:
            # Get contacts in the current period
            contacts_in_period = filter(lambda cn: cn.model.t_end >= ts and cn.model.t_start <= te, contacts)

            # Add the constraint
            self.append(pk.constraint(sum(contact_nodes[cn.id].var for cn in contacts_in_period) <= self.limit))

            # Move to the next period
            ts += self.step
            te += self.step


class RequireProviderConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint to require a specific provider to be selected.
    """

    def __init__(self, key: str = None, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        if key is None:
            raise ValueError("A unique key (id or name) for the provider must be provided")

        self.key = key
        self._matched_id = None

    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Note: this mattaching has to be done in the _generate_constraints method not in the __init__ method
        # because the provider_nodes dictionary is not available at the time of object creation. It is
        # passed as an argument to the _generate_constraints method at the time of optimization.

        # Attempt to match the key to the provider id
        if self.key in provider_nodes.keys():
            self._matched_id = self.key

        # Otherwise attempt to match the key to the provider name
        for pn in provider_nodes.values():
            if pn.model.name.lower() == self.key.lower():
                self._matched_id = pn.model.id
                break

        if self._matched_id is None:
            raise RuntimeError(f"Could not find a provider with key \"{self.key}\"")

        self.append(pk.constraint(provider_nodes[self._matched_id].var == 1))


class RequireStationConstraint(pk.constraint_list, GSOptConstraint):
    """
    Constraint to require a specific station to be selected.
    """

    def __init__(self, id: str | None = None, name: str | None = None, provider: str | None = None, **kwargs):
        pk.constraint_list.__init__(self)
        GSOptConstraint.__init__(self)

        self.required_id = None
        self.required_name = None
        self.required_provider = None

        if id is None:
            if name is None or provider is None:
                raise ValueError("Either the station id or the station name and provider name must be provided.")

            self.required_provider = provider
            self.required_name = name

        if id is not None:
            if name is not None or provider is not None:
                raise ValueError("Providing the station id requires no other arguments.")

            self.required_id = id

        self._matched_id = None

    def _generate_constraints(self, station_nodes: dict[str, StationNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # If and ID was provided, attempt to match it
        if self.required_id is not None:
            if self.required_id in station_nodes.keys():
                self.append(pk.constraint(station_nodes[self.required_id].var == 1))
                return
            else:
                raise RuntimeError(f"Could not find a station with id \"{self.required_id}\".")

        # Otherwise attempt to match the name and provider
        for sn in station_nodes.values():
            if sn.model.name.lower() == self.required_name.lower() and sn.model.provider.lower() == self.required_provider.lower():
                self.append(pk.constraint(station_nodes[sn.id].var == 1))
                return

        raise RuntimeError(f"Could not find a station with name \"{self.required_name}\" and provider \"{self.required_provider}\".")