# Device-lab protocol — sharing the AMI AI Suite's physical phones (v1.0 + am.1)

**What this is:** the agreed protocol for running AMI Trade's device tests on the physical iPhone
and Android phones that belong to the AMI AI Suite project. **Why:** CR267 needs real-device runs
before every TestFlight and Play tester build. The iOS Simulator is paused, and the melehost
Android rig is not a physical phone. Agreed 2026-11-18 between the CR267 session (track B) and
the Suite's coordinator, MC. MC's stakeholder ruling is R-1495.

## Parties

| Role | Who |
|---|---|
| Requester and triage | CR267 session (track B), AMI Trade |
| Booking calendar | NXT ("NXT-Next Rehearsal"), AMI AI Suite |
| Operators (the only ones) | M4 iPhone tester, M4 Android tester, AMI AI Suite |
| Coordinator | MC ("MC-Main CoordinatoR"), AMI AI Suite |

Phone PINs never leave the operators' host. AMI Trade never operates the phones directly.

## 0. Principle — test as a normal user (Saiful, 2026-11-18)

"As much as possible, let things work as a normal user." Every device run uses the app the way a
tester from the public would:

1. The build comes from the store tracks (Play internal, TestFlight), never sideloaded.
2. The app runs against the real Alpha server: no mock data, no seeded shortcuts, no admin or
   operator headers. The rate-limit exemption (DEF490) is for the Mac's API harness only and is
   never used on a device.
3. Each journey starts where a user starts: onboarding from a fresh state, anonymous first, then
   sign-in only when the case is about sign-in.
4. Everything happens through the visible UI: taps, typing, scrolling, back gestures. No deep
   links, dev menus, debug or preview screens, or compile flags (for example `AMI_GAMES`).
5. Waits are real: the Room, quotes and notifications are waited for, never stubbed or skipped.
6. Where a case cannot be done as a user would, the packet says why, and the result is recorded as
   such. It is never silently replaced with a shortcut.

## 1. Booking

1. AMI Trade sends NXT one message per phone, headed **`PHONE BOOKING REQUEST AMI-DL-<n>`**
   (sequential, never reused). It carries:
   1. purpose, in one line;
   2. the phone: Android or iPhone;
   3. the steps (the §2 packet), numbered, with the expected result per step, covering automated
      and manual cases. No credentials or personal account details;
   4. the length, in 30-minute units, **including about 15 minutes for the Suite's hand-back
      check**, plus the earliest and latest acceptable times;
   5. the start state: the build to install and where the operator gets it;
   6. what AMI Trade wants back (the §3 result packet).
2. NXT replies **GRANTED** (slot, operator, exchange folder), **QUEUED** (reason, earliest slot)
   or **DECLINED** (reason), and tells the operator.
3. Before the FIRST grant, the operator checks that its own grant list covers installing and
   running AMI Trade's app. If it doesn't, the question goes to the Suite's stakeholder.
4. One owner per device at a time. The order of priority is:
   1. the Suite's live run (its core platform's R7 run steps);
   2. the Suite's own device work;
   3. AMI Trade, first come first served.
5. Preemption: the operator stops after the current case and returns partial results. AMI Trade
   re-queues the rest.
6. The operator sends **RELEASED** at the end of the slot, after the hand-back check in §4.

## 2. Request packet (AMI Trade → operator, attached to the booking)

1. **Build.**
   - Android: **Play internal testing** (Saiful, 2026-11-18). The copy already installed on the
     Suite's phone stays and updates from Google Play; testers never install or uninstall.
     Application id `ai.agenticmarketintel.ami_trade`. The packet names the expected versionName
     and versionCode. On a mismatch, the tester reports `blocked: build mismatch` and runs nothing.
     Prerequisite: the phone's Google account is on AMI Trade's Play internal-test list.
   - iOS: TestFlight is already installed on the Suite's iPhone, with AMI Trade on auto-update
     (Saiful, 2026-11-18). Bundle id `ai.agenticmarketintel.amiTrade`. The packet names the
     expected version and build number. Before case 1, the tester checks the installed build
     against it (Settings > About in the app, or TestFlight). On a mismatch it reports blocked and
     runs nothing. Testers never sign in or out of TestFlight or the App Store.
2. **Backend:** the app points at the public Alpha server. No setup on the operator's side.
3. **Accounts:** the app is anonymous-first. Any sign-in account is named in the packet.
   Operators never enter a personal Apple or Google account, or any credential of their own.
4. **Cases:** a self-contained markdown list taken from `qa/uat/UAT_SCRIPT.md`. Each case has
   its id (for example `UAT-SIM-031`), title, preconditions, numbered steps and expected results.
   No repo access is needed.
5. **Device setup:** fresh install or upgrade; locale (EN, sometimes AR or MS); text size;
   light or dark mode.
6. **Locator list:** sent with the first packet, for the iPhone (WebDriverAgent) and Android
   (adb) tooling.

## 3. Result packet (operator → AMI Trade)

1. Per case:
   - the case id;
   - an outcome: `passed` / `failed` / `blocked` / `skipped`;
   - a one-line note;
   - screenshot filenames for every failed or blocked case.
2. Per run:
   - device model and OS version;
   - app version and build number;
   - platform (`ios` or `android`);
   - start and end times (UTC);
   - the operator's name.
3. A machine-readable block that AMI Trade folds into its UAT ledger (`qa/uat/ledger.py record`):
   `{"layer":"device","platform":"android","run_id":"AMI-DL-<n>","results":{"UAT-SIM-031":"passed"}}`
4. `blocked` means the case could not be executed. It is never folded into `passed`.
   Testers drive the phones by automation only (adb or WebDriverAgent, UI dump, screenshots). No
   human operates a test device, so a manual case that needs a person comes back
   `blocked: needs a human`. AMI Trade writes manual cases as taps and text entry wherever
   possible.
5. Operators report observations only. AMI Trade files and triages defects in its own register.
   Operators fix nothing, and file nothing through the app's in-app bug reporter.

## 4. Device baseline and hand-back

1. Only AMI Trade's app is installed or uninstalled.
2. Any setting a case changes (locale, text size, dark mode) is restored before RELEASED.
3. **Never change** the phones' DNS, Wi-Fi, certificates, PIN, OS version or the Suite's
   installed apps. Never factory-reset.
4. The phones use the Suite's LAN DNS. The **first run must prove the app reaches the public
   Alpha server**. If it doesn't, the operator reports it and changes nothing.
5. No real money, payments or purchases. AMI Trade is simulation-only.
6. Do Not Disturb is a Settings change outside the testers' grants. It is not set unless the
   Suite's stakeholder grants it. The tester masks any notification in screenshots, and no
   personal data may appear.
7. The Suite's own hand-back check runs at the end of every slot: their app build present,
   network and certificate settings untouched, signed out.

## 5. Cadence

1. Near term: one run per platform before the first tester build, about 15 automated and 20
   manual cases, roughly 1–2 hours per device.
2. During Beta: one run per tester build (about 1–2 a week), changed cases only.

## 6. Channels

1. Messages go by SendMessage: AMI Trade's session is "CR267 beta programme"; the Suite's are
   NXT, MC and the two testers.
2. Files go through a dedicated exchange folder on the operators' host, which is the same Mac
   as AMI Trade's workstation: `/Volumes/Extreme Pro/ami_scratch/android_m4/exchange/`, with
   `steps_in/` and `results_out/`. For the iPhone: `/Volumes/Extreme Pro/ami_scratch/iphone_m4/exchange/`
   with `in/` and `out/`, created by the tester at its first grant. Nothing from the
   Suite's project goes in it.
3. **Amendment R-1495 am.1 (2026-11-18): inside a granted slot, AMI Trade works DIRECTLY with the
   tester** ("M4 ANDROID Tester" / "M4 iPhone tester"): steps, APK and questions in; results out.
   NXT and MC do not relay inside a slot. Booking still goes to NXT.

## Grants ruled (Suite stakeholder, R-1495 am.2, 2026-11-18)

1. **Android:** the tester records the installed version first and NEVER uninstalls. Builds come
   through Play internal testing. The tester opens, drives and closes the app and reads its
   version, with at most 4 PIN entries per slot. A mismatch is `blocked: build mismatch`; the
   tester never opens the Play Store to force an update.
2. **iPhone:** open, drive and close, plus the read-only build check before case 1.
3. **Both:** Do Not Disturb is set for each slot and restored after it (this supersedes §4.6).
   Manual cases MAY be done by a person in AMI Trade's slots, an exception granted to this
   programme only (this supersedes the automation-only note in §3.4).
4. **DNS:** the Suite's LAN DNS forwards public names. The first run proves Alpha resolves.
5. **When to book:** send AMI-DL-1 (Android) and AMI-DL-2 (iPhone) once the build is on the
   Play internal track and in TestFlight.

## Open items

1. Exact device models, OS versions and tooling: the testers state them in their first GRANTED.
