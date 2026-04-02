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
        results = await self.geocode_many(address, max_locations=1)
        if not results:
            raise GeocodingError(f"No geocoding candidates for: {address}")
        return results[0]

    async def geocode_many(
        self, address: str, max_locations: int = 5, min_score: int = 80
    ) -> list[GeocodedLocation]:
        resp = await self.session.get(
            f"{self.BASE_URL}/findAddressCandidates",
            params={
                "SingleLine": address,
                "f": "json",
                "maxLocations": max_locations,
                "outSR": 2229,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for candidate in data.get("candidates", []):
            score = candidate["score"]
            if score < min_score:
                continue
            x = candidate["location"]["x"]
            y = candidate["location"]["y"]
            lat, lng = reproject_2229_to_4326(x, y)
            results.append(
                GeocodedLocation(
                    x=x, y=y, lat=lat, lng=lng, score=score, address=candidate["address"],
                )
            )
        return results
