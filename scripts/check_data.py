import urllib.request
from urllib.error import URLError
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    parsed_url = urlparse(url)
    return parsed_url.scheme in ["http", "https"]


def check_content_length(url: str, expected_content_length: str) -> bool:
    if not is_valid_url(url):
        raise ValueError(f"Invalid or unsafe URL scheme for URL: {url}")

    site = urllib.request.urlopen(url)  # noqa: S310
    if site.getheader("Content-Length") != expected_content_length:
        raise ValueError(f"This url content changed {url}")
    return True


def check_new_year_available_for_gcp(base_url: str, current_year: int) -> None:
    if not is_valid_url(base_url):
        raise ValueError(f"Invalid or unsafe URL scheme for URL: {base_url}")

    next_year = current_year + 1
    next_year_url = base_url.replace(str(current_year), str(next_year))

    try:
        response = urllib.request.urlopen(next_year_url, timeout=10)  # noqa: S310
        if response.getcode() == 200:
            raise ValueError(
                f"New year {next_year} data is available at {next_year_url}. "
                f"Please update the data file and code to use the new year."
            )
    except URLError:
        # URL doesn't exist, which is expected if no new year is available
        pass


if __name__ == "__main__":
    urls = [
        {
            "url": "https://www.eea.europa.eu/en/analysis/maps-and-charts/co2-emission-intensity-15/@@download/file",
            "content_length": "18552",
        },
        {
            "url": "https://raw.githubusercontent.com/cloud-carbon-footprint/ccf-coefficients/main/data/aws-instances.csv",
            "content_length": "160141",
        },
        {
            "url": "https://raw.githubusercontent.com/cloud-carbon-footprint/ccf-coefficients/main/data/grid-emissions-factors-aws.csv",
            "content_length": "1204",
        },
        {
            "url": "https://raw.githubusercontent.com/GoogleCloudPlatform/region-carbon-info/main/data/yearly/2024.csv",
            "content_length": "1621",
        },
    ]
    for url in urls:
        check_content_length(url=url["url"], expected_content_length=url["content_length"])

    gcp_base_url = "https://raw.githubusercontent.com/GoogleCloudPlatform/region-carbon-info/main/data/yearly/2024.csv"
    check_new_year_available_for_gcp(gcp_base_url, current_year=2024)
