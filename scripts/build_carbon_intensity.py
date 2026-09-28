import csv
import io
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import requests
from babel.core import get_global

OUR_WORLD_IN_DATA_CHART_URL = "https://ourworldindata.org/grapher/carbon-intensity-electricity"
CARBON_INTENSITY_COLUMN = "co2_intensity__gco2_kwh"
CARBON_INTENSITY_FILE = (
    Path(__file__).parent.parent / "tracarbon" / "locations" / "data" / "co2-emission-intensity.json"
)
ALPHA_2_CODES_BY_ALPHA_3_CODE = get_global("territory_aliases")


def download_from_our_world_in_data(file_extension: str) -> requests.Response:
    response = requests.get(
        f"{OUR_WORLD_IN_DATA_CHART_URL}.{file_extension}",
        params={"v": 1, "csvType": "full", "useColumnShortNames": "true"},
        timeout=30,
    )
    response.raise_for_status()
    return response


def download_chart_metadata() -> dict[str, Any]:
    return download_from_our_world_in_data("metadata.json").json()


def release_date(chart_metadata: dict[str, Any]) -> str:
    return chart_metadata["columns"][CARBON_INTENSITY_COLUMN]["lastUpdated"]


def is_measured_country(row: dict[str, str]) -> bool:
    return bool(row["code"]) and not row["code"].startswith("OWID_") and float(row[CARBON_INTENSITY_COLUMN]) > 0


def alpha_2_code(alpha_3_code: str) -> str:
    alpha_2_codes = ALPHA_2_CODES_BY_ALPHA_3_CODE.get(alpha_3_code, [])
    if len(alpha_2_codes) != 1:
        raise ValueError(f"No ISO 3166 alpha-2 code for {alpha_3_code}")
    return alpha_2_codes[0].lower()


def latest_carbon_intensity_by_country(rows: Iterable[dict[str, str]]) -> list[dict[str, str | float | int]]:
    country_rows_oldest_first = sorted(filter(is_measured_country, rows), key=lambda row: int(row["year"]))
    latest_row_by_country = {alpha_2_code(row["code"]): row for row in country_rows_oldest_first}
    return [
        {"name": country, "co2g_kwh": float(row[CARBON_INTENSITY_COLUMN]), "year": int(row["year"])}
        for country, row in sorted(latest_row_by_country.items())
    ]


if __name__ == "__main__":
    chart_metadata = download_chart_metadata()
    chart_rows = csv.DictReader(io.StringIO(download_from_our_world_in_data("csv").text))
    countries = latest_carbon_intensity_by_country(chart_rows)
    carbon_intensity = {
        "source": f"{chart_metadata['chart']['citation']}, with major processing by Our World in Data",
        "license": "CC BY 4.0 https://creativecommons.org/licenses/by/4.0/",
        "modifications": "Latest available year of each country, keyed by ISO 3166 alpha-2 code",
        "url": OUR_WORLD_IN_DATA_CHART_URL,
        "updated_at": release_date(chart_metadata),
        "countries": countries,
    }
    CARBON_INTENSITY_FILE.write_text(json.dumps(carbon_intensity, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(countries)} countries to {CARBON_INTENSITY_FILE}")
