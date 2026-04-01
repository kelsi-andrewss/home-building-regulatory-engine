from dataclasses import dataclass

import httpx
from pyproj import Transformer

from backend.app.services.errors import ParcelServiceError

_transformer = Transformer.from_crs("EPSG:2229", "EPSG:4326", always_xy=True)


class GeocodingError(ParcelServiceError):
    pass


def reproject_2229_to_4326(x: float, y: float) -> tuple[float, float]:
    lng, lat = _transformer.transform(x, y)
    return lat, lng


@dataclass
class GeocodedLocation:
    x: float
    y: float
    lat: float
    lng: float
    score: float
    address: str


class CAMSClient:
    BASE_URL = "https://geocode.gis.lacounty.gov/geocode/rest/services/CAMS_Locator/GeocodeServer"

    def __init__(self, session: httpx.AsyncClient):
        self.session = session

    async def geocode(self, address: str) -> GeocodedLocation:
        resp = await self.session.get(
            f"{self.BASE_URL}/findAddressCandidates",
            params={
                "SingleLine": address,
                "f": "json",
                "maxLocations": 1,
                "outSR": 2229,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise GeocodingError(f"No geocoding candidates for: {address}")

        top = candidates[0]
        score = top["score"]
        if score < 80:
            raise GeocodingError(
                f"Best candidate score {score} below threshold 80 for: {address}"
            )

        x = top["location"]["x"]
        y = top["location"]["y"]
        lat, lng = reproject_2229_to_4326(x, y)

        return GeocodedLocation(
            x=x,
            y=y,
            lat=lat,
            lng=lng,
            score=score,
            address=top["address"],
        )
