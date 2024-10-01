"""
Module containing different objective functions for MILP optimization
"""

import copy
import logging

from abc import abstractmethod, ABCMeta
from itertools import combinations, groupby

import pyomo.kernel as pk

from gsopt.milp_core import ProviderNode, StationNode, ContactNode
from gsopt.models import OptimizationWindow
from gsopt.utils import time_milp_generation

logger = logging.getLogger(__name__)


class GSOptConstraint(metaclass=ABCMeta):
    """
    Abstract class for the constraint_list function of the MILP optimization.

    Enforces the implementation of the _generate_constraints method.
    """

    def __init__(self, **kwargs):

        self.kwargs = kwargs

        self.constraints = pk.constraint_list()

    @abstractmethod
    def _generate_constraints(self):
        pass

    def dict(self):
        return {
            'type': self.__class__.__name__,
            'args': self.kwargs
        }

class MinConstellationDataDownlinkConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the constellation is greater than or equal to
    the given threshold over a given period.

    Args:
        value (float): The minimum data downlinked by the constellation in bits over the period.
        period (float): The period over which the value is enforced in seconds.
        step (float): The interval at which the constraint is enforced in seconds.
    """

    def __init__(self, value: float = 0.0, period: float = 86400.0, step: float = 300, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, value=value, period=period, step=step)

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        if value <= 0:
            raise ValueError("Limit must be greater than zero.")

        if step <= 0:
            raise ValueError("Step must be greater than zero.")

        self.value = value
        self.period = period
        self.step = step

    @time_milp_generation
    def _generate_constraints(self,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        ts = copy.deepcopy(opt_window.sim_start)  # Working variable for the start of the current period
        te = copy.deepcopy(ts + self.period)  # Working variable for the end of the current period

        t_max = opt_window.sim_end  # The end of the constraint period

        # Get contacts in the current period, sorted by start time
        contacts = sorted(list(contact_nodes.values()), key=lambda cn: cn.model.t_start)

        while te <= t_max:
            # Get contacts in the current period
            contacts_in_period = filter(lambda cn: cn.model.t_end >= ts and cn.model.t_start <= te, contacts)

            # Add the constraint
            self.constraints.append(pk.constraint(sum(cn.model.datarate * cn.model.t_duration * contact_nodes[cn.id].var for cn in contacts_in_period) >= self.value))

            # Move to the next period
            ts += self.step
            te += self.step


class MinSatelliteDataDownlinkConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the total data downlinked by the satellite is greater than or equal to
    a given threshold over a given period.

    If a satellite key is provided, the constraint is applied to that satellite only. Otherwise, the constraint is
    applied to each satellite in the constellation.

    Args:
        value (float): The minimum data downlinked by the satellite in bits over the period.
        period (float): The period over which the value is enforced in seconds.
        step (float): The interval at which the constraint is enforced in seconds.
        satellite_key (str): The unique key (id or name) of the satellite to which the constraint applies.
    """

    def __init__(self, value: float = 0.0, period: float = 86400.0, step: float = 300,
                 satellite_key: str | int | None = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, value=value, period=period, step=step, satellite_key=satellite_key)

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        if value <= 0:
            raise ValueError("Limit must be greater than zero.")

        if step <= 0:
            raise ValueError("Step must be greater than zero.")

        self.value = value
        self.period = period
        self.step = step


        self.satellite_key = satellite_key
        self._matched_id = None

    @time_milp_generation
    def _generate_constraints(self,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        t_max = opt_window.sim_end  # The end of the constraint period

        # If a satellite key was provided, attempt to match it
        if self.satellite_key is not None:
            satellite_contacts = list(filter(lambda cn:
                                        self.satellite_key in [cn.satellite.id, cn.satellite.name, cn.satellite.satcat_id], contact_nodes.values()))

            if len(satellite_contacts) == 0:
                raise RuntimeError(f"Could not find a satellite with key \"{self.satellite_key}\".")

            # Sort the contacts by start time
            satellite_contacts = sorted(satellite_contacts, key=lambda cn: cn.model.t_start)

            # Apply the constraint to the satellite
            ts = copy.deepcopy(opt_window.sim_start)  # Working variable for the start of the current period
            te = copy.deepcopy(ts + self.period)  # Working variable for the end of the current period

            while te <= t_max:
                # Get contacts in the current period
                contacts_in_period = filter(lambda cn: cn.model.t_end >= ts and cn.model.t_start <= te, satellite_contacts)

                # Add the constraint
                self.constraints.append(pk.constraint(sum(cn.model.datarate * cn.model.t_duration * contact_nodes[cn.id].var for cn in contacts_in_period) >= self.value))

                # Move to the next period
                ts += self.step
                te += self.step

        else:
            # Get unique satellite ids:
            satellite_ids = set([cn.satellite.id for cn in contact_nodes.values()])

            for satellite_id in satellite_ids:
                satellite_contacts = filter(lambda cn: cn.satellite.id == satellite_id, contact_nodes.values())

                # Sort the contacts by start time
                satellite_contacts = sorted(satellite_contacts, key=lambda cn: cn.model.t_start)

                ts = copy.deepcopy(opt_window.sim_start)  # Working variable for the start of the current period
                te = copy.deepcopy(ts + self.period)  # Working variable for the end of the current period

                while te <= t_max:
                    # Get contacts in the current period
                    contacts_in_period = filter(lambda cn: cn.model.t_end >= ts and cn.model.t_start <= te, satellite_contacts)

                    # Add the constraint
                    self.constraints.append(pk.constraint(sum(cn.model.datarate * cn.model.t_duration * contact_nodes[cn.id].var for cn in contacts_in_period) >= self.value))

                    # Move to the next period
                    ts += self.step
                    te += self.step


class MaxOperationalCostConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the operational cost of the constellation is less than or equal to a given
    amount over a desired time period.

    Operational costs are monthly station use costs and contact costs.
    """

    def __init__(self, value: float | None = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, value=value)

        if not value:
            raise ValueError("Value must be provided.")

        self.value = value

    @time_milp_generation
    def _generate_constraints(self,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Define an expression for the operational cost
        expr = pk.expression(0)

        # Add station use costs
        for sn in station_nodes.values():
            expr += sn.model.monthly_cost * sn.var

        # Add contact costs
        for cn in contact_nodes.values():
            # The weight here converts the pass costs over the simulation window to an approximate monthly cost
            expr +=(86400.0 * 365.25) / (12 * opt_window.sim_duration) * (cn.model.cost_per_minute * cn.model.t_duration + cn.model.cost_per_pass) * contact_nodes[cn.id].var

        # Add constraint cost
        self.constraints.append(pk.constraint(expr <= self.value))


class MaxAntennaUsageConstraint(pk.block, GSOptConstraint):
    """
    Constraint function that enforces that the number of simultaneous contacts a station can have is less than or equal
    to the number of antennas at the station.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self)

    @time_milp_generation
    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Group nodes by station
        contact_nodes_by_station = sorted(contact_nodes.values(), key=lambda cn: cn.station.id)

        for station_id, station_contacts in groupby(contact_nodes_by_station, lambda cn: cn.station.id):

            # Get number of antennas for station
            antennas = station_nodes[station_id].model.antennas

            # Sort contacts by start time
            station_contacts = sorted(station_contacts, key=lambda cn: cn.model.t_start)

            # This is an inefficient way to enforce the constraint, but it is simple
            # It works by getting all potential combinations of contacts for the station that could result in the
            # constraint being exceeded, then checks that this combination has a time where all contacts do indeed
            # overlap, then it enforces that only up to the antenna limit is taken.

            # The +1 is used because we only want to check combinations which might exceed the constraint
            contact_combos = list(combinations(station_contacts, antennas + 1))

            for contacts in contact_combos:
                if all(x.model.t_start <= y.model.t_end and y.model.t_start <= x.model.t_end for x, y in combinations(contacts, 2)):
                    self.constraints.append(pk.constraint(sum(contact_nodes[cn.id].var for cn in contacts) <= antennas))


class SatelliteContactExclusionConstraint(pk.block, GSOptConstraint):
    """
    Enforces that a satellite cannot have contacts with two different stations at the same time.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self)

    @time_milp_generation
    def _generate_constraints(self,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Filter contacts by satellite
        contact_nodes_by_satellite = sorted(contact_nodes.values(), key=lambda cn: str(cn.satellite.id))

        for sat_id, sat_contacts in groupby(contact_nodes_by_satellite, lambda cn: cn.satellite.id):

            # Sort contacts by start time
            sat_contacts = sorted(sat_contacts, key=lambda cn: cn.model.t_start)

            # Test all combinations of two contacts to see if they overlap
            # This could be done more efficiently, but the number of contacts is generally expected to be
            # small enough that this is not a problem
            for x, y in combinations(sat_contacts, 2):
                if x.model.t_start <= y.model.t_end and y.model.t_start <= x.model.t_end:
                    self.constraints.append(pk.constraint(x.var + y.var <= 1))

class StationContactExclusionConstraint(pk.block, GSOptConstraint):
    """
    Enforces that a station cannot have contacts with two different satellites at the same time.
    """

    def __init__(self, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self)

    @time_milp_generation
    def _generate_constraints(self,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Filter contacts by station
        contact_nodes_by_station = sorted(contact_nodes.values(), key=lambda cn: str(cn.station.id))

        for sat_id, sta_contacts in groupby(contact_nodes_by_station, lambda cn: cn.station.id):

            # Sort contacts by start time
            sta_contacts = sorted(sta_contacts, key=lambda cn: cn.model.t_start)

            # Test all combinations of two contacts to see if they overlap
            # This could be done more efficiently, but the number of contacts is generally expected to be
            # small enough that this is not a problem
            for x, y in combinations(sta_contacts, 2):
                if x.model.t_start <= y.model.t_end and y.model.t_start <= x.model.t_end:
                    self.constraints.append(pk.constraint(x.var + y.var <= 1))


class MaxContactGapConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces that the time between two contacts for any satellite is less than or equal to a given
    time period.

    Args:
        value (float): The maximum time between contacts in seconds.
    """

    def __init__(self, value: float | None = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, value=value)

        if not value:
            raise ValueError("Value must be provided.")

        self.value = value

    @time_milp_generation
    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # Group contacts by satellite
        contact_nodes_by_satellite = sorted(contact_nodes.values(), key=lambda cn: cn.satellite.id)

        self.variable_dict = pk.variable_dict()

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
                    self.constraints.append(pk.constraint(self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] <= contact_nodes[cn_i.id].var))
                    self.constraints.append(pk.constraint(self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] <= contact_nodes[cn_j.id].var))

                    # Add constraint to ensure that the associated scheduled gap is less than the maximum
                    self.constraints.append(pk.constraint((cn_j.model.t_start - cn_i.model.t_end) * self.variable_dict[(sat_id, cn_i.model.id, cn_j.model.id)] <= self.value))

                # Add constraint that only one of the auxiliary variables can be 1 if the contact node is scheduled
                self.constraints.append(pk.constraint(expr == contact_nodes[cn_i.id].var))


class MaxProvidersConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces the number of ground station providers that can be selected is less than or equal to
    the given number.
    """

    def __init__(self, num_providers: int = 1, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, num_providers=num_providers)

        self.num_providers = num_providers

    @time_milp_generation
    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        self.constraints.append(pk.constraint(sum(pn.var for pn in provider_nodes.values()) <= self.num_providers))


class MinContactDurationConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces the minimum duration of a contact between a satellite and a ground station is greater than
    or equal to the given time period.
    """

    def __init__(self, min_duration: float = 300, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, min_duration=min_duration)

        if min_duration <= 0:
            raise ValueError("Minimum duration must be greater than zero.")

        self.min_duration = min_duration

    @time_milp_generation
    def _generate_constraints(self, contact_nodes: dict[str, ContactNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        for cn in contact_nodes.values():
            if cn.model.t_duration <= self.min_duration:
                # Force all contacts with duration less than the minimum to be zero
                self.constraints.append(pk.constraint(cn.var == 0))


class MaxContactsPerPeriodConstraint(pk.block, GSOptConstraint):
    """
    Constraint that enforces that the total number of contacts in any given period is less than or equal to the given
    limit. The usual period is a day.

    Args:
        value (int): The maximum number of contacts allowed in the period.
        period (float): The period over which the value is enforced in seconds.
        step (float): The interval at which the constraint is enforced in seconds.
    """

    def __init__(self, value: int = 16, period: float = 86400.0, step: float = 300, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, value=value, period=period, step=step)

        if period <= 0:
            raise ValueError("Period must be greater than zero.")

        if value <= 0:
            raise ValueError("Limit must be greater than zero.")

        if step <= 0:
            raise ValueError("Step must be greater than zero.")

        self.value = value
        self.period = period
        self.step = step

    @time_milp_generation
    def _generate_constraints(self, provider_nodes: dict[str, ProviderNode] | None = None,
                             station_nodes: dict[str, StationNode] | None = None,
                             contact_nodes: dict[str, ContactNode] | None = None,
                             opt_window: OptimizationWindow | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        ts = copy.deepcopy(opt_window.sim_start)  # Working variable for the start of the current period
        te = copy.deepcopy(ts + self.period)      # Working variable for the end of the current period

        t_max = opt_window.sim_end  # The end of the constraint period

        # Get contacts in the current period, sorted by start time
        contacts = sorted(contact_nodes.values(), key=lambda cn: cn.model.t_start)

        while te <= t_max:
            # Get contacts in the current period
            contacts_in_period = filter(lambda cn: cn.model.t_end >= ts and cn.model.t_start <= te, contacts)

            # Add the constraint
            self.constraints.append(pk.constraint(sum(contact_nodes[cn.id].var for cn in contacts_in_period) <= self.value))

            # Move to the next period
            ts += self.step
            te += self.step


class RequireProviderConstraint(pk.block, GSOptConstraint):
    """
    Constraint to require a specific provider to be selected.
    """

    def __init__(self, key: str = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, key=key)

        if key is None:
            raise ValueError("A unique key (id or name) for the provider must be provided")

        self.key = key
        self._matched_id = None

    @time_milp_generation
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

        self.constraints.append(pk.constraint(provider_nodes[self._matched_id].var == 1))


class RequireStationConstraint(pk.block, GSOptConstraint):
    """
    Constraint to require a specific station to be selected.
    """

    def __init__(self, id: str | None = None, name: str | None = None, provider: str | None = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, id=id, name=name, provider=provider)

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

    @time_milp_generation
    def _generate_constraints(self, station_nodes: dict[str, StationNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        # If and ID was provided, attempt to match it
        if self.required_id is not None:
            if self.required_id in station_nodes.keys():
                self.constraints.append(pk.constraint(station_nodes[self.required_id].var == 1))
                return
            else:
                raise RuntimeError(f"Could not find a station with id \"{self.required_id}\".")

        # Otherwise attempt to match the name and provider
        for sn in station_nodes.values():
            if sn.model.name.lower() == self.required_name.lower() and sn.model.provider.lower() == self.required_provider.lower():
                self.constraints.append(pk.constraint(station_nodes[sn.id].var == 1))
                return

        raise RuntimeError(f"Could not find a station with name \"{self.required_name}\" and provider \"{self.required_provider}\".")

class StationNumberConstraint(pk.block, GSOptConstraint):
    """
    Constraint to require a specific number of stations to be selected. The minimum, maximum, or both bounds
    must be provided. If a provider is provided then the constraint is applied to the stations of that provider.
    """

    def __init__(self, minimum: int | None = None, maximum: int | None = None, provider: str | None = None, **kwargs):
        pk.block.__init__(self)
        GSOptConstraint.__init__(self, minimum=minimum, maximum=maximum, provider=provider)

        self.minimum = minimum
        self.maximum = maximum
        self.provider = provider

        if minimum is None and maximum is None:
            raise ValueError("Either the minimum or maximum number of stations must be provided.")

    @time_milp_generation
    def _generate_constraints(self, station_nodes: dict[str, StationNode] | None = None, **kwargs):
        """
        Generate the constraint_list function.
        """

        if self.provider is not None:
            station_nodes = filter(lambda sn: sn.model.provider == self.provider, station_nodes.values())
        else:
            station_nodes = station_nodes.values()

        if self.minimum is not None:
            self.constraints.append(pk.constraint(sum(sn.var for sn in station_nodes) >= self.minimum))

        if self.maximum is not None:
            self.constraints.append(pk.constraint(sum(sn.var for sn in station_nodes) <= self.maximum))