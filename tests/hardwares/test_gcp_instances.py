import csv
import io
import runpy
import shutil
from pathlib import Path


def test_gcp_generator_uses_documented_cpu_platforms(tmp_path, mocker):
    project = Path(__file__).resolve().parents[2]
    generator = tmp_path / "scripts" / "generate_gcp_instances.py"
    generator.parent.mkdir()
    shutil.copyfile(project / "scripts" / generator.name, generator)
    relative_csv = Path("tracarbon/hardwares/data/gcp-instances.csv")
    generated = tmp_path / relative_csv
    generated.parent.mkdir(parents=True)
    shutil.copyfile(project / relative_csv, generated)

    # Coefficients and instance labels from the pinned b0032d9 upstream data.
    coefficients = (
        b"Architecture,Min Watts,Max Watts\n"
        b"Sapphire Rapids,1.0362861003136936,4.06210101745772\n"
        b"Emerald Rapids,0.8140104166666666,4.3816792499999995\n"
        b"Cascade Lake,0.6902978319127387,3.754854273784877\n"
        b"Ice Lake,0.766796875,3.6515791249999996\n"
    )
    instances = (
        b"Instance Type,Instance vCPU,Instance Memory,Microarchitecture\n"
        b"a3-highgpu-8g,208,1872,Emerald Rapids\n"
        b"a3-megagpu-8g,208,1872,Emerald Rapids\n"
        b"a3-edgegpu-8g,208,1872,Emerald Rapids\n"
        b"a3-ultragpu-8g,224,2952,Emerald Rapids\n"
        b"n2-standard-80,80,320,Ice Lake\n"
        b"n2-standard-96,96,384,Ice Lake\n"
    )
    mocker.patch("urllib.request.urlopen", side_effect=[io.BytesIO(coefficients), io.BytesIO(instances)])

    runpy.run_path(str(generator), run_name="__main__")

    expected = {
        "a3-highgpu-8g": ("Sapphire Rapids", "215.55", "844.92"),
        "a3-megagpu-8g": ("Sapphire Rapids", "215.55", "844.92"),
        "a3-edgegpu-8g": ("Sapphire Rapids", "215.55", "844.92"),
        "a3-ultragpu-8g": ("Emerald Rapids", "182.34", "981.5"),
        "n2-standard-80": ("Cascade Lake", "55.22", "300.39"),
        "n2-standard-96": ("Ice Lake", "73.61", "350.55"),
    }
    for csv_file in (generated, project / relative_csv):
        with csv_file.open(encoding="utf-8") as stream:
            estimates = {
                row["Instance type"]: (row["Architecture"], row["Min Watts"], row["Max Watts"])
                for row in csv.DictReader(stream)
                if row["Instance type"] in expected
            }
        assert estimates == expected
