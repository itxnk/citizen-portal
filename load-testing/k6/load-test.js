/**
 * DESC Cloud-Native Demo — k6 Load Test
 * Targets the API Gateway which fans out to all microservices.
 * /api/stress → Gateway → Records Service (CPU-intensive) → triggers HPA
 *
 * Usage:
 *   k6 run --env BASE_URL=http://<alb-dns> load-test.js
 *
 * Watch HPA in a separate terminal:
 *   watch -n2 "kubectl get hpa -n desc-app"
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const errorRate     = new Rate("custom_error_rate");
const stressLatency = new Trend("stress_endpoint_latency_ms");
const recordsCreated = new Counter("records_created");

export const options = {
  stages: [
    { duration: "1m",  target: 10  },   // warm-up
    { duration: "2m",  target: 50  },   // moderate load
    { duration: "5m",  target: 200 },   // heavy load — push Records Service CPU > 50%
    { duration: "3m",  target: 200 },   // sustain — watch HPA scale replicas
    { duration: "2m",  target: 0   },   // cool-down
  ],
  thresholds: {
    http_req_failed:      ["rate<0.01"],   // <1% errors
    http_req_duration:    ["p(95)<2000"],  // P95 < 2s
    custom_error_rate:    ["rate<0.05"],
  },
};

const HEADERS = { "Content-Type": "application/json" };

export default function () {
  const r = Math.random();

  if (r < 0.50) {
    // 50% — stress Records Service (CPU spike → HPA trigger)
    const start = Date.now();
    const res = http.get(`${BASE_URL}/api/stress?n=8000`);
    stressLatency.add(Date.now() - start);
    const ok = check(res, {
      "stress 200":          (r) => r.status === 200,
      "stress has primes":   (r) => { try { return JSON.parse(r.body).primes_found > 0; } catch { return false; } },
    });
    errorRate.add(!ok);

  } else if (r < 0.70) {
    // 20% — list records (cache-aside path)
    const res = http.get(`${BASE_URL}/api/records`);
    const ok = check(res, {
      "records 200": (r) => r.status === 200,
      "records array": (r) => { try { return Array.isArray(JSON.parse(r.body).records); } catch { return false; } },
    });
    errorRate.add(!ok);

  } else if (r < 0.85) {
    // 15% — list users
    const res = http.get(`${BASE_URL}/api/users`);
    const ok = check(res, { "users 200": (r) => r.status === 200 });
    errorRate.add(!ok);

  } else if (r < 0.95) {
    // 10% — create a record (DB write + cache invalidation)
    const res = http.post(
      `${BASE_URL}/api/records`,
      JSON.stringify({ title: `Load test record ${Date.now()}`, status: "pending" }),
      { headers: HEADERS }
    );
    const ok = check(res, { "create record 201": (r) => r.status === 201 });
    if (ok) recordsCreated.add(1);
    errorRate.add(!ok);

  } else {
    // 5% — list notifications
    const res = http.get(`${BASE_URL}/api/notifications`);
    const ok = check(res, { "notifications 200": (r) => r.status === 200 });
    errorRate.add(!ok);
  }

  sleep(Math.random() * 0.5 + 0.1);
}

export function handleSummary(data) {
  return {
    stdout: `
╔══════════════════════════════════════════════════════╗
║         DESC Microservices Load Test Summary         ║
╠══════════════════════════════════════════════════════╣
║ Total requests  : ${data.metrics.http_reqs.values.count}
║ Error rate      : ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%
║ P95 latency     : ${data.metrics.http_req_duration.values["p(95)"].toFixed(0)}ms
║ Records created : ${data.metrics.records_created ? data.metrics.records_created.values.count : 0}
╚══════════════════════════════════════════════════════╝
`,
  };
}
