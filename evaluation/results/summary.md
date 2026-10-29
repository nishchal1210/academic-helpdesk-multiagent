# Measured evaluation results

Results describe the recorded responses and configuration in experiment.json. Automatic status, keyword and citation checks are reported separately from semantic review.

| Model | Mode | N | Status accuracy | Fact-match proxy | OOS refusal | Citation structure | Error rate | Mean seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3:8b | single | 66 | 0.909 | 0.769 | 1.000 | 1.000 | 0.000 | 3.711 |
| qwen3:8b | multi | 66 | 0.955 | 0.846 | 1.000 | 1.000 | 0.000 | 3.566 |
| qwen2.5:3b | single | 66 | 0.955 | 0.846 | 1.000 | 1.000 | 0.000 | 3.026 |
| qwen2.5:3b | multi | 66 | 0.955 | 0.846 | 1.000 | 1.000 | 0.000 | 2.971 |

## Repeated-run changes

Exact answer changes include wording and content changes. Status/source changes are listed separately. Wording differences are distinct from factual changes.

No exact answer or status/source changes were observed within any recorded model/mode group.

## Semantic review

Review annotations and their provenance are recorded in reviews.csv. Accuracy includes correct refusals and clarification requests. Groundedness is scored on factual answers. Unscored entries are excluded from the corresponding denominator.

| Model / mode | Reviewed accuracy | Reviewed groundedness | Reviewer counts |
|---|---:|---:|---|
| qwen3:8b/single | 0.864 (n=66) | 0.909 (n=33) | {'assistant': 66} |
| qwen3:8b/multi | 0.909 (n=66) | 0.917 (n=36) | {'assistant': 66} |
| qwen2.5:3b/single | 0.909 (n=66) | 0.833 (n=36) | {'assistant': 66} |
| qwen2.5:3b/multi | 0.909 (n=66) | 0.833 (n=36) | {'assistant': 66} |
