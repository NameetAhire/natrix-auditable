'use strict';

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { extractFeatures, featureDictToVector } = require(
  path.resolve(__dirname, '../../../Ai-Agent/proxy/feature_extractor.js'),
);

async function main() {
  const [, , inPath, outPath] = process.argv;
  if (!inPath || !outPath) {
    throw new Error('usage: node extractor_parity.js <in.jsonl> <out.jsonl>');
  }
  const out = fs.createWriteStream(outPath, { encoding: 'utf8' });
  const rl = readline.createInterface({
    input: fs.createReadStream(inPath, { encoding: 'utf8' }),
    crlfDelay: Infinity,
  });
  let n = 0;
  for await (const line of rl) {
    if (!line.trim()) continue;
    const row = JSON.parse(line);
    const features = extractFeatures(
      row.payload || '',
      row.user_agent || '',
      row.method || 'GET',
      'v3',
    );
    out.write(JSON.stringify({ vector: featureDictToVector(features, 'v3') }) + '\n');
    n += 1;
  }
  out.end();
  await new Promise((resolve) => out.on('finish', resolve));
  console.log(`wrote ${n} vectors`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
