/// CR232 reserved this slot; CR226 fills it.
///
/// `HomeShell`'s persistent chrome is nav / ad slot / ticker tape,
/// bottom-to-top. [AnchoredAdBanner] owns the actual AdMob wiring (adaptive
/// sizing, plan gate, dispose/reload on width change) — this widget is just
/// the named slot `home_shell.dart` places in the chrome `Column`, so the
/// shell's own layout code names "where the ad goes" without depending on
/// the ads layer's internals directly.
library;

import 'package:ami_trade/widgets/ads/anchored_ad_banner.dart';
import 'package:flutter/widgets.dart';

class ShellBannerSlot extends StatelessWidget {
  const ShellBannerSlot({super.key});

  @override
  Widget build(BuildContext context) => const AnchoredAdBanner();
}
