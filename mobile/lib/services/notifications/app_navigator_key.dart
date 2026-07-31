/// Global navigator key (CR027) — lets non-widget code (a OneSignal push
/// tap callback, which has no BuildContext of its own) push a route.
/// Assigned to `MaterialApp.navigatorKey` in `app.dart`.
library;

import 'package:flutter/material.dart';

final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();
