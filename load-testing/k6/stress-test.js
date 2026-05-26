/**
 * DESC Cloud-Native Demo — k6 Spike Test (Live Demo)
 * Instantly ramps to 300 VUs all hitting /api/stress.
 * /api/stress routes: ALB → Gateway → Records Service → prime calculation
 *
 * Usage:
 *   k6 run --env BASE_URL=http://<alb-dns> stress-test.js
 *
 * Show to evaluation board:
 *   Terminal 1: watch -n2 "kubectl get hpa,pods -n desc-app --no-headers | column -t"
 *   Terminal 2: k6 run --env BASE_URL=$BASE_URL stress-test.js
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const errorRate = new Rate("errors");

export const options = {
  stages: [
    { duration: "30s", target: 300 },   // instant spike → push Records Service CPU > 50%
    { duration: "4m",  target: 300 },   // sustain — watch replicas 2 → 6 → 12 → 15
    { duration: "30s", target: 0   },   // ramp down — observe scale-down (5 min window)
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    errors:          ["rate<0.05"],
  },
};

export default function () {
  // All VUs hit Records Service /stress via Gateway to maximise CPU pressure
  const res = http.get(`${BASE_URL}/api/stress?n=10000`, { timeout: "30s" });
  const ok  = check(res, { "status 200": (r) => r.status === 200 });
  errorRate.add(!ok);
  sleep(0.05);
}
