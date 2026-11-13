# Reproduce the NATRIX Q1 experiment set (PowerShell, Windows).
#
# Prerequisites:
#   * Python 3.11+ with requirements installed;
#   * Node 18+ (tested on Node 22) for the latency benchmark;
#   * the ONNX serving adapter running on 127.0.0.1:5001:
#       python experiments/scripts/serve_gate.py --port 5001
#
# Every command is idempotent: outputs are overwritten under
# experiments/results/ and artifacts/feature_selection/.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "== 1. feature audit (CSIC) =="
python experiments/scripts/audit_univariate.py
python experiments/scripts/audit_model.py

Write-Host "== 2. leave-one-feature-out ablation =="
python experiments/scripts/evaluate_featuresets.py --out ablation_csic

Write-Host "== 3. merge drop evidence =="
python experiments/scripts/merge_drop_evidence.py
python experiments/scripts/write_drop_appendix.py

Write-Host "== 4. v4 candidate screening =="
python experiments/scripts/screen_candidates.py

Write-Host "== 5. candidate extraction cost and v4 finalisation =="
python experiments/scripts/measure_candidate_cost.py
python experiments/scripts/finalize_v4.py

Write-Host "== 6. headline v3 vs v4 (nested thresholds, 3 seeds) =="
python experiments/scripts/compare_v3_v4.py
python experiments/scripts/calibrate_thresholds.py

Write-Host "== 7. in-distribution corpora (P1/P2, threshold 0.5) =="
python experiments/scripts/evaluate_corpora.py --corpora csic ecml srbh --protocols P1 P2

Write-Host "== 7b. cross-fitted corpus threshold sensitivity =="
python experiments/scripts/calibrate_corpora.py

Write-Host "== 8. cross-corpus transfer and WCP =="
python experiments/scripts/evaluate_transfer.py

Write-Host "== 9. SHAP audit =="
python experiments/scripts/audit_shap.py

Write-Host "== 10. secondary learners =="
python experiments/scripts/evaluate_learners.py

Write-Host "== 11. cross-corpus feature replication =="
python experiments/scripts/audit_cross_corpus.py

Write-Host "== 12. formal verification =="
python -m pytest experiments/tests/test_formal.py -v

Write-Host "== 13. end-to-end latency (service must be running) =="
node experiments/scripts/latency_bench.js

Write-Host "== 14. result tables =="
python experiments/scripts/make_result_tables.py

Write-Host "== 15. result and architecture figures =="
python experiments/scripts/make_figures.py
python experiments/scripts/make_architecture_figure.py

Write-Host "All experiments complete."
