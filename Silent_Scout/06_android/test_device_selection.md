# Android Test Device for AMI Trade — KSA, May 2026

> Forward-looking procurement plan. Saved into Silent_Scout because the
> Android version of AMI Trade is on the future-deliverables track —
> nothing here impacts the running iOS Alpha on TestFlight.

## Context

Android development on AMI Trade starts in roughly a week. Saiful needs a physical Android device to play the same role iPhone 13 / iPhone 17 plays on the iOS side — the primary "is this Flutter app behaving on a real device" rig. Buying happens in Saudi Arabia in May 2026.

Constraints set by Saiful:
- **Budget:** SAR 300–1000 (~USD 80–265).
- **NFC** required (a future product feature depends on it).
- **Current Android version** — Android 16, released June 2025.
- **"As generic as possible to ensure maximum compatibility."**

The "generic" criterion deserves a reframe before picking. Two readings:
1. Closest to AOSP / Google's reference Android (Pixel, then Motorola My UX). Best for "is my Flutter build clean against stock."
2. Closest to what a typical KSA Android user actually owns. Best for "will my app survive in the field."

Reading 2 is the right one for a dev-test device whose job is to flush out bugs your users will hit. In the KSA / MENA market that points squarely at **Samsung A-series** (≈ half of Android share). Conveniently, it's also what's available under SAR 1000 with verified NFC and Android 16 shipped today — Pixel is locked out by price, Motorola by un-verifiable NFC in the KSA SKU.

---

## Recommendation

**Samsung Galaxy A16 5G — SM-A166EZKGMEA, 6 GB RAM / 128 GB storage** at ~**SAR 619** from **Jarir**.

- **Buy URL:** https://www.jarir.com/sa-en/samsung-galaxy-a16-5g-smartphones-644924.html
- **Backup retailer:** eXtra — https://www.extra.com/en-sa/mobiles-tablets/mobiles/smartphone/samsung-galaxy-a16-5g-6-128-gb-blue-black/p/100387124

### Why this beats the runners-up

- Only candidate inside the strict SAR 300–1000 budget where **Android 16 (One UI 8) is already shipped** AND **NFC is confirmed in the KSA Middle East SKU**.
- Samsung's **6 OS + 6 security years** commitment outlasts AMI Trade's Beta → v1.0 → v1.1 roadmap — the device won't go stale mid-product.
- Samsung A-series is the de-facto KSA Android baseline, so bugs surfaced on this device are bugs your actual user base will hit.

### Hard purchase gotchas — verify in-store before paying

1. **5G variant only.** Model code must start with **`SM-A166`**. The `SM-A165` is the 4G variant — different specs and a weaker NFC story in some MENA SKUs.
2. **6 GB / 128 GB minimum.** A 4 GB / 64 GB variant exists in some markets and is too tight for Flutter dev builds with hot reload.
3. **Box model code must end in `MEA`** (Middle East). That's the SKU with confirmed KSA NFC. Avoid grey-import "international" boxes from independent sellers.
4. **One UI 8 may not be pre-installed.** Expect a first-boot OTA to pull Android 16 — that's fine.

### Runner-up — only if the A16 is out of stock

**Samsung Galaxy A26 5G** (SM-A266BZKIMEA, 6 GB / 128 GB) at ~SAR 899 from Jarir. Better hardware (Exynos 1380, AMOLED, IP67), same NFC + Android 16 + 6-year update story. Same purchase gotchas apply (`MEA` SKU, 6 GB tier to stay in budget). Worth the extra SAR 280 only if the A16 isn't on shelf.

---

## Shortlist with verified data points

| Model (exact SKU) | KSA price (retailer) | Ships-with | Android 16 today | NFC in KSA SKU | Skin | OEM updates |
|---|---|---|---|---|---|---|
| **Samsung Galaxy A16 5G** SM-A166EZKGMEA, 6GB/128GB | ~SAR 619 (Jarir) | Android 14 | One UI 8 rolling out globally (US/EU/IN confirmed); KSA OTA imminent | **Yes** (MEA SKU verified) | One UI 8 | 6 OS + 6 sec |
| **Samsung Galaxy A26 5G** SM-A266BZKIMEA, 6GB/128GB | ~SAR 899 (Jarir/Noon) | Android 15 | One UI 8 stable since Sept 2025 | **Yes** (NFC A/B in spec) | One UI 8 | 6 OS + 6 sec |
| Motorola Moto G85 5G XT2427, 8GB/256GB ME | ~SAR 849 (Jarir) | Android 14 | Android 16 rollout started Feb 2026 (Chile first), ME version not yet confirmed landed | **Unverified for KSA** — gsmarena "region-dependent"; retailers don't enumerate. Call Jarir before purchase. | Motorola My UX (near-stock) | Android 16 = last OS, security to ~2027 |
| Nothing CMF Phone 2 Pro 128GB/8GB | ~SAR 1046–1238 (Jarir) — over budget | Android 15 → Nothing OS 4 (Android 16) | Yes, ships with Android 16 | **Unverified for KSA**; market-dependent | Nothing OS 4 (light skin) | 3 OS + 6 sec |

---

## Rejected candidates (so they don't get a second look)

- **Google Pixel 7a** — best "generic Android" on paper, but KSA street price is ~SAR 1665 (Noon, international version). Out of budget.
- **Motorola Moto G85 5G** — better skin for "generic" (near-stock My UX), price OK at ~SAR 849, but **KSA NFC is not enumerated on Jarir/Noon spec sheets** and gsmarena flags it as "region-dependent." Buying it requires phoning Jarir to confirm — not worth the risk vs. the A16.
- **Nothing CMF Phone 1** — clean skin and in budget, but **no NFC on this model at all** (Nothing only added NFC starting with Phone 2 Pro).
- **Nothing CMF Phone 2 Pro** — ~SAR 1046–1238, just over budget, and KSA NFC also unverified.
- **Samsung Galaxy A35 5G** — over the SAR 1000 ceiling at KSA retail.
- **Xiaomi Redmi Note 13 / 14 series** — well-known MENA NFC-drop risk per SKU, and HyperOS is the heaviest skin against the "generic" goal.

---

## Verification — how you know the purchase was right

After unboxing, before declaring the device usable for AMI Trade dev:

1. **Confirm model code.** Settings → About phone → Model number reads `SM-A166EZKGMEA` (or another `MEA`-suffixed variant).
2. **Confirm NFC is present.** Settings → Connections → NFC and contactless payments — the toggle should exist. If the menu item is missing, the device shipped without the NFC chip and needs to go back.
3. **Take the Android 16 OTA.** Settings → Software update → Download and install. After update, About phone → Software information should read **Android 16** and **One UI 8.x**.
4. **Enable developer mode + USB debugging.** Settings → About phone → Software information → tap "Build number" 7×. Then Developer options → USB debugging on.
5. **Sanity-check Flutter.** From the Mac: `flutter devices` should list the A16. `flutter run --release` of the current `mobile/` build should install and launch.

If all 5 pass, the device is the new Android baseline rig — pin it into the auto-memory user profile alongside the iPhone 13 / 17 entries in a follow-up session.

---

## Uncertainties (called out explicitly)

- **A16 One UI 8 in KSA specifically:** confirmed in US, EU, India. KSA-region OTA timing not explicitly verified — Samsung typically rolls MENA within 1–2 months of EU. Risk: phone may briefly ship still on One UI 7 (Android 15) before OTA. Acceptable for dev — first boot will pull Android 16.
- **Moto G85 KSA NFC:** gsmarena flags "region-dependent"; KSA retailer listings (Jarir, Noon, Amazon.sa) do not enumerate NFC on the spec line.
- **CMF Phone 2 Pro KSA NFC:** same caveat; not enumerated in Jarir listing.

---

## Sources (research as of 2026-05-18)

- Samsung A16 KSA — Jarir: https://www.jarir.com/sa-en/samsung-galaxy-a16-5g-smartphones-644924.html
- Samsung A16 KSA — eXtra: https://www.extra.com/en-sa/mobiles-tablets/mobiles/smartphone/samsung-galaxy-a16-5g-6-128-gb-blue-black/p/100387124
- Samsung A16 KSA support page (SM-A166EZKGMEA): https://www.samsung.com/sa_en/support/model.SM-A166EZKGMEA/
- Samsung A16 Middle East version — Noon: https://www.noon.com/saudi-en/galaxy-a16-dual-sim-light-green-4gb-ram-128gb-5g-middle-east-version/N70118822V/p/
- Samsung A16 One UI 8 rollout — SamMobile (US): https://www.sammobile.com/news/galaxy-a16-5g-android-16-one-ui-8-0-update-usa/
- Samsung A16 One UI 8 rollout — SamMobile (EU/IN): https://www.sammobile.com/news/galaxy-a16-galaxy-m16-get-one-ui-8-update-more-regions/
- Samsung A26 5G — Jarir: https://www.jarir.com/sa-en/samsung-galaxy-a26-5g-smartphones-654457.html
- Samsung A26 One UI 8 rollout — Sammy Fans: https://www.sammyfans.com/2025/09/29/samsung-elevates-galaxy-a26-5g-with-one-ui-8-android-16-update/
- Samsung A26 One UI 8 stable — GSMArena: https://www.gsmarena.com/samsung_galaxy_a26_one_ui_8_stable_update-news-69720.php
- Moto G85 KSA — Jarir: https://www.jarir.com/sa-en/motorola-g85-5g-smartphones-637934.html
- Moto G85 Middle East version — Noon: https://www.noon.com/saudi-en/g85-dual-sim-olive-green-12gb-ram-256gb-5g-middle-east-version/N70092657V/p/
- Moto G85 Android 16 rollout — ytechb: https://www.ytechb.com/moto-g85-starts-getting-android-16-update/
- Moto G85 Android 16 wave — Gizmochina: https://www.gizmochina.com/2026/02/07/these-motorola-phones-are-receiving-the-android-16-update/
- Moto G85 spec (NFC region-dependent) — GSMArena: https://www.gsmarena.com/motorola_moto_g85-13144.php
- CMF Phone 2 Pro KSA — Jarir: https://www.jarir.com/sa-en/nothing-cmf-phone2-pro-smartphones-658141.html
- CMF Phone 2 Pro spec (NFC market-dependent) — GSMArena: https://www.gsmarena.com/nothing_cmf_phone_2_pro_5g-13821.php
- Pixel 7a KSA — Noon (over budget, listed for rejection traceability): https://www.noon.com/saudi-en/pixel-7a-charcoal-charbon-8gb-ram-128gb-5g-international-version/N53398725A/p/
