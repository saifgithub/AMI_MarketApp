# Weekly PN17/GN3 list update — guide

For whoever keeps AMI's copy of Bursa's PN17/GN3 list current. Once a week (Monday morning). About 5 minutes when nothing changed, 15 when a company joins the list.

Written from the first real update (2026-11-26: 12 companies, Bursa's list last updated 30 October 2026).

## 1. Open the list in a browser

https://www.bursamalaysia.com/trade/trading_resources/listing_directory/pn17_and_gn3_companies

It is one table with two sections, **PN17 Companies** (Main Market) and **GN3 Companies** (ACE Market). Note three things from the page:

1. **"Last updated: <date>"** under the heading. Bursa updates the list about once a month, so most weeks this date has not moved.
2. For each company: **name**, **Trading status** (`Trading` or `Suspended`), and which of the three **Status** columns carries the tick (√).
3. Any section headed "affected listed issuer" or paragraph 8.03A (none on 2026-11-26).

## 2. Start from last week's file

Copy last week's `pn17_YYYY-MM-DD.csv`. Usually only `bursa_updated`, a trading status or a tick has changed. Compare row by row with the page:

1. A company on the page and in the file: update its `status_group` and `trading_status` if they moved.
2. A company on the page but not in the file: add a row (step 3 for its code).
3. A company in the file but no longer on the page: delete its row. AMI records the removal.

The first time, start from `pn17_weekly_template.csv` (this folder) and add every company.

## 3. Find the stock code (new companies only)

Bursa's PN17 page shows names, not codes, and Bursa's Listing Directory shows names and websites only. If you know the 4-digit code (your broker's app or any quote page shows it), enter it with its leading zero (`0018`, not `18`). If not, enter the name, leave `stock_code` empty, and say so when you send the file: the coordinator fills it in before loading (from AMI's Bursa universe list; suspended companies are missing from that list, so the coordinator looks them up and cites the source). If a company changed its name, Bursa shows "(formerly known as …)"; the code does not change.

## 4. Fill in the CSV

One row per company on the page:

| Column | What to enter | Example |
|---|---|---|
| `stock_code` | 4-digit Bursa code, no `.KL` | `5040` |
| `company_name` | Name as on Bursa's page | `Meridian Berhad` |
| `market` | `Main` for the PN17 section, `ACE` for the GN3 section | `Main` |
| `status_category` | `pn17` (PN17 section), `gn3` (GN3 section), `affected_listed_issuer_8_03a` (8.03A section), or `unclassified` if unsure | `pn17` |
| `status_group` | Which column has the tick: `pending_plan` = "Pending submission of Regularisation Plan", `plan_under_review` = "Regularisation Plans under authorities' review", `plan_approved_awaiting_uplift` = "Regularisation Plan approved … pending upliftment" | `pending_plan` |
| `trading_status` | `trading` or `suspended`, from the Trading status column | `suspended` |
| `bursa_updated` | The page's "Last updated" date as YYYY-MM-DD, the same on every row | `2026-10-30` |

Save as plain CSV (UTF-8). If the spreadsheet app drops leading zeros from codes, format the `stock_code` column as Text before typing. Name the file `pn17_YYYY-MM-DD.csv`, using the day you read the page.

## 5. Send it

Send the file to the CR267 coordinator (Claude session). The coordinator fills any empty codes, checks the file with the loader's own parser, then loads it into Alpha:

```
scp pn17_YYYY-MM-DD.csv melehost:/tmp/
ssh melehost "docker cp /tmp/pn17_YYYY-MM-DD.csv ami_api_alpha:/tmp/ && docker exec ami_api_alpha python -m scripts.bursa_pn17_refresh --from-file /tmp/pn17_YYYY-MM-DD.csv"
```

The loader prints `added`, `changed` and `removed` counts; the coordinator sends them back to you. It refuses the whole file, and changes nothing, if any code is malformed or repeated, a value is not in the lists above, the `bursa_updated` dates differ, or the file has no rows. A list less than half the size of the previous one is refused unless confirmed (`--accept-shrink`).

Keep the CSV files off the public repo.

## 6. What users see

Each Bursa Room's fact sheet states the stock's status with both dates, for example:

1. *listed as a PN17 issuer (Main Market, plan pending, trading suspended); … Bursa's list updated 2026-10-30, read by AMI 2026-11-26*
2. *not on Bursa's PN17/GN3 list (Bursa's list updated 2026-10-30, read by AMI 2026-11-26)*

If no load happens for 14 days, the line reads "unavailable", so a missed week shows up instead of quietly going stale.
