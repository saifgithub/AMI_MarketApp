// k6 multi-persona load test for the disposable CR246 loadtest instance.
// CR246: drive N concurrent synthetic users (default 10) through a realistic
// mix — browsers, Room conveners, a trader, an onboarding interviewee, and a
// Brief/1-on-1 chatter — over HTTP, and FAIL the run on the correctness
// invariants the CR cares about: no 5xx, no cross-user data leaks (any JSON
// response carrying a user_id / user.id that isn't the caller's own), and a
// p(99) latency budget. 429s (per-user rate limits: room stream 5/min,
// 1-on-1 12/min, brief 12/min — rate_limit.py) and 402s (credit wall — a fresh
// Floor Pass user carries a 13-credit allowance after the first credit touch,
// Room costs 8, each Brief/1-on-1 turn 1) are expected backpressure, counted
// but never failures.
//
// Run against the throwaway minihost instance ONLY — never Alpha. The target
// DB must have the ticker reference seeded (AAPL/MSFT/NVDA/GOOGL/AMZN) or the
// trading/Room personas 422 on every call.
//
// Usage (local k6):
//   k6 run -e BASE_URL=http://minihost:8000 -e VUS=10 -e DURATION=20m load_test_mix.js
//   k6 run -e BASE_URL=http://minihost:8000 -e VUS=10 -e SUMMARY_OUT=/tmp/summary.json load_test_mix.js
//
// Usage (dockerized grafana/k6, from the repo root):
//   mkdir -p results
//   docker run --rm -v "$PWD/backend/scripts:/scripts" -v "$PWD/results:/results" \
//     -e BASE_URL=http://minihost:8000 -e VUS=10 -e DURATION=20m \
//     grafana/k6 run /scripts/load_test_mix.js

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const VUS = parseInt(__ENV.VUS || "10", 10);
const DURATION = __ENV.DURATION || "20m";
const SUMMARY_OUT = __ENV.SUMMARY_OUT || "/results/summary.json";
const SETUP_PACE_SECONDS = 6.5; // auth_anon is capped at 10/min per IP (rate_limit.py)

// Correctness counters (CR246's point).
const crossUserLeaks = new Counter("cross_user_leaks");
const serverErrors = new Counter("server_errors");
const rateLimited = new Counter("rate_limited");
const creditsExhausted = new Counter("credits_exhausted");
const clientErrors = new Counter("client_errors");

const PERSONA_MIX = [
  { persona: "browser", weight: 0.5 },
  { persona: "room", weight: 0.2 },
  { persona: "trader", weight: 0.1 },
  { persona: "onboarding", weight: 0.1 },
  { persona: "chat", weight: 0.1 }, // Brief + 1-on-1
];

const TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"];

// Per-user open trade ids, closed on later passes (trader persona).
const openTradesByUser = {};

function buildPersonas(n) {
  // Largest-remainder apportioning so counts sum to exactly n.
  const exact = PERSONA_MIX.map((m) => n * m.weight);
  const counts = exact.map(Math.floor);
  let leftover = n - counts.reduce((a, b) => a + b, 0);
  const byRemainder = exact
    .map((e, i) => ({ i, rem: e - Math.floor(e) }))
    .sort((a, b) => b.rem - a.rem);
  for (const { i } of byRemainder) {
    if (leftover <= 0) break;
    counts[i] += 1;
    leftover -= 1;
  }
  const out = [];
  PERSONA_MIX.forEach((m, i) => {
    for (let k = 0; k < counts[i]; k++) out.push(m.persona);
  });
  return out;
}

const PERSONAS = buildPersonas(VUS);

export const options = {
  scenarios: {
    mixed: {
      executor: "constant-vus",
      vus: VUS,
      duration: DURATION,
    },
  },
  // (VUS + 5) anon mints paced at SETUP_PACE_SECONDS, plus slack for the
  // requests themselves — auth_anon's 10/min cap makes setup the long pole.
  setupTimeout: `${Math.ceil((VUS + 5) * SETUP_PACE_SECONDS) + 60}s`,
  // p(99) is not in the default summary trend stats — without this the JSON
  // summary has no p(99) key even though the threshold below uses it.
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  thresholds: {
    // The 2s bar covers non-SSE requests only. Streams get a loose smoke
    // bound (60s p99 in mock mode) — their tight bar belongs to the deferred
    // real-vLLM phase, where the model, not the app, sets the number.
    "http_req_duration{rt:read}": ["p(99)<2000"],
    "http_req_duration{rt:stream}": ["p(99)<60000"],
    server_errors: ["count==0"],
    cross_user_leaks: ["count==0"],
  },
};

function jitter(min, max) {
  return min + Math.random() * (max - min);
}

function collectForeignUserIds(node, ownUserId) {
  const bad = [];
  if (Array.isArray(node)) {
    for (const el of node) bad.push(...collectForeignUserIds(el, ownUserId));
  } else if (node !== null && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      if (key === "user_id" && typeof value === "string" && value !== ownUserId) {
        // "anonymous-pending-claim" is a hardcoded placeholder in the
        // PRE-AUTH onboarding readback (api/onboarding.py:198) — the same
        // constant for everyone, carrying no user data. Not a leak.
        if (value !== "anonymous-pending-claim") bad.push(value);
      }
      if (
        key === "user" && value !== null && typeof value === "object" &&
        typeof value.id === "string" && value.id !== ownUserId
      ) {
        bad.push(value.id);
      }
      bad.push(...collectForeignUserIds(value, ownUserId));
    }
  }
  return bad;
}

// CR246 core assertion: a JSON response may only ever name the caller's own
// user id. SSE bodies are skipped — their events carry no user_id fields.
function assertNoCrossUserLeak(res, ownUserId, tag) {
  const contentType = res.headers["Content-Type"] || "";
  if (!contentType.includes("application/json")) return;
  let body;
  try {
    body = res.json();
  } catch (e) {
    return;
  }
  const foreign = collectForeignUserIds(body, ownUserId);
  if (foreign.length > 0) {
    crossUserLeaks.add(foreign.length);
    console.error(
      `CROSS-USER LEAK [${tag}] vu=${__VU}: response names ${foreign[0]}, caller is ${ownUserId}`
    );
  }
}

// Accounts for every response: expected backpressure (429/402) is counted and
// neutral; 5xx trip the server_errors counter; other 4xx land in client_errors;
// clean JSON responses get the leak assertion.
function measure(res, me, tag, okStatuses) {
  if (res.status === 429) {
    rateLimited.add(1);
    return "rate_limited";
  }
  if (res.status === 402) {
    creditsExhausted.add(1);
    return "credits_exhausted";
  }
  if (res.status >= 500) {
    serverErrors.add(1);
    check(res, { [`${tag}: no 5xx`]: (r) => r.status < 500 });
    return "server_error";
  }
  if (res.status >= 400) {
    clientErrors.add(1);
    check(res, { [`${tag}: expected ${okStatuses}`]: (r) => okStatuses.includes(r.status) });
    return "client_error";
  }
  assertNoCrossUserLeak(res, me.user_id, tag);
  check(res, { [`${tag}: expected ${okStatuses}`]: (r) => okStatuses.includes(r.status) });
  return "ok";
}

function authHeaders(me, rt = "read") {
  return {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${me.token}`,
    },
    // rt tags split the latency bar: SSE streams (room stream, 1-on-1 and
    // brief messages) legitimately run long — http_req_waiting showed the
    // server answering in ~270ms p99 while http_req_duration ran to 25s
    // because k6 counts the whole streamed body. Reads carry the real p99 bar.
    tags: { rt },
  };
}

// One fresh anon user per VU for the whole run (plus a spare tail the operator
// can borrow for ad-hoc calls). Paced under the 10/min per-IP cap.
export function setup() {
  const users = [];
  const count = VUS + 5;
  for (let i = 0; i < count; i++) {
    const res = http.post(
      `${BASE_URL}/v1/auth/anon`,
      JSON.stringify({}),
      { headers: { "Content-Type": "application/json" } }
    );
    if (res.status !== 200) {
      throw new Error(`setup: anon mint ${i + 1}/${count} failed: HTTP ${res.status}`);
    }
    const body = res.json();
    users.push({ user_id: body.user.id, token: body.token });
    if (i < count - 1) sleep(SETUP_PACE_SECONDS);
  }
  // Seed the custom metrics so the zero-case still evaluates its thresholds.
  serverErrors.add(0);
  crossUserLeaks.add(0);
  return users;
}

function browser(me, h) {
  const reads = [
    ["GET", `/v1/sim/portfolio/${me.user_id}`, null, 200, "browser portfolio"],
    ["GET", `/v1/sector-watch/${me.user_id}`, null, 200, "browser sector-watch"],
    ["GET", `/v1/portfolio/health/${me.user_id}`, null, 200, "browser health"],
    ["GET", `/v1/sim/trades/${me.user_id}`, null, 200, "browser trades"],
  ];
  for (const [method, path, body, ok, tag] of reads) {
    const res = http.request(method, `${BASE_URL}${path}`, body, h);
    measure(res, me, tag, [ok]);
    sleep(jitter(2, 4));
  }
}

function room(me, h) {
  const ticker = TICKERS[Math.floor(Math.random() * TICKERS.length)];
  // SSE: k6 buffers the body until the run finishes; mock LLM completes fast.
  // 5/min per user — 429 is the expected backpressure shape.
  const res = http.post(
    `${BASE_URL}/v1/room/stream`,
    JSON.stringify({ user_id: me.user_id, ticker }),
    authHeaders(me, "stream")
  );
  const outcome = measure(res, me, "room stream", [200]);
  if (outcome === "ok") {
    const list = http.get(`${BASE_URL}/v1/room/user/${me.user_id}`, h);
    measure(list, me, "room user runs", [200]);
  }
  sleep(jitter(4, 8));
}

function trader(me, h) {
  // Prime ensure_portfolio first (CR246's race lives behind this call).
  const pf = http.get(`${BASE_URL}/v1/sim/portfolio/${me.user_id}`, h);
  measure(pf, me, "trader portfolio", [200]);
  sleep(jitter(1, 3));

  const ticker = TICKERS[Math.floor(Math.random() * TICKERS.length)];
  const order = JSON.stringify({
    user_id: me.user_id,
    ticker,
    side: "buy",
    quantity: 1,
    order_type: "market",
  });
  const preview = http.post(`${BASE_URL}/v1/sim/preview`, order, h);
  measure(preview, me, "trader preview", [200]);
  sleep(jitter(1, 3));

  const submit = http.post(`${BASE_URL}/v1/sim/submit`, order, h);
  if (measure(submit, me, "trader submit", [200]) === "ok") {
    let body;
    try {
      body = submit.json();
    } catch (e) {
      body = null;
    }
    if (body && body.ok && body.resting === false && body.trade && body.trade.id) {
      (openTradesByUser[me.user_id] = openTradesByUser[me.user_id] || []).push(
        body.trade.id
      );
    }
  }

  // Close the oldest open position from an earlier pass.
  const open = openTradesByUser[me.user_id];
  if (open && open.length > 0) {
    sleep(jitter(2, 5));
    const tradeId = open.shift();
    const close = http.post(
      `${BASE_URL}/v1/sim/trades/${me.user_id}/close`,
      JSON.stringify({ trade_id: tradeId }),
      h
    );
    measure(close, me, "trader close", [200]);
  }
  sleep(jitter(3, 6));
}

// The onboarding routes are anonymous-first (no router-level auth) — run them
// bare, mirroring a real cold interview. Steps/echoes come from the server's
// own responses; Q6 must parse as a percentage or the step re-asks (DEF428).
const ONBOARDING_ANSWERS = {
  q1_goal: "Build long-term wealth",
  q2_horizon: "3-10 years",
  q3_scenario_drawdown: "Hold and wait",
  q4_scenario_regret: "About the same",
  q5_scenario_concentration: "10% (cautious)",
  q6_max_drawdown: "20%",
  q7_constraints: "No hard rules",
};

function onboarding(me) {
  const bare = {
    headers: { "Content-Type": "application/json" },
    tags: { rt: "read" },
  };
  const start = http.post(
    `${BASE_URL}/v1/onboarding/start`,
    JSON.stringify({ locale: "en", timezone: "UTC" }),
    bare
  );
  if (measure(start, me, "onboarding start", [201]) !== "ok") {
    sleep(3);
    return;
  }
  const sessionId = start.json("session_id");
  let step = start.json("first_question.step");
  for (let i = 0; i < 10 && step && step !== "readback" && step !== "complete"; i++) {
    const answer = http.post(
      `${BASE_URL}/v1/onboarding/answer`,
      JSON.stringify({
        session_id: sessionId,
        step,
        answer: ONBOARDING_ANSWERS[step] || "No hard rules",
      }),
      bare
    );
    if (measure(answer, me, `onboarding answer ${step}`, [200]) !== "ok") {
      sleep(3);
      return;
    }
    step = answer.json("next_step");
    sleep(jitter(1, 3));
  }
  if (step === "readback") {
    const confirm = http.post(
      `${BASE_URL}/v1/onboarding/readback/confirm`,
      JSON.stringify({ session_id: sessionId, confirm: "confirm", restart: false }),
      bare
    );
    measure(confirm, me, "onboarding confirm", [200]);
  }
  sleep(jitter(3, 6));
}

function chat(me, h) {
  const oneOnOneStart = http.post(
    `${BASE_URL}/v1/agents/one_on_one/start`,
    JSON.stringify({ agent_id: "concierge", locale: "en" }),
    h
  );
  let out = measure(oneOnOneStart, me, "1on1 start", [201]);
  if (out === "ok") {
    const sessionId = oneOnOneStart.json("id");
    sleep(jitter(1, 2));
    const msg = http.post(
      `${BASE_URL}/v1/agents/one_on_one/message`,
      JSON.stringify({
        session_id: sessionId,
        user_message: "What should I watch on AAPL this week?",
        history: [],
      }),
      authHeaders(me, "stream")
    );
    out = measure(msg, me, "1on1 message", [200]);
  }
  sleep(jitter(2, 5));

  if (out !== "credits_exhausted" && out !== "rate_limited") {
    const briefStart = http.post(
      `${BASE_URL}/v1/brief/start`,
      JSON.stringify({
        agent_id: "fundamentals_analyst",
        user_id: me.user_id,
        mode: "from_scratch",
      }),
      h
    );
    out = measure(briefStart, me, "brief start", [201]);
    if (out === "ok") {
      const sessionId = briefStart.json("session.id");
      sleep(jitter(1, 2));
      const msg = http.post(
        `${BASE_URL}/v1/brief/message`,
        JSON.stringify({
          session_id: sessionId,
          user_message: "Always lead with revenue growth when you brief me.",
          history: [],
        }),
        authHeaders(me, "stream")
      );
      out = measure(msg, me, "brief message", [200]);
    }
    sleep(jitter(2, 5));
  }

  // Credit wall or message-rate cap: this iteration degrades to browsing.
  if (out === "credits_exhausted" || out === "rate_limited") {
    const pf = http.get(`${BASE_URL}/v1/sim/portfolio/${me.user_id}`, h);
    measure(pf, me, "chat->browse portfolio", [200]);
    const trades = http.get(`${BASE_URL}/v1/sim/trades/${me.user_id}`, h);
    measure(trades, me, "chat->browse trades", [200]);
    sleep(jitter(2, 4));
  }
}

export default function (users) {
  const idx = (__VU - 1) % Math.min(VUS, users.length);
  const me = users[idx];
  const persona = PERSONAS[(__VU - 1) % PERSONAS.length];
  const h = authHeaders(me);
  switch (persona) {
    case "browser":
      browser(me, h);
      break;
    case "room":
      room(me, h);
      break;
    case "trader":
      trader(me, h);
      break;
    case "onboarding":
      onboarding(me);
      break;
    case "chat":
      chat(me, h);
      break;
  }
}

export function handleSummary(data) {
  const v = data.metrics;
  const line = (name) => {
    const m = v[name];
    return m ? `  ${name}: ${JSON.stringify(m.values)}` : `  ${name}: (no samples)`;
  };
  const text = [
    "CR246 load-test summary",
    `  base_url=${BASE_URL} vus=${VUS} duration=${DURATION}`,
    `  http_reqs=${v.http_reqs ? v.http_reqs.values.count : 0}`,
    `  read p(99)=${v["http_req_duration{rt:read}"] ? Math.round(v["http_req_duration{rt:read}"].values["p(99)"]) : "n/a"} ms  stream p(99)=${v["http_req_duration{rt:stream}"] ? Math.round(v["http_req_duration{rt:stream}"].values["p(99)"]) : "n/a"} ms`,
    line("cross_user_leaks"),
    line("server_errors"),
    line("rate_limited"),
    line("credits_exhausted"),
    line("client_errors"),
    `  thresholds=${data.thresholds ? `${Object.values(data.thresholds).filter((t) => t.ok).length}/${Object.keys(data.thresholds).length} passed` : "n/a"} (k6 exit code is non-zero if any failed)`,
    "",
  ].join("\n");
  const files = { "stdout": text };
  files[SUMMARY_OUT] = JSON.stringify(data, null, 2);
  return files;
}
