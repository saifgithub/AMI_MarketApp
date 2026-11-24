# CR283 — One market setting for the whole app; Bursa names resolve to codes

Filed 2026-11-24 (AT:B1). Part of CR282 Bursa phase 1. Behind the same switch as CR282
(`AMI_BURSA` / `MARKET_BURSA_ENABLED`): on in Alpha, off for testers until counsel rules.

## Why

Saiful, 2026-11-24: *"do we need a switch to change the market from US to Malaysian, which
would then direct the rest of the application to the right market? for example, when
"CIMB" is entered, the app set for malaysian market will look for the malaysian bank,
instead of another US ticker?"* → *"yes"* (file and build).

Measured state at filing:
1. `routeOmnibox` treats any 1–5 letter word as a US ticker: "CIMB" convenes a Room on US "CIMB".
2. Bursa is reachable only by its number code ("1023" / "1023.KL").
3. The US/MY toggle (`selectedMarketProvider`) exists only on the Portfolio screen; nothing else follows it.
4. No Bursa name→code table is stored. The SC Shariah list names only its 886 compliant stocks.
5. Yahoo search (`query2.finance.yahoo.com/v1/finance/search`), filtered to exchange `KLS`,
   resolves short names and company names: CIMB→1023.KL, MAYBANK→1155.KL, PBBANK→1295.KL,
   "public bank"→1295.KL, TENAGA→5347.KL (probed 2026-11-24). It is already Alpha's Bursa
   price source, so the lookup shares the price feed's licence status (pending, CR282).

## Scope

1. **One app-wide market setting.** `selectedMarketProvider` becomes the active market for the
   whole app (default US, persisted per user). The Portfolio toggle stays as one control of it.
   Followers: the Floor search box, the ticker picker / ticker tape defaults
   (`activeBourseProvider`), the trade ticket's default book, watchlist defaults.
2. **Market chip on the search box** ("US" / "MY"), tappable to switch.
3. **Name resolution (backend).** `GET /v1/tickers/resolve?q=&market=` → candidates
   `{ticker, market, short_name, long_name}`, filtered to the market's exchanges (MY: `KLS`;
   US: the US listing exchanges), cached. Upstream failure returns an explicit error, never
   an empty "no match" (CR040 degrade loudly).
4. **Search box routing with Bursa on.**
   1. A number code always goes to Bursa, whatever market is active.
   2. A word is resolved against both markets. One market matches → that ticker. Both match →
      a two-line chooser, active market first. Never a silent pick.
   3. Lookup down → in MY mode say "can't look up names right now — use the 4-digit code";
      in US mode fall back to today's ticker-shape rule (US tickers keep working offline).
   4. The CTA names the resolved ticker and market ("CONVENE THE ROOM · CIMB · 1023").
5. **Bursa off ⇒ no change at all**: no resolve call, no chip, today's routing exactly.

## Acceptance

1. In MY mode "CIMB" convenes 1023.KL; "maybank" convenes 1155.KL.
2. In US mode "AAPL" convenes AAPL; a word listed in both markets shows the chooser.
3. "1023" goes to 1023.KL in either mode.
4. Resolver outage → the visible message above, never a wrong ticker.
5. Bursa-off build: routing and widgets byte-for-byte today's behaviour (tests pin it).
6. UAT cases for the above (API + device), and the controls area updated.

## Log

1. 2026-11-24 — filed; worker briefed (Sonnet, own worktree).
