from typing_extensions import Annotated
from pydantic import BaseModel, Field


class GroundStation(BaseModel):
    name: str
    provider: str
    longitude: Annotated[float, Field(strict=True, ge=-180, le=180, description="Longitude in degrees")]
    latitude: Annotated[float, Field(strict=True, ge=-90, le=90, description="Latitude in degrees")]
    altitude: Annotated[float, Field(description="Altitude in meters")]

