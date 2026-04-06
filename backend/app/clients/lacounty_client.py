from dataclasses import dataclass
from typing import Optional

import httpx

from backend.app.services.errors import ParcelServiceError


class ParcelNotFoundError(ParcelServiceError):
    pass


@dataclass
class ParcelRecord:
    apn: str
    ain: str
    situs_address: str
    geometry: dict
    use_type: Optional[str]
    year_built: Optional[int]
    units: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    sqft: Optional[float]
    lot_area_sf: Optional[float]
    land_value: Optional[float]


class LACountyClient:
    BASE_URL = "https://cache.gis.lacounty.gov/cache/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"

    def __init__(self, session: httpx.AsyncClient):
        self.session = session

    async def get_parcel_at_point(self, lat: float, lng: float) -> ParcelRecord:
        resp = await self.session.get(
            f"{self.BASE_URL}/query",
            params={
                "geometry": f"{lng},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "APN,AIN,SitusAddress,UseType,YearBuilt1,Units1,Bedrooms1,Bathrooms1,SQFTmain1,Roll_LandValue,Shape.STArea()",
                "returnGeometry": "true",
                "f": "geojson",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            raise ParcelNotFoundError(
                f"No parcel found at point ({lat}, {lng})"
            )

        return self._parse_parcel_feature(features[0])

    async def get_parcel_by_apn(self, apn: str) -> ParcelRecord:
        resp = await self.session.get(
            f"{self.BASE_URL}/query",
            params={
                "where": f"APN = '{apn}'",
                "outFields": "APN,AIN,SitusAddress,UseType,YearBuilt1,Units1,Bedrooms1,Bathrooms1,SQFTmain1,Roll_LandValue,Shape.STArea()",
                "returnGeometry": "true",
                "f": "geojson",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            raise ParcelNotFoundError(f"No parcel found for APN {apn}")

        return self._parse_parcel_feature(features[0])

    @staticmethod
    def _parse_parcel_feature(feature: dict) -> ParcelRecord:
        props = feature["properties"]
        return ParcelRecord(
            apn=props["APN"],
            ain=props["AIN"],
            situs_address=props.get("SitusAddress", ""),
            geometry=feature["geometry"],
            use_type=props.get("UseType"),
            year_built=int(yb) if (yb := props.get("YearBuilt1")) else None,
            units=props.get("Units1"),
            bedrooms=props.get("Bedrooms1"),
            bathrooms=props.get("Bathrooms1"),
            sqft=props.get("SQFTmain1"),
            lot_area_sf=props.get("Shape.STArea()"),
            land_value=props.get("Roll_LandValue"),
        )
