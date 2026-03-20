#!/usr/bin/env node
/**
 * stress-webhook.js — generate concurrent Twilio webhook requests for load testing.
 *
 * IMPORTANT:
 * - This is meant for environments where TWILIO_SKIP_VALIDATION=true (dev/staging).
 * - In production, Twilio Signature validation will fail without a valid signature.
 *
 * Example:
 *   node scripts/stress-webhook.js \
 *     --url "http://localhost:8000/api/twilio/webhook?step=start" \
 *     --count 50 --concurrency 10 \
 *     --speech "appointment"
 */

const args = process.argv.slice(2);
function getArg(flag, fallback) {
  const idx = args.indexOf(flag);
  if (idx === -1) return fallback;
  return args[idx + 1];
}
function getInt(flag, fallback) {
  const v = getArg(flag, null);
  if (v === null || v === undefined) return fallback;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : fallback;
}

const url = getArg("--url", "");
if (!url) {
  console.error("Missing --url");
  process.exit(2);
}

const count = getInt("--count", 20);
const concurrency = getInt("--concurrency", 5);
const speech = getArg("--speech", "appointment");
const from = getArg("--from", "+15551234567");

// Minimal fields required by the webhook handler:
// - CallSid: key for per-call state and Redis result keying
// - From: logged/trace context (optional for logic, but realistic)
// - SpeechResult: triggers the LLM-intent path at step=start
function randomCallSid() {
  return "CA" + Math.random().toString(36).slice(2, 15);
}

async function sendOne(i) {
  const callSid = randomCallSid();
  const params = new URLSearchParams();
  params.set("CallSid", callSid);
  params.set("From", from);
  params.set("SpeechResult", speech);
  // Digits and Confidence are optional; webhook code handles missing/None.

  const t0 = Date.now();
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });
  const t1 = Date.now();

  // We don't parse body to keep overhead low; TwiML is XML and large enough.
  return {
    i,
    callSid,
    status: res.status,
    ms: t1 - t0,
  };
}

async function run() {
  const results = [];
  let next = 0;
  let inFlight = 0;

  const startAll = Date.now();

  await new Promise((resolve, reject) => {
    const launch = () => {
      while (inFlight < concurrency && next < count) {
        const i = next++;
        inFlight++;
        sendOne(i)
          .then((r) => results.push(r))
          .catch((e) => {
            results.push({ i, status: 0, ms: 0, error: String(e) });
          })
          .finally(() => {
            inFlight--;
            if (next >= count && inFlight === 0) resolve();
            else launch();
          });
      }
    };
    launch();
  });

  const endAll = Date.now();
  results.sort((a, b) => a.ms - b.ms);
  const latencies = results.map((r) => r.ms).filter((n) => typeof n === "number" && n >= 0);
  const ok = results.filter((r) => r.status >= 200 && r.status < 500); // some 4xx expected without signature in wrong env
  const avg = latencies.reduce((a, b) => a + b, 0) / Math.max(1, latencies.length);
  const p95 = latencies[Math.floor(latencies.length * 0.95)] ?? 0;

  console.log("=== Stress results ===");
  console.log(`Requests: ${count}`);
  console.log(`Concurrency: ${concurrency}`);
  console.log(`Total wall time (ms): ${endAll - startAll}`);
  console.log(`OK/Received: ${ok.length}/${results.length}`);
  console.log(`Avg latency (ms): ${avg.toFixed(1)}`);
  console.log(`P95 latency (ms): ${p95}ms`);

  // Print a small sample of slowest requests
  const worst = results.slice(-10).reverse();
  console.log("\nSlowest requests:");
  for (const r of worst) {
    if (r && r.error) console.log(`  #${r.i} ERROR ${r.error}`);
    else console.log(`  #${r.i} status=${r.status} ms=${r.ms} callSid=${r.callSid}`);
  }
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});

