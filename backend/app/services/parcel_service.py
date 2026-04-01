import asyncio
from dataclasses import dataclass
from typing import Optional

from backend.app.clients.cams_client import CAMSClient
from backend.app.clients.lacounty_client import LACountyClient
from backend.app.clients.navigatela_client import NavigateLAClient
from backend.app.services.errors import ParcelServiceError  # noqa: F401


@dataclass
class ParcelZoning:
    zone_complete: str
    zone_class: str
    zone_code: str
    general_plan_land_use: str
    land_use_category: str
    specific_plan: Optional[str]
    hpoz: Optional[str]


@dataclass
class ParcelData:
    apn: str
    address: str
    lat: float
    lng: float
    geometry: dict
    lot_area_sf: Optional[float]
    year_built: Optional[int]
    existing_units: Optional[int]
    existing_sqft: Optional[float]
    zoning: ParcelZoning


class ParcelService:
    def __init__(
        self,
        cams: CAMSClient,
        lacounty: LACountyClient,
        navigatela: NavigateLAClient,
    ):
        self.cams = cams
        self.lacounty = lacounty
        self.navigatela = navigatela

    async def lookup_by_address(self, address: str) -> ParcelData:
        location = await self.cams.geocode(address)

        parcel, zoning, land_use, specific_plan, hpoz = await asyncio.gather(
            self.lacounty.get_parcel_at_point(location.lat, location.lng),
            self.navigatela.get_zoning(location.lat, location.lng),
            self.navigatela.get_land_use(location.lat, location.lng),
            self.navigatela.get_specific_plan(location.lat, location.lng),
            self.navigatela.get_hpoz(location.lat, location.lng),
        )

        return ParcelData(
            apn=parcel.apn,
            address=location.address,
            lat=location.lat,
            lng=location.lng,
            geometry=parcel.geometry,
            lot_area_sf=parcel.lot_area_sf,
            year_built=parcel.year_built,
            existing_units=parcel.units,
            existing_sqft=parcel.sqft,
            zoning=ParcelZoning(
                zone_complete=zoning.zone_complete,
                zone_class=zoning.zone_class,
                zone_code=zoning.zone_code,
                general_plan_land_use=land_use.gplu,
                land_use_category=land_use.category,
                specific_plan=specific_plan,
                hpoz=hpoz,
            ),
        )
