# CR164 prompt leakage scan — batch `r70-paired-1`

Guard (b): post-as_of dates hard-fail; post-as_of close-price matches flag.
Correlation: `llm_audit` rows by same user_id, created_at within
[started_at − 60s, finished_at + 60s].

## Totals

- Index rows scanned: **126** (sample=1.0, seed=164)
- llm_audit rows scanned: **1514**
- Hard fails (post-as_of dates): **0**
- Flags (post-as_of close prices): **278**
- Correlation failures: **0**

## Hard fails

None.

## Flags (post-as_of closes found in prompt text)

| run_id | ticker | as_of | audit row | price date | price | context |
|---|---|---|---|---|---|---|
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 23b47699-2cbf-4ff5-abd9-a645daedf3c5 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 7db42b1c-8a9e-499d-905c-9e248ef896a4 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 41fc47df-d0b0-4b3f-a8ea-2adf31dd51f5 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 04b86fd3-2987-468b-bd00-a6cee21d7c89 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 3c122190-41c1-4537-b72b-bcb5532c06c1 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | f11052c3-40a9-4de6-8251-010f4e18706b | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | c96dc785-a7e9-4742-b289-af009b3ab7fc | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | 4d731f60-a41c-40db-8fca-a6e357b22e3f | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| a0d3d251-e3b0-4485-a1fd-ecbf2209f8cf | BGS | 2025-03-07 | cf24dfe2-2ae9-4ff5-8f39-2f5f97dfa0b6 | 2025-03-11 | 6.04 | `rimary trend (LIVE): 200-day average $6.04, price 1.5% above it (equivalently, t` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 7a303b04-5f86-481d-8d95-a17651468f9f | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 7a303b04-5f86-481d-8d95-a17651468f9f | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 04c1b631-5dd1-4371-93c1-8cadd7b205a2 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 04c1b631-5dd1-4371-93c1-8cadd7b205a2 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 19581b49-9ca3-437d-bab2-adf0dea9b6e4 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 19581b49-9ca3-437d-bab2-adf0dea9b6e4 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | e7bcc8c2-4d9f-4fa1-b3d6-fb2c64eed207 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | e7bcc8c2-4d9f-4fa1-b3d6-fb2c64eed207 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | d09182d1-7e3a-4296-a6aa-a05fc7e7af23 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | d09182d1-7e3a-4296-a6aa-a05fc7e7af23 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | e61e9d55-c331-41a7-82aa-3fe9d597338e | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | e61e9d55-c331-41a7-82aa-3fe9d597338e | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 20e7b6ca-6cbb-40f9-adbc-68907d4f16a8 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 20e7b6ca-6cbb-40f9-adbc-68907d4f16a8 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 430ff1b5-564a-49cd-95cf-d0bda5ecf9ca | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 430ff1b5-564a-49cd-95cf-d0bda5ecf9ca | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 0603937d-55b9-4adc-9b59-55e7a55fa141 | 2025-04-02 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 162bb90f-8d81-4888-9c62-d5f11679f39b | XPEV | 2025-03-14 | 0603937d-55b9-4adc-9b59-55e7a55fa141 | 2025-04-03 | 21.12 | `.73 (79% of that range) 20-day SMA: $21.12, 50-day SMA: $17.07 — the last close` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 0c7acb77-1e54-4b08-9ff8-1af52364d154 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 0c7acb77-1e54-4b08-9ff8-1af52364d154 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | e93f9631-db4d-45b5-87b3-0e2056e27ade | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 RSI: 28 (oversold), trend: downtrend` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | e93f9631-db4d-45b5-87b3-0e2056e27ade | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 RSI: 28 (oversold), trend: downtrend` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | e93f9631-db4d-45b5-87b3-0e2056e27ade | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | e93f9631-db4d-45b5-87b3-0e2056e27ade | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | b4f45090-ace8-4e88-a4fb-00682c198e44 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Catalysts — recent: Q3 earnings (beat` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | b4f45090-ace8-4e88-a4fb-00682c198e44 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Catalysts — recent: Q3 earnings (beat` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | ab154be9-4611-44b5-aaae-ad52eb79a860 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Retail sentiment: moderately bullish` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | ab154be9-4611-44b5-aaae-ad52eb79a860 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Retail sentiment: moderately bullish` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 615eb366-6236-4aa5-ac02-e60e76afb1c2 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 615eb366-6236-4aa5-ac02-e60e76afb1c2 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 615eb366-6236-4aa5-ac02-e60e76afb1c2 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 615eb366-6236-4aa5-ac02-e60e76afb1c2 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 40058a61-7501-4cdd-b65b-076be0262842 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 40058a61-7501-4cdd-b65b-076be0262842 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 40058a61-7501-4cdd-b65b-076be0262842 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 40058a61-7501-4cdd-b65b-076be0262842 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 4471cf9e-7cb0-4643-94bc-eba017c9196e | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 4471cf9e-7cb0-4643-94bc-eba017c9196e | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 4471cf9e-7cb0-4643-94bc-eba017c9196e | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 4471cf9e-7cb0-4643-94bc-eba017c9196e | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 1174dfa1-d700-426a-82f9-e5dac599c152 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 1174dfa1-d700-426a-82f9-e5dac599c152 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 1174dfa1-d700-426a-82f9-e5dac599c152 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 1174dfa1-d700-426a-82f9-e5dac599c152 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 3be627aa-6c9a-4da3-a6a8-09b2c2c7c552 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 3be627aa-6c9a-4da3-a6a8-09b2c2c7c552 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 3be627aa-6c9a-4da3-a6a8-09b2c2c7c552 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 3be627aa-6c9a-4da3-a6a8-09b2c2c7c552 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 3be627aa-6c9a-4da3-a6a8-09b2c2c7c552 | 2025-05-05 | 3.98 | `$3.31 (~6% protective stop). Target $3.98 (R:R = 2.2:1). Time horizon: 6 weeks.` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 477b2cd8-f69d-42f9-a739-f668fe5bcb8a | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 477b2cd8-f69d-42f9-a739-f668fe5bcb8a | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 477b2cd8-f69d-42f9-a739-f668fe5bcb8a | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 477b2cd8-f69d-42f9-a739-f668fe5bcb8a | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 477b2cd8-f69d-42f9-a739-f668fe5bcb8a | 2025-05-05 | 3.98 | `$3.31 (~6% protective stop). Target $3.98 (R:R = 2.2:1). Time horizon: 6 weeks.` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 57d05dca-553a-4771-994a-064b53babb5f | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 57d05dca-553a-4771-994a-064b53babb5f | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 57d05dca-553a-4771-994a-064b53babb5f | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 57d05dca-553a-4771-994a-064b53babb5f | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 57d05dca-553a-4771-994a-064b53babb5f | 2025-05-05 | 3.98 | `$3.31 (~6% protective stop). Target $3.98 (R:R = 2.2:1). Time horizon: 6 weeks.` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 5a13a092-ffb5-4bb7-8136-fad95c35b0f4 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 5a13a092-ffb5-4bb7-8136-fad95c35b0f4 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 5a13a092-ffb5-4bb7-8136-fad95c35b0f4 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 5a13a092-ffb5-4bb7-8136-fad95c35b0f4 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 5d00a56d-e9bf-475d-a325-abd2bc1ecc03 | NIO | 2025-04-11 | 5a13a092-ffb5-4bb7-8136-fad95c35b0f4 | 2025-05-05 | 3.98 | `$3.31 (~6% protective stop). Target $3.98 (R:R = 2.2:1). Time horizon: 6 weeks.` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 1dbca5ac-8124-478d-8c13-a83eb8d5c805 | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 3781ef14-de85-4989-a243-7db480c77f80 | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 17dd034d-1a74-4332-8382-26889313407d | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 6c7ed55d-365f-46e6-ab81-aad40eb2f035 | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 05559794-1c25-4d06-b7b9-91f9f9d3f7db | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | b6e107d7-5bb3-4d59-bd34-6740ed0d1ac1 | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 83442fb6-7b7e-461f-9ad5-f426ed78d93e | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 3d7c2521-7503-4345-8429-3f21a54ba465 | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| da5e9e3f-fe30-4cb7-8ee5-99d4ada5e12a | SO | 2025-04-25 | 8112a0f7-a9cc-4dc9-a18a-afe0c274336c | 2025-05-22 | 86.03 | `ge) 20-day SMA: $86.78, 50-day SMA: $86.03 — the last close is +0.1% vs the 20-d` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 336c8cf3-f996-4b72-a1d8-a22485012952 | 2025-05-05 | 82.06 | `4M shares out 52-week range: $60.36–$82.06; from the reference price $81.81: -0.` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 8b850bb8-4276-4489-a9a8-c6def427a1eb | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | eba02040-905e-42f0-8b50-12ab8288a522 | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | efbe8368-1c4a-440d-b270-a86b4d64bcc4 | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 9f6276fc-6c1e-49f7-936a-b68fffcc7ccd | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 047cbf83-6f0d-473e-89bd-59f3c02dd630 | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | e65ab117-4b7f-46b5-8dd4-f45ae613be4d | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | bd73da39-3fd0-4714-b19a-5ee19aa096b9 | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 573f63c1-e5f8-4ee8-8e45-53b40c7ea3bb | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 80d4039a-9e6a-493d-a105-dfade9b929e6 | SCHW | 2025-05-02 | 257ba39f-217f-4908-826b-25fe50c1869e | 2025-05-05 | 82.06 | `month average 52-week range: $60.36–$82.06; from the last close $81.81: -0.3% vs` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | 9b4e2335-5ab3-4e72-a376-7dc302533d5f | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | cfbdfb1f-f371-400e-88b6-0560d87aad67 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | ca110e56-78cd-4358-9c3f-e1575032d8f0 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | e2cc55ac-0b94-43c9-a6b1-9c6993a0e6e0 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | dc0f14e0-6955-4e92-beef-fd552268cf7f | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | 9d498a8b-7ed6-4b08-b8da-2e023cc5f6d6 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | aadf533d-7c8f-42fd-8d15-de8bb074778d | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | 53a70595-6962-4a98-bdf8-487afdffe442 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| 6c3efeb2-dce2-437f-92aa-8cb46b1d1ebe | NIO | 2025-05-09 | 9a69d84d-2b83-4fbc-9189-39399210eb68 | 2025-05-22 | 3.88 | `3.97 (38% of that range) 20-day SMA: $3.88, 50-day SMA: $4.1 — the last close is` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 1509c724-8e8f-4b35-a8ca-e693a5c31783 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 14488c76-b49d-4d20-bbb5-5db4ef1fbebf | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 4f5cfc25-6ab9-444c-b887-e6fb1edf4df0 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 3b0cb47c-92be-4dfa-b014-82998c1c969d | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 76164afa-19e4-40f9-be84-7d3a89d5bcb5 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 2f0188e6-eb0a-4094-849d-9f5690b5bf07 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | e73f2e15-4200-43f5-97fc-6d6a7efdcfbb | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | 0fefd111-488e-406a-a4aa-abbf37bb56c3 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| abcd815c-9089-421e-9939-59b679242aa9 | CAG | 2025-09-12 | f3116ee6-2073-4f3d-95ac-046404dfee7a | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 08492ed0-8c99-4c73-bab8-579d98eef0b5 | 2025-10-21 | 2.89 | `e. Instrument: AMC Reference price: $2.89 Retail sentiment: moderately bullish` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | eead7e94-4938-4f82-85bb-e64be866092c | 2025-10-21 | 2.89 | `e. Instrument: AMC Reference price: $2.89 Catalysts — recent: Q3 earnings (beat` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 29167b85-04c1-4bc5-818f-352d87469c23 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 29167b85-04c1-4bc5-818f-352d87469c23 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 29167b85-04c1-4bc5-818f-352d87469c23 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 29167b85-04c1-4bc5-818f-352d87469c23 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 29167b85-04c1-4bc5-818f-352d87469c23 | 2025-10-21 | 2.89 | `e. Instrument: AMC Reference price: $2.89 RSI: 54 (neither overbought nor overs` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 52929e60-16cc-47f1-a201-82eb2ef32a24 | 2025-10-21 | 2.89 | `e. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9dd31788-13e1-45a0-8306-f653dbe54119 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9dd31788-13e1-45a0-8306-f653dbe54119 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9dd31788-13e1-45a0-8306-f653dbe54119 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9dd31788-13e1-45a0-8306-f653dbe54119 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9dd31788-13e1-45a0-8306-f653dbe54119 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 82de2ae3-dfe5-4ccb-a909-cd9e6717eee0 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 82de2ae3-dfe5-4ccb-a909-cd9e6717eee0 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 82de2ae3-dfe5-4ccb-a909-cd9e6717eee0 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 82de2ae3-dfe5-4ccb-a909-cd9e6717eee0 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 82de2ae3-dfe5-4ccb-a909-cd9e6717eee0 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | cd69ad57-6285-4951-a8fc-a297f74f7794 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | cd69ad57-6285-4951-a8fc-a297f74f7794 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | cd69ad57-6285-4951-a8fc-a297f74f7794 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | cd69ad57-6285-4951-a8fc-a297f74f7794 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | cd69ad57-6285-4951-a8fc-a297f74f7794 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | b24af704-dd10-4013-81b3-7cc3bdcd50b5 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | b24af704-dd10-4013-81b3-7cc3bdcd50b5 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | b24af704-dd10-4013-81b3-7cc3bdcd50b5 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | b24af704-dd10-4013-81b3-7cc3bdcd50b5 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | b24af704-dd10-4013-81b3-7cc3bdcd50b5 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9e3aca7e-1802-45de-a939-5f5d03022ff8 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9e3aca7e-1802-45de-a939-5f5d03022ff8 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9e3aca7e-1802-45de-a939-5f5d03022ff8 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9e3aca7e-1802-45de-a939-5f5d03022ff8 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 9e3aca7e-1802-45de-a939-5f5d03022ff8 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 41ba5833-ed9c-475e-86e5-d207d30f36e2 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 41ba5833-ed9c-475e-86e5-d207d30f36e2 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 41ba5833-ed9c-475e-86e5-d207d30f36e2 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 41ba5833-ed9c-475e-86e5-d207d30f36e2 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 41ba5833-ed9c-475e-86e5-d207d30f36e2 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 13ec9d1a-5250-4358-8658-5d7d4b0e57e4 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 13ec9d1a-5250-4358-8658-5d7d4b0e57e4 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 13ec9d1a-5250-4358-8658-5d7d4b0e57e4 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 13ec9d1a-5250-4358-8658-5d7d4b0e57e4 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | 13ec9d1a-5250-4358-8658-5d7d4b0e57e4 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | aff7b3a0-b97d-4381-8d38-0d51fcf46673 | 2025-10-01 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | aff7b3a0-b97d-4381-8d38-0d51fcf46673 | 2025-10-07 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | aff7b3a0-b97d-4381-8d38-0d51fcf46673 | 2025-10-08 | 2.84 | `2.89 (24% of that range) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close i` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | aff7b3a0-b97d-4381-8d38-0d51fcf46673 | 2025-10-10 | 2.95 | `ange) 20-day SMA: $2.84, 50-day SMA: $2.95 — the last close is +1.8% vs the 20-d` |
| 57973bc9-8624-4fa5-89c5-6cfff22055bd | AMC | 2025-09-26 | aff7b3a0-b97d-4381-8d38-0d51fcf46673 | 2025-10-21 | 2.89 | `d. Instrument: AMC Reference price: $2.89 P/E: not available TTM revenue growth` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | e1505906-fe6b-4e1d-b5b0-78faa8bc52b0 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 Retail sentiment: moderately bullish` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 84867078-632c-4aea-aac8-aea019a32edf | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 Catalysts — recent: Q3 earnings (bea` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 0981aab4-60dc-4b8a-8cea-da7d7e1d10b7 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | b33ff47f-e054-4dd0-8be2-2a4c9eed73f9 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 RSI: 46 (neither overbought nor over` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | e860da9c-f58c-4324-9e37-a2b62b1eaffa | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | dc548e5e-849c-46da-beb7-942d43075b1f | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 1b8832e5-dad4-488f-8d61-67d94c8c94fe | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | bd541546-8b9f-43f4-a05f-58097f80877b | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | e5b9ad98-cce6-48cd-88c4-30b4af3a1994 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 0296a957-d462-434c-bb8e-682906a49614 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 4b3f9fab-405d-439d-ab5e-58b6d613ef45 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b47dc95d-4bb0-4a26-95a9-d444c0862d8a | PEP | 2025-09-26 | 30b00dfc-b095-458d-b1f4-b838ea23b868 | 2025-09-30 | 136.41 | `. Instrument: PEP Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| b34e9b73-7ce9-4778-b7ed-625cec24c244 | LUV | 2025-10-24 | f84aaf94-8eac-4152-a028-4deabda92138 | 2025-10-30 | 29.70 | `f the cap already spent, that leaves 29.70 pt of the 30 pt cap unused once this` |
| b34e9b73-7ce9-4778-b7ed-625cec24c244 | LUV | 2025-10-24 | 4b82f6ec-0793-40ba-9a93-6a0006c03384 | 2025-10-30 | 29.70 | `* pt to the **30** pt cap, leaving **29.70** pt of remaining headroom. Declining` |
| b34e9b73-7ce9-4778-b7ed-625cec24c244 | LUV | 2025-10-24 | 4b82f6ec-0793-40ba-9a93-6a0006c03384 | 2025-10-31 | 29.91 | `f the cap already spent, that leaves 29.91 pt of the 30 pt cap unused once this` |
| b34e9b73-7ce9-4778-b7ed-625cec24c244 | LUV | 2025-10-24 | baeab4ac-0b89-4e43-8589-73db54731854 | 2025-10-30 | 29.70 | `* pt to the **30** pt cap, leaving **29.70** pt of remaining headroom. Declining` |
| b34e9b73-7ce9-4778-b7ed-625cec24c244 | LUV | 2025-10-24 | dc5a5fc3-ba87-430f-ad01-217a97190e98 | 2025-10-30 | 29.70 | `* pt to the **30** pt cap, leaving **29.70** pt of remaining headroom. Declining` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | e434d49a-97dc-4dd5-b5da-51a3682e67f7 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | 4fd718c4-d5ec-428f-9d61-58202ee9678f | 2025-11-06 | 42.68 | `7, debt/equity 0.47x 52-week range: $42.68–$59.81; from the reference price $43.` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | 59cf619e-cfd9-46c1-84a9-3a8c9d6d5ca5 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | 1ef88383-e300-44e4-ae30-414d25b15197 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | 357159d3-f7e3-449d-9018-175301321d9d | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | eec150e3-34c0-44c3-9e95-74ec95eae7e8 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | 97a67036-ed69-498c-8c34-413e2a167547 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | ea7b8952-1540-4be1-898d-68a764fc3af8 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | dad6eaad-a863-4e7e-bb05-86ea271e4f61 | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| b07c72a7-304b-47f7-812f-438301c9b0c6 | TAP | 2025-10-24 | e839f0b3-833c-4bca-8c60-cba2f9377aed | 2025-11-06 | 42.68 | `,256 3-month average 52-week range: $42.68–$59.81; from the last close $43.99: -` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | e6dfe03d-4f84-498b-87b9-a9320cf9dbdd | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | 7fc83719-6658-407d-b140-6e93adcac745 | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | 2f2be62e-f5ff-4b31-b220-cbd97f4a896d | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | c09c0292-fb7f-4aad-823b-2793f8e869c4 | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | eaf4390e-94d1-4a4c-b88c-e8e81c3c745c | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | bde98747-64e3-48b5-bdf8-19e61e2823b5 | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | 51aaddf4-59d0-4806-bfa2-0636a353825e | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | d662fe37-015b-448e-adce-a5c4c6d04874 | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 11815be8-106a-4559-a5d8-9ae58d2f19be | DUK | 2025-11-07 | 11e9aa9b-e180-4156-b22c-962dfbe2e95b | 2025-11-17 | 123.06 | `.52 (38% of that range) 20-day SMA: $123.06, 50-day SMA: $120.82 — the last clos` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 86c93933-0ee2-463b-a6bb-006d67c38a9a | 2025-12-03 | 2.28 | `e. Instrument: AMC Reference price: $2.28 Retail sentiment: moderately bullish` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 86c93933-0ee2-463b-a6bb-006d67c38a9a | 2025-12-09 | 2.28 | `e. Instrument: AMC Reference price: $2.28 Retail sentiment: moderately bullish` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 03592682-a521-45bf-8340-bf67d72c602c | 2025-12-03 | 2.28 | `e. Instrument: AMC Reference price: $2.28 Catalysts — recent: Q3 earnings (beat` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 03592682-a521-45bf-8340-bf67d72c602c | 2025-12-09 | 2.28 | `e. Instrument: AMC Reference price: $2.28 Catalysts — recent: Q3 earnings (beat` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | a5c56ac2-7093-48a6-b565-d31c42144ea0 | 2025-12-03 | 2.28 | `e. Instrument: AMC Reference price: $2.28 RSI: 27 (oversold), trend: downtrend` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | a5c56ac2-7093-48a6-b565-d31c42144ea0 | 2025-12-09 | 2.28 | `e. Instrument: AMC Reference price: $2.28 RSI: 27 (oversold), trend: downtrend` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | ac8bf06e-76f2-41b5-b500-fdf4cbfdc63b | 2025-12-03 | 2.28 | `e. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | ac8bf06e-76f2-41b5-b500-fdf4cbfdc63b | 2025-12-09 | 2.28 | `e. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 029092e2-f79a-49d2-bf57-95136694c4e0 | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 029092e2-f79a-49d2-bf57-95136694c4e0 | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 694a6e95-820c-4669-83d8-a8315fc42fff | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 694a6e95-820c-4669-83d8-a8315fc42fff | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | cfe434e5-23cf-479e-8194-59f718f8d355 | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | cfe434e5-23cf-479e-8194-59f718f8d355 | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 6c351d87-3040-491a-bdc8-db573fd38eef | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | 6c351d87-3040-491a-bdc8-db573fd38eef | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | fb969f54-5bf4-4be5-b83f-17dce78867a7 | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | fb969f54-5bf4-4be5-b83f-17dce78867a7 | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | ab86d2a1-0165-4c77-9704-daa398bbe390 | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | ab86d2a1-0165-4c77-9704-daa398bbe390 | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | bf373bd4-3552-44c7-b502-b968592363ec | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | bf373bd4-3552-44c7-b502-b968592363ec | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | d6407269-8ff9-4f05-b301-a07aba7c1937 | 2025-12-03 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 3391e918-d03a-4aaa-8124-7db815c7c14e | AMC | 2025-11-14 | d6407269-8ff9-4f05-b301-a07aba7c1937 | 2025-12-09 | 2.28 | `d. Instrument: AMC Reference price: $2.28 P/E: not available TTM revenue growth` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | 96f3656d-627d-46cc-b5fb-11c5ed94606c | 2025-12-23 | 55.91 | `e. Instrument: MO Reference price: $55.91 Catalysts — recent: Q3 earnings (beat` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | f8a88260-a7ba-4ab4-a9f6-9b9e47299206 | 2025-12-23 | 55.91 | `e. Instrument: MO Reference price: $55.91 Retail sentiment: moderately bullish` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | a4bf9212-fc6b-4d84-bfcc-29408fb4fa00 | 2025-12-23 | 55.91 | `e. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | eb1f73ba-fd9f-459d-ba91-2d8cfbe8e3a4 | 2025-12-23 | 55.91 | `e. Instrument: MO Reference price: $55.91 RSI: 56 (neither overbought nor overs` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | 4ec79af1-cca0-4127-ba18-0b47d4f70cbd | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | 63caacb7-707d-4210-b513-5673ebd985e0 | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | a3d0a2fc-bbd5-4a3c-9fc1-23ebd3232cfe | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | 07619903-be85-4399-8f69-c559d1bf0f24 | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | b9dd7542-227a-4a7a-ae0c-b43ea86a63c3 | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | d244e035-e9fe-4aec-9073-60d74d5b3be3 | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | a7fa8bf2-f42c-4e66-b53a-70855b95a338 | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 4a0640da-47ef-4601-b2d2-971633ed78eb | MO | 2025-12-12 | 978de448-5f91-43cc-a7b4-014bdf2ea40e | 2025-12-23 | 55.91 | `d. Instrument: MO Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | b4c49c31-08e2-472c-a1bd-c33bc89e5263 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 12740546-9a8e-4440-89a3-d3cf1cdb7915 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | d8d8633f-a514-4e46-a04e-34a74fbfb3ce | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 36433dbc-c75f-4bed-8d37-4fa58b1d0155 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 0930ae1a-b19c-457c-915b-387cffcb51b7 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | c5dbcb81-eefe-45bf-9f0d-af755c586c48 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 70d8364b-8164-4085-b3c2-a855427f4e08 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 6b93ecb6-e1cc-46b2-ad13-bdb41e98d8ae | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8a74f34b-09b1-4262-a7bd-8cc1574de92d | NIO | 2026-01-02 | 3135493a-315d-4ae9-a720-a41ef4f94df3 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 36ed6c4e-788b-47d5-9544-e46b513739fe | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 36ed6c4e-788b-47d5-9544-e46b513739fe | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | c19b32a0-13b2-45da-acfa-f9b5ec1ceb0e | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | c19b32a0-13b2-45da-acfa-f9b5ec1ceb0e | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 194a1f5b-5c54-498c-852e-ea58a315051f | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 194a1f5b-5c54-498c-852e-ea58a315051f | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 6ea488a9-fe1d-40f2-bf3b-216e4ee6d80d | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 6ea488a9-fe1d-40f2-bf3b-216e4ee6d80d | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 3bb954a4-b0e2-43ed-9ad0-0467465c15a2 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 3bb954a4-b0e2-43ed-9ad0-0467465c15a2 | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | bd0bc4da-9536-410c-b041-147d98968a48 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | bd0bc4da-9536-410c-b041-147d98968a48 | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 1a1128c2-1eb1-471c-b0f8-83228593ce10 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 1a1128c2-1eb1-471c-b0f8-83228593ce10 | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | e4b2982c-d268-4aa4-beed-07e21a6f3e57 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | e4b2982c-d268-4aa4-beed-07e21a6f3e57 | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 19204a2c-285b-4606-9733-bac1ddff55e6 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| d7ece3d4-352a-4ac9-bf5d-3a48cc362c65 | PLUG | 2026-02-13 | 19204a2c-285b-4606-9733-bac1ddff55e6 | 2026-03-09 | 2.18 | `$1.89 (9% of that range) 20-day SMA: $2.18, 50-day SMA: $2.2 — the last close is` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 9114ce40-615e-44b1-b1e2-e800ed3ea2a9 | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 4114fa80-81ad-4c7e-9a99-1289ea61518f | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 3a2b2f0b-a390-4e9d-8eed-5da50c4815e3 | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 8244e75b-ee5a-4f43-b441-931eef4b98af | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 3a7ce37e-175c-4c01-a062-df371fd9a2ce | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 0495f8c9-18d9-477f-beee-1a1f52780f9e | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 35b6b9ab-5e84-4c21-8655-ddfe2ef99f37 | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | 5f9d0eaf-26e3-4fad-a81e-2170a1c1bc25 | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 8d2c852d-d378-4b68-90a7-8c004f1da9aa | SHOP | 2026-05-22 | d12403b2-a869-4d26-aaac-fb1907a06a5a | 2026-06-05 | 109.54 | `3.0 (21% of that range) 20-day SMA: $109.54, 50-day SMA: $116.53 — the last clos` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 6123a032-d16c-4a85-ba8a-7ce1820c21a5 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 5aae28a4-ca8a-42e2-b6d0-5e4c112baabd | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 RSI: 54 (neither overbought nor over` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 03962863-7745-438e-b8c7-ea8112ec4856 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 Catalysts — recent: Q3 earnings (bea` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | d0eeed24-0944-4aa5-bde3-187286b8e2d4 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 Retail sentiment: mixed (typical int` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 4852faf5-b012-4b48-b30a-cd3badca518a | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 2b837586-1351-4b03-ab21-ec876902800f | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 7672fce9-b611-4c52-b45d-1c7462d272a4 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 2be668a7-4c93-48d5-9f23-b5698a932f31 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | d5b63af7-5406-4e04-9123-e8eb3989493d | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | eee2dccd-12a4-45e1-8609-8c53770f21d9 | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 2b419306-3f27-4102-9c54-3197dcb7175b | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| 577488bd-6d10-42ab-9e44-5f7f025a276e | WMT | 2026-06-19 | 3860bee3-84b1-4ffb-89a7-91d9ddf8a52a | 2026-06-22 | 117.18 | `. Instrument: WMT Reference price: $117.18 P/E: 41.0 trailing (measured — last` |

## Correlation failures

None.
