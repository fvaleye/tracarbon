# Measure a local LLM

Start Tracarbon in a terminal:

```sh
pip install tracarbon
tracarbon run
```

Use your local LLM as usual. For example, with
[Ollama](https://docs.ollama.com/quickstart) installed, run this in another terminal:

```sh
ollama run qwen3.8:27b --think=false "Explain how to use Tracarbon."
```

[Qwen3.8-27B](https://ollama.com/library/qwen3.8:27b) needs an 18 GB download.
Download it before tracking to exclude setup. Any local model or runtime works.

Tracarbon displays power and estimated CO2. Press `Ctrl+C` in its terminal when
finished to print the report. Readings include all activity on the measured hardware;
run on a quiet machine. Token counts and per-model attribution are unavailable.

| Platform | Measured hardware |
| --- | --- |
| macOS | Apple Silicon chip counters, with system power fallbacks. |
| Linux | Readable Intel or AMD RAPL counters, plus supported GPU readings. |
| Windows | NVIDIA GPU via `nvidia-smi`. CPU, memory and host totals are unavailable. |

Country is detected by IP; `--country-code-alpha-iso-2 fr` overrides it. Without an API key,
Tracarbon uses bundled factors for 28 European countries. Set
`TRACARBON_CO2SIGNAL_API_KEY` for live factors, including supported zones outside Europe.

Set `TRACARBON_INTERVAL_IN_SECONDS=1` for more frequent readings.
Remote API calls only measure the client computer.
