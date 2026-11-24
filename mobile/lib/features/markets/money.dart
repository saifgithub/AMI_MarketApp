/// CR282 lane F1 - the one money formatter. Every amount that belongs to a
/// ticker or a book is printed through [formatMoney] with that ticker's
/// [AppMarket], so `$` is a US fact and not a constant.
///
/// The US output is byte-identical to the hand-built `'\$${fmt.format(x)}'`
/// strings it replaced (`NumberFormat('#,##0.00')` digits, symbol always a
/// prefix, no space) - the pattern is pinned to `¤#,##0.00` rather than the
/// locale's currency pattern so an Arabic or Malay UI does not move the symbol
/// to the other side of a number the surrounding layout already isolates.
/// Digits and separators still follow the active locale, exactly as before.
///
/// Negatives print `-$12.00`, never the `$-12.00` the old string-gluing
/// produced when a P&L went below zero.
///
/// An amount that DISPLAYS as zero is zero: `-0.0` and `-0.001` print
/// `$0.00` (or `+$0.00` when signed), never `-$0.00` / `+-$0.00` (DEF531).
library;

import 'package:ami_trade/features/markets/market.dart';
import 'package:intl/intl.dart';

final Map<String, NumberFormat> _cache = {};

NumberFormat _formatter(
    AppMarket market, int decimals, bool compact, bool grouped) {
  final key =
      '${Intl.getCurrentLocale()}|${market.name}|$decimals|$compact|$grouped';
  return _cache.putIfAbsent(key, () {
    if (compact) {
      return NumberFormat.compactCurrency(
        symbol: market.symbol,
        decimalDigits: decimals,
      )
        ..minimumFractionDigits = 0
        ..maximumFractionDigits = decimals
        ..significantDigitsInUse = false;
    }
    final frac = decimals == 0 ? '' : '.${List.filled(decimals, '0').join()}';
    final pattern = '¤${grouped ? '#,##0' : '0'}$frac';
    return NumberFormat.currency(
      customPattern: pattern,
      symbol: market.symbol,
      decimalDigits: decimals,
    );
  });
}

/// `$1,234.50` / `RM1,234.50`.
///
/// 1. [decimals] defaults to 2 (1 when [compact]).
/// 2. [compact] gives `$1.2K` / `RM3.4M`.
/// 3. [grouped] false drops the thousands separator (`$1234.50`) - for the
///    call sites that used `toStringAsFixed` and never grouped.
/// 4. [signed] prefixes `+` to zero and positive amounts (`+$12.00`); a
///    negative always carries its own `-` whether or not [signed] is set.
String formatMoney(
  num amount, {
  required AppMarket market,
  int? decimals,
  bool compact = false,
  bool signed = false,
  bool grouped = true,
}) {
  final fmt =
      _formatter(market, decimals ?? (compact ? 1 : 2), compact, grouped);
  // Judge zero by what the formatter would print, so rounding, compact
  // scaling and locale digits all agree with the text on screen. A negative
  // that rounds to zero would otherwise print `-$0.00` (and `+-$0.00` signed).
  final displaysZero = fmt.format(amount.abs()) == fmt.format(0);
  final body = displaysZero ? fmt.format(0) : fmt.format(amount);
  return signed && (displaysZero || amount >= 0) ? '+$body' : body;
}
