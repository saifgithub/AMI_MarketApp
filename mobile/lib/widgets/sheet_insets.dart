/// Bottom clearance a modal bottom sheet must add so its last control clears
/// both the on-screen keyboard and the system navigation bar.
///
/// DEF075 — sheets that padded by `viewInsets.bottom` alone (keyboard height)
/// drew their primary button *under* the Android 3-button nav bar whenever the
/// keyboard was closed (`viewInsets.bottom == 0`), leaving "Send report" /
/// "GO TO LESSONS" unclickable. `viewPadding.bottom` is the nav-bar inset and
/// is unaffected by the keyboard; the keyboard, when raised, already covers the
/// nav bar — so the larger of the two is the correct clearance in every state.
library;

import 'dart:math' as math;

import 'package:flutter/widgets.dart';

/// The safe bottom inset for a modal bottom sheet's content padding.
double sheetBottomInset(MediaQueryData mq) =>
    math.max(mq.viewInsets.bottom, mq.viewPadding.bottom);
