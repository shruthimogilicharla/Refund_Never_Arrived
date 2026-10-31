# Usage report

## Final full-dataset run (300 complaints)

| Item | Value |
| --- | --- |
| Mode | Default (rules engine, no `--llm`) |
| Model provider / model | None |
| Model calls | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total / average tokens per complaint | 0 / 0 |
| Estimated cost | USD 0.00 total, USD 0.00 per complaint |
| Wall time | about 20 s on one CPU core (most of it parsing 1,049 statements, each parsed once and cached) |

Every complaint in this dataset was read correctly by the rule-based reader, so the final output did not need a model.

## Optional `--llm` mode

`python code/main.py --llm` sends each complaint's text (and nothing else) to an OpenAI-compatible endpoint, one call per complaint. It hasn't been run for this report because no API key was available in the build environment.

Rough size per call: about 250 input and 40 output tokens, so about 87,000 tokens for 300 complaints. Check your provider's current prices to estimate the cost. When it runs, every call's token counts are appended to `llm_usage.jsonl`, and the run prints the totals. Copy those numbers here.

| Item | Value |
| --- | --- |
| Model provider / model | _fill in after a run_ |
| Model calls | _from the run summary_ |
| Input / output tokens | _from `llm_usage.jsonl`_ |
| Estimated cost total / per complaint | _tokens × provider price_ |
