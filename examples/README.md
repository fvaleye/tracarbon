# Measure a local LLM

Load the model, then measure at least 5 seconds of requests in one session. To compare sessions,
follow [measure a local LLM](../docs/source/usage.rst#measure-a-local-llm).

## Ollama

```sh
pip install tracarbon
ollama pull qwen2.5:0.5b
ollama run qwen2.5:0.5b "Say hello."
tracarbon exec --output ollama-session.json -- sh -ec \
  'for request in 1 2 3 4 5; do ollama run --verbose qwen2.5:0.5b "Explain how a database executes a join."; done'
```

Ollama prints each request's token counts, then Tracarbon prints the session totals. The end of a
run on an Apple M4 Pro, after `sudo -v` so that macOS 27 reports CPU:

```text
prompt eval rate:     220.60 tokens/s
eval count:           437 token(s)
eval duration:        1.56133s
eval rate:            279.89 tokens/s
Tracarbon measured 9.9 s:
  host: 0.086175 Wh, 0.003475 g CO2e
  cpu: 0.055301 Wh, 0.002431 g CO2e
  memory: unavailable
  gpu: 0.030875 Wh, 0.001044 g CO2e
```

For token counts as JSON, measure API requests and keep each
[response](https://docs.ollama.com/api/generate):

```sh
echo '{"model": "qwen2.5:0.5b", "prompt": "Explain how a database executes a join.", "stream": false}' > ollama-request.json
tracarbon exec --output ollama-api-session.json -- sh -ec \
  'set -C; for request in 1 2 3 4 5; do curl --fail-with-body -sS http://localhost:11434/api/generate -d @ollama-request.json > "ollama-response-$request.json"; done'
```

## Read the report

`metric_report.energy_consumption_gpu.total` is GPU energy in Wh and `carbon_emission_gpu.total` is
grams of CO2e. Other components use the same names. A missing component is unavailable on this
platform ([supported devices](../README.md#-supported-devices)).
