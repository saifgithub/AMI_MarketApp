/// CR232 — the reserved slot for CR226's global anchored banner.
///
/// `HomeShell`'s persistent chrome is nav / ad slot / ticker tape,
/// bottom-to-top, per CR226 §Scope 1 (the shell change lands the slot;
/// CR226 fills it). This widget is that slot **today**: zero height, so no
/// layout is visible until CR226 lands the actual `google_mobile_ads`
/// integration (gated on CR225) behind it. Do not add AdMob wiring here —
/// that is CR226's scope, not CR232's.
library;

import 'package:flutter/widgets.dart';

class ShellBannerSlot extends StatelessWidget {
  const ShellBannerSlot({super.key});

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
