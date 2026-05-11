import 'package:ami_trade/screens/dev_preview_screen.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AmiTradeApp extends ConsumerWidget {
  const AmiTradeApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'AMI Trade',
      debugShowCheckedModeBanner: false,
      theme: amiTheme(),
      // Alpha bootstrap: start on the design-system preview screen until
      // the real router is wired in (W2).
      home: const DevPreviewScreen(),
    );
  }
}
