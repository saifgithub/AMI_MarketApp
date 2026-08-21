# CR164 prompt leakage scan — batch `r70-outcome-2`

Guard (b): post-as_of dates hard-fail; post-as_of close-price matches flag.
Correlation: `llm_audit` rows by same user_id, created_at within
[started_at − 60s, finished_at + 60s].

## Totals

- Index rows scanned: **450** (sample=1.0, seed=164)
- llm_audit rows scanned: **5386**
- Hard fails (post-as_of dates): **7**
- Flags (post-as_of close prices): **592**
- Correlation failures: **0**

## Hard fails

| run_id | ticker | as_of | audit row | found date | context |
|---|---|---|---|---|---|
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | e3e11615-db04-4280-8ca3-9e67e7f6fd08 | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | f8c63d9b-8641-4f68-a196-511f42a714b8 | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | 85693ecf-c00e-4010-bbd1-3f3ac2f1578f | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | 880c4904-eb96-4d1f-95cf-73d3dd62ec4c | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | 35c82806-d17c-4350-b150-05c710023c45 | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | 7953120b-bebb-4232-b90a-3ac9569ffd19 | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |
| 58149372-6dc7-4a4e-9933-7cb01fdb409d | CL | 2026-06-12 | 99ae987a-a09d-4709-bb28-b9f52585343f | 2027-06-12 ('2027-06-12') | `de: **$97.97** (52-week high) by **2027-06-12**. The thesis requires a macro piv` |

## Flags (post-as_of closes found in prompt text)

| run_id | ticker | as_of | audit row | price date | price | context |
|---|---|---|---|---|---|---|
| cd134561-269f-43f8-a563-223e4fac7b22 | BAC | 2025-02-28 | b85420de-853b-444b-9e3a-815c35cc1f75 | 2025-03-24 | 41.90 | `ceiling 3.0% size, entry 44.57, stop 41.90) → stop 6.0% below THAT entry (41.90` |
| cd134561-269f-43f8-a563-223e4fac7b22 | BAC | 2025-02-28 | 279f05d1-aab3-47ca-8f43-705db5029f8e | 2025-03-24 | 41.90 | `ceiling 3.0% size, entry 44.57, stop 41.90) → stop 6.0% below THAT entry (41.90` |
| cd134561-269f-43f8-a563-223e4fac7b22 | BAC | 2025-02-28 | 32c20064-de44-47cd-ae39-e6c93cabbd3d | 2025-03-24 | 41.90 | `ceiling 3.0% size, entry 44.57, stop 41.90) → stop 6.0% below THAT entry (41.90` |
| cd134561-269f-43f8-a563-223e4fac7b22 | BAC | 2025-02-28 | 6ce24479-2b44-46c0-ae2f-bc975b0c65c3 | 2025-03-24 | 41.90 | `ceiling 3.0% size, entry 44.57, stop 41.90) → stop 6.0% below THAT entry (41.90` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | 7a532f62-8866-4b8b-94ad-f66774eeea77 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | e281528b-3c51-4524-80ae-357286b21ce7 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | 068f9307-44a7-4a52-bf11-356bdbd6115a | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | 9399e02b-39e6-479f-a715-757fed4b8a84 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | 0f3e8339-c755-43f3-8df5-1e34cb962cee | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | e28b46fe-fc99-4efc-ac68-89bb93ccf688 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | 42a62fc6-8829-4fd4-9d03-13d92596cec3 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | e7476ade-1e35-45a8-9780-2d9af41d99c6 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| b86c31ba-3084-44f6-8d14-98002ed1b0e8 | EOG | 2025-02-28 | a5fadcf1-88ea-47ab-832e-6ba61d5e78f4 | 2025-03-24 | 121.83 | `e) 20-day SMA: $123.37, 50-day SMA: $121.83 — the last close is -2.3% vs the 20-` |
| 80997fb1-9099-409d-bcfd-3c86ec396f6c | NIO | 2025-02-28 | 91fc0ab9-9e10-495c-9788-5ca2efb7703b | 2025-03-05 | 4.35 | `r ceiling 3.0% size, entry 4.63, stop 4.35) → stop 6.0% below THAT entry (4.35 f` |
| 80997fb1-9099-409d-bcfd-3c86ec396f6c | NIO | 2025-02-28 | ca715bca-c146-490d-8291-e1b9614f4ed9 | 2025-03-05 | 4.35 | `r ceiling 3.0% size, entry 4.63, stop 4.35) → stop 6.0% below THAT entry (4.35 f` |
| 80997fb1-9099-409d-bcfd-3c86ec396f6c | NIO | 2025-02-28 | e21a7138-da2b-4713-9f76-bcdc6b7a7e28 | 2025-03-05 | 4.35 | `r ceiling 3.0% size, entry 4.63, stop 4.35) → stop 6.0% below THAT entry (4.35 f` |
| 80997fb1-9099-409d-bcfd-3c86ec396f6c | NIO | 2025-02-28 | ac2fa5ed-559f-4c50-8952-af15930036c1 | 2025-03-05 | 4.35 | `r ceiling 3.0% size, entry 4.63, stop 4.35) → stop 6.0% below THAT entry (4.35 f` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 2cd75ae8-94e5-420d-95af-efe4ad62b040 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Catalysts — recent: Q3 earnings (beat` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 2cd75ae8-94e5-420d-95af-efe4ad62b040 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Catalysts — recent: Q3 earnings (beat` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5c8bfff7-0382-417a-8e35-b44c97e90e9e | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Retail sentiment: moderately bullish` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5c8bfff7-0382-417a-8e35-b44c97e90e9e | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 Retail sentiment: moderately bullish` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | f2a419dc-cab4-46ad-8d0a-da9e39cc49f9 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | f2a419dc-cab4-46ad-8d0a-da9e39cc49f9 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | bec2060b-3966-40e2-9740-65c6152752b9 | 2025-04-16 | 3.52 | `e. Instrument: NIO Reference price: $3.52 RSI: 28 (oversold), trend: downtrend` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | bec2060b-3966-40e2-9740-65c6152752b9 | 2025-04-17 | 3.52 | `e. Instrument: NIO Reference price: $3.52 RSI: 28 (oversold), trend: downtrend` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | bec2060b-3966-40e2-9740-65c6152752b9 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | bec2060b-3966-40e2-9740-65c6152752b9 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5226a409-804c-475d-9347-4d7d138be389 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5226a409-804c-475d-9347-4d7d138be389 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5226a409-804c-475d-9347-4d7d138be389 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5226a409-804c-475d-9347-4d7d138be389 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | a1860458-5ebe-4645-ae3e-9da600269afd | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | a1860458-5ebe-4645-ae3e-9da600269afd | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | a1860458-5ebe-4645-ae3e-9da600269afd | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | a1860458-5ebe-4645-ae3e-9da600269afd | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5560c530-f48b-453b-ab22-7baddd0dc404 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5560c530-f48b-453b-ab22-7baddd0dc404 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5560c530-f48b-453b-ab22-7baddd0dc404 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 5560c530-f48b-453b-ab22-7baddd0dc404 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 9a352508-30bd-4512-9b7b-f4c7c532cf29 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 9a352508-30bd-4512-9b7b-f4c7c532cf29 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 9a352508-30bd-4512-9b7b-f4c7c532cf29 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 9a352508-30bd-4512-9b7b-f4c7c532cf29 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | e2ff8484-b61f-418a-b5ed-42364bf5a85f | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | e2ff8484-b61f-418a-b5ed-42364bf5a85f | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | e2ff8484-b61f-418a-b5ed-42364bf5a85f | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | e2ff8484-b61f-418a-b5ed-42364bf5a85f | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 0166acec-f6d6-4f63-9dc2-b1fe83764ff2 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 0166acec-f6d6-4f63-9dc2-b1fe83764ff2 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 0166acec-f6d6-4f63-9dc2-b1fe83764ff2 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 0166acec-f6d6-4f63-9dc2-b1fe83764ff2 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | c1264682-3df2-4643-a3ad-d1524050a292 | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | c1264682-3df2-4643-a3ad-d1524050a292 | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | c1264682-3df2-4643-a3ad-d1524050a292 | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | c1264682-3df2-4643-a3ad-d1524050a292 | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 445de27c-33c7-4844-b33b-67d3095a604d | 2025-04-16 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 445de27c-33c7-4844-b33b-67d3095a604d | 2025-04-17 | 3.52 | `d. Instrument: NIO Reference price: $3.52 P/E: not available TTM revenue growth` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 445de27c-33c7-4844-b33b-67d3095a604d | 2025-04-25 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 0c666105-3d67-4c9e-8043-27a752f6fc19 | NIO | 2025-04-11 | 445de27c-33c7-4844-b33b-67d3095a604d | 2025-05-02 | 4.03 | `3.52 (20% of that range) 20-day SMA: $4.03, 50-day SMA: $4.28 — the last close i` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | aa11e5ea-b708-4e8a-8922-4c7b67ed2fc0 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 Catalysts — recent: Q3 earnings (beat` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 368ceaa6-6f1d-4d7e-9f9e-307c1fc4e4db | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 Retail sentiment: mixed (subdued inte` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 90676f4e-abf8-4e11-9e96-c70edb0c2cee | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 RSI: 36 (neither overbought nor overs` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 0d8af1e0-1d5e-41d3-904d-4023fbddd0f8 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 364db7fc-988d-490f-ab51-f3b57e773968 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 51779558-f997-4836-ab97-10047512132a | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | ffbcf6df-5f4b-4eea-bc55-090e1a79fe6e | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 677a4405-68a6-44a7-924b-ef39a4a7c120 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 832c7a0f-c266-4717-8a99-34f2ab7d4cb4 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | a0b663ee-041f-4f6f-b5b7-ff81c8b2ac93 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 1ca09740-822f-4597-b923-e87bdbd7ddff | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 2d48cc8b-a0ef-46bb-babf-6ee107df85f0 | SNAP | 2025-04-11 | 697f28ac-2db2-4240-a23a-3f1fd8cf4f59 | 2025-04-30 | 7.96 | `. Instrument: SNAP Reference price: $7.96 P/E: not available TTM revenue growth` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | aa6e8d15-e9a2-412b-94b8-ef994a083e49 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | aa6e8d15-e9a2-412b-94b8-ef994a083e49 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 8fbb989c-0ac2-4e17-94ce-4644c90ddd10 | 2025-05-22 | 9.05 | `IVE): 712M shares out 52-week range: $9.05–$19.39; from the reference price $10.` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 1d40e2b6-5304-4cf4-ae74-02247033dadd | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 1d40e2b6-5304-4cf4-ae74-02247033dadd | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 587b677f-2f60-4910-a17c-20a9390ba65b | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 587b677f-2f60-4910-a17c-20a9390ba65b | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | a1356357-bb4e-4790-bed0-aa4cc4df2d79 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | a1356357-bb4e-4790-bed0-aa4cc4df2d79 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 3afbfe04-74d3-44b0-b579-cc7d2e1742b6 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 3afbfe04-74d3-44b0-b579-cc7d2e1742b6 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 9f207b6f-10da-4f95-92ec-d4e79ea02055 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 9f207b6f-10da-4f95-92ec-d4e79ea02055 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 84040e2d-85c2-437a-8f84-3bc626b3d198 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | 84040e2d-85c2-437a-8f84-3bc626b3d198 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | f51fd7bd-a132-4004-92d4-36018fb7a298 | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | f51fd7bd-a132-4004-92d4-36018fb7a298 | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | c00b7655-4613-4a0a-9ba4-c63e3ca33aac | 2025-05-21 | 9.52 | `0.45 (48% of that range) 20-day SMA: $9.52, 50-day SMA: $10.4 — the last close i` |
| 236aed60-7b21-4401-a9b6-309393e2daa8 | AES | 2025-05-09 | c00b7655-4613-4a0a-9ba4-c63e3ca33aac | 2025-05-22 | 9.05 | `5,260 3-month average 52-week range: $9.05–$19.39; from the last close $10.45: -` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 2c447f97-2a53-4b8a-a338-25d205e5591d | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 Retail sentiment: mixed (elevated int` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 1f4993d3-5b9b-4131-8593-12f2fae27607 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 Catalysts — recent: Q3 earnings (beat` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | ca9ecd83-d4cb-4780-adad-a82622a77188 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 RSI: 80 (overbought), trend: consolid` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 00978e7d-c97e-4feb-af3f-901682869aa2 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 8213ed1f-85b4-49c4-8ab4-ceca96504c44 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 157d0d5a-9fb7-45af-b935-7a7cfbc2b24f | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 0accecf5-7f37-4501-add7-13b8b4aab685 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | d648d3eb-2eab-4c90-b2e1-06f395208ff4 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 3a7503f4-51e3-4747-baa7-c4065e40f02c | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 405a2bb4-aebb-4ef6-9c10-a7974175066b | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | 25136a5f-74f6-40c0-9a4e-1327b6cdd736 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| 4b0117b8-c17d-4cfb-b27d-5059d6ccc644 | JBLU | 2025-05-09 | e44b7ced-fb86-486b-98db-8a03020612c9 | 2025-06-05 | 4.88 | `. Instrument: JBLU Reference price: $4.88 P/E: not available TTM revenue growth` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | 9dab8042-226f-4e87-912e-9f03c04d4216 | 2025-05-21 | 11.02 | `le. Instrument: M Reference price: $11.02 Retail sentiment: moderately bullish` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | b99390cb-d216-464e-8835-4f0bce0c8475 | 2025-05-21 | 11.02 | `le. Instrument: M Reference price: $11.02 Catalysts — recent: Q3 earnings (beat` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | d810de63-bcf5-4a75-96bb-af3c999bfe5d | 2025-05-21 | 11.02 | `le. Instrument: M Reference price: $11.02 RSI: 67 (neither overbought nor overs` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | d11e2f28-2518-4924-b1bd-7e9b1580b0bd | 2025-05-21 | 11.02 | `le. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | fbcb9cd5-a567-4c0f-b177-6d00e722bb12 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | b62735cc-a9ae-4a6a-899e-31990a8b0e16 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | f80ba342-80c3-4c8b-b280-deed21eb374f | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | d9c68257-084f-40d8-ae58-bddfb5f1b20c | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | 93d05461-1fe2-46ec-872b-f835acdc9bd9 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | 29218142-193d-4f51-93ab-80d2380038c0 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | d888ec25-f770-4094-a71f-db71ba225889 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| d1610ee1-c400-4189-a0c0-64bb5db70204 | M | 2025-05-09 | 43aa4f33-51c7-4945-9e7f-c6f644520932 | 2025-05-21 | 11.02 | `ed. Instrument: M Reference price: $11.02 P/E: 5.3 trailing (measured — last 12` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | ffa1033a-70b2-4d51-9e76-bfcdb9f09118 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | 01bb1a5c-c35a-4504-94c6-4cee7727fc04 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | b443eebe-e2b9-4071-9dc6-dc930878ad81 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | a5b560bc-25ce-46c1-8321-d3f07c316713 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | 1606320d-8860-495c-bfed-cda80d83ac4e | 2025-05-16 | 0.78 | `y Metric:** $559M cash / $-717M FCF = 0.78 years runway. * **Risk:** 100% loss` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | 1606320d-8860-495c-bfed-cda80d83ac4e | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | c28d1cd6-3bf4-4943-bbd6-a92333cf7b6a | 2025-05-16 | 0.78 | `y Metric:** $559M cash / $-717M FCF = 0.78 years runway. * **Risk:** 100% loss` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | c28d1cd6-3bf4-4943-bbd6-a92333cf7b6a | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | c28d1cd6-3bf4-4943-bbd6-a92333cf7b6a | 2025-06-04 | 0.63 | `r ceiling 3.0% size, entry 0.67, stop 0.63) → stop 6.0% below THAT entry (0.63 f` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d994f7cf-ee50-476c-b6a0-f41a234232b1 | 2025-05-16 | 0.78 | `y Metric:** $559M cash / $-717M FCF = 0.78 years runway. * **Risk:** 100% loss` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d994f7cf-ee50-476c-b6a0-f41a234232b1 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d994f7cf-ee50-476c-b6a0-f41a234232b1 | 2025-06-04 | 0.63 | `r ceiling 3.0% size, entry 0.67, stop 0.63) → stop 6.0% below THAT entry (0.63 f` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d216ac27-7e5e-45dc-abdf-4ffc5f02cda3 | 2025-05-16 | 0.78 | `y Metric:** $559M cash / $-717M FCF = 0.78 years runway. * **Risk:** 100% loss` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d216ac27-7e5e-45dc-abdf-4ffc5f02cda3 | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | d216ac27-7e5e-45dc-abdf-4ffc5f02cda3 | 2025-06-04 | 0.63 | `r ceiling 3.0% size, entry 0.67, stop 0.63) → stop 6.0% below THAT entry (0.63 f` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | cd6fd5f2-7230-465c-9557-3add25334d8c | 2025-05-16 | 0.78 | `y Metric:** $559M cash / $-717M FCF = 0.78 years runway. * **Risk:** 100% loss` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | cd6fd5f2-7230-465c-9557-3add25334d8c | 2025-05-30 | 0.65 | `old), trend: downtrend 50-day range: $0.65–$1.36, last close $0.67 (3% of that r` |
| cd82077d-a6a0-4b09-8543-cd93106800fa | OPEN | 2025-05-09 | cd6fd5f2-7230-465c-9557-3add25334d8c | 2025-06-04 | 0.63 | `r ceiling 3.0% size, entry 0.67, stop 0.63) → stop 6.0% below THAT entry (0.63 f` |
| b968ffeb-9266-49c9-8fd5-1aa4264f7740 | CAG | 2025-06-13 | 138968bc-4d4a-4261-a26b-6997c0c402ce | 2025-06-26 | 18.65 | `risk is a further **-5%** move to **$18.65**, which we absorb via the **6.0%** s` |
| b968ffeb-9266-49c9-8fd5-1aa4264f7740 | CAG | 2025-06-13 | 867c2fa8-3313-4a5f-9c03-065193e6126f | 2025-06-26 | 18.65 | `risk is a further **-5%** move to **$18.65**, which we absorb via the **6.0%** s` |
| b968ffeb-9266-49c9-8fd5-1aa4264f7740 | CAG | 2025-06-13 | 4f5e1a91-7143-4069-99fa-20560ba62ef5 | 2025-06-26 | 18.65 | `risk is a further **-5%** move to **$18.65**, which we absorb via the **6.0%** s` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | c6257a03-22eb-4efe-829b-a3ca2e2a5ec6 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 Catalysts — recent: Q3 earnings (beat` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 440d623e-e16c-4572-bfc9-d955195fb0e6 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 Retail sentiment: mixed (elevated int` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 5c54fa1c-e974-463d-9c21-776d6de20d3a | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 RSI: 40 (neither overbought nor overs` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | c69158e5-6eb1-4f86-b59f-1787cfeac1d6 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 0a55ac04-5b56-43fb-a36c-b3a0cae34114 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 522c3845-01dc-43a9-84b2-31df43a590c4 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 477e109d-3fc6-4984-a271-cd315f4e2f42 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | b9fbfbb3-ebc5-4433-9968-cb3bb1186c8c | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 4cb32986-ff84-4a9c-98b9-7821b22555b9 | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 2656c824-3d37-4185-aef8-534b5b04bd8c | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | 71018393-8ce6-441c-a862-b1b98365c0de | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 22036d23-bcdb-4b07-be21-cdfcaa029aa3 | JBLU | 2025-06-13 | be44c254-4b73-4b86-b990-44e5838bc23d | 2025-07-02 | 4.47 | `. Instrument: JBLU Reference price: $4.47 P/E: not available TTM revenue growth` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | b01d22d9-ff06-43ef-907f-b67cc95f00b1 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 1c9946ac-3adb-4efd-becf-91487f93f851 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | f375e5a3-5f6a-418e-806f-f7d81e0dfa1e | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 1fcd1b5e-4561-4a49-b68c-fc72fc2735b4 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | d56e955c-9513-4d78-8a98-358f3afb8887 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 34a397a7-43ef-46e1-a17e-328ad95325b0 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 9b2aed44-3958-462f-af9d-938c28882b10 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 0bab6bee-7d39-4b28-b36e-2b70ba2b4933 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| 901b2d32-79e6-4646-be2e-4411ca11bb9f | KO | 2025-06-13 | 94d6f050-a5a3-4b82-90f9-e5e6c5383e02 | 2025-07-07 | 69.05 | `ge) 20-day SMA: $69.22, 50-day SMA: $69.05 — the last close is -0.2% vs the 20-d` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 9fb549b6-6b17-4488-b812-580ca0eb30c3 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | e8b6f875-9908-4ddb-a6f4-777297e6ecd0 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 0ce728c7-56f8-46d5-ada9-56484ecc842c | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | dc9301d9-7001-4eec-9864-152d6e0dff30 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 4f31d5ab-2ccb-404b-aaef-f829148701b6 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 05f9ff3a-37e6-43b8-8566-8057f47273e0 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 73e9ab29-728b-4f0c-9241-0e6b53137bb9 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 853a0a21-d763-462c-8a74-ef7ebd55f58d | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| fb944b4f-74d5-41e0-9a38-95fe69d262a2 | NEE | 2025-06-13 | 8078078f-9772-4a10-8784-9b94a60250e9 | 2025-06-26 | 68.99 | `.68 (97% of that range) 20-day SMA: $68.99, 50-day SMA: $66.68 — the last close` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 32c14817-a9af-4d4d-8ed7-06de116e428a | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 00202423-ed58-4d53-a4e5-51c5c19fa203 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 7e2a55dc-ba18-4b86-bdc0-fb3ad26d8168 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 4a2d464e-0f20-4665-8799-a1488e2cc3a5 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 1eba955c-c750-4ed8-8c34-0ed1539369ed | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | e0215b49-e967-4b91-be22-cef328b037c2 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | 4a1f32c0-fa7e-40a0-92e0-ccd3e0b3ed75 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | a4cbb70f-e8e5-4168-a131-ef8fc66ada80 | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 6f716e2a-1ebf-4b5b-a75b-54bf0052c07c | RTX | 2025-06-13 | cfd0f75e-dfd8-4ac2-bda6-1e1606208e1d | 2025-06-30 | 143.73 | `rend: uptrend 50-day range: $109.95–$143.73, last close $143.4 (99% of that rang` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | f1b1c9e9-edd2-4bd8-ad37-01ef5447d8dd | 2025-06-26 | 87.49 | `e. Instrument: SO Reference price: $87.49 Catalysts — recent: Q3 earnings (beat` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 6e67dc41-fedc-4375-84e3-84e7c200c025 | 2025-06-26 | 87.49 | `e. Instrument: SO Reference price: $87.49 Retail sentiment: mixed (typical inte` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 80582b6a-a213-4435-879f-8e1d262621c4 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 80582b6a-a213-4435-879f-8e1d262621c4 | 2025-06-26 | 87.49 | `e. Instrument: SO Reference price: $87.49 RSI: 55 (neither overbought nor overs` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 883c8bb1-ab60-40cb-9068-233e8a702665 | 2025-06-26 | 87.49 | `e. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 41618228-bb80-4706-9e9b-c234140d4e58 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 41618228-bb80-4706-9e9b-c234140d4e58 | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 57342329-b937-42f1-9f94-4c3cfdad9c59 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 57342329-b937-42f1-9f94-4c3cfdad9c59 | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | d8f7aabb-5011-4056-b7d0-7c4e46513f1a | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | d8f7aabb-5011-4056-b7d0-7c4e46513f1a | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 5c168b27-8a19-4ce7-8e2c-134aabe61724 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 5c168b27-8a19-4ce7-8e2c-134aabe61724 | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 1c73b4e2-948c-4327-a2bc-43efd9e72881 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 1c73b4e2-948c-4327-a2bc-43efd9e72881 | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 9137cb2f-e546-4827-aa8e-af69471858bb | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 9137cb2f-e546-4827-aa8e-af69471858bb | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 4a96dbc3-35b1-42ea-83f4-24009dbea013 | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 4a96dbc3-35b1-42ea-83f4-24009dbea013 | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 26d3c803-d2dd-499c-86e5-0fb3273704bf | 2025-06-20 | 86.47 | `.49 (76% of that range) 20-day SMA: $86.47, 50-day SMA: $86.41 — the last close` |
| 58fdb519-c10d-468f-bc94-6c8bad98092b | SO | 2025-06-13 | 26d3c803-d2dd-499c-86e5-0fb3273704bf | 2025-06-26 | 87.49 | `d. Instrument: SO Reference price: $87.49 P/E: not available TTM revenue growth` |
| c86ca6a3-d224-4145-bb2c-f220775d387e | TRIP | 2025-06-13 | 9f2e4273-9258-4bb3-9506-4f71454a9781 | 2025-06-25 | 12.50 | `ceiling 3.0% size, entry 13.30, stop 12.50) → stop 6.0% below THAT entry (12.50` |
| c86ca6a3-d224-4145-bb2c-f220775d387e | TRIP | 2025-06-13 | 271a06d7-7922-4502-aa14-d4b5304bca1e | 2025-06-25 | 12.50 | `ceiling 3.0% size, entry 13.30, stop 12.50) → stop 6.0% below THAT entry (12.50` |
| c86ca6a3-d224-4145-bb2c-f220775d387e | TRIP | 2025-06-13 | c1767374-4fd2-41b7-9d6c-1f1e11efc6cf | 2025-06-25 | 12.50 | `ceiling 3.0% size, entry 13.30, stop 12.50) → stop 6.0% below THAT entry (12.50` |
| c86ca6a3-d224-4145-bb2c-f220775d387e | TRIP | 2025-06-13 | 8544d200-c874-41aa-88da-56623c64ac03 | 2025-06-25 | 12.50 | `ceiling 3.0% size, entry 13.30, stop 12.50) → stop 6.0% below THAT entry (12.50` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 2fcd8b2a-61c3-4de9-8853-20fb0613ad35 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | ce9a20f9-3da4-4593-9732-0ff482bd6b99 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 308c75db-6f4c-4363-9b53-f9b98e920ea2 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 452c8cc4-b027-4142-b3cc-fe43870eb87a | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 02a115de-3924-49dc-9617-ce32dc2a9fb6 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 57c9a52e-7498-4f6b-90d8-5df91d95a366 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 068344d7-54df-4fdf-b45c-5239a6097dc6 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 08dd1a67-491d-4a50-b849-2b5a79f44f26 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| c96b26b3-5a6e-4bc1-a4e6-c704882af681 | XRX | 2025-06-13 | 98ccd9df-8eee-4384-b685-63012d844cb7 | 2025-07-11 | 4.88 | `4.91 (63% of that range) 20-day SMA: $4.88, 50-day SMA: $4.55 — the last close i` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | cbbfdfb7-4542-467a-9e57-26a6009301cb | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 Catalysts — recent: Q3 earnings (beat` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 459ae09c-c00a-47e8-a037-107c3d9783d6 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 Retail sentiment: moderately bullish` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | d8bec68d-5c04-406e-a02c-300add59e764 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 RSI: 26 (oversold), trend: downtrend` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 4a40caae-507f-4c6d-b7b5-f5332edd32b7 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 8770eb10-0d5d-41f3-994c-15e35241ee8f | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 02242e83-1f8a-481c-a960-9b236573f5ef | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | eeaa1bd7-ad0f-4a54-b298-fdcf8cc7f1c8 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 57217e3b-5fad-499a-93a4-a219032202a8 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | d29b3c6f-09dd-45c1-94c2-da9c659d056c | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 0ab5d933-8b0a-4630-b9e1-8bcbc32d9e25 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 52b9f244-3634-4673-b34e-5be717c2ea22 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| 14971260-f724-49f2-abae-063c945a54fb | CAG | 2025-07-11 | 7307651c-adaa-4ade-a9da-b08ea259d832 | 2025-07-22 | 17.65 | `. Instrument: CAG Reference price: $17.65 P/E: 7.3 trailing (measured — last 12` |
| d402ce3c-9669-41c1-8777-0a2de4897ad8 | F | 2025-07-11 | afeb3623-0cbc-4383-b61f-13d986ebfc9e | 2025-07-29 | 10.56 | `ceiling 3.0% size, entry 11.23, stop 10.56) → stop 6.0% below THAT entry (10.56` |
| d402ce3c-9669-41c1-8777-0a2de4897ad8 | F | 2025-07-11 | c94e7be0-b367-4cc3-8079-9b36d03fc95b | 2025-07-29 | 10.56 | `ceiling 3.0% size, entry 11.23, stop 10.56) → stop 6.0% below THAT entry (10.56` |
| d402ce3c-9669-41c1-8777-0a2de4897ad8 | F | 2025-07-11 | a2270b4a-f925-43ce-8ea9-5a919dd4ed48 | 2025-07-29 | 10.56 | `ceiling 3.0% size, entry 11.23, stop 10.56) → stop 6.0% below THAT entry (10.56` |
| d402ce3c-9669-41c1-8777-0a2de4897ad8 | F | 2025-07-11 | 6e0a2a00-1fb0-46b6-9ef2-09cf94ceb659 | 2025-07-29 | 10.56 | `ceiling 3.0% size, entry 11.23, stop 10.56) → stop 6.0% below THAT entry (10.56` |
| 4e9f914f-8dbe-42c1-b8ba-934c925c26ca | SLB | 2025-07-11 | 50fd9c0f-8657-40ff-b865-d7b0bb2d3e15 | 2025-07-15 | 34.14 | `ceiling 3.0% size, entry 36.32, stop 34.14) → stop 6.0% below THAT entry (34.14` |
| 4e9f914f-8dbe-42c1-b8ba-934c925c26ca | SLB | 2025-07-11 | 8fac4ad5-3307-423e-a30c-fc9128c74e93 | 2025-07-15 | 34.14 | `ceiling 3.0% size, entry 36.32, stop 34.14) → stop 6.0% below THAT entry (34.14` |
| 4e9f914f-8dbe-42c1-b8ba-934c925c26ca | SLB | 2025-07-11 | c9462c02-9278-41c8-a8a3-08949edcf77b | 2025-07-15 | 34.14 | `ceiling 3.0% size, entry 36.32, stop 34.14) → stop 6.0% below THAT entry (34.14` |
| 4e9f914f-8dbe-42c1-b8ba-934c925c26ca | SLB | 2025-07-11 | 051ea29a-23af-4613-aecb-77dbeceeef3e | 2025-07-15 | 34.14 | `ceiling 3.0% size, entry 36.32, stop 34.14) → stop 6.0% below THAT entry (34.14` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 72e13521-80c1-4b88-b78f-f3951ac54cb0 | 2025-08-11 | 3.51 | `e. Instrument: BGS Reference price: $3.51 Retail sentiment: moderately bullish` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 7af4dbff-fd37-42c3-8d41-17d0a9f70781 | 2025-08-11 | 3.51 | `e. Instrument: BGS Reference price: $3.51 Catalysts — recent: Q3 earnings (beat` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 079f61d1-2adf-489e-bbc8-e2990719dbcf | 2025-08-11 | 3.51 | `e. Instrument: BGS Reference price: $3.51 RSI: 50 (neither overbought nor overs` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 079f61d1-2adf-489e-bbc8-e2990719dbcf | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | d5cce9ce-4703-4d63-b828-c95105bc29ce | 2025-08-11 | 3.51 | `e. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | bdd2b5bf-b05c-47d4-a483-27a594ca2a7f | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | bdd2b5bf-b05c-47d4-a483-27a594ca2a7f | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | a4dfd93b-5102-40fc-8927-8df991c437be | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | a4dfd93b-5102-40fc-8927-8df991c437be | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | d98b55d0-c0d8-45cd-b580-6a191f107895 | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | d98b55d0-c0d8-45cd-b580-6a191f107895 | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | b7fb38c8-6d9c-4aa7-835c-668edffeb9cc | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | b7fb38c8-6d9c-4aa7-835c-668edffeb9cc | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | f74d6a04-9d64-4423-9891-a8ea39a1e875 | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | f74d6a04-9d64-4423-9891-a8ea39a1e875 | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | cef62396-bbbf-4558-97da-9c650a843683 | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | cef62396-bbbf-4558-97da-9c650a843683 | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 214b64a3-b355-4d9c-88f8-1c152025b81d | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 214b64a3-b355-4d9c-88f8-1c152025b81d | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 0565313e-1181-4aff-8cdb-c5b2fa8ccfed | 2025-08-11 | 3.51 | `d. Instrument: BGS Reference price: $3.51 P/E: not available TTM revenue growth` |
| 28080bba-7c05-4ae8-9009-1166e351e8a1 | BGS | 2025-08-08 | 0565313e-1181-4aff-8cdb-c5b2fa8ccfed | 2025-08-15 | 3.63 | `3.51 (35% of that range) 20-day SMA: $3.63, 50-day SMA: $3.63 — the last close i` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | ba643e9c-6ddc-460b-9864-32a0b471682c | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | 94812411-a403-4cfe-8c4a-06612edf496b | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | e8f447c7-6b49-4ac6-b182-f98b1e5f206d | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | 1ccbcfba-e095-4ed6-8c8e-f47ba95d2fb7 | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | f20d7e3a-16f7-41d0-8f7a-d9ae09089790 | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | 900214dd-8924-4296-86a5-fe50ea116ee5 | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | 662bda0a-31f9-49de-82e7-914a287c5f6e | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | a932590f-aed7-4bd9-a721-5a28bc253df8 | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| b92e6266-cb17-4dcc-8e64-cc628a04cc12 | KHC | 2025-08-08 | 1b4e5906-7e95-4920-97dd-8898b3eeb13c | 2025-08-27 | 26.14 | `.01 (62% of that range) 20-day SMA: $26.14, 50-day SMA: $25.25 — the last close` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 7daec9a9-a52a-4f9a-a580-826d42435a9a | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 7daec9a9-a52a-4f9a-a580-826d42435a9a | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 7daec9a9-a52a-4f9a-a580-826d42435a9a | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3ba3c0c6-246f-4a05-a563-87caa6da6227 | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3ba3c0c6-246f-4a05-a563-87caa6da6227 | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3ba3c0c6-246f-4a05-a563-87caa6da6227 | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | d49e8d0e-4472-45c7-8a66-04b514d88832 | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | d49e8d0e-4472-45c7-8a66-04b514d88832 | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | d49e8d0e-4472-45c7-8a66-04b514d88832 | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | cc8b73a3-565d-4e09-8e30-c23486e562b4 | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | cc8b73a3-565d-4e09-8e30-c23486e562b4 | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | cc8b73a3-565d-4e09-8e30-c23486e562b4 | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | b23528a8-4790-4aed-8564-88c02ef6a0fd | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | b23528a8-4790-4aed-8564-88c02ef6a0fd | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | b23528a8-4790-4aed-8564-88c02ef6a0fd | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | aae6b103-1e54-4556-9f2e-fac673855010 | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | aae6b103-1e54-4556-9f2e-fac673855010 | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | aae6b103-1e54-4556-9f2e-fac673855010 | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3327e5d3-964e-4814-89ac-1dbaa635068c | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3327e5d3-964e-4814-89ac-1dbaa635068c | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 3327e5d3-964e-4814-89ac-1dbaa635068c | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 594bd1db-1e87-4363-b23b-ad602045b71a | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 594bd1db-1e87-4363-b23b-ad602045b71a | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | 594bd1db-1e87-4363-b23b-ad602045b71a | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | ca927c49-8354-431c-84ff-32ad8b80c815 | 2025-08-14 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | ca927c49-8354-431c-84ff-32ad8b80c815 | 2025-08-26 | 1.65 | `rimary trend (LIVE): 200-day average $1.65, price 8.7% below it (equivalently, t` |
| 57242278-0722-4508-958c-22e6c0208084 | PLUG | 2025-08-08 | ca927c49-8354-431c-84ff-32ad8b80c815 | 2025-08-27 | 1.62 | `1.51 (57% of that range) 20-day SMA: $1.62, 50-day SMA: $1.38 — the last close i` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 22a89a40-cbd5-4b1e-8579-0b8e625d0136 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | d9227506-1f52-4872-9e1b-091588d1c436 | 2025-08-21 | 42.15 | `6M shares out 52-week range: $34.28–$42.15; from the reference price $40.39: -4.` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 77e787ba-aecd-44d2-8420-6475344e017e | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 4fc1b8fd-3f0d-43d5-a191-6a322cc11b06 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 928485ea-712c-4461-bcae-c0f88a09ea22 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | bac7d5b1-1881-4b11-8e65-469b69998127 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | a9288b99-9e7d-47f1-8014-d85b294b6112 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | fb66cc17-d5a2-4649-a0d9-ffeadd240b52 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 331dc10a-5eee-4354-95d7-1910e2a78830 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 2d608cf8-6411-4259-9bdf-8815cd838a8e | VZ | 2025-08-08 | 4260a9a0-bafe-414e-80f5-c55b96e80879 | 2025-08-21 | 42.15 | `month average 52-week range: $34.28–$42.15; from the last close $40.39: -4.2% vs` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 2da9a91d-d2da-485d-9515-945247a6c132 | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 Retail sentiment: moderately bullish` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | d0b0e54c-2f7b-481d-884d-e1b80a0b46e1 | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 Catalysts — recent: Q3 earnings (beat` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 542bf7df-884f-43ee-9931-2a61812b217c | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 RSI: 35 (neither overbought nor overs` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | e7c46809-0902-45a9-9745-de9978e5ac91 | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | d093aee0-b63f-4997-bfa4-3d43391709ef | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | a2f4242a-9d71-4df4-a406-0cce0d4a305e | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | c058bd4c-e3f4-4d0f-9534-ffa115aa8414 | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | ef7fcc91-0123-418a-afe5-51dd4f7e818d | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 9ba960cd-0467-400e-8534-11878841262f | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 884a33fe-438b-47a2-b63b-b5ad2c350fa2 | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 52d63d41-01f7-4c57-8257-ff63945cd3ad | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 7516ed10-02ba-4625-ae91-3e299bb2860b | BBWI | 2025-08-15 | 47c45287-b80a-4a75-bacc-e9fb8a8cdaba | 2025-09-08 | 27.58 | `Instrument: BBWI Reference price: $27.58 P/E: 7.2 trailing (measured — last 12` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | a19046d4-e3e7-4a53-9e40-b2420a188b7d | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | d9a09d0f-5850-42eb-9bfe-dfd997977599 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | a7c0cfcf-3871-4b56-914f-fd1b4b75beb8 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | 0fe77f61-cccb-4089-a6b3-b792c24bdbfb | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | 1ac21ba9-151b-48ca-8ef4-991aac66d2a3 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | 59f43452-7d57-4020-ab97-cee5a65dc945 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | ccb87214-cfd4-442d-8ecc-ab462bc9eff1 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | f52d3918-817e-43bb-bc99-2289352a351a | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| 18b8825d-6be8-4e7c-babe-5360174e0be8 | EOG | 2025-08-15 | 60c40fe8-7045-4f02-bc40-7fb3a93597b9 | 2025-08-21 | 114.53 | `.99 (55% of that range) 20-day SMA: $114.53, 50-day SMA: $115.22 — the last clos` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 2e520416-9f2b-48de-9bc8-8e44606137e5 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 2e520416-9f2b-48de-9bc8-8e44606137e5 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 0bea69c3-c75d-4acd-aa57-ac0e670a2bb9 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 0bea69c3-c75d-4acd-aa57-ac0e670a2bb9 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | e6154a57-618f-4ae4-8d02-3881730e14fb | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | e6154a57-618f-4ae4-8d02-3881730e14fb | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 6e2f2443-b3d9-41ea-87a9-2c076f5ff640 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 6e2f2443-b3d9-41ea-87a9-2c076f5ff640 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 88172aa8-0d7e-4aa4-a5ff-714f743be857 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 88172aa8-0d7e-4aa4-a5ff-714f743be857 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | e1bb213d-2388-4ad5-bfd6-07680c88c6f9 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | e1bb213d-2388-4ad5-bfd6-07680c88c6f9 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 7da17188-e4f6-4553-8fb8-d52627c9ae41 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 7da17188-e4f6-4553-8fb8-d52627c9ae41 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 1284bd77-0e54-4e10-9222-681f58d0522f | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 1284bd77-0e54-4e10-9222-681f58d0522f | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 0ef2d327-0ffe-4851-beb6-b1a00b7a1ef4 | 2025-08-27 | 1.62 | `$1.7 (72% of that range) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close i` |
| d6c7250e-449d-4f29-8838-6e82e784b0f5 | PLUG | 2025-08-15 | 0ef2d327-0ffe-4851-beb6-b1a00b7a1ef4 | 2025-09-05 | 1.46 | `ange) 20-day SMA: $1.62, 50-day SMA: $1.46 — the last close is +4.9% vs the 20-d` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 381416c0-d6e0-4bea-bff5-f9a17f9e83b3 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 Retail sentiment: mixed (typical inte` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | b28d1df1-3f04-41ed-a545-4821768c5c2b | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 Catalysts — recent: Q3 earnings (beat` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 35d5ad21-86f1-426b-89da-d685e392f6cd | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 RSI: 60 (neither overbought nor overs` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | eb86fdb7-f98d-4758-b415-2b63f390e089 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 6a020936-151e-470c-9d7b-eed5d182805f | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 2ae10651-7993-4b5d-bbf4-aec64e7d2fba | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | bf29ca4f-da53-44a1-9c93-879cbea0f051 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 1e7ed7dd-f9d8-4795-a422-35261174b616 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 5f7fd7df-c2f6-4628-bc56-1b6838fe33ff | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | f2bef11a-422c-43ba-a352-4540a26cede3 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | ac102ada-acb5-444f-98a2-431323f51385 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 443a9102-a40a-4984-a96b-cc4ff9873c82 | SWKS | 2025-08-15 | 9eadc6f1-b3ea-4de4-8a8c-196d34c29915 | 2025-08-21 | 71.51 | `Instrument: SWKS Reference price: $71.51 P/E: 26.8 trailing (measured — last 1` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | faa51cb2-aaa9-4926-b790-63a5915fb11d | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | 069fda81-d61e-4f11-8bd9-c7d98d552a48 | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | 8c14520f-1a64-4d7b-a49d-a9d8f2a2b9de | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | d7c219ee-6bb6-4ec8-a932-2ce88e8ee0d8 | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | 919bf1bf-2b39-4d43-8fcf-2108637fa5d2 | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | 852f2aeb-6af6-4d6d-8937-2f5ed549358c | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | 7d6cff49-5858-48d7-a660-9152518921d0 | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | ba08d6e5-c6a9-4def-a041-cb300eadb995 | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| 64725d03-4fd0-43f6-8a01-4dbaca771070 | WU | 2025-08-15 | a0ae18d4-4e59-4c7e-8ab0-ba2cb316ef7f | 2025-08-25 | 7.56 | `range) 20-day SMA: $7.4, 50-day SMA: $7.56 — the last close is +1.2% vs the 20-d` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 75e8e404-0ba2-4a97-8e6b-0d27829e6127 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 Catalysts — recent: Q3 earnings (bea` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 0d5e0e0a-9d4c-466b-8a6d-e2fe8c94b7f6 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 Retail sentiment: moderately bullish` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | f1b717b0-421d-4212-bc53-27e43bbcbd02 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | c345bbf6-dd37-40b6-aab6-e7b786e7f983 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 RSI: 32 (neither overbought nor over` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 3792c715-4c13-483c-b456-9ab8823470bf | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | a98e5965-7009-4bdf-a0aa-1e416c82c12e | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | b136ec53-9acb-45d5-bb6b-41fc5951f7c7 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | d8f31eb6-dcec-45ef-8275-fa76f6cc9b4b | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 917b7474-69f8-43c8-9b0d-c06cf3f503fd | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 7820fd06-38dd-4747-9f1d-11205cd0ec30 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 16e99e8a-6eb7-408b-b699-913079d90e43 | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| d0509e00-b282-430e-aeee-351f3bbfac5c | ADP | 2025-09-12 | 57f561ec-1d09-4467-8a3e-79b52e66051b | 2025-09-30 | 287.05 | `. Instrument: ADP Reference price: $287.05 P/E: 28.5 trailing (measured — last` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 57848049-571c-428a-835c-d6c83a82ffd4 | 2025-09-15 | 11.28 | `le. Instrument: F Reference price: $11.28 Retail sentiment: moderately bullish` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 6f64f682-f5a1-4f59-83bf-0c418628da07 | 2025-09-15 | 11.28 | `le. Instrument: F Reference price: $11.28 Catalysts — recent: Q3 earnings (beat` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 8d48678e-1913-4695-973f-569fc53a96a3 | 2025-09-15 | 11.28 | `le. Instrument: F Reference price: $11.28 RSI: 48 (neither overbought nor overs` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 115c0925-16d0-40e1-b06e-6047b11d6482 | 2025-09-15 | 11.28 | `le. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 9cffdc04-f2b4-4b0e-9bb1-cbab016dc728 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 468e1f26-0dac-4368-b83d-e3f805f88112 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | a4b822e1-2b9b-4c21-a3f6-f7800323a889 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 4fe63d91-0dae-4fd9-bdae-98003eee5d00 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 83f60a80-ac2f-44dc-a081-90b492c31689 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | b3a272ab-9fde-484f-a078-cd25a27aca05 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 837cb2df-8486-4bd3-92da-8ea3b825d572 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| 476b1b3e-3037-4404-90d7-bc60ac10b5c1 | F | 2025-09-12 | 7d27241f-d7c9-437e-989c-bc2025db1041 | 2025-09-15 | 11.28 | `ed. Instrument: F Reference price: $11.28 P/E: 0.0 trailing (measured — last 12` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | bd48a425-0c9e-4281-b94f-e4c57cfedd8e | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | bd985c8d-a649-4e63-9259-340cb0ee5184 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | 7eaa9ce6-a819-4063-a0b3-77f3193cf484 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | fb82ea31-82a0-44a4-9b23-54e548cd81e5 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | e17e000c-b72d-43f6-8f54-b7a13de64c26 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | 5e4af23d-a193-4855-a051-55653815d1f7 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | b0e72f40-efcd-4429-96ca-3dc975005078 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | f77afd36-ca38-4bf7-b2b9-01a73c5dadc3 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| f77b8c2b-7a81-4691-b024-45032ad7cbcd | JPM | 2025-09-12 | a024ba3c-9a9c-4a81-8d5b-64f7f8a11797 | 2025-10-02 | 301.78 | `rend: uptrend 50-day range: $275.05–$301.78, last close $301.15 (98% of that ran` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | f6638686-73ce-4c7b-bb1c-86d2c62a985f | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | f1eea382-8011-4bb6-8a2c-acff531b5b69 | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | aae38fa5-95f6-4dda-9d18-ca74deaaa15a | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | 2d8a9f0b-aa2d-45de-a159-d5527e93e96f | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | 6d5e25d2-eb54-401d-8565-e58f63680ad8 | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | cb5fc473-0eef-44b3-9d65-d4238189c1e3 | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | 5ed9cb18-0279-40f7-b00b-ddfc65110d0b | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | 23ed9d1b-1184-453e-8206-ab356e7ad1cc | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 9404a61f-d389-4202-ba84-9b2e3a16b1da | XPEV | 2025-09-12 | 000ff01e-1050-4837-9451-d5606214decc | 2025-09-23 | 21.19 | `.87 (47% of that range) 20-day SMA: $21.19, 50-day SMA: $19.7 — the last close i` |
| 13a2a4a8-0d40-49f9-a6f2-a9c10c014297 | AMC | 2025-10-31 | ff754a95-22c0-4e5c-b4c4-89a83c25ca6a | 2025-11-11 | 2.43 | `r ceiling 3.0% size, entry 2.59, stop 2.43) → stop 6.2% below THAT entry (2.43 f` |
| 13a2a4a8-0d40-49f9-a6f2-a9c10c014297 | AMC | 2025-10-31 | 8b2319c9-6131-4f61-8141-18bf4f418869 | 2025-11-11 | 2.43 | `r ceiling 3.0% size, entry 2.59, stop 2.43) → stop 6.2% below THAT entry (2.43 f` |
| 13a2a4a8-0d40-49f9-a6f2-a9c10c014297 | AMC | 2025-10-31 | 3be145df-f4d6-4b07-8815-753274794be7 | 2025-11-11 | 2.43 | `r ceiling 3.0% size, entry 2.59, stop 2.43) → stop 6.2% below THAT entry (2.43 f` |
| 13a2a4a8-0d40-49f9-a6f2-a9c10c014297 | AMC | 2025-10-31 | 7482a9a1-9d0b-44d4-8ed5-421b0912196a | 2025-11-11 | 2.43 | `r ceiling 3.0% size, entry 2.59, stop 2.43) → stop 6.2% below THAT entry (2.43 f` |
| a206c4e7-8faf-4da6-8243-79f92f82f43d | AMC | 2025-11-28 | 11ee2939-3651-4d0d-a185-66b377f1795f | 2025-12-02 | 2.30 | `r ceiling 3.0% size, entry 2.45, stop 2.30) → stop 6.1% below THAT entry (2.30 f` |
| a206c4e7-8faf-4da6-8243-79f92f82f43d | AMC | 2025-11-28 | 8d69987a-fd06-42e5-a839-71980ad2deb1 | 2025-12-02 | 2.30 | `r ceiling 3.0% size, entry 2.45, stop 2.30) → stop 6.1% below THAT entry (2.30 f` |
| a206c4e7-8faf-4da6-8243-79f92f82f43d | AMC | 2025-11-28 | 3154961c-628c-4488-a6af-5b0ef93356d3 | 2025-12-02 | 2.30 | `r ceiling 3.0% size, entry 2.45, stop 2.30) → stop 6.1% below THAT entry (2.30 f` |
| a206c4e7-8faf-4da6-8243-79f92f82f43d | AMC | 2025-11-28 | a0979ac4-6601-43f8-ad46-2f84583a2a99 | 2025-12-02 | 2.30 | `r ceiling 3.0% size, entry 2.45, stop 2.30) → stop 6.1% below THAT entry (2.30 f` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | c9e76f55-4999-4435-80d0-f6009160da77 | 2025-12-05 | 53.49 | `): 1,290M shares out 52-week range: $53.49–$68.37; from the reference price $56.` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 23682a78-0b64-4ed9-8a25-0e91b82c656b | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 8e38b6c0-630b-42dc-bc2c-9e2df33493c3 | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 95726aae-722e-4a03-a2c6-e2451eeff3fb | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | b730b88c-223d-457d-af75-04e7494ba88d | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 4d1a4009-e4a3-4bb2-8967-dc08a2eb80d7 | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 47fe8501-6fd5-4fed-a5cf-a69830c28101 | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | be30c7c5-110b-47e2-9901-7d297d24a568 | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | 52452902-5c70-455d-9ae9-66d12ca6465e | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 473bdf35-3030-4dc1-a541-e9dda6a58a4f | MDLZ | 2025-11-28 | cc2fea2a-f161-455d-87a0-2308a599dd68 | 2025-12-05 | 53.49 | `,004 3-month average 52-week range: $53.49–$68.37; from the last close $56.09: -` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | ec1f38e4-66ad-472a-b7eb-994638233d3b | 2025-12-24 | 4.62 | `e. Instrument: UAA Reference price: $4.62 Catalysts — recent: Q3 earnings (beat` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | fd028811-cb9c-4c60-acc0-ad9e09b23925 | 2025-12-24 | 4.62 | `e. Instrument: UAA Reference price: $4.62 Retail sentiment: mixed (typical inte` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 62bca4af-304d-4f71-9338-b4f353ae15d0 | 2025-12-24 | 4.62 | `e. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | b8c4db70-00c0-45b8-8e31-903f23bdc58a | 2025-12-24 | 4.62 | `e. Instrument: UAA Reference price: $4.62 RSI: 49 (neither overbought nor overs` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 2deea666-f5e3-407f-9093-dffbd2a5851d | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | fdd4c0c3-7f75-43f4-b0da-4393c29001c2 | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 1620b23d-ec84-42b9-904d-b9059b48db7c | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | c1d25e58-590b-43b7-9a45-8f8b01d203f3 | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 979abb28-f4b0-43bd-8158-f05e94d07950 | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 3d0e7fa2-a2c3-4803-8383-9339aaf0da94 | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 192f57b1-f0ff-4221-bba5-a0040018ad23 | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| 29fa3aec-9175-48ea-b6f6-6f7baeb14b6b | UAA | 2025-11-28 | 5493ccb5-5c74-420f-bcfc-4ad4840d9d1f | 2025-12-24 | 4.62 | `d. Instrument: UAA Reference price: $4.62 P/E: not available TTM revenue growth` |
| f44a749c-edce-49b3-892b-702eab410acc | XPEV | 2025-11-28 | 516e81fe-2724-4cd0-bf2c-bdc396a7a9df | 2025-12-08 | 20.52 | `ceiling 3.0% size, entry 21.83, stop 20.52) → stop 6.0% below THAT entry (20.52` |
| f44a749c-edce-49b3-892b-702eab410acc | XPEV | 2025-11-28 | e580d988-0577-40f6-96b6-90966359a4b2 | 2025-12-08 | 20.52 | `ceiling 3.0% size, entry 21.83, stop 20.52) → stop 6.0% below THAT entry (20.52` |
| f44a749c-edce-49b3-892b-702eab410acc | XPEV | 2025-11-28 | 504e209a-116b-45ed-b5df-1b2b5a3da3c1 | 2025-12-08 | 20.52 | `ceiling 3.0% size, entry 21.83, stop 20.52) → stop 6.0% below THAT entry (20.52` |
| f44a749c-edce-49b3-892b-702eab410acc | XPEV | 2025-11-28 | dd27d509-b96c-4629-a8f8-1720551df7d8 | 2025-12-08 | 20.52 | `ceiling 3.0% size, entry 21.83, stop 20.52) → stop 6.0% below THAT entry (20.52` |
| ed2952ae-54ab-45b5-a622-e6317d52f35f | PYPL | 2026-01-09 | e6a3db31-0b97-4622-9b60-455b05da38c3 | 2026-01-14 | 57.30 | `(risk-tier ceiling 3.0% size, entry 57.30, stop 53.86) → stop 6.0% below THAT e` |
| ed2952ae-54ab-45b5-a622-e6317d52f35f | PYPL | 2026-01-09 | 955c6bed-7fb7-472f-872d-4d2d6dcb465d | 2026-01-14 | 57.30 | `(risk-tier ceiling 3.0% size, entry 57.30, stop 53.86) → stop 6.0% below THAT e` |
| ed2952ae-54ab-45b5-a622-e6317d52f35f | PYPL | 2026-01-09 | cb928ca1-2c73-4865-b522-ca4386c4914e | 2026-01-14 | 57.30 | `(risk-tier ceiling 3.0% size, entry 57.30, stop 53.86) → stop 6.0% below THAT e` |
| ed2952ae-54ab-45b5-a622-e6317d52f35f | PYPL | 2026-01-09 | 0235b323-39c7-4a89-b4f5-89a78e823375 | 2026-01-14 | 57.30 | `(risk-tier ceiling 3.0% size, entry 57.30, stop 53.86) → stop 6.0% below THAT e` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 684cdd22-9850-42a1-a60b-bda7f8a66f86 | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | bf133994-c53e-4bf0-aee4-cd83a85c78bb | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 490f652c-a690-4a92-a7fe-6d39eb5b07c4 | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 70c4529e-e227-404a-9e9b-3e8f547a1929 | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 7d160d3e-d32c-48c6-bb6f-956bbac8a46b | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | a9657730-a48a-48dc-97c9-cf8b70ae20bd | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 9ac040c5-842e-4f15-b3c8-55515f6120a2 | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 75f0a7b4-05a4-40e0-a6d7-0852fc62870f | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| d3596015-3ef7-4c2b-997b-ddffd55274ba | QRVO | 2026-02-06 | 39b61eb6-aa37-4c45-bec6-0aa1fabf8d43 | 2026-02-17 | 84.29 | `ge) 20-day SMA: $80.66, 50-day SMA: $84.29 — the last close is +3.8% vs the 20-d` |
| 3e35728e-f6e2-4606-bc8e-f828b055a5f2 | RBLX | 2026-02-06 | 4d34852d-5f97-468f-a752-5b61d16ce0af | 2026-02-23 | 62.43 | `ceiling 3.0% size, entry 66.42, stop 62.43) → stop 6.0% below THAT entry (62.43` |
| 3e35728e-f6e2-4606-bc8e-f828b055a5f2 | RBLX | 2026-02-06 | a623bf85-7517-4bbe-83ac-83e97e965367 | 2026-02-23 | 62.43 | `ceiling 3.0% size, entry 66.42, stop 62.43) → stop 6.0% below THAT entry (62.43` |
| 3e35728e-f6e2-4606-bc8e-f828b055a5f2 | RBLX | 2026-02-06 | d227c84f-b050-43f5-980a-53b1d984c8f7 | 2026-02-23 | 62.43 | `ceiling 3.0% size, entry 66.42, stop 62.43) → stop 6.0% below THAT entry (62.43` |
| 3e35728e-f6e2-4606-bc8e-f828b055a5f2 | RBLX | 2026-02-06 | ac1b7dcd-dcaf-47a0-bafe-5a92216c7486 | 2026-02-23 | 62.43 | `ceiling 3.0% size, entry 66.42, stop 62.43) → stop 6.0% below THAT entry (62.43` |
| ffedf436-a58c-443b-bab3-d8cb976dd6bb | SOFI | 2026-02-06 | 3d1542d9-1d3d-4b7e-870c-19df673eaf22 | 2026-02-13 | 19.61 | `ceiling 3.0% size, entry 20.86, stop 19.61) → stop 6.0% below THAT entry (19.61` |
| ffedf436-a58c-443b-bab3-d8cb976dd6bb | SOFI | 2026-02-06 | 97105f20-1564-4ab0-9544-be6b1996f049 | 2026-02-13 | 19.61 | `ceiling 3.0% size, entry 20.86, stop 19.61) → stop 6.0% below THAT entry (19.61` |
| ffedf436-a58c-443b-bab3-d8cb976dd6bb | SOFI | 2026-02-06 | d840eb2f-b32b-4466-8fcc-1323e15a510e | 2026-02-13 | 19.61 | `ceiling 3.0% size, entry 20.86, stop 19.61) → stop 6.0% below THAT entry (19.61` |
| ffedf436-a58c-443b-bab3-d8cb976dd6bb | SOFI | 2026-02-06 | c59a9bba-7603-4093-8e3d-45c29d383bc1 | 2026-02-13 | 19.61 | `ceiling 3.0% size, entry 20.86, stop 19.61) → stop 6.0% below THAT entry (19.61` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | e12a100e-01fb-48c2-bb5b-028f6d9824cf | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | e12a100e-01fb-48c2-bb5b-028f6d9824cf | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | e5050179-f3ee-4b62-984a-400e265dc2f3 | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | e5050179-f3ee-4b62-984a-400e265dc2f3 | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 000f0843-f139-44f5-9c8b-b30374a29096 | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 000f0843-f139-44f5-9c8b-b30374a29096 | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 793304e7-8b8e-4d70-a5ba-b16350b9d08c | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 793304e7-8b8e-4d70-a5ba-b16350b9d08c | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 3dfab98d-1f4e-4a10-829a-44fee53bc49a | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 3dfab98d-1f4e-4a10-829a-44fee53bc49a | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ad51584c-fabd-4fae-86bd-19bda59bca98 | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ad51584c-fabd-4fae-86bd-19bda59bca98 | 2026-03-18 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ad51584c-fabd-4fae-86bd-19bda59bca98 | 2026-03-23 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ad51584c-fabd-4fae-86bd-19bda59bca98 | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | d9b49944-d2c7-4300-a653-50f34cbd0cf2 | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | d9b49944-d2c7-4300-a653-50f34cbd0cf2 | 2026-03-18 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | d9b49944-d2c7-4300-a653-50f34cbd0cf2 | 2026-03-23 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | d9b49944-d2c7-4300-a653-50f34cbd0cf2 | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ff39db55-2ba6-4e90-8b73-5e8b6e18596e | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ff39db55-2ba6-4e90-8b73-5e8b6e18596e | 2026-03-18 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ff39db55-2ba6-4e90-8b73-5e8b6e18596e | 2026-03-23 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | ff39db55-2ba6-4e90-8b73-5e8b6e18596e | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 23b8dd8f-b49c-40af-bda3-29cf8c07b51a | 2026-03-17 | 1.08 | `old), trend: downtrend 50-day range: $1.08–$1.79, last close $1.09 (1% of that r` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 23b8dd8f-b49c-40af-bda3-29cf8c07b51a | 2026-03-18 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 23b8dd8f-b49c-40af-bda3-29cf8c07b51a | 2026-03-23 | 1.02 | `r ceiling 3.0% size, entry 1.09, stop 1.02) → stop 6.4% below THAT entry (1.02 f` |
| ec619ac5-b10e-47eb-b675-247d64bc207e | AMC | 2026-03-13 | 23b8dd8f-b49c-40af-bda3-29cf8c07b51a | 2026-03-26 | 0.97 | `Volume: in-line with 20-day average (0.97× the 20-day average, 5-day mean) Day` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 35f2831c-fb01-41c7-a624-d095d365709f | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 35f2831c-fb01-41c7-a624-d095d365709f | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 222d47a7-5ae8-450f-9ad0-cc6682d03028 | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 222d47a7-5ae8-450f-9ad0-cc6682d03028 | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | c45574dd-ac66-411a-92d5-aa627a5c652e | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | c45574dd-ac66-411a-92d5-aa627a5c652e | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | fd260f62-639b-4cfd-95b7-c2e5bee4b756 | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | fd260f62-639b-4cfd-95b7-c2e5bee4b756 | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 2a4f7012-680c-48f6-a011-6bf6499ee4a7 | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 2a4f7012-680c-48f6-a011-6bf6499ee4a7 | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | de1bc1e7-bc5e-4e5a-b79b-ba744c002bdb | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | de1bc1e7-bc5e-4e5a-b79b-ba744c002bdb | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 519c2d5f-edca-46d7-ac05-df240815f198 | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 519c2d5f-edca-46d7-ac05-df240815f198 | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 2c9b58a3-c544-4727-bf4f-eba0ecb4be3f | 2026-03-31 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 047ceb6a-9fa5-4ba0-a364-c9f3eee2abc9 | KSS | 2026-03-13 | 2c9b58a3-c544-4727-bf4f-eba0ecb4be3f | 2026-04-07 | 12.80 | `he way up the **50-day range** of **$12.80–$21.93** and is **15.1%** below the p` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | 95ff1740-71be-425f-8af9-46682854d755 | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | 362a0e2c-e487-4e46-992e-a7f215c01d74 | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | d1a8b614-4732-4617-ae2d-eec7138b5b7e | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | 443e0913-d9a0-4422-a127-ad5d78f4b9ee | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | c1e3f79b-2d4a-4bef-ba81-e5661c47b721 | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | b3f2113f-d65c-492a-9a8c-c463b626d925 | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | c4f388ed-02b7-45ca-873a-15437c128b8c | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | f144ce4b-5174-41bf-ba29-4a81f09a0b90 | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 9db231e7-26d9-4359-a0f8-e2d4bae74e1a | OSCR | 2026-03-13 | 82177bc4-9a02-465e-9d3d-089c3bf0cc6b | 2026-03-17 | 13.51 | `.23 (23% of that range) 20-day SMA: $13.51, 50-day SMA: $14.51 — the last close` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | d15c7de3-a12a-44b9-a1de-0cca7089098b | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 799e027a-38e3-4f61-b28e-65e15ed0338e | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 9d04f9e7-ded0-4460-acaf-5a8f3f94f105 | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 9d04f9e7-ded0-4460-acaf-5a8f3f94f105 | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | d15bea72-1bc0-4f95-a9ed-2797f72424a8 | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | d15bea72-1bc0-4f95-a9ed-2797f72424a8 | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 642d3320-2a5a-4743-bb38-68766338954e | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 642d3320-2a5a-4743-bb38-68766338954e | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | b942677f-e085-4ac5-9bd9-68a1aad3e8c5 | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | b942677f-e085-4ac5-9bd9-68a1aad3e8c5 | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 63c5d5e3-bfe3-4424-982c-3bb75469194f | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 63c5d5e3-bfe3-4424-982c-3bb75469194f | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 5a9252cf-b880-45bc-bcff-8d517d5c1abf | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 5a9252cf-b880-45bc-bcff-8d517d5c1abf | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 88d4a7a6-4092-4a4c-9232-58fcf06b95c4 | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 88d4a7a6-4092-4a4c-9232-58fcf06b95c4 | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 40665f82-4315-4aa4-bb39-4a7b1b1252ac | 2026-03-23 | 2.31 | `% Balance sheet (LIVE): current ratio 2.31, quick ratio 1.46 Ownership (LIVE): 1` |
| 46038f2d-0462-45d5-b52d-9eb78f057bc7 | PLUG | 2026-03-13 | 40665f82-4315-4aa4-bb39-4a7b1b1252ac | 2026-03-30 | 2.14 | `ange) 20-day SMA: $2.03, 50-day SMA: $2.14 — the last close is +5.9% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | f5401fe8-8541-4ee7-8434-78a86f08d29d | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 189467cb-3c48-4706-8418-89a940b3516b | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | f6d0454f-d0d7-4479-a68f-b809f6ef4be2 | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 1d30aea3-b2ac-4c66-8757-d92269956f22 | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 7a75b031-6383-454c-b867-c4dd0ed809b9 | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | c859cd01-c64c-4dfd-ae4b-43653cfc79e1 | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 60e9d423-1a10-458c-b547-0833a6791040 | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 169f6d2b-1824-4ea8-8642-77711465f9cb | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| fe1b6fa4-57c0-4549-81ed-732704380339 | BBWI | 2026-04-10 | 4aa3b033-b969-44b7-bb14-7aad0d31bfae | 2026-04-20 | 20.67 | `ge) 20-day SMA: $18.55, 50-day SMA: $20.67 — the last close is -3.5% vs the 20-d` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | f10537ca-d529-481f-ab36-dc20be9ed69e | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | f5b5e5fb-c269-4626-b126-2ec83bd0cc4b | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | bffe4bfd-89d4-4ad6-8e6e-665140a9c465 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | 552eb14f-d9c7-422e-8d59-0c0d7351b8b8 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | f4909139-d1b5-4e61-b7f1-6eb71c4e9628 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | a367addd-9eb0-40a0-82e7-b6a9c3ede8b1 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | 74bd2d71-abe3-4c91-84db-deb3f60a47fa | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | 27e56768-f8cc-476c-9fb8-4059e85d2d09 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| c952e8c3-c8d4-4624-88c9-0665b16b3639 | SPCE | 2026-04-10 | 7c09cbfd-1659-4233-a566-f01b6fc6b528 | 2026-04-24 | 2.58 | `3.02 (75% of that range) 20-day SMA: $2.58, 50-day SMA: $2.58 — the last close i` |
| 60378747-4e6f-4b4a-bca7-de3194cd769c | ABNB | 2026-04-24 | 4783c716-503e-4c64-b156-7aaf7a1e0efb | 2026-05-21 | 134.25 | `eiling 3.0% size, entry 142.82, stop 134.25) → stop 6.0% below THAT entry (134.2` |
| 60378747-4e6f-4b4a-bca7-de3194cd769c | ABNB | 2026-04-24 | 0fe10517-2be3-4b46-a7ef-f933ff4deadd | 2026-05-21 | 134.25 | `eiling 3.0% size, entry 142.82, stop 134.25) → stop 6.0% below THAT entry (134.2` |
| 60378747-4e6f-4b4a-bca7-de3194cd769c | ABNB | 2026-04-24 | 5339be43-2d48-4fc4-ae2f-66f0cb4d83e4 | 2026-05-21 | 134.25 | `eiling 3.0% size, entry 142.82, stop 134.25) → stop 6.0% below THAT entry (134.2` |
| 60378747-4e6f-4b4a-bca7-de3194cd769c | ABNB | 2026-04-24 | 7ecbcf42-139a-40a8-b583-cfc6f3bb0d69 | 2026-05-21 | 134.25 | `eiling 3.0% size, entry 142.82, stop 134.25) → stop 6.0% below THAT entry (134.2` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 393bf416-b485-45fb-ba53-60a86eddd0a7 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 20fc20b3-0b3b-4041-a680-b544c3505107 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | bc71b332-35f4-4495-b4b1-1714c487b659 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | e0a4fce9-9e1f-4ecc-9c86-411fa98e8225 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 9a6143d2-2cc9-4107-91fa-c73c92d7ee28 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | c292ae6b-85ab-4e22-a0ce-5b7fc8c1b1e3 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 964206b0-60f9-4f0f-9ab2-8b03ee7ff184 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 1dbf9259-6ad1-4f62-b873-2cb031543438 | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 484fb782-58fc-4e0f-b880-fb4cd01004da | PM | 2026-04-24 | 77e519a0-69e0-4c7c-ae51-5e69ecedb01c | 2026-05-15 | 188.05 | `consolidating 50-day range: $150.38–$188.05, last close $162.85 (33% of that ran` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | e66a71b0-a4f7-4ec4-9bc3-a49193dbc3d0 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | 79d6a9e2-2b30-4ba7-86ac-f307eb4821ad | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | 95f72161-207f-42b4-b63e-24ec749a79f4 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | 3b53560c-226b-4699-9c8c-e13e9fcd9612 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | 18383a82-cc00-41d8-b7bb-e14a80be2f05 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | 9dfae4ea-d76e-4de0-84b1-1993874e6f94 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | eab7f385-55c1-431e-8eda-6c027138abc2 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | fe5b3c9a-e907-483c-a4c0-dafd5c011729 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 3cb091c9-5945-48fb-9760-02bffa91a1a6 | VZ | 2026-04-24 | f53942cb-3cb5-488e-a740-347aef5b95a2 | 2026-05-13 | 46.42 | `5.6 (32% of that range) 20-day SMA: $46.42, 50-day SMA: $47.68 — the last close` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 5c98dcd1-37ea-4677-be6c-664de4281bf3 | 2026-07-06 | 5.02 | `e. Instrument: NIO Reference price: $5.02 Retail sentiment: moderately bullish` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 62ef7ee9-90e6-4693-8772-ca5420cde549 | 2026-07-06 | 5.02 | `e. Instrument: NIO Reference price: $5.02 Catalysts — recent: Q3 earnings (beat` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 3c61b0db-ac25-4300-885f-89bd18faf1e8 | 2026-07-06 | 5.02 | `e. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | b8ad3fad-07fa-482d-ad94-fd8e90ea0a11 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | b8ad3fad-07fa-482d-ad94-fd8e90ea0a11 | 2026-07-06 | 5.02 | `e. Instrument: NIO Reference price: $5.02 RSI: 34 (neither overbought nor overs` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 5ae5d99d-343f-4791-8aa6-a7d4e89add98 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 5ae5d99d-343f-4791-8aa6-a7d4e89add98 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | e8521ffa-a116-4314-be6a-e88331055104 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | e8521ffa-a116-4314-be6a-e88331055104 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | ed9a473a-7de6-4c11-8b73-ed11347cf121 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | ed9a473a-7de6-4c11-8b73-ed11347cf121 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | d79299b1-8a35-4fdf-b250-76ec4b49b582 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | d79299b1-8a35-4fdf-b250-76ec4b49b582 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | f8cb7d05-09bc-4509-9503-513760fb504a | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | f8cb7d05-09bc-4509-9503-513760fb504a | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 71856431-ed23-45a1-88ff-bf91bc190dd5 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 71856431-ed23-45a1-88ff-bf91bc190dd5 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 5d7a6e72-d599-4eac-950b-3a343b18ad30 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 5d7a6e72-d599-4eac-950b-3a343b18ad30 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 00c7f186-3123-4859-a47f-13c49fafc5c1 | 2026-06-29 | 4.95 | `old), trend: downtrend 50-day range: $4.95–$7.0, last close $5.02 (3% of that ra` |
| 897365ea-cb27-497e-9d8d-3e3ee57c047e | NIO | 2026-06-19 | 00c7f186-3123-4859-a47f-13c49fafc5c1 | 2026-07-06 | 5.02 | `d. Instrument: NIO Reference price: $5.02 P/E: not available TTM revenue growth` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 39b94282-bac5-43af-90e0-2cfcc87ca3b4 | 2026-06-22 | 7.09 | `IVE): 312M shares out 52-week range: $7.09–$9.71; from the reference price $7.12` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 9ad7ae03-6be1-4352-976c-6fca8fa57f52 | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | ef3bf648-ed1b-413b-b767-af8d4360463d | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 2a02f482-2e9c-4fee-8b57-63ce4a621633 | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | cf328d30-ce98-4066-be8d-9f6545b2b089 | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 1d9cdeba-0748-4800-8d05-315b4a49e0d1 | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 8142d522-cc7a-4dce-865f-9a0b0b8bff7b | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | c1a1df3f-91bf-4119-ab92-ee2f33ebd5ec | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 6d9a405e-cf0a-49d9-b09d-3498ea1a6f0b | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |
| 8e19e795-93ee-4ede-af86-ada7e66d021e | WU | 2026-06-19 | 05560a7c-07fc-40b5-9b27-2f7dd6f2c48c | 2026-06-22 | 7.09 | `2,649 3-month average 52-week range: $7.09–$9.71; from the last close $7.12: -26` |

## Correlation failures

None.
