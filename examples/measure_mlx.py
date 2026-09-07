import argparse
import asyncio
import json
import math
import sys
from contextlib import redirect_stdout

from tracarbon import EnergyUsageUnit
from tracarbon import IOReportEnergy
from tracarbon import TracarbonBuilder
from tracarbon import TracarbonConfiguration
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.hardwares.energy import Power
from tracarbon.locations import Country


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure local text generation with Tracarbon and MLX.")
    parser.add_argument("--model", default="mlx-community/Qwen3.8-27B-4bit")
    parser.add_argument("--revision", help="Model commit hash for reproducible comparisons")
    parser.add_argument(
        "--prompt", default="Explain how to use Tracarbon to measure a Python workload's carbon emissions."
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--country", help="Country code; detected from your public IP when omitted")
    args = parser.parse_args()
    if args.max_tokens < 1 or args.repeats < 1:
        parser.error("--max-tokens and --repeats must be positive")
    if not IOReportEnergy.is_available():
        parser.error("This example requires Apple Silicon with readable IOReport energy counters")

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler

    location = Country.from_eu_file(args.country or Country.get_current_country())
    intensity = asyncio.run(location.get_latest_co2g_kwh())
    mx.set_default_device(mx.gpu)
    with redirect_stdout(sys.stderr):
        model, tokenizer = load(args.model, revision=args.revision, tokenizer_config={"trust_remote_code": False})
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": args.prompt}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    sampler = make_sampler(temp=0.0)

    def generate() -> tuple[int, str]:
        final = None
        chunks = []
        with redirect_stdout(sys.stderr):
            for response in stream_generate(model, tokenizer, prompt, max_tokens=args.max_tokens, sampler=sampler):
                chunks.append(response.text)
                final = response
        mx.synchronize()
        if final is None or final.generation_tokens < 1:
            raise RuntimeError("MLX returned no generated tokens")
        return final.generation_tokens, "".join(chunks)

    generate()  # Loading and one complete warmup stay outside the measured window.
    output_tokens = 0
    sampling_errors = []
    with IOReportEnergy() as sensor:

        async def read_power() -> float:
            try:
                usage = await sensor.get_energy_report()
                if None in (usage.cpu_energy_usage, usage.gpu_energy_usage, usage.memory_energy_usage):
                    raise RuntimeError("IOReport must report CPU, GPU and memory energy")
                return usage.host_energy_usage
            except Exception as error:
                sampling_errors.append(error)
                raise

        metric = Metric(
            name="energy_consumption_host", value=read_power, tags=[Tag(key="units", value=EnergyUsageUnit.WATT.value)]
        )
        tracker = TracarbonBuilder(
            configuration=TracarbonConfiguration(interval_in_seconds=1),
            exporter=StdoutExporter(metric_generators=[MetricGenerator(metrics=[metric])]),
            location=location,
        ).build()
        with tracker:
            for _ in range(args.repeats):
                tokens, text = generate()
                output_tokens += tokens

    if sampling_errors:
        raise RuntimeError("Energy sampling failed; discard this measurement") from sampling_errors[0]
    energy = tracker.report.metric_report.get(metric.name)
    if energy is None or energy.call_count < 2 or not math.isfinite(energy.total) or energy.total <= 0:
        raise RuntimeError("No positive energy interval was collected; use the current Tracarbon checkout")
    co2g = Power.co2g_from_watts_hour(energy.total, intensity)
    result = {
        **vars(args),
        "country": location.name,
        "device": mx.device_info()["device_name"],
        "carbon_intensity": location.carbon_intensity_metadata.model_dump(mode="json", exclude_none=True),
        "output_tokens": output_tokens,
        "energy_wh": energy.total,
        "joules_per_output_token": energy.total * 3600 / output_tokens,
        "co2g": co2g,
        "co2g_per_output_token": co2g / output_tokens,
        "text": text,
    }
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
