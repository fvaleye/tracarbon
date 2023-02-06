import pytest

from tracarbon.exceptions import CloudProviderRegionIsMissing, CountryIsMissing
from tracarbon.hardwares import CloudProviders
from tracarbon.locations import AWSLocation, Country, Location


@pytest.mark.asyncio
async def get_current_country(mocker):
    location_expected = "fr"

    mocker.patch.object(Location, "request", location_expected)
    location = Location.get_current_country()

    assert location_expected == location


def test_country_location(mocker):
    mocker.patch.object(
        CloudProviders,
        "is_running_on_cloud_provider",
        return_value=False,
    )
    location_expected = "be"
    co2g_kwh = 161.0

    mocker.patch.object(Country, "get_current_country", return_value=location_expected)

    country = Country.get_location()

    assert country.name == location_expected
    assert country.co2g_kwh == co2g_kwh


def test_unknown_location(mocker):
    mocker.patch.object(
        CloudProviders,
        "is_running_on_cloud_provider",
        return_value=False,
    )
    location = "ze"
    mocker.patch.object(Country, "get_current_country", return_value=location)

    with pytest.raises(CountryIsMissing) as exception:
        Country.get_location()

    assert (
        exception.value.args[0] == "The country [ze] is not in the co2 emission file."
    )


def test_world_emission_should_get_country():
    country_code_alpha_iso_2 = "fr"
    co2g_kwh_expected = 51.1
    country_expected = Country(
        name=country_code_alpha_iso_2,
        co2g_kwh=co2g_kwh_expected,
    )

    country = Country.from_eu_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    assert country == country_expected


def test_world_emission_should_raise_error_when_country_is_missing():
    country_code_alpha_iso_2 = "zf"

    with pytest.raises(CountryIsMissing) as exception:
        Country.from_eu_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    assert (
        exception.value.args[0]
        == f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file."
    )


def test_aws_location_should_return_an_error_if_region_not_exists():
    region_name = "zf"

    with pytest.raises(CloudProviderRegionIsMissing) as exception:
        AWSLocation(region_name=region_name)
    assert (
        exception.value.args[0]
        == f"The region [{region_name}] is not in the AWS grid emissions factors file."
    )


def test_aws_location_should_return_ok_if_region_exists():
    region_name = "eu-west-1"

    location = AWSLocation(region_name=region_name)

    assert location.name == "AWS(eu-west-1)"
    assert location.co2g_kwh == 316.0
    assert location.co2g_kwh_source.value == "file"
