import urllib.request
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
    ]
    for url in urls:
        check_content_length(url=url["url"], expected_content_length=url["content_length"])
