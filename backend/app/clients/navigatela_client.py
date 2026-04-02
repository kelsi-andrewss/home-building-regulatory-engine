from dataclasses import dataclass
from typing import Optional

import httpx

from backend.app.services.errors import ParcelServiceError


class ZoningNotFoundError(ParcelServiceError):
    pass


@dataclass
class ZoningInfo:
    zone_complete: str
    zone_class: str
    zone_code: str


@dataclass
class LandUseInfo:
    gplu: str
    category: str


class NavigateLAClient:
    BASE_URL = "https://maps.lacity.org/arcgis/rest/services/Mapping/NavigateLA/MapServer"

    def __init__(self, session: httpx.AsyncClient):
        self.session = session

    def _spatial_query_params(
        self, lat: float, lng: float, out_fields: str
    ) -> dict:
        return {
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "false",
            "f": "geojson",
        }

    async def get_zoning(self, lat: float, lng: float) -> ZoningInfo:
        resp = await self.session.get(
            f"{self.BASE_URL}/71/query",
            params=self._spatial_query_params(
                lat, lng, "ZONE_CMPLT,ZONE_CLASS,ZONE_CODE"
            ),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            raise ZoningNotFoundError(
                f"No zoning found at point ({lat}, {lng})"
            )

        props = features[0]["properties"]
        return ZoningInfo(
            zone_complete=props["ZONE_CMPLT"],
            zone_class=props["ZONE_CLASS"],
            zone_code=props["ZONE_CODE"],
        )

    async def get_land_use(self, lat: float, lng: float) -> LandUseInfo:
        resp = await self.session.get(
            f"{self.BASE_URL}/70/query",
            params=self._spatial_query_params(lat, lng, "GPLU,Category"),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            raise ParcelServiceError(
                f"No land use data at point ({lat}, {lng})"
            )

        props = features[0]["properties"]
        return LandUseInfo(
            gplu=str(props["GPLU"]),
            category=str(props["Category"]),
        )

    async def get_specific_plan(
        self, lat: float, lng: float
    ) -> Optional[str]:
        resp = await self.session.get(
            f"{self.BASE_URL}/93/query",
            params=self._spatial_query_params(lat, lng, "NAME,DIST_TYPE"),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            return None

        return features[0]["properties"]["NAME"]

    async def get_hpoz(self, lat: float, lng: float) -> Optional[str]:
        resp = await self.session.get(
            f"{self.BASE_URL}/75/query",
            params=self._spatial_query_params(lat, lng, "NAME,DIST_TYPE"),
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            return None

        return features[0]["properties"]["NAME"]
