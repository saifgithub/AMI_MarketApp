# Landing page changes — `website/index.html`

**Status: SPECIFIED, NOT APPLIED.** These are diffs for the webmaster track to make. Nothing here
has been edited or deployed.

Ranked by expected value. The first three are the ones worth doing this week; the site has been
live for months and produced **zero waitlist signups** (T2), and these are the three cheapest
hypotheses for why.

Deploy path, cache rules and smoke checks: `docs/WEBSITE.md`. Current cache-bust token is
`?v=cr072b` at `index.html:34`.

---

## C1 — Instrument the waitlist. Do this first.

**Why first:** everything else on this page is a guess until we can tell "nobody visits" from
"people visit and don't convert." Those two diagnoses have opposite fixes, and right now we cannot
distinguish them.

**Change:** add page-view and conversion instrumentation to all four pages (`index.html`,
`privacy/`, `terms/`, `ami-trade/sad-to-see-you-go/`). Minimum measurements:

| Measure | Why |
|---|---|
| Unique visitors, by referrer | Distinguishes no-traffic from no-conversion |
| Scroll depth to `#pricing` and `#waitlist` | Tells us whether people reach the ask at all |
| Waitlist form submit attempts vs successes | **`website_api` may be silently failing.** 0 signups is also consistent with a broken POST, and nobody has verified otherwise |
| Clicks on every `#waitlist` CTA (there are 7) | Tells us which CTA position works |

**Verify the endpoint independently of analytics**, because a broken form is the cheapest possible
explanation for zero and takes five minutes to rule out:

```bash
curl -sS -X POST https://api-website.agenticmarketintel.ai/waitlist \
  -H 'Content-Type: application/json' \
  -d '{"email":"probe+lp@agenticmarketintel.ai","source":"manual_probe"}'
# expect {"ok":true,"new":true}
```

Then confirm the row landed:

```bash
ssh melehost "docker exec ami_postgres sh -lc 'psql -U \$POSTGRES_USER -d ami_website -c \
  \"select email, source, created_at from waitlist order by created_at desc limit 5;\"'"
```

If that probe fails, C1 is not a marketing task at all — it is a defect, and it is the whole
explanation for T2.

**Privacy note:** whatever tool is used has to be reflected in the published privacy policy and,
if it sets cookies, in a consent mechanism. Adding untracked tracking to a finance site is a worse
problem than having no analytics.

---

## C2 — Re-lead the hero on outcome, not agent count

**Current** (`index.html:115-116`):

```html
<h1 class="hero-h1">13 AI agents.<br>One decision.<br>No shortcuts.</h1>
<p class="hero-sub">…<strong>AMI Trade</strong> is the flagship Applied AI product from AMI.
It deploys a team of 13 specialised agents — each with a defined role — to debate every stock
in real time. You watch the team work. You make the final call.</p>
```

**Three problems.**

1. **It leads with architecture.** `so_what.md` is explicit — users don't buy agents, they buy *"I
   can practice without losing money."* `positioning_and_personas.md` Rule 1 adopts that, and this
   hero is the main thing contradicting it.
2. **"the flagship Applied AI product from AMI" is company positioning in the customer's
   slot.** A first-time visitor does not know what AMI is and has no reason to care which of its
   products is flagship. That sentence is investor copy on a user page.
3. **"debate every stock in real time" is a compliance risk.** It means "the debate streams live,"
   but a reader in a finance context reads "real-time market data" — which we do not have (F7,
   15-minute delayed). Rewrite regardless of the rest.

**Proposed:**

```html
<h1 class="hero-h1">Practice the call.<br>Real market data.<br>None of your money.</h1>
<p class="hero-sub">Pick a stock and <strong>AMI Trade</strong> puts thirteen specialists to
work on it in front of you — fundamentals, news, sentiment, a bull case, a bear case, three
risk analysts arguing about size. You read the debate. You make the call. It runs in
simulation, and it remembers why you did it.</p>
```

Agents arrive in sentence one of the sub-head, as the mechanism. "Applied AI" and "flagship"
move to the `#applied-ai` section, where company positioning belongs and where it already lives.

**This is a hypothesis, not a certainty.** It becomes testable once C1 ships — which is the
argument for doing C1 first even though C2 is more satisfying.

---

## C3 — Correct the stale Sharia line. It is now factually wrong.

**Current** (`index.html:817`):

```html
US equities at launch &nbsp;·&nbsp; GCC, Tadawul &amp; Bursa coverage and Sharia screening
are on the roadmap, not shipped
```

**Sharia screening shipped.** `SHARIA_SCREEN_ENABLED=true` on Alpha; AAOIFI standard; **216
compliant of the 503-name S&P 500 parent index**, as-of 2026-07-28; and the verdict has reached
the client since DEF094 was fixed and merged (`66ad136`, AT:R65). Three ethical-exclusion mandate
flags shipped alongside it (DEF112).

We are publicly denying our most defensible differentiator — the one `vs_finelo.md` identifies as
the thing mass-market competitors will not build.

**Proposed:**

```html
US equities at launch &nbsp;·&nbsp; AAOIFI-based Sharia screening is live — 216 of the S&amp;P
500 on the current list, with the as-of date on every verdict &nbsp;·&nbsp; GCC, Tadawul
&amp; Bursa coverage is on the roadmap, not shipped
```

GCC/Tadawul/Bursa stays disclaimed — that part is still true (F9).

**Guardrail.** Per `_facts/claim_register.md` N1: the universe is the S&P 500, not all equities;
it is a screen, not a religious ruling; `unknown` must never read as approval. The proposed line
scopes the universe and dates the verdict, which is what makes it safe. Do not shorten it to
"Sharia screening is live" — the specifics are the credibility.

Also worth a dedicated feature block near `#compare`, since this is a reason-to-choose and not a
footnote. Currently the only mention is a role label at `index.html:530`.

---

## C4 — Real screenshots in `#app-preview`

`docs/WEBSITE.md` records these as placeholders. `screenshots_and_captions.md` produces the set;
use frames 1 (live debate), 2 (verdict board), 4 (Sharia verdict) and 6 (lessons comb).

Same no-large-gain rule as the store frames: a screenshot showing a big simulated gain is a
performance claim (F13) wherever it appears.

---

## C5 — Designed og-image

`docs/WEBSITE.md` open item. A PIL-generated stopgap is live reading *"13 AI agents. One
decision."* — the same builder-first line C2 replaces, so **these two ship together** or the
social card contradicts the page it links to.

1200×630, built from frame 1 or 2, carrying C2's outcome line.

---

## C6 — Store buttons, once listings are public

Every CTA currently points at `#waitlist` because `docs/WEBSITE.md` records the TestFlight and
Play opt-in URLs as never supplied. Once Gate B closes, the 7 `#waitlist` links become App Store
and Play badges — and the waitlist section becomes a fallback for unsupported platforms, not the
primary ask.

Do not do this early. A store badge that 404s is worse than a waitlist.

---

## C7 — Pricing: blocked

`#pricing` says "TBD / month" and "Exact pricing revealed at launch." The spec says $14.99 /
$34.99. And the site's free tier (3 analysts per session, 5 Convene sessions/week) does not match
the spec's Floor Pass (13 credits, 1 Room, 5 one-on-ones).

**Do not touch this section until Saiful confirms which is current** — see
`user_acquisition_plan.md` §11. Publishing a price that disagrees with the store listing is worse
than publishing no price.

---

## C8 — A "what's not built yet" block

Counter-intuitive, and worth doing: **a short honest list of what is not shipped converts better
with a skeptical finance audience than silence does.** This audience's default assumption is that
every claim is inflated; a page that volunteers its own gaps resets that prior, and it is the same
instinct that makes C3's specificity work.

Suggested, near the footer:

```
NOT SHIPPED YET — so you know what you're joining
· Push notifications and daily briefings
· GCC, Tadawul and Bursa coverage
· Real-time data (market data is delayed 15 minutes)
· Huawei AppGallery
Closed alpha. iOS via TestFlight, Android via Play internal testing.
```

Every line is from the claim register's FORBIDDEN block, which is what makes it safe to publish —
it is the same list, stated as a disclosure instead of a prohibition.

---

## Sequence and deploy notes

| Order | Change | Blocked on |
|---|---|---|
| 1 | **C1** instrument + probe the endpoint | Analytics choice; privacy-policy update |
| 2 | **C2** hero + **C5** og-image, together | — |
| 3 | **C3** Sharia correction | — (do before halal outreach, per `organic_playbook.md` §4) |
| 4 | **C8** honesty block | — |
| 5 | **C4** screenshots | A capture session on device |
| 6 | **C6** store buttons | Gate B |
| 7 | **C7** pricing | Saiful |

**Deploy rules from `docs/WEBSITE.md`, all load-bearing:**

- rsync target is `agenticmarketintel.ai/`, the addon-domain docroot — **not** `public_html`,
  which hosts a different site.
- The `.well-known/` and `.ftpquota` excludes are not optional with `--delete`.
- **Always dry-run (`-n`) and read the deletion list first.**
- Cloudflare caches static assets 7 days. Any `site.css` change needs the `?v=` token bumped in
  **all four** pages — `index.html`, `privacy/`, `terms/`, `ami-trade/sad-to-see-you-go/`. Current
  token: `cr072b`.
- C2/C3/C8 are HTML-only, and HTML is served `DYNAMIC` — so those land without a cache-bust. C4
  and C5 touch assets and do need one.

Post-deploy smoke:

```bash
curl -sS https://agenticmarketintel.ai/ | grep -c 'honey-hex t-'          # 13 curriculum tracks
curl -sS https://agenticmarketintel.ai/ | grep -o 'site.css?v=[a-z0-9]*'  # cache-bust token
curl -sS https://agenticmarketintel.ai/ | grep -i 'roadmap, not shipped'  # C3: no Sharia mention
for f in Archive.zip WEBSITE.md deploy_ftp.py; do
  curl -s -o /dev/null -w "$f %{http_code}\n" "https://agenticmarketintel.ai/$f"; done  # all 404
```
