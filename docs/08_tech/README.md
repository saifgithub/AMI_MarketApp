# 08 — Tech

Stack, architecture, auth, hosting, data model, APIs, payments, platform facade, Flutter implementation.

| File | What it covers |
|---|---|
| [`stack.md`](stack.md) | Top-level stack snapshot — every service and why |
| [`architecture.md`](architecture.md) | System diagram, data flows, background jobs |
| [`auth.md`](auth.md) | Anonymous-first auth, federated providers, claim flow |
| [`hosting.md`](hosting.md) | GCP services, regions, cost expectations |
| [`llm_routing.md`](llm_routing.md) | Model routing per tier × locale via OpenRouter + direct |
| [`tradingagent_integration.md`](tradingagent_integration.md) | How we wrap the TradingAgents framework |
| [`data_model.md`](data_model.md) | All Postgres tables + Pydantic models |
| [`api_design.md`](api_design.md) | FastAPI endpoint structure |
| [`payments.md`](payments.md) | RevenueCat + Apple IAP + Google Play Billing + HMS IAP |
| [`platform_facade.md`](platform_facade.md) | Per-platform service abstractions (GMS/HMS/Apple) |
| [`flutter_implementation.md`](flutter_implementation.md) | Riverpod, project structure, key patterns |
