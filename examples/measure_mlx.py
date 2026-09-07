"""Measure local MLX generation on Apple Silicon. See docs/source/usage.rst."""

import argparse
import asyncio
import json
import math
import platform
import sys
import time
from contextlib import redirect_stdout
from importlib.metadata import version

from tracarbon import EnergyUsageUnit
from tracarbon import IOReportEnergy
from tracarbon import Tracarbon
from tracarbon import TracarbonConfiguration
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.hardwares.energy import Power
from tracarbon.locations import Country


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    parser.add_argument("--revision", help="Model commit hash for reproducible comparisons")
    parser.add_argument("--prompt", default="Explain how a computer generates text, in plain English.")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--country", required=True, help="Country code in Tracarbon's bundled static intensity data")
    args = parser.parse_args()
    if args.max_tokens < 1 or args.repeats < 1:
        parser.error("--max-tokens and --repeats must be positive")
    if not IOReportEnergy.is_available():
        parser.error("This example requires Apple Silicon with readable IOReport energy counters")

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm import stream_generate
    from mlx_lm.generate import GenerationResponse
    from mlx_lm.sample_utils import make_sampler

    location = Country.from_eu_file(args.country)
    intensity = asyncio.run(location.get_latest_co2g_kwh())
    mx.set_default_device(mx.gpu)
    with redirect_stdout(sys.stderr):
        model, tokenizer, model_config = load(
            args.model, revision=args.revision, return_config=True, tokenizer_config={"trust_remote_code": False}
        )
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": args.prompt}], tokenize=True, add_generation_prompt=True
    )
    sampler = make_sampler(temp=0.0)

    def generate() -> tuple[GenerationResponse, str]:
        final = None
        chunks = []
        with redirect_stdout(sys.stderr):
            for response in stream_generate(model, tokenizer, prompt, max_tokens=args.max_tokens, sampler=sampler):
                chunks.append(response.text)
                final = response
        mx.synchronize()
        if final is None or final.generation_tokens < 1:
            raise RuntimeError("MLX returned no generated tokens")
        return final, "".join(chunks)

    generate()  # Loading and one complete warmup stay outside the measured window.
    requests = []
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
        tracker = Tracarbon(
            configuration=TracarbonConfiguration(interval_in_seconds=1),
            exporter=StdoutExporter(metric_generators=[MetricGenerator(metrics=[metric])]),
            location=location,
        )
        with tracker:
            started = time.perf_counter()
            for _ in range(args.repeats):
                response, text = generate()
                requests.append(
                    {"prompt_tokens": response.prompt_tokens, "output_tokens": response.generation_tokens, "text": text}
                )
            elapsed = time.perf_counter() - started

    if sampling_errors:
        raise RuntimeError("Energy sampling failed; discard this measurement") from sampling_errors[0]
    energy = tracker.report.metric_report.get(metric.name)
    if energy is None or energy.call_count < 2 or not math.isfinite(energy.total) or energy.total <= 0:
        raise RuntimeError("No positive energy interval was collected; use the current Tracarbon checkout")
    output_tokens = sum(request["output_tokens"] for request in requests)
    co2g = Power.co2g_from_watts_hour(energy.total, intensity)
    print(
        json.dumps(
            {
                "model": args.model,
                "revision": args.revision,
                "model_config": model_config,
                "versions": {package: version(package) for package in ("tracarbon", "mlx", "mlx-lm")},
                "python": platform.python_version(),
                "platform": platform.platform(),
                "device": mx.device_info(),
                "prompt": args.prompt,
                "max_tokens": args.max_tokens,
                "temperature": 0.0,
                "repeats": args.repeats,
                "warmup_requests": 1,
                "prompt_cache_reused": False,
                "sensor": "IOReport",
                "scope": "Shared CPU + GPU + memory during prompt processing and generation (plus ANE where reported)",
                "carbon_intensity": location.carbon_intensity_metadata.model_dump(mode="json"),
                "generation_seconds": elapsed,
                "measurement_samples": energy.call_count,
                "measurement_seconds": energy.average_interval_in_seconds * (energy.call_count - 1),
                "prompt_tokens": sum(request["prompt_tokens"] for request in requests),
                "output_tokens": output_tokens,
                "output_tokens_per_second": output_tokens / elapsed,
                "energy_wh": energy.total,
                "joules_per_output_token": energy.total * 3600 / output_tokens,
                "co2g": co2g,
                "co2g_per_output_token": co2g / output_tokens,
                "requests": requests,
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
