import socket

import pytest
from aiohttp import web
from loguru import logger

from tracarbon.exceptions import CloudProviderRegionIsMissing
from tracarbon.exceptions import CountryIsMissing
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares import CloudProviders
from tracarbon.locations import AWSLocation
from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import Country
from tracarbon.locations import Location
from tracarbon.locations.country import AzureLocation
from tracarbon.locations.country import GCPLocation


@pytest.mark.asyncio
async def test_request_raises_for_http_error(mocker):
    response = mocker.MagicMock()
    response.raise_for_status.side_effect = RuntimeError("HTTP 401")
    response.text = mocker.AsyncMock(return_value='{"error": "unauthorized"}')
    response_context = mocker.MagicMock()
    response_context.__aenter__ = mocker.AsyncMock(return_value=response)
    response_context.__aexit__ = mocker.AsyncMock(return_value=None)
    session = mocker.MagicMock()
    session.get.return_value = response_context
    session_context = mocker.MagicMock()
    session_context.__aenter__ = mocker.AsyncMock(return_value=session)
    session_context.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch("tracarbon.locations.location.aiohttp.ClientSession", return_value=session_context)

    with pytest.raises(RuntimeError, match="HTTP 401"):
        await Location.request("https://example.com")


async def test_an_http_error_reaches_the_caller_unchanged_without_the_api_key():
    received_tokens = []

    async def fail(request: web.Request) -> web.Response:
        received_tokens.append(request.headers["auth-token"])
        return web.json_response({"error": "boom"}, status=500)

    runner, url = await start_server(fail)
    country = Country(
        name="fr",
        co2signal_api_key="SECRET_API_KEY",
        co2signal_url=f"{url}?zone=",
        co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
    )
    host_logs = []
    host_handler_id = logger.add(host_logs.append, backtrace=True, diagnose=True)
    try:
        await country.get_latest_co2g_kwh()
    except Exception as error:
        logger.exception("Host caught a failed request")
        raised = error
    finally:
        logger.remove(host_handler_id)
        await runner.cleanup()

    assert not isinstance(raised, TracarbonException)
    assert received_tokens == ["SECRET_API_KEY"]
    assert "SECRET_API_KEY" not in repr(raised) + "".join(host_logs)


async def test_a_refused_request_keeps_the_api_key_out_of_a_diagnosed_traceback():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    country = Country(
        name="fr",
        co2signal_api_key="SECRET_API_KEY",
        co2signal_url=f"http://127.0.0.1:{closed_port}/?zone=",
        co2g_kwh_source=CarbonIntensitySource.CO2SignalAPI,
    )
    host_logs = []
    host_handler_id = logger.add(host_logs.append, backtrace=True, diagnose=True)
    try:
        await country.get_latest_co2g_kwh()
    except Exception:
        logger.exception("Host caught a failed refresh")
    finally:
        logger.remove(host_handler_id)

    host_log = "".join(host_logs)
    assert "Traceback" in host_log
    assert "SECRET_API_KEY" not in host_log


async def start_server(handler) -> tuple[web.AppRunner, str]:
    application = web.Application()
    application.router.add_get("/", handler)
    runner = web.AppRunner(application)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    return runner, f"http://127.0.0.1:{runner.addresses[0][1]}/"


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


def test_country_location(mocker):
    mocker.patch.object(
        CloudProviders,
        "is_running_on_cloud_provider",
        return_value=False,
    )
    location_expected = "be"
    co2g_kwh = 154.0

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
    co2g_kwh_expected = 74.0
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

    assert exception.value.args[0] == f"The country [{country_code_alpha_iso_2}] is not in the co2 emission file."


def test_aws_location_should_return_an_error_if_region_not_exists():
    region_name = "zf"

    with pytest.raises(CloudProviderRegionIsMissing) as exception:
        AWSLocation(region_name=region_name)
    assert exception.value.args[0] == f"The region [{region_name}] is not in the AWS grid emissions factors file."


def test_aws_location_should_return_ok_if_region_exists():
    region_name = "eu-west-1"

    location = AWSLocation(region_name=region_name)

    assert location.name == "AWS(eu-west-1)"
    assert location.co2g_kwh == 316.0
    assert location.co2g_kwh_source.value == "file"


def test_gcp_location_should_return_an_error_if_region_not_exists():
    region_name = "unknown-region"

    with pytest.raises(CloudProviderRegionIsMissing) as exception:
        GCPLocation(region_name=region_name)
    assert exception.value.args[0] == f"The region [{region_name}] is not in the GCP grid emissions factors file."


def test_gcp_location_should_return_ok_if_region_exists():
    region_name = "europe-west1"

    location = GCPLocation(region_name=region_name)

    assert location.name == "GCP(europe-west1)"
    assert location.co2g_kwh == 126.43
    assert location.co2g_kwh_source.value == "file"


def test_gcp_location_us_central1():
    region_name = "us-central1"

    location = GCPLocation(region_name=region_name)

    assert location.name == "GCP(us-central1)"
    assert location.co2g_kwh == 431.95


def test_azure_location_should_return_an_error_if_region_not_exists():
    region_name = "unknown-region"

    with pytest.raises(CloudProviderRegionIsMissing) as exception:
        AzureLocation(region_name=region_name)
    assert exception.value.args[0] == f"The region [{region_name}] is not in the Azure grid emissions factors file."


def test_azure_location_should_return_ok_if_region_exists():
    region_name = "West Europe"

    location = AzureLocation(region_name=region_name)

    assert location.name == "Azure(West Europe)"
    assert location.co2g_kwh > 380
    assert location.co2g_kwh < 400
    assert location.co2g_kwh_source.value == "file"


def test_azure_location_east_us():
    region_name = "East US"

    location = AzureLocation(region_name=region_name)

    assert location.name == "Azure(East US)"
    assert location.co2g_kwh > 410
    assert location.co2g_kwh < 420
