import pytest
from unittest.mock import AsyncMock

from backend.app.clients.cams_client import (
    CAMSClient,
    GeocodedLocation,
    GeocodingError,
    reproject_2229_to_4326,
)
from backend.app.clients.lacounty_client import (
    LACountyClient,
    ParcelNotFoundError,
    ParcelRecord,
)
from backend.app.clients.navigatela_client import (
    LandUseInfo,
    NavigateLAClient,
    ZoningInfo,
    ZoningNotFoundError,
)
from backend.app.services.parcel_service import (
    ParcelData,
    ParcelService,
    ParcelServiceError,
)


def _mock_location():
    return GeocodedLocation(
        x=6502000.0,
        y=1853000.0,
        lat=34.054,
        lng=-118.243,
        score=100,
        address="123 MAIN ST, LOS ANGELES, CA, 90012",
    )


def _mock_parcel():
    return ParcelRecord(
        apn="5173-018-011",
        ain="5173018011",
        situs_address="123 MAIN ST",
        geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        use_type="Single Family Residence",
        year_built=1952,
        units=1,
        bedrooms=3,
        bathrooms=2.0,
        sqft=1400.0,
        lot_area_sf=6200.0,
        land_value=450000,
    )


def _mock_zoning():
    return ZoningInfo(zone_complete="R1-1", zone_class="R1", zone_code="12")


def _mock_land_use():
    return LandUseInfo(gplu="Low Residential", category="Residential")


@pytest.mark.asyncio
async def test_lookup_by_address_happy_path():
    cams = AsyncMock(spec=CAMSClient)
    cams.geocode.return_value = _mock_location()

    lacounty = AsyncMock(spec=LACountyClient)
    lacounty.get_parcel_at_point.return_value = _mock_parcel()

    navigatela = AsyncMock(spec=NavigateLAClient)
    navigatela.get_zoning.return_value = _mock_zoning()
    navigatela.get_land_use.return_value = _mock_land_use()
    navigatela.get_specific_plan.return_value = None
    navigatela.get_hpoz.return_value = None

    service = ParcelService(cams=cams, lacounty=lacounty, navigatela=navigatela)
    result = await service.lookup_by_address("123 Main St, Los Angeles, CA")

    assert isinstance(result, ParcelData)
    assert result.apn == "5173-018-011"
    assert result.address == "123 MAIN ST, LOS ANGELES, CA, 90012"
    assert result.lat == 34.054
    assert result.lng == -118.243
    assert result.geometry["type"] == "Polygon"
    assert result.lot_area_sf == 6200.0
    assert result.year_built == 1952
    assert result.existing_units == 1
    assert result.existing_sqft == 1400.0
    assert result.zoning.zone_complete == "R1-1"
    assert result.zoning.zone_class == "R1"
    assert result.zoning.zone_code == "12"
    assert result.zoning.general_plan_land_use == "Low Residential"
    assert result.zoning.land_use_category == "Residential"
    assert result.zoning.specific_plan is None
    assert result.zoning.hpoz is None


@pytest.mark.asyncio
async def test_geocoding_error_propagates():
    cams = AsyncMock(spec=CAMSClient)
    cams.geocode.side_effect = GeocodingError("No candidates")

    lacounty = AsyncMock(spec=LACountyClient)
    navigatela = AsyncMock(spec=NavigateLAClient)

    service = ParcelService(cams=cams, lacounty=lacounty, navigatela=navigatela)

    with pytest.raises(GeocodingError):
        await service.lookup_by_address("Nonexistent Address")


@pytest.mark.asyncio
async def test_parcel_not_found_propagates():
    cams = AsyncMock(spec=CAMSClient)
    cams.geocode.return_value = _mock_location()

    lacounty = AsyncMock(spec=LACountyClient)
    lacounty.get_parcel_at_point.side_effect = ParcelNotFoundError("No parcel")

    navigatela = AsyncMock(spec=NavigateLAClient)
    navigatela.get_zoning.return_value = _mock_zoning()
    navigatela.get_land_use.return_value = _mock_land_use()
    navigatela.get_specific_plan.return_value = None
    navigatela.get_hpoz.return_value = None

    service = ParcelService(cams=cams, lacounty=lacounty, navigatela=navigatela)

    with pytest.raises(ParcelNotFoundError):
        await service.lookup_by_address("123 Main St, Los Angeles, CA")


@pytest.mark.asyncio
async def test_nullable_overlays():
    cams = AsyncMock(spec=CAMSClient)
    cams.geocode.return_value = _mock_location()

    lacounty = AsyncMock(spec=LACountyClient)
    lacounty.get_parcel_at_point.return_value = _mock_parcel()

    navigatela = AsyncMock(spec=NavigateLAClient)
    navigatela.get_zoning.return_value = _mock_zoning()
    navigatela.get_land_use.return_value = _mock_land_use()
    navigatela.get_specific_plan.return_value = None
    navigatela.get_hpoz.return_value = None

    service = ParcelService(cams=cams, lacounty=lacounty, navigatela=navigatela)
    result = await service.lookup_by_address("123 Main St, Los Angeles, CA")

    assert result.zoning.specific_plan is None
    assert result.zoning.hpoz is None


@pytest.mark.asyncio
async def test_with_specific_plan_and_hpoz():
    cams = AsyncMock(spec=CAMSClient)
    cams.geocode.return_value = _mock_location()

    lacounty = AsyncMock(spec=LACountyClient)
    lacounty.get_parcel_at_point.return_value = _mock_parcel()

    navigatela = AsyncMock(spec=NavigateLAClient)
    navigatela.get_zoning.return_value = _mock_zoning()
    navigatela.get_land_use.return_value = _mock_land_use()
    navigatela.get_specific_plan.return_value = "Venice Coastal Zone"
    navigatela.get_hpoz.return_value = "Angelino Heights"

    service = ParcelService(cams=cams, lacounty=lacounty, navigatela=navigatela)
    result = await service.lookup_by_address("123 Main St, Los Angeles, CA")

    assert result.zoning.specific_plan == "Venice Coastal Zone"
    assert result.zoning.hpoz == "Angelino Heights"


def test_reproject_la_city_hall():
    # LA City Hall actual WKID 2229 coords
    lat, lng = reproject_2229_to_4326(6488061.0, 1842123.0)
    assert abs(lat - 34.054) < 0.01
    assert abs(lng - (-118.243)) < 0.01


def test_error_hierarchy():
    assert issubclass(GeocodingError, ParcelServiceError)
    assert issubclass(ParcelNotFoundError, ParcelServiceError)
    assert issubclass(ZoningNotFoundError, ParcelServiceError)
