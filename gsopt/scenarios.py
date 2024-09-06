"""
This module contains helper functions for generating different simulation scenarios for evaluation and demonstration.
"""

import copy
import random
import os
import pathlib

import polars as pl
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from gsopt.ephemeris import get_satcat_df
from gsopt.models import GroundStationProvider, OptimizationWindow, Satellite
from gsopt.widgets import satellites_from_dataframe

# Get directory of current file
DIR = pathlib.Path(__file__).parent.absolute()

PROVIDERS = os.listdir(DIR / '..' / 'data' / 'groundstations')

CONSTELLATIONS = sorted(['YAM', 'UMBRA', 'SKYSAT', 'ICEYE', 'FLOCK', 'HAWK', 'CAPELLA', 'LEGION', 'WORLDVIEW', 'GEOEYE',
                  'NUSAT'])

class Random(random.Random):
    """
    Custom Random class that allows for seeding with a string or bytes object. This is useful for reproducibility.
    It also allows for retrieving the current seed value.
    """

    def seed(self, a=None, version=2, num_bytes=2500):
        # Note num_bytes should normally be really big (like 2500) to ensure that the seed is long enough to span the
        # entire state space of the Mersenne Twister. However, for the purposes of this project, we don't need to worry
        # about that.
        from os import urandom as _urandom
        from hashlib import sha512 as _sha512
        if a is None:
            try:
                # Seed with enough bytes to span the 19937 bit
                # state space for the Mersenne Twister
                a = int.from_bytes(_urandom(num_bytes), 'big')
            except NotImplementedError:
                import time
                a = int(time.time() * 256)  # use fractional seconds

        if version == 2:
            if isinstance(a, (str, bytes, bytearray)):
                if isinstance(a, str):
                    a = a.encode()
                a += _sha512(a).digest()
                a = int.from_bytes(a, 'big')

        self._current_seed = a
        super().seed(a)

    def get_seed(self):
        return self._current_seed

class Scenario():
    def __init__(self, opt_window: OptimizationWindow, providers: list[GroundStationProvider], satellites: list[Satellite], seed=None):
        self.opt_window = opt_window
        self.providers = providers
        self.satellites = satellites
        self.seed = seed

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        for provider in self.providers:
            console.print(provider)

            for station in provider.stations:
                console.print(station)

        for satellite in self.satellites:
            console.print(satellite)

        tbl = Table(title='Scenario Summary')
        tbl.add_column('Property')
        tbl.add_column('Value')

        tbl.add_row('Optimization Window', f'{self.opt_window.opt_start} to {self.opt_window.opt_end}')
        tbl.add_row('Simulation Window', f'{self.opt_window.sim_start} to {self.opt_window.sim_end}')
        tbl.add_row('Number of Providers', str(len(self.providers)))
        tbl.add_row('Number of Satellites', str(len(self.satellites)))
        tbl.add_row('Seed', str(hex(self.seed)))

        yield tbl

class ScenarioGenerator():

    def __init__(self, opt_window: OptimizationWindow | None = None, seed=None):
        # Create a random number generator
        self.seed = None
        self._rng = Random(seed)

        # Initialize storage variables
        self.providers = []
        self.satellites = []
        self.opt_window = opt_window

        # Load the satellite catalog data from Celestrak
        self._satcat_df = get_satcat_df()

        # Store randomization parameters
        self._sat_datarate_ranges = {'default': (0.9e9, 1.8e9)}
        self._provider_elevation_min = {'default': 10.0}
        self._provider_integration_cost = {'default': (50000.0, 200000.0)}
        self._provider_setup_cost = {'default': (10000.0, 100000.0)}
        self._provider_per_satellite_license_cost = {'default': (1000.0, 5000.0)}
        self._provider_monthly_cost = {'default': (200.0, 5000.0)}
        self._provider_datarate = {'default': (1.2e9, 2.0e9)}
        self._provider_probability_of_pass_pricing = {'default': 0.5}
        self._provider_cost_per_pass = {'default': (25.0, 175.0)}
        self._provider_cost_per_minute = {'default': (5.0, 35.0)}
        self._provider_num_antennas = {'default': (1, 3)}

    def set_seed(self, seed):
        self._rng.seed(seed)

    def add_provider(self, provider: str):

        if provider not in PROVIDERS:
            raise ValueError(f'Provider {provider} not found in {PROVIDERS}')

        provider_file = DIR / '..' / 'data' / 'groundstations' / provider

        with open(provider_file, 'r') as f:
            self.providers.append(GroundStationProvider.load_geojson(f))

    def add_all_providers(self):
        for provider in PROVIDERS:
            self.add_provider(provider)

    def _set_provider_property(self, property_name, value, provider_name=None):
        if provider_name is None:
            getattr(self, f'_provider_{property_name}')['default'] = value

        else:
            if provider_name not in self.get_provider_names():
                raise ValueError(f'Provider {provider_name} not found in scenario providers. Add the provider before setting the property')

            getattr(self, f'_provider_{property_name}')[provider_name] = value

    def set_provider_elevation_min(self, elevation_min: float, provider_name: str | None = None):
        """
        Set the minimum elevation angle. This is the minimum angle above the horizon that a satellite must be to be
        visible to the ground station.

        If provider_name is None, the elevation angle will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            elevation_min (float): Minimum elevation angle in degrees
            provider_name (str): Name of the provider to set the elevation angle for. Optional.
        """
        self._set_provider_property('elevation_min', elevation_min, provider_name)

    def set_provider_integration_cost(self, integration_cost_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the integration cost for the ground station provider. This is the one-time cost to integrate with the
        provider network.

        If provider_name is None, the integration cost will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            integration_cost_range (tuple): Tuple of the form (min, max) representing the range of integration costs to
                sample from
            provider_name (str): Name of the provider to set the integration cost for. Optional.
        """
        self._set_provider_property('integration_cost', integration_cost_range, provider_name)

    def set_provider_setup_cost(self, setup_cost_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the setup cost for the ground station provider. This is the one-time cost to set up a new ground station.

        If provider_name is None, the setup cost will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            setup_cost_range (tuple): Tuple of the form (min, max) representing the range of setup costs to sample from
            provider_name (str): Name of the provider to set the setup cost for. Optional.
        """

        self._set_provider_property('setup_cost', setup_cost_range, provider_name)

    def set_provider_per_satellite_license_cost(self, per_satellite_license_cost_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the per-satellite license cost for the ground station provider. This is the cost to license a new satellite
        for use with the provider network.

        If provider_name is None, the per-satellite license cost will be set for all providers. Otherwise, it will be
        set for the specified provider.

        Args:
            per_satellite_license_cost_range (tuple): Tuple of the form (min, max) representing the range of license costs
                to sample from
            provider_name (str): Name of the provider to set the license cost for. Optional.
        """
        self._set_provider_property('per_satellite_license_cost', per_satellite_license_cost_range, provider_name)

    def set_provider_monthly_cost(self, monthly_cost_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the monthly cost for the ground station provider. This is the cost per month to maintain a ground station.

        If provider_name is None, the monthly cost will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            monthly_cost_range (tuple): Tuple of the form (min, max) representing the range of monthly costs to sample from
            provider_name (str): Name of the provider to set the monthly cost for. Optional.
        """
        self._set_provider_property('monthly_cost', monthly_cost_range, provider_name)

    def set_provider_datarate(self, datarate_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the maximum data rate for the ground station provider. This is the maximum data rate that the provider can
        support.

        If provider_name is None, the data rate will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            datarate_range (tuple): Tuple of the form (min, max) representing the range of data rates to sample from
            provider_name (str): Name of the provider to set the data rate for. Optional.
        """
        self._set_provider_property('datarate', datarate_range, provider_name)

    def set_provider_probability_of_pass_pricing(self, probability_of_pass_pricing: float, provider_name: str | None = None):
        """
        Set the probability of pass pricing for the ground station provider. This is the probability that the provider
        will charge per pass rather than per minute.

        If provider_name is None, the probability of pass pricing will be set for all providers. Otherwise, it will be
        set for the specified provider.

        Args:
            probability_of_pass_pricing (float): Probability of pass pricing, between 0 and 1
            provider_name (str): Name of the provider to set the probability of pass pricing for. Optional.

        """
        self._set_provider_property('probability_of_pass_pricing', probability_of_pass_pricing, provider_name)

    def set_provider_cost_per_pass(self, cost_per_pass_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the cost per pass for the ground station provider. This is the cost to download data from a satellite during a
        single pass.

        If provider_name is None, the cost per pass will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            cost_per_pass_range (tuple): Tuple of the form (min, max) representing the range of pass costs to sample from
            provider_name (str): Name of the provider to set the pass cost for. Optional.

        """
        self._set_provider_property('cost_per_pass', cost_per_pass_range, provider_name)

    def set_provider_cost_per_minute(self, cost_per_minute_range: tuple[float, float], provider_name: str | None = None):
        """
        Set the cost per minute for the ground station provider. This is the cost to download data from a satellite for
        each minute of contact time.

        If provider_name is None, the cost per minute will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            cost_per_minute_range (tuple): Tuple of the form (min, max) representing the range of minute costs to sample from
            provider_name (str): Name of the provider to set the minute cost for. Optional.

        """
        self._set_provider_property('cost_per_minute', cost_per_minute_range, provider_name)

    def set_provider_num_antennas(self, num_antennas_range: tuple[int, int], provider_name: str | None = None):
        """
        Set the number of antennas for the ground station provider. This is the number of antennas at each ground station.

        If provider_name is None, the number of antennas will be set for all providers. Otherwise, it will be set for the
        specified provider.

        Args:
            num_antennas_range (tuple): Tuple of the form (min, max) representing the range of antennas to sample from
            provider_name (str): Name of the provider to set the antennas for. Optional.

        """
        self._set_provider_property('num_antennas', num_antennas_range, provider_name)

    def set_satellite_random_datarate(self, datarate_range: tuple[float, float], sat_id: str | None = None):
        if sat_id is None:
            self._sat_datarate_ranges['default'] = datarate_range

        else:
            if sat_id not in self.satellite_ids():
                raise ValueError(f'Satellite {sat_id} not found in scenario satellites. Add the satellite before setting the datarate.')

            self._sat_datarate_ranges[sat_id] = datarate_range

    def add_constellation(self, name=str):
        """
        Add a constellation of satellites to the scenario generator

        Args:
            name: str: Name of the constellation to add. Must be one of the following:
                - YAM
                - UMBRA
                - SKYSAT
                - ICEYE
                - FLOCK
                - HAWK
                - CAPELLA
                - LEGION
                - WORLDVIEW
                - GEOEYE

        """
        if name.upper() not in CONSTELLATIONS:
            raise ValueError(f'Constellation {name} not found in {CONSTELLATIONS}')

        constellation_sats = self._satcat_df.filter(pl.col('object_name').str.contains(name.upper()))

        self.satellites.extend(satellites_from_dataframe(constellation_sats))

    def add_satellite(self, sat_id: str):
        """
        Add a specific satellite to the scenario generator

        Args:
            sat_id: str: NORAD ID of the satellite to add
        """
        sat = self._satcat_df.filter(pl.col('satcat_id') == sat_id)
        self.satellites.extend(satellites_from_dataframe(sat))

    def add_random_satellites(self, num_satellites: int, alt_range: tuple = (300, 1000)):
        """
        Add a random selection of satellites to the scenario generator

        Args:
            num_satellites: int: Number of random satellites to add
            sma_range: tuple: Range of altitudes to select random satellites from
        """

        # Get all satellites with altitudes within the specified range
        random_sats = self._satcat_df.filter(pl.col('altitude').is_between(alt_range[0], alt_range[1]))

        # Get all unique satellite NORAD IDs
        sat_ids = list(sorted(random_sats['satcat_id'].unique().to_list()))

        # Randomly select a subset of the satellite NORAD IDs
        selected_sat_ids = self._rng.sample(sat_ids, num_satellites)

        # Filter the satellite catalog DataFrame to only include the selected satellites
        selected_sats = self._satcat_df.filter(pl.col('satcat_id').is_in(selected_sat_ids))

        # Add the selected satellites to the scenario generator
        self.satellites.extend(satellites_from_dataframe(selected_sats))

    def satellite_ids(self):
        for sat in self.satellites:
            yield sat.satcat_id

    def provider_names(self):
        for provider in self.providers:
            yield provider.name

    def get_provider_names(self):
        return [p.name for p in self.providers]

    @property
    def num_satellites(self):
        return len(self.satellites)

    def get_seed(self):
        return self._rng.get_seed()

    def sample_scenario(self) -> Scenario:
        """
        Sample a scenario from the scenario generator

        Returns:
            Scenario: The sampled scenario
        """

        # Create copies of the providers and satellites

        opt_window = copy.deepcopy(self.opt_window)
        providers = [copy.deepcopy(p) for p in self.providers]
        satellites = [copy.deepcopy(s) for s in self.satellites]

        # Set properites for the providers based on the scenario generator settings
        for provider in providers:
            provider.set_property('elevation_min', self._provider_elevation_min.get(provider.name, self._provider_elevation_min['default']))
            provider.integration_cost = self._rng.uniform(*self._provider_integration_cost.get(provider.name, self._provider_integration_cost['default']))
            provider.set_property('setup_cost', self._rng.uniform(*self._provider_setup_cost.get(provider.name, self._provider_setup_cost['default'])))

            provider_cost_type = self._rng.uniform(0, 1) >= self._provider_probability_of_pass_pricing.get(provider.name, self._provider_probability_of_pass_pricing['default'])

            for station in provider.stations:

                # Randomize number of antennas
                provider.set_property('antennas', self._rng.randint(*self._provider_num_antennas.get(provider.name, self._provider_num_antennas['default'])), key=station.id)

                # Randomize monthly cost, per satellite license cost, and data rate for each station
                provider.set_property('monthly_cost', self._rng.uniform(
                    *self._provider_monthly_cost.get(provider.name, self._provider_monthly_cost['default'])),
                                      key=station.id)

                provider.set_property('per_satellite_license_cost', self._rng.uniform(
                    *self._provider_per_satellite_license_cost.get(provider.name,
                                                                   self._provider_per_satellite_license_cost[
                                                                       'default'])), key=station.id)

                provider.set_property('datarate', self._rng.uniform(
                    *self._provider_datarate.get(provider.name, self._provider_datarate['default'])),
                                      key=station.id)

                # Set station costs
                if provider_cost_type:
                    provider.set_property('cost_per_pass', self._rng.uniform(*self._provider_cost_per_pass.get(provider.name, self._provider_cost_per_pass['default'])), key=station.id)
                    provider.set_property('cost_per_minute', 0.0, key=station.id)
                else:
                    provider.set_property('cost_per_pass', 0.0, key=station.id)
                    provider.set_property('cost_per_minute', self._rng.uniform(*self._provider_cost_per_minute.get(provider.name, self._provider_cost_per_minute['default'])), key=station.id)

        # Set properties for the satellites based on the scenario generator settings
        for satellite in satellites:
            satellite.datarate = self._rng.uniform(*self._sat_datarate_ranges.get(satellite.satcat_id, self._sat_datarate_ranges['default']))

        # Create the scenario
        scenario = Scenario(opt_window, providers, satellites, self._rng.get_seed())

        # Reinitialize the random number generator to ensure reproducibility
        if self.seed is None:
            self._rng = Random()

        return scenario
