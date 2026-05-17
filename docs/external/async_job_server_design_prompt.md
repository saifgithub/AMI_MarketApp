# Design Prompt: Resilient Async Job Server for Mobile Clients

## Context

You are designing the backend for a mobile application that sends instructions to a server for asynchronous processing. The mobile network connection between the app and the server can be disrupted at any time. The server must continue processing submitted instructions even when the client is disconnected, and the client must be able to retrieve results on reconnect.

This is a greenfield design. Produce an architectural design document and a reference implementation skeleton. Do not produce production-grade code for every component; focus on correctness of the architecture, the data model, the API contract, and the failure-handling logic. Highlight any decisions where you make a recommendation and explain the trade-off.

## Functional Requirements

1. **Submit instruction.** The mobile app submits an instruction to the server. The server immediately acknowledges receipt with a job ID and begins processing asynchronously. The app may disconnect at any time after submission without affecting processing.

2. **Per-user FIFO execution.** Each user has their own queue. Instructions from the same user are processed sequentially in submission order. Instructions from different users are processed in parallel, subject to the global worker pool capacity.

3. **Poll for result.** The app, on reconnect or periodically, can query the server for the status and result of a job. The response is one of:
   - `queued` — accepted, not yet started
   - `running` — currently executing
   - `succeeded` — terminal state, includes the JSON result payload
   - `failed` — terminal state, includes an error reason

   The app does not need to track job IDs locally. The server exposes an endpoint to list the user's recent jobs (e.g. last N or within a time window), so the app can discover completed jobs on reconnect.

4. **Push notification on terminal state.** When a job reaches a terminal state (`succeeded` or `failed`), the server fires a push notification (APNs/FCM) to the user's registered device as a best-effort wake signal. The push notification is **not** authoritative; the source of truth is the polling endpoint. The app must still poll on reconnect regardless of whether a push was received.

5. **Resubmission semantics.** Submission is **not** idempotent by default — the same user may legitimately resubmit the same instruction on different days and expect a fresh execution (e.g. a daily query whose result varies over time). However, the server must distinguish between intentional re-runs and accidental resubmissions caused by network flakiness or user-initiated retries after a perceived failure.

   On every submission, the server computes a deterministic hash of the canonicalized instruction payload and checks the user's recent job history within a **configurable lookback window** (default: 5 days). The most recent matching job determines behavior:

   | Earlier job status | Age | Server behavior |
   |---|---|---|
   | `succeeded` | within lookback window | Return the existing job's result. Do **not** re-run. |
   | `running` or `queued` | (any) | Return the existing job ID. The app will poll it. |
   | `failed` | < 1 hour ago (configurable) | **Resume** from the LangGraph checkpoint of the failed run. |
   | `failed` | ≥ 1 hour ago | Start a **fresh** job. |
   | No matching job | — | Start a fresh job. |

   Both the lookback window and the failed-resume staleness threshold must be server-side configuration values. The submission endpoint's response must indicate which path was taken (e.g. `action: "new" | "deduped" | "resumed" | "attached"`) so the client can log it.

6. **Result retention.** Completed job records (status, result payload, error, timestamps, metadata) must be persisted durably for **days to weeks** for audit and replay purposes. Retention is policy-driven; design for a configurable retention period with a background sweeper that deletes expired jobs.

## Execution Model

Instructions are executed as **LangGraph state-driven workflows**. Each job corresponds to a LangGraph run with a `thread_id` equal to the job ID. LangGraph's checkpointer (Postgres-backed) persists intermediate state after each node so that:

- **In-run retries** for transient failures (LLM rate limits, tool timeouts, network errors to external APIs) resume from the last completed checkpoint rather than restarting from scratch. Retries use exponential backoff with a bounded attempt count and a bounded total elapsed budget — both configurable. On exhaustion, the job is marked `failed` with a descriptive error.

- **Worker process crashes** (pod eviction, OOM, segfault, unhandled exception killing the worker) are detected via heartbeats. Each worker emits a heartbeat for its current job at a regular interval; a separate reaper process marks jobs as `failed` if their heartbeat has been silent for longer than the configured threshold. **A crashed job is not automatically resumed on another worker** — the app must resubmit if it still wants the result. The LangGraph checkpoint remains intact, so a resubmission within the resume-staleness window (per the resubmission semantics above) will pick up where the crashed run left off.

The instruction payload schema, the LangGraph graph definitions, and the available tools/nodes are out of scope for this design — assume they are a separate concern. Your design should make the job-execution layer pluggable so a graph can be selected based on the instruction `type` field.

## Non-Functional Requirements

- **Scale.** Target tens of thousands of users. Design distributed from day one. Per-user job volume is low (roughly one submission per user per day on average) but bursts are possible. Total throughput is bound by worker pool size, not per-user contention.

- **Stack.** Python 3.11+. FastAPI for the HTTP API. Celery (or, if you have a strong preference, justify Arq/Dramatiq) as the task queue with Redis or RabbitMQ as the broker. PostgreSQL 16 for durable job state, results, and the LangGraph checkpointer. LangGraph for execution.

- **Result payload size.** Results are small JSON objects, expected to be well under 64 KB. Store inline in Postgres. Object storage is out of scope.

- **Authentication.** Not yet implemented; will be added later. For now, the API accepts a `user_id` as a header or request field, trusted as-is. **All data models, queries, and queue partitioning must be keyed by `user_id` from the start** so that a real auth layer (JWT/OAuth) can be inserted in front of the API without schema changes.

- **Observability.** Structured logging with job ID, user ID, and state transitions. Metrics for queue depth, worker utilization, job duration, retry counts, failure rates, and dedup-hit rates. Tracing is a plus but not required for the first cut.

## Deliverables

1. **Architecture diagram** (text or ASCII) showing the API layer, broker, worker pool, Postgres (with LangGraph checkpointer schema and application schema), Redis (if used for anything besides broker), and the push notification path.

2. **Data model.** Postgres schema for jobs, including: `job_id`, `user_id`, `instruction_type`, `payload`, `payload_hash`, `status`, `result`, `error`, `attempt_count`, `langgraph_thread_id`, `created_at`, `started_at`, `last_heartbeat_at`, `finished_at`. Show indexes that support (a) per-user recent-jobs lookup, (b) resubmission hash lookup within the lookback window, and (c) the heartbeat reaper.

3. **HTTP API.** Endpoint definitions with request/response shapes for: submit, get-job-by-id, list-recent-jobs-for-user, register-push-token. Include the `action` field in the submit response indicating which resubmission path was taken.

4. **Worker logic pseudocode.** Show how a worker claims a job, emits heartbeats, drives the LangGraph run, handles in-run retries, and writes terminal state. Show the reaper's logic separately.

5. **Resubmission decision logic.** A clear, testable function `decide_action(user_id, payload_hash) -> (action, job_id)` implementing the table in Functional Requirement 5. Include the SQL query it issues.

6. **Configuration surface.** A single config object/file listing every tunable: lookback window, failed-resume staleness, retry attempts, retry backoff parameters, heartbeat interval, reaper timeout, retention period, worker concurrency, push notification provider settings.

7. **Open questions and recommended defaults.** For any decision the spec leaves underspecified, state your recommendation and the reasoning. Flag anything that should be revisited after prototyping.

## Out of Scope

- The instruction schema and the LangGraph graphs themselves.
- Production authentication (placeholder `user_id` only).
- Object storage for large results.
- Multi-region deployment, disaster recovery, encryption-at-rest beyond Postgres defaults.
- The mobile app itself — only the server contract.

## Style

Be concrete. Prefer "use Postgres advisory locks on `user_id` for the per-user FIFO" over "use some locking mechanism." Where you make a judgment call, say so and explain briefly. The reader will iterate on this design after prototyping, so make the points of flexibility (config values, pluggable components) explicit.
