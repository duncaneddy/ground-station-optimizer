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
from rich import table
import logging
from abc import abstractmethod, ABCMeta

from gsopt import utils
from gsopt.models import GroundStation, GroundStationNetwork, Satellite, OptimizationWindow

logger = logging.getLogger()

class SolverStatus(Enum):
    """
    Enumeration of possible solver statuses.
    """
    NOT_SOLVED = 0
    SOLVED = 1
    ERROR = 2


class GroundStationOptimizer(metaclass=ABCMeta):

    def __init__(self, opt_window: OptimizationWindow):
        super().__init__()

        self.opt_window = opt_window

        # Problem inputs
        self.satellites = []
        self.networks = []

        # Working variables
        self.contacts = []

        # Common optimization problem variables
        self.solver_status = SolverStatus.NOT_SOLVED
        self.solve_time = 0.0
        self.contact_compute_time = 0.0

    def add_satellite(self, satellite: Satellite):
        self.satellites.append(satellite)

    def add_network(self, network: GroundStationNetwork):
        """
        Add a station network to the optimizer.
        """
        self.networks.append(network)

    def get_network(self, key: str | int):
        """
        Get a network by name or index.
        """
        if isinstance(key, int):
            return self.networks[key]
        elif isinstance(key, str):
            for network in self.networks:
                if network.name == key:
                    return network

            raise ValueError(f"Network with name {key} not found")
        else:
            raise ValueError("Invalid key type")

    @property
    def stations(self):
        """
        Get all stations in all networks.
        """
        stations = []
        for network in self.networks:
            stations.extend(network.stations)

        return stations

    def compute_contacts(self):
        """
        Compute all contacts between the satellites and ground stations.
        """

        # Get contact computation window times
        t_start = Epoch(self.opt_window.sim_start)
        t_end = Epoch(self.opt_window.sim_end)

        t_duration = t_end - t_start

        logger.info(f"Computing contacts for {len(self.satellites)} satellites and {len(self.networks)} networks over {utils.get_time_string(t_duration)} period...")

        ts = time.perf_counter()

        # Check that the simulation window is within the EOP
        utils.initialize_eop() # Ensure EOP is initialized before checking
        if t_end.mjd() > max(bh.EOP._data.keys()):
            msg = f"Simulation end time {self.opt_window.sim_end} is after the EOP end time {max(bh.EOP._data.keys())}"
            logger.error(msg)
            raise RuntimeError(msg)

        # Generate work
        tasks = []
        for network in self.networks:
            for station in network.stations:
                for sc in self.satellites:
                    tasks.append((station, sc, t_start, t_end))

        # Compute contacts
        mpctx = mp.get_context('fork')
        with mpctx.Pool(mp.cpu_count()) as pool:

            results = pool.starmap(utils.compute_contacts, tasks)

            for r in results:
                # convert result back to Contact objects

                self.contacts.extend(r)

        te = time.perf_counter()

        self.contact_compute_time = te - ts
        logger.info(f"Contacts computed successfully. Found {len(self.contacts)} contacts. Took {utils.get_time_string(self.contact_compute_time)}.")

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

        for network in self.networks:
            network.set_property('elevation_min', elevation_min)

    def __rich_console__(self):
        raise NotImplementedError
