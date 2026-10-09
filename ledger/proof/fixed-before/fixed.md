# 'Fixed' check

- **passed: False**  (provisional thresholds: False)
- runs evaluated: 3

| criterion | passed | details |
|---|---|---|
| min_consecutive_runs | yes | `{"have": 3, "need": 3}` |
| no_steady_periodic | yes | `{"offenders": [], "max_period_s": 10.0, "p_threshold": 0.01}` |
| fps_0p1pct_low_min | NO | `{"offenders": [{"run": "live-baseline-1", "fps_0.1pct_low": 1.622116359552495}, {"run": "live-baseline-2", "fps_0.1pct_low": 0.8135889649004321}, {"run": "live-baseline-3", "fps_0.1pct_low": 0.8568058351904599}], "value": 30.0}` |
| min_run_duration_min | yes | `{"offenders": [], "value": 5.0}` |
| hitches_per_min_max | NO | `{"offenders": [{"run": "live-baseline-1", "per_min": 54.574696407055}, {"run": "live-baseline-2", "per_min": 39.46064969851666}, {"run": "live-baseline-3", "per_min": 39.28896591483449}], "value": 6.0}` |
| worst_hitch_ms_max | NO | `{"offenders": [{"run": "live-baseline-1", "worst_ms": 1734.24}, {"run": "live-baseline-2", "worst_ms": 2958.38}, {"run": "live-baseline-3", "worst_ms": 3265.24}], "value": 100.0}` |
| longest_run_min | NO | `{"longest_min": 6.0067755540212, "need": 15.0}` |

