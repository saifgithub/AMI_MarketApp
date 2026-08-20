# CR122 — Privacy policy v2.1 draft (advertising clauses)

Clause-level replacement text for `website/privacy/index.html`, ready to
publish **with the first AdMob-enabled store build** — not before (see the
liaison doc §5: while AdMob is dark the live v2.0 claims are true, and the
build scripts' ADS POLICY GATE blocks an ads build until this ships).
Saiful reviews wording before publish; the archive/notice mechanics are the
site's standard ones (clause 16, `/privacy/v2/`).

---

## Edit 1 — clause 5, replace the final paragraph

**Current:**
> We do **not** collect advertising identifiers, location data, contacts, …

**Replace with:**

```html
<p>We do <strong>not</strong> collect location data, contacts, your photo
library other than the bug-report attachment you explicitly choose, or any
biometric data. Advertising identifiers are collected <strong>only</strong>
in the circumstances described in clause 7A — on the free Floor Pass plan,
by our advertising partner, and on iOS only if you allow tracking when
asked. Paid plans see no ads and no advertising identifier is used.</p>
```

## Edit 2 — clause 7, replace the final paragraph

**Current:**
> We do not sell your personal information and we do not share it with advertisers, data brokers, or AI training providers.

**Replace with:**

```html
<p>We do not sell your personal information and we do not share it with
data brokers or AI training providers. Your conversations, mandate,
simulated trades, and account data are never shared with advertisers.
The only advertising-related sharing is the device-level data our ad
partner processes to serve ads on the free plan, described in clause 7A —
and you can restrict it there.</p>
```

## Edit 3 — new clause 7A (insert after clause 7)

```html
<section class="legal-section">
  <h2><span class="num">7A.</span> Advertising on the free plan</h2>
  <p>The free <strong>Floor Pass</strong> plan is ad-supported. Paid plans
  (Trader, Floor Manager, and trials of them) contain no advertising.</p>
  <p>Two kinds of ads can appear:</p>
  <ul>
    <li><strong>House ads</strong> — our own upgrade suggestions. These are
    generated inside the app from your plan and usage and involve
    <strong>no third party and no data sharing at all</strong>.</li>
    <li><strong>Partner ads</strong> — served by <strong>Google
    AdMob</strong>. When an ad is requested, Google receives device-level
    data (such as device model, IP address, and — only with your
    permission — the advertising identifier) and acts as described in
    <a href="https://policies.google.com/technologies/partner-sites"
    rel="noopener" target="_blank">Google's privacy &amp; terms</a>. We
    never send Google your conversations, your mandate, your simulated
    trades, or your identity.</li>
  </ul>
  <p>Your controls, all available before any partner ad is shown:</p>
  <ul>
    <li><strong>European Economic Area / UK:</strong> a consent form is
    shown before any partner ad; declining consent limits ads to
    non-personalised delivery. You can change your choice any time in
    Settings → Ad Privacy.</li>
    <li><strong>iOS:</strong> the system App Tracking Transparency prompt
    asks before any tracking; declining still shows ads, just
    non-personalised.</li>
    <li><strong>California and similar US states:</strong> Settings → Ad
    Privacy → "Do Not Sell or Share My Personal Information" sends every ad
    request with restricted data processing.</li>
    <li><strong>Everyone:</strong> upgrading to a paid plan removes ads
    entirely.</li>
  </ul>
  <p>Ad frequency is capped in the app (per session, per day, and per
  10 minutes), and ads never appear inside your agent conversations,
  onboarding, or trade tickets.</p>
</section>
```

## Edit 4 — version history, prepend

```html
<li><strong>v2.1</strong> — effective <!-- date: publish + 14 days -->.
Added clause 7A (advertising on the free Floor Pass plan via Google AdMob,
with consent, ATT, and Do-Not-Sell controls); scoped the advertising-
identifier statement in clause 5 and the advertiser-sharing statement in
clause 7 accordingly. No change to conversations, mandate, or trade data —
those are never shared with advertisers.</li>
```

## Publish checklist (webmaster lane)

1. Archive the current page to `website/privacy/v2/` (same pattern as v1).
2. Apply edits 1–4; set the effective date ≥ 14 days out (clause 16).
3. Deploy website (rsync `ami-web` + melehost, `?v=` cache-bust).
4. In-app banner / email notice per clause 16.
5. Only then: store privacy labels (liaison doc §4) and the first
   `ADMOB_POLICY_PUBLISHED=1` build.
