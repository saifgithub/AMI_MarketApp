// k6 load test for the 1-on-1 streaming endpoint (B12, CR126). Targets
// p95 latency at 10/50/100 concurrent per project_plan.md's B12 spec.
//
// Authored only — NOT run against live Alpha under CR126. Running this
// against production traffic needs Saiful's explicit go-ahead and an
// off-peak window; point BASE_URL at a Beta/staging Cloud Run revision once
// one exists, or a throwaway local instance first.
//
// Usage:
//   k6 run -e BASE_URL=https://api-alpha.agenticmarketintel.ai -e VUS=10 load_test_1on1.js
//   k6 run -e BASE_URL=... -e VUS=50 load_test_1on1.js
//   k6 run -e BASE_URL=... -e VUS=100 load_test_1on1.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const VUS = parseInt(__ENV.VUS || "10", 10);

export const options = {
  scenarios: {
    one_on_one: {
      executor: "constant-vus",
      vus: VUS,
      duration: __ENV.DURATION || "2m",
    },
  },
  thresholds: {
    // hosting.md's Cloud Run sample allows up to 300s for a Room session;
    // a single 1-on-1 message should land well inside that.
    http_req_duration: ["p(95)<5000"],
    checks: ["rate>0.95"],
  },
};

export default function () {
  // Fresh anonymous session per iteration — mirrors a real cold-start user,
  // not a single warmed-up token reused across every request.
  const anonRes = http.post(
    `${BASE_URL}/v1/auth/anon`,
    JSON.stringify({ locale: "en", timezone: "UTC" }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(anonRes, { "anon session created": (r) => r.status === 200 });
  if (anonRes.status !== 200) {
    sleep(1);
    return;
  }
  const token = anonRes.json("token");
  const authHeaders = {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  };

  // Concierge is free at every plan (Floor Pass included) — no agent-unlock
  // gate to work around for a pure infra load test.
  const startRes = http.post(
    `${BASE_URL}/v1/agents/one_on_one/start`,
    JSON.stringify({ agent_id: "concierge", locale: "en" }),
    authHeaders
  );
  check(startRes, { "session started": (r) => r.status === 201 });
  if (startRes.status !== 201) {
    sleep(1);
    return;
  }
  const sessionId = startRes.json("id");

  const msgRes = http.post(
    `${BASE_URL}/v1/agents/one_on_one/message`,
    JSON.stringify({
      session_id: sessionId,
      user_message: "What's a good first lesson for a beginner?",
      history: [],
    }),
    authHeaders
  );
  check(msgRes, { "message streamed": (r) => r.status === 200 });

  sleep(1);
}
