/**
 * End-to-end inline latency benchmark.
 *
 * Path measured per request:
 *   Node payload build -> 22-D extraction -> local feature-risk score
 *   -> HTTP /predict (gate inference + threat typing) -> policy branch
 *
 * The model service is the real ml_engine/model_service.py request handler,
 * with the shipped forests executed by ONNX Runtime (see serve_gate.py).
 *
 * Usage:
 *   node experiments/scripts/latency_bench.js <inputs.json> <output.json>
 */
'use strict';

const fs = require('fs');
const path = require('path');
const AI = path.resolve(__dirname, '..', '..', '..', 'Ai-Agent');
const extractor = require(path.join(AI, 'proxy', 'feature_extractor.js'));

const SERVICE = process.env.ML_ENGINE_URL || 'http://127.0.0.1:5001';
const WARMUP = 300;

function percentile(sorted, p) {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[idx];
}

function summarise(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return {
    n: sorted.length,
    p50: percentile(sorted, 50),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
    mean: sorted.reduce((a, b) => a + b, 0) / sorted.length,
    max: sorted[sorted.length - 1],
  };
}

async function main() {
  const inputPath = process.argv[2] || path.join(__dirname, '..', 'results', 'latency', 'latency_inputs.json');
  const outputPath = process.argv[3] || path.join(__dirname, '..', 'results', 'latency', 'latency_report.json');
  const items = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  console.log(`loaded ${items.length} requests`);

  const rows = [];
  let failures = 0;

  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    const req = {
      originalUrl: item.url,
      method: item.method,
      headers: { 'user-agent': item.userAgent || '' },
      body: item.body || '',
    };

    const t0 = process.hrtime.bigint();
    const bundle = extractor.extractFeatureBundle(req, 'v3');
    const t1 = process.hrtime.bigint();
    const risk = extractor.scoreFeatureRisk(bundle.features);
    const t2 = process.hrtime.bigint();

    let ok = false;
    let isAnomaly = false;
    let threatType = '';
    let httpStart = process.hrtime.bigint();
    try {
      const res = await fetch(`${SERVICE}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload: bundle.payload,
          userAgent: item.userAgent || '',
          method: item.method,
          version: 'v3',
          featureNames: bundle.names,
          features: bundle.vector,
        }),
      });
      const body = await res.json();
      const t3 = process.hrtime.bigint();
      ok = res.ok;
      isAnomaly = Boolean(body.isAnomaly);
      threatType = body.threatType || '';
      var httpMs = Number(t3 - httpStart) / 1e6;
    } catch (err) {
      failures += 1;
      if (failures <= 5) console.error(`request ${i} failed: ${err.message}`);
    }
    if (httpMs === undefined) httpMs = 0;
    const t4 = process.hrtime.bigint();

    const extractionMs = Number(t1 - t0) / 1e6;
    const scoreMs = Number(t2 - t1) / 1e6;
    const totalMs = Number(t4 - t0) / 1e6;

    if (i >= WARMUP) {
      rows.push({
        corpus: item.corpus,
        label: item.label,
        extractionMs,
        scoreMs,
        httpMs,
        totalMs,
        risk,
        isAnomaly,
        threatType,
        ok,
      });
    }
    if ((i + 1) % 1000 === 0) {
      console.log(`  ${i + 1}/${items.length}  last total=${totalMs.toFixed(3)} ms`);
    }
  }

  const measured = rows.filter((r) => r.ok);
  const groups = {};
  for (const corpus of ['csic', 'ecml', 'wcp', 'all']) {
    const subset = corpus === 'all' ? measured : measured.filter((r) => r.corpus === corpus);
    groups[corpus] = {
      count: subset.length,
      extraction: summarise(subset.map((r) => r.extractionMs)),
      score: summarise(subset.map((r) => r.scoreMs)),
      http: summarise(subset.map((r) => r.httpMs)),
      total: summarise(subset.map((r) => r.totalMs)),
    };
  }

  const report = {
    service: SERVICE,
    requests: items.length,
    warmup: WARMUP,
    measured: measured.length,
    failures,
    slo_ms: 5.0,
    slo_met: groups.all.total.p95 < 5.0,
    groups,
    generated_at: new Date().toISOString(),
  };

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
  const header = 'corpus,label,extractionMs,scoreMs,httpMs,totalMs,risk,isAnomaly,threatType,ok';
  const csv = [header].concat(rows.map((r) => [
    r.corpus, r.label, r.extractionMs.toFixed(6), r.scoreMs.toFixed(6),
    r.httpMs.toFixed(6), r.totalMs.toFixed(6), r.risk, r.isAnomaly, r.threatType, r.ok,
  ].join(','))).join('\n');
  fs.writeFileSync(path.join(path.dirname(outputPath), 'latency_samples.csv'), csv);

  console.log(JSON.stringify(report, null, 2));
  if (!report.slo_met) process.exitCode = 2;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
