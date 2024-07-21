from typing import Any, Dict, Optional
from typing_extensions import Annotated

import datetime

from pydantic import BaseModel, Field, ConfigDict, model_validator, model_serializer

import polars as pl
import brahe as bh


class OptimizationWindow(BaseModel):
    opt_start: Annotated[datetime.datetime, Field(description="Start time of optimization window")]
    opt_end: Annotated[datetime.datetime, Field(description="End time of optimization window")]

    sim_start: Annotated[datetime.datetime, Field(description="Start time of simulation window")]
    sim_end: Annotated[datetime.datetime, Field(description="End time of simulation window")]


class GroundStation(BaseModel):
    name: str
    provider: str
    longitude: Annotated[float, Field(strict=True, ge=-180, le=180, description="Longitude in degrees")]
    latitude: Annotated[float, Field(strict=True, ge=-90, le=90, description="Latitude in degrees")]
    altitude: Annotated[float, Field(description="Altitude in meters")] = 0.0

    @property
    def lon(self):
        return self.longitude

    @property
    def lat(self):
        return self.latitude

    @property
    def alt(self):
        return self.altitude


def ground_stations_from_dataframe(df: pl.DataFrame) -> list[GroundStation]:
    """
    Create a list of GroundStation objects from a Polars DataFrame
    """
    stations = []
    for sta in df.iter_rows(named=True):
        stations.append(GroundStation(
            name=sta['station_name'],
            provider=sta['provider_name'],
            longitude=sta['longitude'],
            latitude=sta['latitude'],
            altitude=sta['altitude']
        ))

    return stations


class Satellite(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    satcat_id: str
    name: str
    tle_line1: str
    tle_line2: str

    @model_serializer
    def ser_model(self) -> Dict[str, Any]:
        """
        Serialize the model into a dictionary. This is needed to avoid serializing the TLE object.
        """
        return {
            'satcat_id': self.satcat_id,
            'tle_line1': self.tle_line1,
            'tle_line2': self.tle_line2
        }


def satellites_from_dataframe(df: pl.DataFrame) -> list[Satellite]:
    """
    Create a list of Satellite objects from a Polars DataFrame
    """
    satellites = []
    for sat in df.iter_rows(named=True):
        satellites.append(Satellite(
            satcat_id=sat['satcat_id'],
            name=sat['object_name'],
            tle_line1=sat['tle_line1'],
            tle_line2=sat['tle_line2']
        ))

    return satellites
