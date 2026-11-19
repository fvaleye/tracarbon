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
run on an Apple M4 Pro:

```text
prompt eval rate:     178.22 tokens/s
eval count:           240 token(s)
eval duration:        1.119126s
eval rate:            214.45 tokens/s
Tracarbon measured 7.9 s:
  host: 0.123134 Wh, 0.005103 g CO2e
  cpu: 0.079348 Wh, 0.003288 g CO2e
  memory: 0.007019 Wh, 0.000291 g CO2e
  gpu: 0.036767 Wh, 0.001524 g CO2e
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
