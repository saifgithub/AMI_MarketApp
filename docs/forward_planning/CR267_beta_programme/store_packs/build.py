"""Builds the two Beta store-release packs (Apple, Android) as standalone HTML pages (WP-50 prep, CR267). Run: python3 build.py — then republish both artifacts."""
import html, json, pathlib

OUT = pathlib.Path(__file__).parent
APP_ID = "ai.agenticmarketintel.trade"
PRIVACY = "https://www.agenticmarketintel.ai/privacy/"
TERMS = "https://www.agenticmarketintel.ai/terms/"
SITE = "https://www.agenticmarketintel.ai/"
SUPPORT_URL = "https://www.agenticmarketintel.ai/#contact"
DELETE_URL = "https://www.agenticmarketintel.ai/ami-trade/sad-to-see-you-go"
EMAIL = "support.ai@agenticmarketintel.ai"

BETA_DESCRIPTION = """AMI Trade teaches you to make a trading decision and defend it. You practise on real market data, in a simulated portfolio, with none of your money at risk.

The practice arena is the Room: a simulated desk of AMI analysts. Choose a ticker and the desk works it in front of you: fundamentals, market technicals, news and events, retail positioning, a bull case, a bear case, three Risk Officers pressing the position size from three directions, and a Chief Investment Officer who rules on the trade. You read the debate. You question anyone you disagree with. Then you make your call, and AMI runs it in your simulated portfolio and records your reasoning.

WHAT YOU PRACTISE

• Building a thesis and stress-testing it. Every call meets a bear case and three Risk Officers before you commit.
• Defending a position against your own mandate. Your goals, risk limits, constraints and holdings shape what every analyst says. Submit a trade that breaks your own mandate and the Chief Investment Officer refuses it, with the reason.
• Reading analysis critically. The analysts disagree on the record, and the Evaluation track teaches you to spot a weak argument or a fabricated number.
• Learning from your own record. Every debate, call and reason is stored in your decision journal.
• The foundations. 342 lessons, daily challenges, streaks and leagues.
• Sharia and ethical screening against an AAOIFI-based compliant list, with the as-of date on every verdict.

THIS IS A BETA

The Room is experimental: it can be slow or wrong, and finding out where is the point of the Beta. Everything is free during the Beta. Report a problem from YOU > SETTINGS > HELP.

IMPORTANT

AMI Trade is an educational simulation for adults. It is not investment advice, not a brokerage, and not a recommendation service. All trading is simulated with virtual money. There is no real-money trading and no live brokerage connection: the only broker link is an optional Alpaca paper-trading account, which also uses simulated money. What the Room produces is a training exercise, not guidance on what to buy or sell. Market data is delayed by 15 minutes. Sharia screening reports a screen against a published compliant list; it is not a religious ruling. Nothing in this app is a prediction or forecasts a return.

Privacy Policy: https://www.agenticmarketintel.ai/privacy/
Terms of Service: https://www.agenticmarketintel.ai/terms/
Delete your account and data: https://www.agenticmarketintel.ai/ami-trade/sad-to-see-you-go"""

TF_BETA_APP_DESCRIPTION = """AMI Trade Beta is a training simulator for making and defending trading decisions. Pick a ticker and a simulated desk of AMI analysts debates it in front of you: a bull case, a bear case, three Risk Officers and a Chief Investment Officer who rules on the trade. You make the call; AMI runs it in a simulated portfolio and keeps your reasoning in a journal.

Simulation only. No real money, no real orders, not investment advice. For adults (18+). Everything is free during the Beta."""

WHAT_TO_TEST = """AMI Trade Beta: practise making and defending trading decisions.

AMI Trade is an experimental training simulator. It is simulation-only and is not investment advice. No real money, no real orders. The Room, a simulated desk of AMI analysts, is experimental: it can be slow or wrong, and that is what we want to find out.

PLEASE TRY
1. First run: tick "I am 18 or older", finish the short interview with AMI and set your mandate.
2. Convene a Room on a ticker you know. Read the verdict. Does it fit your mandate? Does the reasoning make sense?
3. Place a simulated trade, then check PORTFOLIO and your Journal (YOU tab).
4. Ask AMI how to do something, for example "How do I report a problem?"
5. Take a lesson or the daily challenge.
6. Sign in (YOU > SETTINGS > ACCOUNT > SIGN IN), then confirm your data is still there after a reinstall.
7. Try Export my data. If you are happy to test it, try Delete account on a spare install, then sign in again within 30 days to restore it.

HOW TO REPORT A PROBLEM
1. YOU > SETTINGS > HELP > Report a problem. Pick a category, describe what happened, add a photo if it helps.
2. If an error shows "Ref: ...", tap it to copy the code and include it. It lets us find the failed request.
3. Use "Report this response" on AMI's text, or the thumbs rating after a Room, to flag a bad answer. They are the fastest route.
4. Say which ticker and which Room it was.

WHAT WE COLLECT
An anonymous ID tied to your chats, journal, Room analyses and simulated trades. If you sign in, the email and name Apple or Google share. Device model, OS and app version, crash diagnostics and basic request data. No advertising IDs, location or contacts. Not sold, not used for advertising. Delete or export your data any time from YOU > SETTINGS > ACCOUNT. Beta servers are in [BETA SERVER LOCATION]. Full policy: https://www.agenticmarketintel.ai/privacy/

SUPPORT
support.ai@agenticmarketintel.ai

Thank you for testing."""

PLAY_RELEASE_NOTES = """AMI Trade Beta, an experimental training simulator. Practise making and defending trading decisions with a simulated desk of AMI analysts (the Room). Simulation-only: no real money, no real orders, not investment advice.

Try: onboarding, a Room on a ticker you know, a simulated trade, a lesson, sign-in. Report problems from YOU > SETTINGS > HELP > Report a problem, and include any "Ref:" code. Export or delete your data in SETTINGS > ACCOUNT."""

APPLE_REVIEW_NOTES = """AMI Trade is an educational trading simulator for adults. There is no real-money trading and no live brokerage. All trades are simulated with virtual money. The only broker link is an optional Alpaca PAPER account (simulated money; live Alpaca accounts cannot be linked). The Sharia screen reports a published compliant list and makes no certification claim. Nothing in the app is investment advice; the disclaimer appears in onboarding, Settings and on every Room verdict.

No sign-in is needed. The app starts anonymously: confirm 18+, then AMI (the Concierge) runs a short interview (about 3 minutes) that sets a simulated mandate. Sign-in (Sign in with Apple) is optional, from YOU > SETTINGS > ACCOUNT > SIGN IN.

Core feature: FLOOR tab > pick a ticker > CONVENE THE ROOM. A desk of AMI analysts debates the stock and a Chief Investment Officer rules on a simulated trade (1 to 3 minutes). Market data is Yahoo Finance, delayed 15 minutes.

Account closure: YOU > SETTINGS > ACCOUNT > Delete account (restorable for 30 days, then deleted), or on the web at https://www.agenticmarketintel.ai/ami-trade/sad-to-see-you-go.

Everything is free during the Beta; there are no in-app purchases in this build."""

# ── step data ───────────────────────────────────────────────────────────────
# status: ready | you | blocked | me
R, Y, B, M = "ready", "you", "blocked", "me"

def item(label, value=None, status=R, note=None, copy=False, limit=None, mono=False):
    return dict(label=label, value=value, status=status, note=note, copy=copy, limit=limit, mono=mono)

APPLE = dict(
    slug="apple", platform="Apple", title="AMI Trade Beta: TestFlight Pack",
    lede="Everything App Store Connect asks for to put the AMI Trade Beta on TestFlight external testing under the company account, in the order the console asks for it.",
    target="TestFlight external testing, reviewed by Beta App Review",
    steps=[
        dict(id="a-gates", title="Gates before the first upload", items=[
            item("Company Apple Developer Program membership", "Enrolled (WP-49 prep steps 1–7 done).", R),
            item("Beta server live at api-beta.agenticmarketintel.ai", "A Beta build bakes this address in and cannot switch servers. Until the host exists, testers would reach nothing.", B, "Gate S4, the last decision of the programme."),
            item("Release go", "Your go for WP-49 release steps 8–23.", Y, "Gate S7."),
            item("Support mailbox works", EMAIL + " receives mail (it is the TestFlight feedback address).", Y, "WP-52: confirm the mailbox; outbound DNS is on the tester-note checklist."),
        ]),
        dict(id="a-ids", title="Certificates, Identifiers & Profiles", items=[
            item("App ID (explicit)", APP_ID, R, "Permanent once created. Description: AMI Trade.", copy=True, mono=True),
            item("Capabilities to tick", "Sign In with Apple · Push Notifications · In-App Purchase (on by default; billing stays off in Beta builds)", R),
            item("APNs key (.p8)", "Create one key with Apple Push Notifications service; upload it to a new OneSignal app for Beta.", Y, "Keep the .p8 file; Apple lets you download it once."),
            item("App Store Connect API key", "Users and Access > Integrations > Team key, role App Manager. Give me the Key ID and Issuer ID; the .p8 stays on this Mac in mobile/beta_accounts.env.", Y, "build_testflight.sh uploads with it."),
            item("Backend Sign in with Apple audience", "APPLE_AUDIENCES=" + APP_ID, M, "I set it in the Beta env (WP-41).", mono=True),
        ]),
        dict(id="a-record", title="App Store Connect: new app record", items=[
            item("Platform", "iOS", R),
            item("Name", "AMI Trade", R, "Store names are unique. If the Alpha record on the personal account already holds 'AMI Trade', rename that record to 'AMI Trade Alpha' first to free the name.", copy=True, limit=30),
            item("Primary language", "English (U.S.)", R, "The copy uses British spelling (practise); either English works."),
            item("Bundle ID", APP_ID, R, copy=True, mono=True),
            item("SKU", "AMITRADE-BETA-01", R, "Internal only, never shown.", copy=True, mono=True),
            item("User access", "Full access", R),
        ]),
        dict(id="a-info", title="App Information", items=[
            item("Subtitle", "Learn to defend your trades", R, copy=True, limit=30),
            item("Category", "Primary: Finance · Secondary: Education", R),
            item("Content rights", "Market data comes from Yahoo Finance via the yfinance library. Answer 'contains third-party content' and confirm you have the rights.", Y, "Counsel item: add to S6 if unsure."),
            item("Age rating questionnaire", "All content categories: None. Gambling, simulated gambling, contests: No. Unrestricted web access: No. Medical or treatment info: No. User-generated content shared with others: No.", R, "Where the console offers a minimum age above the computed rating, choose 18+ to match the in-app gate (CR273). The old draft's '17+' predates Apple's 2025 age tiers."),
            item("Privacy Policy URL", PRIVACY, R, "Live page is v2.1. The v2.2 Beta draft needs counsel and 14 days' notice before publishing (S6).", copy=True, mono=True),
            item("Encryption (export compliance)", "Answered by the build: ITSAppUsesNonExemptEncryption = NO in Info.plist. No upload prompt.", R),
        ]),
        dict(id="a-privacy", title="App Privacy labels", note="From PrivacyInfo.xcprivacy (WP-32). Tracking: No for every type. Revisit only if personalised ads ever ship.", table=dict(
            head=["Category", "Data type", "Linked to user", "Purposes"],
            rows=[
                ["Contact Info", "Email Address", "Yes", "App Functionality"],
                ["Contact Info", "Name", "Yes", "App Functionality"],
                ["Identifiers", "User ID", "Yes", "App Functionality, Analytics"],
                ["Identifiers", "Device ID", "Yes", "App Functionality"],
                ["Usage Data", "Product Interaction", "Yes", "Analytics"],
                ["Purchases", "Purchase History", "Yes", "App Functionality"],
                ["User Content", "Photos or Videos", "Yes", "App Functionality"],
                ["User Content", "Customer Support", "Yes", "App Functionality"],
                ["User Content", "Other User Content", "Yes", "App Functionality"],
                ["Diagnostics", "Crash Data", "No", "App Functionality"],
                ["Diagnostics", "Performance Data", "No", "App Functionality"],
            ]), items=[
            item("Data used to track you", "None", R),
        ]),
        dict(id="a-testinfo", title="TestFlight: Test Information", items=[
            item("Beta App Description", TF_BETA_APP_DESCRIPTION, R, copy=True, limit=4000),
            item("Feedback email", EMAIL, R, copy=True, mono=True),
            item("Marketing URL", SITE, R, copy=True, mono=True),
            item("Privacy Policy URL", PRIVACY, R, copy=True, mono=True),
            item("Beta App Review contact", "First name, last name, phone, email of the person Apple calls.", Y),
            item("Sign-in required", "No. The app starts anonymously; no demo account is needed.", R),
            item("Review notes", APPLE_REVIEW_NOTES, R, copy=True, limit=4000),
        ]),
        dict(id="a-build", title="Build and upload", items=[
            item("Fill mobile/beta_accounts.env", "Company team ID, ASC API key ID + issuer, OneSignal Beta app ID, SENTRY_DSN. Template: mobile/beta_accounts.env.example.", Y, "Values only you can create; I wire them in once they exist."),
            item("Build command", "scripts/build_testflight.sh --channel beta --no-games --no-billing", B, "The script refuses until every company value is set and the Beta URL exists (S4).", copy=True, mono=True),
            item("Version", "0.1.0, next build number after 129", R),
            item("What to Test", WHAT_TO_TEST, R, "Replace [BETA SERVER LOCATION] once S4 picks the host.", copy=True, limit=4000),
        ]),
        dict(id="a-groups", title="Testers", items=[
            item("Internal group first", "Add the build to an internal group and book a device-lab run (AMI-DL) before any external tester sees it.", M),
            item("External group", "AMI Trade Beta", R, "Add the build, then Submit for Review. The first build of each version goes to Beta App Review (usually a day or two); later builds of the same version mostly skip it.", copy=True),
            item("Invite", "By email, or a public link with a tester cap you choose.", Y),
        ]),
        dict(id="a-assets", title="Assets", items=[
            item("App icon 1024×1024", "In the build (Assets.xcassets). Nothing to upload.", R),
            item("Screenshots", "Not needed for TestFlight. Needed later for the App Store listing (6.9-inch iPhone).", M, "I capture them from the device rig when the store listing (WP-50) starts."),
        ]),
    ])

PLAY = dict(
    slug="android", platform="Google Play", title="AMI Trade Beta: Play Pack",
    lede="Everything the company Play Console asks for to run the AMI Trade Beta on a closed testing track, in the order the console asks for it.",
    target="Closed testing track, reviewed by Google Play",
    steps=[
        dict(id="p-gates", title="Gates before the first upload", items=[
            item("Company (organization) developer account", "Enrolled. The 12-testers-for-14-days rule applies to personal accounts, so it should not apply here.", R, "Check the Dashboard: if it shows a testing requirement for production access, it applies after all."),
            item("Beta server live at api-beta.agenticmarketintel.ai", "A Beta build bakes this address in and cannot switch servers.", B, "Gate S4."),
            item("Release go", "Your go for WP-49 release steps 8–23.", Y, "Gate S7."),
            item("Support mailbox works", EMAIL + " receives mail (it is the listing contact address).", Y, "WP-52."),
        ]),
        dict(id="p-create", title="Create app", items=[
            item("App name", "AMI Trade", R, "You were doing this on 2026-11-23.", copy=True, limit=30),
            item("Default language", "English (United States), en-US", R),
            item("App or game", "App", R),
            item("Free or paid", "Free", R, "Cannot be changed to paid later; in-app purchases are still allowed."),
            item("Declarations", "Developer Program Policies, US export laws: tick both.", Y),
            item("Package name", APP_ID, R, "Set permanently by the first uploaded AAB.", copy=True, mono=True),
        ]),
        dict(id="p-content", title="Policy > App content", items=[
            item("Privacy policy", PRIVACY, R, copy=True, mono=True),
            item("App access", "All functionality is available without special access. The app starts anonymously; sign-in is optional.", R),
            item("Ads", "Recommended answer: Yes, contains ads.", Y, "Beta builds show house fill (our own promos) and link the AdMob SDK without starting it. Answering Yes is the safe side; switch to No only if you rule house fill out of the Beta."),
            item("Content rating (IARC)", "Category: Reference, News, or Educational. Violence, sexuality, language, controlled substances: None. Real-money gambling: No. Simulated gambling: No. Users interact or exchange content: No. Shares location: No. Digital purchases: Yes (the app has in-app purchases, off during Beta).", R, "Expected result: a low age rating. The 18+ audience is set in the next item."),
            item("Target audience", "18 and over only. Appeals to children: No.", R, "Matches the in-app 18+ gate (CR273)."),
            item("News app", "No", R),
            item("Financial features", "Declare no regulated financial features: no loans, no payments, no real trading or brokerage. Describe it as simulated trading education.", R, "Check the console's current option list; pick the 'none of these' path."),
            item("Government app · Health", "No · No", R),
            item("Advertising ID", "Answered after I check the first Beta AAB's merged manifest.", M, "The AdMob plugin can add the AD_ID permission even though our manifest does not. I report which answer is true."),
            item("Data safety", "Form below.", R),
        ]),
        dict(id="p-datasafety", title="Data safety form", note="Built from the app's privacy manifest and SDK list. Service providers (Supabase, RevenueCat, Sentry, OneSignal, model hosts) process data for us, which Play does not count as sharing.", table=dict(
            head=["Data type", "Collected", "Required", "Purposes"],
            rows=[
                ["Personal info › Name", "Yes", "Optional (sign-in)", "App functionality, Account management"],
                ["Personal info › Email address", "Yes", "Optional (sign-in)", "App functionality, Account management"],
                ["Personal info › User IDs", "Yes", "Required", "App functionality, Analytics"],
                ["Financial info › Other financial info", "Yes", "Required", "App functionality, Personalization (the simulated mandate: goals, risk limits, holdings)"],
                ["Financial info › Purchase history", "No (Beta)", "n/a", "Add when billing turns on"],
                ["Photos", "Yes", "Optional", "App functionality (bug-report attachment)"],
                ["App activity › App interactions", "Yes", "Required", "Analytics, App functionality"],
                ["App activity › Other user-generated content", "Yes", "Required", "App functionality (journal, questions to the desk, bug-report text)"],
                ["App info and performance › Crash logs", "Yes", "Required", "App functionality"],
                ["App info and performance › Diagnostics", "Yes", "Required", "App functionality"],
                ["Device or other IDs", "Yes", "Required", "App functionality (push notifications)"],
                ["Location, Contacts, Messages, Audio, Calendar, Health, Web history", "No", "n/a", ""],
            ]), items=[
            item("Data shared with third parties", "No", R),
            item("Encrypted in transit", "Yes", R),
            item("Account creation", "Anonymous by default; optional sign-in with Google or an email code.", R),
            item("Deletion", "Users can request deletion in the app and on the web.", R),
            item("Delete account URL", DELETE_URL, R, copy=True, mono=True),
        ]),
        dict(id="p-listing", title="Grow > Store presence > Main store listing", items=[
            item("App name", "AMI Trade: Practise the Call", R, copy=True, limit=30),
            item("Short description", "Learn to make and defend a trading call. A simulated desk debates; you decide.", R, copy=True, limit=80),
            item("Full description", BETA_DESCRIPTION, R, "Beta edition of the WP-29 copy: English only, no pricing block, Alpaca paper named, deletion link added.", copy=True, limit=4000),
            item("App icon 512×512", "I export it from the 1024 hi-res icon.", M),
            item("Feature graphic 1024×500", "Not made yet.", M, "I build it in the same hex style as the developer header."),
            item("Phone screenshots (2–8)", "Not taken yet.", M, "I capture them from the device rig on the dark theme; plan in marketing/users/assets/screenshots_and_captions.md."),
            item("Category · Tags", "Finance · Education, Stock trading, Investing", R),
            item("Contact email", EMAIL, R, copy=True, mono=True),
            item("Website", SITE, R, copy=True, mono=True),
        ]),
        dict(id="p-signing", title="First upload and app signing", items=[
            item("First AAB", "Upload by hand in the console (Play needs this to enrol the app in Play App Signing). I build the AAB; you drag it in.", Y),
            item("Play App Signing", "Accept Google-managed signing key.", Y),
            item("SHA-1 of the app signing key", "Setup > App signing. Send it to me.", Y),
            item("Google sign-in clients", "Google Cloud: an Android OAuth client (package + SHA-1) and a Web client; backend GOOGLE_AUDIENCES gets the Web client ID.", M, "WP-49 prep step 4 has the consent-screen details."),
            item("Forced-update link", "ANDROID_PLAY_STORE_URL=https://play.google.com/store/apps/details?id=" + APP_ID, M, "Required on Beta (DEF511).", mono=True),
        ]),
        dict(id="p-closed", title="Testing > Closed testing", items=[
            item("Track", "Create a closed track named 'Beta'.", Y, copy=False),
            item("Testers", "A Google Group (easiest to manage) or an email list.", Y),
            item("Feedback URL or email", EMAIL, R, copy=True, mono=True),
            item("Countries", "All countries, or the Beta markets you choose.", Y),
            item("Release name", "0.1.0 (next build after 129)", R),
            item("Release notes", PLAY_RELEASE_NOTES, R, copy=True, limit=500),
            item("Later uploads", "publish_playstore.sh has only an internal lane. I add a closed-testing lane before the second Beta build.", M),
            item("Send for review", "Publishing overview > Send changes for review.", Y),
        ]),
    ])

STATUS_LABEL = {R: "Ready", Y: "You", B: "Blocked", M: "I do"}

def render_value(it, sid, n):
    v = it["value"]
    if v is None:
        return ""
    esc = html.escape(v)
    long = "\n" in v or len(v) > 160
    cnt = ""
    if it["limit"]:
        over = len(v) > it["limit"]
        cnt = f'<span class="count{" over" if over else ""}">{len(v):,} / {it["limit"]:,}</span>'
    btn = f'<button class="copy" type="button" data-target="v-{sid}-{n}">Copy</button>' if it["copy"] else ""
    cls = "val" + (" mono" if it["mono"] else "") + (" block" if long else "")
    tag = "pre" if long else "div"
    tools = f'<div class="tools">{cnt}{btn}</div>' if (cnt or btn) else ""
    return f'<{tag} class="{cls}" id="v-{sid}-{n}">{esc}</{tag}>{tools}'

def render(pack):
    steps = pack["steps"]
    counts = {k: 0 for k in STATUS_LABEL}
    for s in steps:
        for it in s["items"]:
            counts[it["status"]] += 1
    blockers = [(s, it) for s in steps for it in s["items"] if it["status"] in (B, Y)]
    parts = []
    for i, s in enumerate(steps, 1):
        rows = []
        for n, it in enumerate(s["items"]):
            note = f'<p class="note">{html.escape(it["note"])}</p>' if it["note"] else ""
            rows.append(
                f'<li class="item st-{it["status"]}"><div class="ihead"><span class="label">{html.escape(it["label"])}</span>'
                f'<span class="chip c-{it["status"]}">{STATUS_LABEL[it["status"]]}</span></div>'
                f'{render_value(it, s["id"], n)}{note}</li>')
        table = ""
        if s.get("table"):
            t = s["table"]
            th = "".join(f"<th>{html.escape(h)}</th>" for h in t["head"])
            tr = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in t["rows"])
            table = f'<div class="tablewrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'
        snote = f'<p class="snote">{html.escape(s["note"])}</p>' if s.get("note") else ""
        parts.append(
            f'<section class="step" id="{s["id"]}"><header class="shead">'
            f'<label class="done"><input type="checkbox" id="chk-{s["id"]}" data-step="{s["id"]}"><span class="num">{i:02d}</span></label>'
            f'<h2>{html.escape(s["title"])}</h2></header>{snote}{table}<ul class="items">{"".join(rows)}</ul></section>')
    you = "".join(
        f'<li><a href="#{s["id"]}">{html.escape(it["label"])}</a><span class="chip c-{it["status"]}">{STATUS_LABEL[it["status"]]}</span></li>'
        for s, it in blockers)
    summary = "".join(
        f'<div class="tally t-{k}"><span class="n">{counts[k]}</span><span class="k">{STATUS_LABEL[k]}</span></div>'
        for k in (R, M, Y, B))
    out = TEMPLATE
    for k, v in dict(TITLE=html.escape(pack["title"]), PLATFORM=html.escape(pack["platform"]),
                     LEDE=html.escape(pack["lede"]), TARGET=html.escape(pack["target"]), APP_ID=APP_ID,
                     SUMMARY=summary, YOU=you, BODY="".join(parts), SLUG=pack["slug"]).items():
        out = out.replace(f"%%{k}%%", v)
    return out

TEMPLATE = open(OUT / "template.html").read()
for p in (APPLE, PLAY):
    (OUT / f"ami_trade_beta_{p['slug']}_pack.html").write_text(render(p))
    print(p["slug"], "ok")
