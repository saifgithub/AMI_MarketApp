import 'package:ami_trade/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('App renders without throwing', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: AmiTradeApp()));
    await tester.pump();

    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
