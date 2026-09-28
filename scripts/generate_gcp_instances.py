import csv
import io
import urllib.request
from pathlib import Path

CCF_COEFFICIENTS = "https://raw.githubusercontent.com/cloud-carbon-footprint/ccf-coefficients/b0032d9"
GCP_INSTANCES = Path(__file__).parent.parent / "tracarbon" / "hardwares" / "data" / "gcp-instances.csv"


def read_csv(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return list(csv.DictReader(io.StringIO(response.read().decode("utf-8"))))


if __name__ == "__main__":
    coefficients = {
        row["Architecture"]: (float(row["Min Watts"]), float(row["Max Watts"]))
        for row in read_csv(f"{CCF_COEFFICIENTS}/output/coefficients-gcp-use.csv")
    }
    instances = {
        row["Instance Type"]: (row["Instance vCPU"], row["Instance Memory"], row["Microarchitecture"])
        for row in read_csv(f"{CCF_COEFFICIENTS}/data/gcp-instances-latest-2026.csv")
    }
    with GCP_INSTANCES.open(encoding="utf-8") as bundled:
        for row in csv.DictReader(bundled):
            instances.setdefault(
                row["Instance type"], (row["Instance vCPU"], row["Instance Memory (in GB)"], row["Architecture"])
            )

    with GCP_INSTANCES.open("w", encoding="utf-8", newline="") as generated:
        writer = csv.writer(generated)
        writer.writerow(
            ["Instance type", "Instance vCPU", "Instance Memory (in GB)", "Min Watts", "Max Watts", "Architecture"]
        )
        for instance_type, (vcpus, memory, architecture) in sorted(instances.items()):
            # The pinned upstream list mislabels these A3 families; only Ultra uses Emerald Rapids.
            # https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#a3-vms
            if instance_type.startswith(("a3-highgpu-", "a3-megagpu-", "a3-edgegpu-")):
                architecture = "Sapphire Rapids"
            # N2 defaults to Cascade Lake through 80 vCPUs; larger sizes require Ice Lake.
            # https://docs.cloud.google.com/compute/docs/general-purpose-machines#n2_series
            elif instance_type.startswith("n2-") and float(vcpus) <= 80:
                architecture = "Cascade Lake"
            if architecture in coefficients:
                min_watts, max_watts = coefficients[architecture]
                writer.writerow(
                    [
                        instance_type,
                        float(vcpus),
                        float(memory),
                        round(float(vcpus) * min_watts, 2),
                        round(float(vcpus) * max_watts, 2),
                        architecture,
                    ]
                )
