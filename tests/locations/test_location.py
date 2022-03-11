import pytest

from tracarbon.locations import Country, Location


@pytest.mark.asyncio
async def get_current_country(mocker):
    location_expected = "fr"

    mocker.patch.object(Location, "request", location_expected)
    location = Location.get_current_country()

    assert location_expected == location


@pytest.mark.asyncio
async def test_country_location(mocker):
    location_expected = "be"
    co2g_kwh = 161.0

    mocker.patch.object(Country, "get_current_country", return_value=location_expected)

    country = await Country.get_location()

    assert country.name_alpha_iso_2 == location_expected
    assert country.co2g_kwh == co2g_kwh


@pytest.mark.asyncio
async def test_unknown_location(mocker):
    location = "ze"
    mocker.patch.object(Country, "get_current_country", return_value=location)

    with pytest.raises(ValueError) as exception:
        await Country.get_location()

    assert exception.value.args[0] == "The country ze is not in the co2 emission file."


def test_world_emission_should_get_country():

    country_name_alpha_iso_2 = "fr"
    co2g_kwh_expected = 51.1
    country_expected = Country(
        name_alpha_iso_2=country_name_alpha_iso_2, co2g_kwh=co2g_kwh_expected
    )

    country = Country.from_eu_file(country_name_alpha_iso_2=country_name_alpha_iso_2)

    assert country == country_expected


def test_world_emission_should_raise_error_when_country_is_missing():

    country_name_alpha_iso_2 = "zf"

    with pytest.raises(ValueError) as exception:
        Country.from_eu_file(country_name_alpha_iso_2=country_name_alpha_iso_2)

    assert (
        exception.value.args[0]
        == f"The country {country_name_alpha_iso_2} is not in the co2 emission file."
    )
