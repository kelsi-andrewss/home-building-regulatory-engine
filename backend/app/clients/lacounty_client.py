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
    BASE_URL = "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer/0"

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
                "outFields": "APN,AIN,SitusAddress,UseType,YearBuilt1,Units,Bedrooms,Bathrooms,SQFT,Roll_LandValue,Shape_Area",
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

        feature = features[0]
        props = feature["properties"]

        return ParcelRecord(
            apn=props["APN"],
            ain=props["AIN"],
            situs_address=props.get("SitusAddress", ""),
            geometry=feature["geometry"],
            use_type=props.get("UseType"),
            year_built=props.get("YearBuilt1"),
            units=props.get("Units"),
            bedrooms=props.get("Bedrooms"),
            bathrooms=props.get("Bathrooms"),
            sqft=props.get("SQFT"),
            lot_area_sf=props.get("Shape_Area"),
            land_value=props.get("Roll_LandValue"),
        )
