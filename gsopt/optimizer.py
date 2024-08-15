'''
This module contains the base GroundStationOptimizer class, which allows for the definition of
the problem of ground station selection and optimization.
'''
from enum import Enum
from pathlib import Path

from rich import table
import logging
from abc import abstractmethod, ABCMeta

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

        # Workign variables
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

    def compute_contacts(self):
        """
        Compute all contacts between the satellites and ground stations.
        """
        pass

        # Settings for elevation thresholds
        #

    @abstractmethod
    def solve(self):
        pass

    @abstractmethod
    def write_solution(self, output_file: Path):
        pass

    def __rich_console__(self):
        raise NotImplementedError
