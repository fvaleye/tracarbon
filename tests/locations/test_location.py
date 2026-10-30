import asyncio

import pytest
import requests
from aiohttp import ClientResponseError
from aiohttp import web
from aiohttp.test_utils import RawTestServer
from loguru import logger

from tracarbon.exceptions import CloudProviderRegionIsMissing
from tracarbon.exceptions import CountryIsMissing
from tracarbon.hardwares import CloudProviders
from tracarbon.locations import AWSLocation
from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import Country
from tracarbon.locations import Location
from tracarbon.locations import location
from tracarbon.locations.country import AzureLocation
from tracarbon.locations.country import GCPLocation


async def test_request_times_out(monkeypatch):
    async def answer_late(request: web.BaseRequest) -> web.Response:
        await asyncio.sleep(0.5)
        return web.json_response({"carbonIntensity": 42.0})

    monkeypatch.setattr(location, "REQUEST_TIMEOUT_IN_SECONDS", 0.05)
    async with RawTestServer(answer_late) as server:
        with pytest.raises(asyncio.TimeoutError):
            await Location.request(str(server.make_url("/")))


async def test_http_error_preserves_status_and_hides_api_key():
    received_tokens = []

    async def fail(request: web.BaseRequest) -> web.Response:
        received_tokens.append(request.headers["auth-token"])
        return web.json_response({"error": "boom"}, status=500)

    async with RawTestServer(fail) as server:
        country = Country(
            name="fr",
            co2signal_api_key="SECRET_API_KEY",
            co2signal_url=str(server.make_url("/?zone=")),
            co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
        )
        host_logs = []
        host_handler_id = logger.add(host_logs.append, backtrace=True, diagnose=True)
        raised = None
        try:
            await country.get_latest_co2g_kwh()
        except Exception as error:
            logger.exception("Host caught a failed request")
            raised = error
        finally:
            logger.remove(host_handler_id)

    assert isinstance(raised, ClientResponseError)
    assert raised.status == 500
    assert received_tokens == ["SECRET_API_KEY"]
    assert "SECRET_API_KEY" not in repr(raised) + "".join(host_logs)


def test_get_current_country_returns_country_code(mocker):
    response = mocker.Mock(text='{"country": "fr"}')
    get = mocker.patch("tracarbon.locations.country.requests.get", return_value=response)

    country = Country.get_current_country()

    assert country == "fr"
    assert get.call_args.kwargs["timeout"] == 10
    assert get.call_args.kwargs["headers"] is None


def test_get_current_country_uses_explicit_ipinfo_token(mocker):
    response = mocker.Mock(text='{"country": "be"}')
    get = mocker.patch("tracarbon.locations.country.requests.get", return_value=response)

    country = Country.get_current_country(token="secret")

    assert country == "be"
    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer secret"}


def test_get_current_country_reads_ipinfo_token_from_environment(mocker, monkeypatch):
    monkeypatch.setenv("TRACARBON_IPINFO_TOKEN", "env-token")
    response = mocker.Mock(text='{"country": "de"}')
    get = mocker.patch("tracarbon.locations.country.requests.get", return_value=response)

    Country.get_current_country()

    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer env-token"}


@pytest.mark.parametrize(
    ("status_error", "text", "request_error"),
    [
        (requests.HTTPError("403 Client Error: Forbidden"), "<html>Forbidden</html>", None),
        (None, "<html>Captive portal</html>", None),
        (None, '{"ip": "10.0.0.1", "bogon": true}', None),
        (None, None, requests.ConnectionError("offline")),
        (None, None, requests.Timeout("read timed out")),
    ],
    ids=["http_error", "not_json", "no_country", "offline", "timeout"],
)
def test_country_detection_failure_suggests_explicit_country(mocker, status_error, text, request_error):
    response = mocker.Mock(text=text)
    response.raise_for_status.side_effect = status_error
    mocker.patch("tracarbon.locations.country.requests.get", return_value=response, side_effect=request_error)

    with pytest.raises(CountryIsMissing, match="--country-code-alpha-iso-2"):
        Country.get_current_country()


def test_country_location(mocker):
    mocker.patch.object(
        CloudProviders,
        "is_running_on_cloud_provider",
        return_value=False,
    )
    location_expected = "be"
    co2g_kwh = 149.82

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

    assert exception.value.args[0] == "The country [ze] is not in the co2 emission file."


def test_world_emission_should_get_country():
    country_code_alpha_iso_2 = "fr"
    co2g_kwh_expected = 41.44

    country = Country.from_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    assert country.name == country_code_alpha_iso_2
    assert country.co2g_kwh == co2g_kwh_expected


def test_from_eu_file_warns_that_it_is_deprecated_and_still_returns_the_bundled_country():
    with pytest.warns(DeprecationWarning, match="Country.from_file"):
        country = Country.from_eu_file(country_code_alpha_iso_2="fr")

    assert country == Country.from_file(country_code_alpha_iso_2="fr")


def test_world_emission_should_raise_error_when_country_is_missing():
    country_code_alpha_iso_2 = "zf"

    with pytest.raises(CountryIsMissing) as exception:
        Country.from_file(country_code_alpha_iso_2=country_code_alpha_iso_2)

    assert exception.value.args[0] == f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file."


@pytest.mark.parametrize(
    ("location_type", "provider_name", "region_name"),
    [(AWSLocation, "AWS", "zf"), (GCPLocation, "GCP", "unknown-region"), (AzureLocation, "Azure", "unknown-region")],
    ids=["aws", "gcp", "azure"],
)
def test_cloud_location_rejects_unknown_regions(location_type, provider_name, region_name):
    with pytest.raises(CloudProviderRegionIsMissing) as exception:
        location_type(region_name=region_name)

    assert str(exception.value) == (
        f"The region [{region_name}] is not in the {provider_name} grid emissions factors file."
    )


@pytest.mark.parametrize(
    ("location_type", "region_name", "expected_name", "co2g_kwh"),
    [
        pytest.param(AWSLocation, "eu-west-1", "AWS(eu-west-1)", 316.0, id="aws"),
        pytest.param(AWSLocation, " EU-WEST-1 ", "AWS( EU-WEST-1 )", 316.0, id="aws-normalized"),
        pytest.param(GCPLocation, "europe-west1", "GCP(europe-west1)", 126.43, id="gcp-europe"),
        pytest.param(GCPLocation, "us-central1", "GCP(us-central1)", 431.95, id="gcp-us"),
        pytest.param(AzureLocation, "West Europe", "Azure(West Europe)", 390.0, id="azure-europe"),
        pytest.param(AzureLocation, "East US", "Azure(East US)", 415.755, id="azure-us"),
    ],
)
def test_cloud_location_loads_bundled_carbon_intensity(location_type, region_name, expected_name, co2g_kwh):
    location = location_type(region_name=region_name)

    assert location.name == expected_name
    assert location.co2g_kwh == pytest.approx(co2g_kwh)
    assert location.co2g_kwh_source is CarbonIntensitySource.FILE
