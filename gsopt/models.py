import enum
import uuid
import json
import logging
from datetime import datetime, timedelta
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table

from brahe import TLE, tle_string_from_elements, mean_motion, Epoch, sun_sync_inclination, R_EARTH
import brahe.data_models as bdm

logger = logging.getLogger(__name__)

class DataUnits(enum.Enum):
    b = 1
    bits = b
    B = 8
    bytes = B
    Kb = 1e3
    kilobits = Kb
    KB = 8 * 1e3
    kilobytes = KB
    Mb = 1e6
    megabits = Mb
    MB = 8 * 1e6
    megabytes = MB
    Gb = 1e9
    gigabits = Gb
    GB = 8 * 1e9
    gigabytes = GB
    Tb = 1e12
    terabits = Tb
    TB = 8 * 1e12
    terabytes = TB


class OptimizationWindow():

    def __init__(self, opt_start: datetime | Epoch | str, opt_end: datetime | Epoch | str, sim_start: datetime | Epoch | str, sim_end: datetime | Epoch | str):

        if not opt_start or not opt_end:
            raise ValueError("Optimization window must have start and end times")

        if not sim_start or not sim_end:
            logger.debug("No simulation window provided. Using default 7-day simulation window")
            sim_start = Epoch(opt_start)
            sim_end = sim_start + 7 * 86400.0

        self.opt_start = Epoch(opt_start)
        self.opt_end = Epoch(opt_end)
        self.sim_start = Epoch(sim_start)
        self.sim_end = Epoch(sim_end)

        if opt_start > opt_end:
            raise ValueError("Optimization start time must be before optimization end time")

        if sim_start > sim_end:
            raise ValueError("Simulation start time must be before simulation end time")

        self.T_opt = self.opt_end - self.opt_start
        self.T_sim = self.sim_end - self.sim_start

    @property
    def sim_duration(self):
        """
        Get the duration of the simulation window in seconds.

        Returns:
            - float: Duration of the simulation window in seconds
        """
        return self.sim_end - self.sim_start

    @property
    def opt_duration(self):
        """
        Get the duration of the optimization window in seconds.

        Returns:
            - float: Duration of the optimization window in seconds
        """
        return self.opt_end - self.opt_start

    def as_dict(self):
        return {
            'opt_start': self.opt_start.isoformat(),
            'opt_end': self.opt_end.isoformat(),
            'sim_start': self.sim_start.isoformat(),
            'sim_end': self.sim_end.isoformat()
        }

class GroundStation():

    def __init__(self, name: str, longitude: float, latitude: float,
                 altitude: float = 0.0,
                 id: str | None = None,
                 provider: str | None = None,
                 provider_id: str | None = None,
                 elevation_min: float = 0.0,
                 datarate: float = 0.0,
                 setup_cost: float = 0.0,
                 per_satellite_license_cost: float = 0.0,
                 monthly_cost: float = 0.0,
                 cost_per_pass: float = 0.0,
                 cost_per_minute: float = 0.0,
                 antennas: int = 1,
                 ):

        if not name:
            raise ValueError("Ground station must have a name")

        if longitude < -180 or longitude > 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")

        if latitude < -90 or latitude > 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")

        if altitude < 0:
            raise ValueError("Altitude must be greater than or equal to 0")

        self.id = id

        if not id:
            self.id = str(uuid.uuid4())

        self.name = name
        self.provider = provider
        self.provider_id = provider_id
        self.longitude = longitude
        self.latitude = latitude
        self.altitude = altitude
        self.elevation_min = elevation_min

        # Set cost objects
        self.setup_cost = setup_cost
        self.per_satellite_license_cost = per_satellite_license_cost
        self.monthly_cost = monthly_cost
        self.cost_per_pass = cost_per_pass
        self.cost_per_minute = cost_per_minute

        # Set data rate
        self.datarate = datarate

        # Set antenna count
        self.antennas = antennas

    @classmethod
    def from_geojson(cls, data: dict):
        """
        Create a GroundStation object from a GeoJSON dictionary
        """

        properties = data['properties']
        geometry = data['geometry']

        if geometry['type'] != 'Point':
            raise ValueError("Only Point geometries are supported")

        if 'provider' not in properties:
            raise ValueError("Missing 'provider' property")

        if 'name' not in properties:
            raise ValueError("Missing 'name' property")

        return cls(
            id=properties['id'] if 'id' in properties else None,
            name=properties['name'],
            provider=properties['provider'],
            provider_id=properties['provider_id'] if 'provider_id' in properties else None,
            longitude=geometry['coordinates'][0],
            latitude=geometry['coordinates'][1],
            altitude=geometry['coordinates'][2] if len(geometry['coordinates']) > 2 else 0.0,
            elevation_min=properties['elevation_min'] if 'elevation_min' in properties else 0.0,
            datarate=properties['datarate'] if 'datarate' in properties else 0.0,
            setup_cost=properties['setup_cost'] if 'setup_cost' in properties else 0.0,
            per_satellite_license_cost=properties['per_satellite_license_cost'] if 'per_satellite_license_cost' in properties else 0.0,
            monthly_cost=properties['monthly_cost'] if 'monthly_cost' in properties else 0.0,
            cost_per_pass=properties['cost_per_pass'] if 'cost_per_pass' in properties else 0.0,
            cost_per_minute=properties['cost_per_minute'] if 'cost_per_minute' in properties else 0.0,
            antennas=properties['antennas'] if 'antennas' in properties else 1
        )

    @property
    def lon(self):
        return self.longitude

    @property
    def lat(self):
        return self.latitude

    @property
    def alt(self):
        return self.altitude

    def as_brahe_model(self):
        return bdm.Station(
            **{
                "properties": {
                    "constraints": bdm.AccessConstraints(elevation_min=self.elevation_min),
                    "name": self.name,
                },
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [self.longitude, self.latitude, self.altitude]
                },
            }
        )

    def as_geojson(self):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.lon, self.lat, self.alt]
            },
            "properties": {
                "id": self.id,
                "name": self.name,
                "provider": self.provider,
                "elevation_min": self.elevation_min,
                "datarate": self.datarate,
                "setup_cost": self.setup_cost,
                "per_satellite_license_cost": self.per_satellite_license_cost,
                "monthly_cost": self.monthly_cost,
                "cost_per_pass": self.cost_per_pass,
                "cost_per_minute": self.cost_per_minute,
                "antennas": self.antennas
            }
        }

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        tbl = Table(title=f"{self.name.capitalize()} Station")

        tbl.add_column("Property", justify="left")
        tbl.add_column("Value")

        tbl.add_row("Name", self.name)
        tbl.add_row("Id", self.id)
        tbl.add_row("Provider", self.provider)
        tbl.add_row("Provider Id", self.provider_id)
        tbl.add_row("Longitude [deg]", f"{self.lon:.3f}")
        tbl.add_row("Latitude [deg]", f"{self.lat:.3f}")
        tbl.add_row("Altitude [m]", f"{self.alt:.3f}")
        tbl.add_row("Elevation Min [deg]", f"{self.elevation_min:.3f}")
        tbl.add_row("Setup Cost", f"${self.setup_cost:.2f}")
        tbl.add_row("Per Satellite License Cost", f"${self.per_satellite_license_cost:.2f}")
        tbl.add_row("Monthly Cost", f"${self.monthly_cost:.2f}")
        tbl.add_row("Cost per Pass", f"${self.cost_per_pass:.2f}")
        tbl.add_row("Cost per Minute", f"${self.cost_per_minute:.2f}")
        tbl.add_row("Data Rate [Mbps]", f"{self.datarate * 1e-6:.3f}")
        tbl.add_row("Antennas", f"{self.antennas:d}")

        yield tbl

class GroundStationProvider():
    """
    A GroundStationProvider represents the ground stations of a single ground station provider.
    """

    def __init__(self, stations: list[GroundStation] | None = None,
                 integration_cost: float = 0.0, id: str | None = None):

        self.provider = None
        self.id = id if id else str(uuid.uuid4())

        if not stations:
            self.stations = []
        else:
            self.stations = stations

        # Ensure all stations have the same provider ID
        for sta in self.stations:
            sta.provider_id = self.id

        if len(self.stations) > 0:
            self.provider = self.stations[0].provider

            # Check consistency of provider
            for sta in self.stations:
                if sta.provider != self.provider:
                    raise RuntimeError(f"Found unexpected provider \"{sta.provider}\". All stations in a provider must "
                                       f"share the same provider.")

        # Create Lookups:
        self._station_id_lookup = {sta.id: sta for sta in self.stations}
        self._station_name_lookup = {sta.name: sta for sta in self.stations}

        self.integration_cost = integration_cost

    @property
    def name(self):
        return self.provider

    @classmethod
    def load_geojson(cls, data, integration_cost: float = 0.0):
        """
        Load a GroundStationProvider from a GeoJSON dictionary

        Args:
            - data (dict): The GeoJSON dictionary to load
        """

        if "type" not in data.keys():
            raise RuntimeError("File missing expected GeoJSON field \"type\"")

        if data["type"] == "FeatureCollection":

            stations = [GroundStation.from_geojson(obj) for obj in data["features"]]

            integration_cost = 0.0
            id = None

            if "properties" in data and "properties" in data:
                if "integration_cost" in data["properties"]:
                    integration_cost = data["properties"]["integration_cost"]

                if "id" in data["properties"]:
                    id = data["properties"]["id"]


            return cls(stations, integration_cost=integration_cost, id=id)

        elif data["type"] == "Feature":
            station = GroundStation.from_geojson(data)

            return cls([station], integration_cost=integration_cost)

        else:
            raise RuntimeError(f"Found unsupported GeoJSON type \"{data['type']}\"")

    @classmethod
    def load_geojson_file(cls, f, integration_cost: float = 0.0):
        """
        Load a GroundStationProvider from a GeoJSON file

        Args:
            - f (file): The file to load. Should be a file-pointer to a GeoJSON file.
        """

        data = json.load(f)

        return cls.load_geojson(data, integration_cost=integration_cost)

    def as_brahe_model(self):
        return [sta.as_brahe_model() for sta in self.stations]

    def as_dict(self):
        return {
            "type": "FeatureCollection",
            "features": [sta.as_geojson() for sta in self.stations],
            "properties": {
                "provider": self.provider,
                "id": self.id,
                "integration_cost": self.integration_cost
            }
        }

    def get(self, key: str) -> GroundStation | ValueError:
        """
        Get a specific Ground Station object by ID or name. Returns and error if not found

        :param key: String of either a station ID or name value
        :return: GroundStation
        """

        if key in self._station_id_lookup:
            return self._station_id_lookup[key]
        elif key in self._station_name_lookup:
            return self._station_name_lookup[key]
        else:
            raise ValueError(f"No station with identifier \"{key}\" found in {self.provider} provider.")

    def set_property(self, property: str, value: float, key: str | None = None):
        """
        Set a property for all stations in the provider. If a provider is provided then only stations with that
        provider will be updated.

        Args:
            - property (str): The property to set
            - value (float): The value to set the property to
            - key (str): ID of specific station to update
        """

        if property not in ['cost_per_pass', 'cost_per_minute', 'per_satellite_license_cost', 'monthly_cost', 'setup_cost', 'elevation_min', 'datarate', 'antennas']:
            raise ValueError(f"\"{property}\" is not a settable property")

        if value < 0.0:
            raise ValueError("Property value must be greater than 0")

        # Set single station property if key is provided
        if key:
            setattr(self.get(key), property, value)
        else:
            for sta in self.stations:
                setattr(sta, property, value)

    def __iadd__(self, other: GroundStation):
        """
        Add new ground station to the provider.

        :param other: Ground Station to add to the provider
        :return:
        """
        return self + other

    def __add__(self, other: GroundStation):
        if self.provider is not None and other.provider != self.provider:
            raise RuntimeError("Cannot add ground station from different provider to provider")

        if self.provider is None and other.provider is not None:
            self.provider = other.provider

        # Update data store and lookups
        self.stations.append(other)
        self._station_id_lookup[other.id] = other
        self._station_name_lookup[other.name] = other

        return self

    def __len__(self):
        return len(self.stations)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        tbl = Table(title=f"Provider Information")

        tbl.add_column("Property", justify="left")
        tbl.add_column("Value", justify="left")

        tbl.add_row("Name", self.provider)
        tbl.add_row("Id", self.id)
        tbl.add_row("Number of Stations", str(len(self.stations)))
        tbl.add_row("Integration Cost", f"${self.integration_cost:.2f}")

        yield tbl

class Satellite():
    def __init__(self, satcat_id: str | int, name: str, tle_line1: str, tle_line2: str, id: str = None, datarate: float = 0.0):

        if not satcat_id:
            raise ValueError("Satellite must have a satcat_id")

        if int(satcat_id) < 0:
            raise ValueError("Satellite satcat_id must be greater than 0")

        if not name:
            raise ValueError("Satellite must have a name")

        if not tle_line1:
            raise ValueError("Satellite must have a TLE line 1")

        if not tle_line2:
            raise ValueError("Satellite must have a TLE line 2")

        self.id = id

        if not id:
            self.id = str(uuid.uuid4())

        self.satcat_id = str(satcat_id)
        self.name = name
        self.tle_line1 = tle_line1
        self.tle_line2 = tle_line2

        # Create Internal TLE object

        self.tle = TLE(self.tle_line1, self.tle_line2)

        # Set data rate
        self.datarate = datarate

    @classmethod
    def from_elements(cls, satcat_id: str | int, name: str, epoch: Epoch, sma: float, ecc: float, inc: float, raan: float, argp: float, mean_anomaly: float, is_sso: bool = False, datarate: float = 0.0):
        """
        Initialize Satellite Object from orbital elements

        Args:
            satcat_id: Name of satellite
            name: Name of satellite
            epoch: Epoch of the satellite
            sma: Semi-major axis of the satellite
            ecc: Eccentricity of the satellite
            inc: Inclination of the satellite [deg]
            raan: Right Ascension of the Ascending Node of the satellite [deg]
            argp: Argument of Perigee of the satellite [deg]
            mean_anomaly: Mean Anomaly of the satellite [deg]
            is_sso: Flag to indicate if satellite is in a Sun-Synchronous Orbit, if set inclination will be adjusted to be SSO and inc will be ignored

        Returns: Satellite object
        """

        if is_sso:
            inc = sun_sync_inclination(sma, ecc, use_degrees=True)

        tle_line1, tle_line2 = tle_string_from_elements(
            epoch,
            [
                mean_motion(sma, use_degrees=True) * 86400 / 360,
                # Convert sma into mean motion rev/day
                ecc, inc, raan, argp, mean_anomaly, 0.0, 0.0, 0.0],
            norad_id=int(satcat_id),
        )

        return cls(satcat_id, name, tle_line1, tle_line2, datarate=datarate)

    def as_brahe_model(self):
        return bdm.Spacecraft(
            id=int(self.satcat_id),
            name=self.name,
            line1=self.tle_line1,
            line2=self.tle_line2,
        )

    def as_dict(self):
        """
        Serialize the model into a dictionary. This is needed to avoid serializing the TLE object.
        """
        return {
            'satcat_id': self.satcat_id,
            'tle_line1': self.tle_line1,
            'tle_line2': self.tle_line2,
            'name': self.name,
            'id': self.id,
            'datarate': self.datarate
        }

    @property
    def alt(self):
        return self.tle.a - R_EARTH

    def __str__(self):
        return f"Satellite({self.satcat_id}, {self.name}, {self.tle.a:.3f} km, {self.tle.e:.3f}, {self.tle.i:.3f} deg, {self.tle.RAAN:.3f} deg, {self.tle.w:.3f} deg, {self.tle.M:.3f} deg, {self.datarate*1e-6:.3f} Mbps)"

    def __repr__(self):
        return self.__str__()

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        tbl = Table(title=f"{self.name.upper()} Satellite")

        tbl.add_column("Property", justify="left")
        tbl.add_column("Value")

        tbl.add_row("Name", self.name)
        tbl.add_row("Id", str(self.id))
        tbl.add_row("Satcat ID", self.satcat_id)
        tbl.add_row("Epoch", str(self.tle.epoch))
        tbl.add_row("Semi-Major Axis [km]", f"{self.tle.a/1e3:.3f}")
        tbl.add_row("Altitude [km]", f"{(self.tle.a - R_EARTH)/1e3:.3f}")
        tbl.add_row("Eccentricity", f"{self.tle.e:.3f}")
        tbl.add_row("Inclination [deg]", f"{self.tle.i:.3f}")
        tbl.add_row("RAAN [deg]", f"{self.tle.RAAN:.3f}")
        tbl.add_row("Argument of Perigee [deg]", f"{self.tle.w:.3f}")
        tbl.add_row("Mean Anomaly [deg]", f"{self.tle.M:.3f}")
        tbl.add_row("Data Rate [Mbps]", f"{self.datarate * 1e-6:.3f}")

        yield tbl


class Contact():

    def __init__(self, contact: bdm.Contact, station: GroundStation, satellite: Satellite):

        # Set contact properties
        self.id = str(uuid.uuid4())

        # Set Station Values
        self.station_id = station.id
        self.station_name = station.name
        self.provider_id = station.provider_id
        self.provider = station.provider
        self.longitude = station.lon
        self.latitude = station.lat
        self.altitude = station.alt

        # Set Satellite Values
        self.satellite_id = satellite.id
        self.satcat_id = str(satellite.satcat_id)
        self.satellite_name = satellite.name
        self.tle = satellite.tle

        # Set window values
        self.t_start = Epoch(contact.t_start)
        self.t_end = Epoch(contact.t_end)
        self.t_duration = contact.t_duration

        # Set cost values

        self.cost = station.cost_per_pass + self.t_duration/60*station.cost_per_minute
        self.cost_per_pass = station.cost_per_pass
        self.cost_per_minute = station.cost_per_minute

        # Set data transfer values
        self.datarate = min(station.datarate, satellite.datarate) # Get the minimum of the two data rates
        self.data_volume = self.datarate * self.t_duration

    @classmethod
    def from_solution(cls, data, station: GroundStation, satellite: Satellite):
        return cls(data, station, satellite)

    @property
    def lon(self):
        return self.longitude

    @property
    def lat(self):
        return self.latitude

    @property
    def alt(self):
        return self.altitude

    def as_dict(self, minimal: bool = False):

        if minimal:
            return {
                'id': self.id,
                'station_id': self.station_id,
                'provider_id': self.provider_id,
                'satellite_id': self.satellite_id,
                't_start': self.t_start.isoformat(),
                't_end': self.t_end.isoformat(),
                't_duration': self.t_duration,
                'cost': self.cost,
                'cost_per_minute': self.cost_per_minute,
                'cost_per_pass': self.cost_per_pass,
                'datavolume': self.data_volume
            }
        else:
            return {
                'id': self.id,
                'station_id': self.station_id,
                'station_name': self.station_name,
                'provider_id': self.provider_id,
                'provider': self.provider,
                'longitude': self.longitude,
                'latitude': self.latitude,
                'altitude': self.altitude,
                'satellite_id': self.satellite_id,
                'satcat_id': self.satcat_id,
                'satellite_name': self.satellite_name,
                'tle_line1': self.tle.line1,
                'tle_line2': self.tle.line2,
                't_start': self.t_start.isoformat(),
                't_end': self.t_end.isoformat(),
                't_duration': self.t_duration,
                'cost': self.cost,
                'cost_per_pass': self.cost_per_pass,
                'cost_per_minute': self.cost_per_minute,
                'datarate': self.datarate,
                'data_volume': self.data_volume
            }

