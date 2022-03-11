import urllib.request


def check_content_length(url: str, expected_content_length: str) -> bool:
    site = urllib.request.urlopen(url)
    assert site.getheader("Content-Length") == expected_content_length, f"This url content changed {url}"


if __name__ == "__main__":
    urls = [
        {
            "url": "https://www.eea.europa.eu/data-and-maps/daviz/co2-emission-intensity-9/download.exhibit",
            "content_length": "106078",
        },
        {
            "url": "https://raw.githubusercontent.com/cloud-carbon-footprint/cloud-carbon-coefficients/main/data/aws-instances.csv",
            "content_length": "160141",
        },
        {
            "url": "https://raw.githubusercontent.com/cloud-carbon-footprint/cloud-carbon-coefficients/main/data/grid-emissions-factors-aws.csv",
            "content_length": "1204",
        },
    ]
    for url in urls:
        check_content_length(
            url=url["url"], expected_content_length=url["content_length"]
        )
