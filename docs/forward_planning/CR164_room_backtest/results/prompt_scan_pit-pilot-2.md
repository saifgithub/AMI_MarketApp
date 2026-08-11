# CR164 prompt leakage scan — batch `pit-pilot-2`

Guard (b): post-as_of dates hard-fail; post-as_of close-price matches flag.
Correlation: `llm_audit` rows by same user_id, created_at within
[started_at − 60s, finished_at + 60s].

## Totals

- Index rows scanned: **127** (sample=1.0, seed=164)
- llm_audit rows scanned: **1520**
- Hard fails (post-as_of dates): **0**
- Flags (post-as_of close prices): **156**
- Correlation failures: **1**

## Hard fails

None.

## Flags (post-as_of closes found in prompt text)

| run_id | ticker | as_of | audit row | price date | price | context |
|---|---|---|---|---|---|---|
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | c5d8a7ef-4254-46b3-8333-9fbda9be38a4 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | c5d8a7ef-4254-46b3-8333-9fbda9be38a4 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 314d485a-173a-4481-83d2-0ce3ada14876 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 314d485a-173a-4481-83d2-0ce3ada14876 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 0f3e2fff-6cfb-4362-a8e0-ebd6621e8352 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 0f3e2fff-6cfb-4362-a8e0-ebd6621e8352 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 1c7d913b-c23a-4413-9555-1fc5348cc8cc | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 1c7d913b-c23a-4413-9555-1fc5348cc8cc | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | e0cc2944-2f08-4d7c-93ff-978d3ac4e60f | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | e0cc2944-2f08-4d7c-93ff-978d3ac4e60f | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 335d06d1-e36b-4dfe-a8b2-bd2010434eb5 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 335d06d1-e36b-4dfe-a8b2-bd2010434eb5 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | fa126b66-d503-4f7d-a383-dddfd4e535bf | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | fa126b66-d503-4f7d-a383-dddfd4e535bf | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 46246434-6501-4a0a-91d9-b29df3c0e273 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 46246434-6501-4a0a-91d9-b29df3c0e273 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | da89f388-3ba1-42c7-988f-9b6d6ffd2510 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | da89f388-3ba1-42c7-988f-9b6d6ffd2510 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 76955baf-154c-4f81-8288-19d233080308 | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 76955baf-154c-4f81-8288-19d233080308 | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 9f76f2dd-9244-47e6-9065-af33d689486b | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 9f76f2dd-9244-47e6-9065-af33d689486b | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 248ddcf2-3ee1-44fd-bd7b-0466a5e96bde | 2025-04-16 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| 4a9ddb7c-e0f0-4edf-b9af-60176d2f8489 | NIO | 2025-04-11 | 248ddcf2-3ee1-44fd-bd7b-0466a5e96bde | 2025-04-17 | 3.52 | `ublished calendar. Reference price: $3.52 P/E: not available TTM revenue growth` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 198afebd-37aa-47a8-bde4-9ba36f3a36d1 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | bba97a29-8a5a-468b-b782-cdcb8517969f | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 68dd0098-0225-46a8-b78d-fa11e16c8483 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | bc04d418-ef3b-4e2f-9ddf-4a1cd5997742 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | b79a55e6-d4cf-40d9-a33c-5385ccfd5535 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 5f377990-285e-46ab-93ef-ef7dc65e07fd | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 7e965a0a-9212-4af7-8af2-7fcd6bf8560d | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 924a8092-965c-4ad2-bbaf-4bd4ee8aa413 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | fdffea7d-b437-4ee7-a5b5-d1f65db6bea5 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 698d99ff-b822-44a5-a7e5-1188ae3ef6dd | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 6f03bc24-19bf-4eb3-bba4-27ebc5cfa305 | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| b3c7d0fc-453f-4028-9f58-50293455c8e8 | SCHW | 2025-05-02 | 665c516b-4b72-400f-bf98-3a88be46645d | 2025-05-05 | 82.06 | `0-day average 52-week range: $60.36–$82.06 Catalysts — recent: Q3 earnings (beat` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | c6fdadc4-8815-40c4-828c-65e65588e570 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 580a4e7a-98b2-4cc5-b9b0-bcacaf06d864 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | e68869ee-9173-4c8a-a6ae-104272cd56b4 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | d7075b74-aaf8-49ce-98a2-146c2dd93646 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 1cd08cab-0e94-412a-b007-72336a88d9cc | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | fc90c916-5539-4826-95c6-d18063c17dc7 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 4bdded15-8900-42d2-90b3-8b7c534eae78 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 97d25f9c-779e-48c9-b027-0a3524a90fab | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 39115bb3-a6d5-4d43-a5f2-902018f622d3 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | a17d59fb-1de0-49df-9b7b-040198c910a0 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 50d6d155-8c16-4686-a3e8-3ca4595d40fa | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 1318f423-9f2e-40a7-97b6-7db692947aff | CAG | 2025-09-12 | 9c3c6833-5933-4db9-a218-1741c95b3f55 | 2025-09-26 | 16.85 | `trend: consolidating 50-day range: $16.85–$19.35, last close $17.76 (36% of tha` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 40679580-866a-4549-9c77-1fcbbeca7df3 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 2d69a03e-b081-419d-9068-86063aacaa8a | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 92be2fca-4fbd-4c1e-bf4f-cd604b72dbf4 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | fc566fb4-d53b-4dd4-a763-c604595c867a | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | ae94ba81-17d4-4a18-8071-f066023d6467 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 6bea67e6-1ee8-4102-ab94-fb94b302637a | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 0fbc62a1-59e5-448f-8d16-c9f088c044ca | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 073755b2-3133-4ae4-94cc-5148b313620d | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 98ba2de1-b907-4bbf-9f00-5a692eadb80f | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | e15e76b8-2ef8-4575-87d8-0d306d358cf6 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 602a0fef-2ea1-44cd-9f49-ef0ad99ecff3 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 73bcd786-5fc5-4c67-bd76-6a2c821f5af4 | AMC | 2025-09-26 | 0caaa4bf-357f-4377-95ae-061f96cbc6b8 | 2025-10-21 | 2.89 | `ublished calendar. Reference price: $2.89 P/E: not available TTM revenue growth` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 98b28e12-c4ae-498f-98f2-5b3d11c30224 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 99fc8bc2-90c9-4579-9072-fde23095057e | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 682c965d-e725-4ba6-9a5b-6e3955b48d60 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | ded2b7f8-a3c6-4c9c-b40b-02f1f0f2834e | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 026a35c1-1836-484a-ad98-3903968f62c1 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | a0fbca50-c7cc-41d0-a21a-fdd379e2ab52 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 22e354a6-038d-4d87-927f-98499a409992 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 5a8903ca-d077-4d55-9a78-2336b3d3737d | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | c1fb0ec1-6cb4-48a5-a875-e0b34577bc8e | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 511edcf5-e37e-480f-b31e-203351cbfc9b | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | af078d61-2d7f-4abe-84f2-f507d53fcce1 | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 98b8f224-1a98-4066-948f-2e6f1f5a006a | PEP | 2025-09-26 | 1f180590-20a7-4eaa-be00-73cf9a28d85b | 2025-09-30 | 136.41 | `blished calendar. Reference price: $136.41 P/E: 24.7 trailing (measured — last` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 1ad485dd-fade-4a37-b3d1-0be2876ad84c | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 6c04fabf-7269-4848-8410-12f946e7e06d | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 4ee807d2-680e-40e8-a705-d4dbd1ab4b0b | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 4ce75fe2-b081-4199-b803-7574bc3ce0c1 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 135c4711-060a-4a9c-b499-da373f80b3ad | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | e669d558-a9b0-4118-9e99-dab3e5ea3d07 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 43dfe051-52b7-4377-b6c5-66ed4a01f560 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | a27c8d79-f3cf-42fd-a16f-13ae5b134124 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 472e17b2-ca48-4832-82f4-b8ba2c17ede6 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | c3780e3b-d2ca-4631-b9ad-875d23f588da | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 5193170f-6119-4c50-92ff-2e26c849dec3 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 84bf47e1-003d-436e-862f-cbfac735e42e | TAP | 2025-10-24 | 41dd10cd-36e9-4c95-8bc7-419b7227a061 | 2025-11-06 | 42.68 | `below 20-day average 52-week range: $42.68–$59.81 Catalysts — recent: Q3 earning` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 310a2bce-962d-4b4a-bd09-60617374aa05 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 310a2bce-962d-4b4a-bd09-60617374aa05 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | f6435a87-ef38-4f69-86fd-1e65dc7d7446 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | f6435a87-ef38-4f69-86fd-1e65dc7d7446 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | b39b7e27-397c-4260-b296-0ac8a8e65283 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | b39b7e27-397c-4260-b296-0ac8a8e65283 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 7a489d94-d5ed-40d7-8fc2-bf46dcc8993e | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 7a489d94-d5ed-40d7-8fc2-bf46dcc8993e | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 068ecbbe-993c-4476-afe8-d000c1e7b1a2 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 068ecbbe-993c-4476-afe8-d000c1e7b1a2 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 174c030f-4dd3-4308-8606-2b78ce9e74dc | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 174c030f-4dd3-4308-8606-2b78ce9e74dc | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 0c75fcfa-6c78-4b33-8583-a7254d8cb2c7 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 0c75fcfa-6c78-4b33-8583-a7254d8cb2c7 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 21c43917-3c5f-4a53-82d0-72833921098f | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 21c43917-3c5f-4a53-82d0-72833921098f | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | f9a2d51d-6799-4cc7-b986-20e63ffffcbf | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | f9a2d51d-6799-4cc7-b986-20e63ffffcbf | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 9bb91a94-d6d4-4e1b-a389-c917327a5a25 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 9bb91a94-d6d4-4e1b-a389-c917327a5a25 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 91b0d549-a4a2-459e-b9f8-76e982da98cd | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | 91b0d549-a4a2-459e-b9f8-76e982da98cd | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | be0c7bdd-52e8-4f85-bee4-89bd2abc9c40 | 2025-12-03 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| 50144c0e-262f-473f-8e43-42f7c6f03c1b | AMC | 2025-11-14 | be0c7bdd-52e8-4f85-bee4-89bd2abc9c40 | 2025-12-09 | 2.28 | `ublished calendar. Reference price: $2.28 P/E: not available TTM revenue growth` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | f40cdfcc-fe42-46bf-94ee-554714a322a3 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 22adacef-3f77-476b-bef7-14f5f1c8fae8 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 61db9d84-40ab-4217-a8e1-706fbd8c6b5d | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | af3699d6-262a-4a66-99b4-d50a0f0eff48 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 7a3eb09d-9388-45dc-9619-444a83269e3a | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | c93d5405-dc2e-46ae-9474-e1d2ecc4a42e | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 68041cf9-f9df-4454-ba44-1520468b95bc | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | cc36a243-6040-4d5a-9427-4c88bff8259d | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 3abb6b03-01a0-4d2c-b832-b64da2d7ec05 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 8650915f-ab9a-4959-9c63-f076323ab845 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 9c2d7e22-f739-4a52-b486-93d49f68bcc0 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| e2d3806c-3d93-4a4e-b832-2e2c5658b399 | MO | 2025-12-12 | 8aa03c52-552a-44eb-ab70-b5ee77378bc4 | 2025-12-23 | 55.91 | `blished calendar. Reference price: $55.91 P/E: 10.6 trailing (measured — last 1` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 182d15a7-3b69-4d87-9e63-ae53064b26ab | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 84efe50c-59e1-40e4-9720-1a835e0cfd9c | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | a32a823d-d3f7-4591-be1d-141142f2d384 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | ef9bd0a3-d51d-4fe8-b8e6-6179b7f28c47 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 49c17860-d604-484d-9d22-368fa261a23e | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 624f9fcd-ce41-48a7-896a-fbe3de496cac | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 38b5223b-e6d7-4725-a5e5-5750d72d7411 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | c8cd7615-2b68-4bd7-8c66-e57c4eecadbd | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 58ee98a2-1787-4ab2-b7a4-443d42f5d56e | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 8a461c24-34c6-4674-93b7-0c36a7ff99d1 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 5deafa8e-c158-494e-b0b9-8356cd9cda0e | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 351e9c99-39b7-4d8a-86a4-74849a467a6e | NIO | 2026-01-02 | 146680ce-ec42-48ef-9f9e-e25410d5ce35 | 2026-01-08 | 4.73 | `, trend: consolidating 50-day range: $4.73–$7.54, last close $5.14 (15% of that` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 7f48e210-dfe9-40e6-aaea-6815023f859d | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | c466ce9d-9c76-4f10-8b83-e9bf05a109f9 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | abf28db1-f84a-4fcf-a070-2fb5f8688778 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | ed1661fb-468f-4bd3-9b40-90b09d47ba71 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 185efccb-ec8f-47c7-8abe-b9f5901f5178 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 6c4c677e-c2c8-4352-953c-18b2940af703 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 76151b00-96d2-44be-9444-539338182550 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 9c2396e2-5838-4b72-8102-0d6167585cb8 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 2c246496-ff18-492a-8b36-8a4f758ffacf | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | db8fd667-e497-4d6d-b87f-033135e18f8c | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | bc54e213-89c5-4a52-a076-9decc8093528 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| 8ab2d701-8fd5-48bc-a9a7-49ecba5fe1bf | PLUG | 2026-02-13 | 9fe15556-ab92-4caa-b6c1-928a66317f17 | 2026-03-02 | 1.81 | `old), trend: downtrend 50-day range: $1.81–$2.66, last close $1.89 (9% of that r` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 6847e5cb-8ff1-49bc-b574-3c32278d0cc9 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | acf32393-13fe-42ab-a199-d7418d67330c | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 886393f1-42c4-48a8-921f-65e7db828ac4 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | ff8bc315-8dbf-4967-8c3f-0687617c9d50 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 8a7352c0-215d-4e0a-b273-0d1e84e375e4 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 055e0071-2bba-43b5-8ddd-7450c1ddcfc0 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 972444c4-cd28-4e8d-8a81-cad820af9c6c | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | ac7b6838-142a-4181-9e2b-cfe577fbbac6 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 7a7aa794-b700-4ff4-b1bf-c80bd775156b | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | 8a7afb13-3dda-41ce-97d8-059842f52558 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | c0e1b612-8cdd-4cfa-abfc-9ea328088313 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |
| adf81bb0-99c3-447c-9a7f-b9c0312593dd | WMT | 2026-06-19 | e03eff32-5df1-4cb7-b8f2-9dc5a53e6288 | 2026-06-22 | 117.18 | `blished calendar. Reference price: $117.18 P/E: 41.0 trailing (measured — last` |

## Correlation failures

| run_id | ticker | as_of | reason |
|---|---|---|---|
| cc58cb46-373b-4c63-b25c-cab9f79b1c75 | GIS | 2025-09-12 | no wall-clock window (status=running) |

A correlation failure means the prompt that run actually saw is UNVERIFIED — the batch cannot be declared scan-clean.
