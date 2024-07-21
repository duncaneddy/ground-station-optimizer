from typing import Any, Dict, Optional
from typing_extensions import Annotated

import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_serializer

import polars as pl
import brahe as bh


class OptimizationWindow(BaseModel):
    opt_start: Annotated[datetime.datetime, Field(description="Start time of optimization window")]
    opt_duration: Annotated[float | None, Field(description="Duration in seconds of optimization window")] = None
    opt_end: Annotated[datetime.datetime, Field(description="End time of optimization window")]

    sim_start: Annotated[datetime.datetime, Field(description="Start time of simulation window")]
    sim_end: Annotated[datetime.datetime | None, Field(description="End time of simulation window")] = None
    sim_duration: Annotated[float, Field(description="Duration in seconds")]

    @field_validator('sim_end', mode='before', check_fields=False)
    @classmethod
    def validate_sim_end(cls, v: Any):
        """
        Set the end time based on the start time and duration
        """

        return v['sim_start'] + datetime.timedelta(seconds=v['sim_duration'])

    @field_validator('opt_duration', mode='before', check_fields=False)
    @classmethod
    def validate_opt_duration(cls, v: Any):
        """
        Set the duration based on the start and end times
        """

        dt = v['opt_end'] - v['opt_start']

        return dt.total_seconds()


class GroundStation(BaseModel):
    name: str
    provider: str
    longitude: Annotated[float, Field(strict=True, ge=-180, le=180, description="Longitude in degrees")]
    latitude: Annotated[float, Field(strict=True, ge=-90, le=90, description="Latitude in degrees")]
    altitude: Annotated[float, Field(description="Altitude in meters")]

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
            name=sta['location_name'],
            provider=sta['location_id'],
            longitude=sta['longitude_deg'],
            latitude=sta['latitude_deg'],
            altitude=sta['altitude_m']
        ))

    return stations


class Satellite(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    satcat_id: str
    name: str
    tle_line1: str
    tle_line2: str
    tle: bh.TLE | None = None

    @field_validator('tle', mode='before', check_fields=False)
    @classmethod
    def validate_tle(cls, v: Any):
        """
        Initialize the TLE object from the TLE line 1 and line 2 strings
        """
        if 'tle_line1' not in v:
            raise ValueError('tle_line1 is required')
        if 'tle_line2' not in v:
            raise ValueError('tle_line2 is required')

        return bh.TLE(v['tle_line1'], v['tle_line2'])

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
