'''
This module contains the base GroundStationOptimizer class, which allows for the definition of
the problem of ground station selection and optimization.
'''
import time
import multiprocessing as mp
import brahe as bh
from enum import Enum
from pathlib import Path

from brahe import Epoch
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table
import logging
from abc import abstractmethod, ABCMeta

from gsopt import utils
from gsopt.models import GroundStation, GroundStationProvider, Satellite, OptimizationWindow

logger = logging.getLogger()

class GroundStationOptimizer(metaclass=ABCMeta):

    def __init__(self, opt_window: OptimizationWindow, verbose: bool = False, time_limit: float | None = None):
        super().__init__()

        self.verbose = verbose
        self.time_limit = time_limit

        self.opt_window = opt_window

        # Problem inputs
        self.satellites = {}
        self.providers = {}
        self.stations = {}

        # Working variables
        self.contacts = {}

        # Common optimization problem variables
        self.solver_status = 'Not Solved'
        self.solve_time = 0.0
        self.contact_compute_time = 0.0
        self.problem_setup_time = 0.0

    def add_satellite(self, satellite: Satellite):
        self.satellites[satellite.id] = satellite

    def add_provider(self, provider: GroundStationProvider):
        """
        Add a station provider to the optimizer.
        """
        self.providers[provider.id] = provider

        for station in provider.stations:
            self.stations[station.id] = station

    @classmethod
    def from_scenario(cls, scenario):
        """
        Create a GroundStationOptimizer from a ScenarioGenerator object.
        """
        opt_window = scenario.opt_window
        optimizer = cls(opt_window)

        for sat in scenario.satellites:
            optimizer.add_satellite(sat)

        for provider in scenario.providers:
            optimizer.add_provider(provider)

        return optimizer

    @property
    def provider_ids(self):
        return list(self.providers.keys())

    @property
    def station_ids(self):
        return list(self.stations.keys())

    @property
    def satellite_ids(self):
        return list(self.satellites.keys())

    def compute_contacts(self):
        """
        Compute all contacts between the satellites and ground stations.
        """

        # Get contact computation window times
        t_start = Epoch(self.opt_window.sim_start)
        t_end = Epoch(self.opt_window.sim_end)

        t_duration = t_end - t_start

        logger.info(f"Computing contacts for {len(self.satellites)} satellites and {len(self.providers)} providers, {len(self.stations)} stations, over {utils.get_time_string(t_duration)} period...")

        ts = time.perf_counter()

        # Check that the simulation window is within the EOP
        utils.initialize_eop() # Ensure EOP is initialized before checking
        if t_end.mjd() > max(bh.EOP._data.keys()):
            msg = f"Simulation end time {self.opt_window.sim_end} ({self.opt_window.sim_end.mjd()}) is after the EOP end time {max(bh.EOP._data.keys())}"
            logger.error(msg)
            raise RuntimeError(msg)

        # Generate work
        tasks = []
        for station in self.stations.values():
            for sc in self.satellites.values():
                tasks.append((station, sc, t_start, t_end))

        # Compute contacts
        mpctx = mp.get_context('fork')
        with mpctx.Pool(mp.cpu_count()) as pool:

            results = pool.starmap(utils.compute_contacts, tasks)

            for r in results:
                # convert result back to Contact objects

                for c in r:
                    self.contacts[c.id] = c

        te = time.perf_counter()

        self.contact_compute_time = te - ts
        logger.info(f"Contacts computed successfully. Found {len(self.contacts)} contacts. Took {utils.get_time_string(self.contact_compute_time)}.")

    def contact_list(self):
        """
        Return a list of contacts.
        """
        return list(self.contacts.values())

    @abstractmethod
    def solve(self):
        pass

    @abstractmethod
    def write_solution(self, output_file: Path):
        pass

    def set_access_constraints(self, elevation_min: float):
        """
        Set the minimum elevation angle for a contact to be considered.
        """

        for provider in self.providers:
            provider.set_property('elevation_min', elevation_min)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        raise NotImplementedError

    def set_verbose(self, verbose: bool):
        self.verbose = verbose

    def set_time_limit(self, time_limit: float):
        self.time_limit = time_limit
