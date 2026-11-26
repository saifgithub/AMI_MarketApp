# Weekly PN17/GN3 list update — guide

For whoever keeps AMI's copy of Bursa's PN17/GN3 list current. About 10 minutes, once a week (Monday morning).

## 1. Open the list in a browser

https://www.bursamalaysia.com/trade/trading_resources/listing_directory/pn17_and_gn3_companies

Check both markets (the Main / ACE selector).

## 2. Fill in the CSV

Start from `pn17_weekly_template.csv` (this folder). One row per company on the page:

| Column | What to enter |
|---|---|
| `stock_code` | Bursa stock code, e.g. `0123` or `5678` (no `.KL`) |
| `company_name` | Company name as listed |
| `market` | `Main` or `ACE` |
| `status_category` | `pn17` (Main Market PN17), `gn3` (ACE Market GN3), `affected_listed_issuer_8_03a` (Main Market paragraph 8.03A "affected listed issuer"), or `unclassified` if unsure |
| `status_group` | optional: `pending_plan`, `plan_under_review`, `plan_approved` or `plan_approved_awaiting_uplift` |

Enter every company currently on the page, not only the changes. A company that left the list is simply not in the file; AMI records its removal. Name the file `pn17_YYYY-MM-DD.csv` (the day you read the page).

## 3. Send it

Send the file to the CR267 coordinator (Claude session), who loads it:

```
scp pn17_YYYY-MM-DD.csv melehost:/tmp/
ssh melehost "docker cp /tmp/pn17_YYYY-MM-DD.csv ami_api_alpha:/tmp/ && docker exec ami_api_alpha python -m scripts.bursa_pn17_refresh --from-file /tmp/pn17_YYYY-MM-DD.csv"
```

The load is recorded as a manual read with its date. A file with a malformed code, a duplicate code, an unknown category or no rows is refused and changes nothing; a list less than half the size of the previous one is refused unless confirmed (`--accept-shrink`).

## 4. What users see

Every Bursa Room's fact sheet states each stock's status with the date of the last load ("not on Bursa's PN17/GN3 list as of 2026-12-07", or "listed as a PN17 issuer (Main Market, plan under review) …"). After 14 days without a load it reads "unavailable", so a missed week is visible, never silently out of date.
