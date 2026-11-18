/// WP-38 (CR267) / CR239 - the small copyable "Ref: abc12345" line under an
/// error, and the wrapper that pulls it out of a `friendlyError` message.
///
/// Why this exists: the backend puts a trace id on every error response and
/// every log line of that request, so a screenshot of an error that carries
/// the reference lets support go from "what the user saw" to "the exact log
/// lines" with one paste. `friendlyError()` already appends the reference to
/// its copy as a trailing sentence (so all ~28 call sites that print it get it
/// for free); the shared error surfaces use these two widgets to render it as
/// its own small, tap-to-copy line instead of running text.
///
/// - [TraceRefLine] shows a reference. Given an explicit `id` it shows that;
///   `TraceRefLine.recent()` shows the id of the app's most recent failed call
///   (for the panels whose copy is a fixed localised string that never saw the
///   exception) - and shows NOTHING when there is none, or when the latest
///   failure never reached the server, rather than a stale unrelated id.
/// - [AmiErrorMessage] renders an error message string and, if it ends in a
///   trace reference, splits that into a [TraceRefLine] under the headline.
library;

import 'package:ami_trade/generated/l10n/app_localizations.dart';
import 'package:ami_trade/services/api/trace_ids.dart';
import 'package:ami_trade/theme/ami_theme.dart';
import 'package:ami_trade/widgets/hex/hex_toast.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class TraceRefLine extends StatelessWidget {
  const TraceRefLine(this.id, {super.key, this.store}) : _recent = false;

  /// The id of the most recent failed request, or nothing.
  const TraceRefLine.recent({super.key, this.store})
      : id = null,
        _recent = true;

  /// A short prefix or a full id. Ignored by [TraceRefLine.recent].
  final String? id;
  final bool _recent;

  /// Test seam; defaults to [TraceIdStore.instance].
  final TraceIdStore? store;

  @override
  Widget build(BuildContext context) {
    final s = store ?? TraceIdStore.instance;
    final shown = _recent ? s.recentId() : id;
    if (shown == null || shown.isEmpty) return const SizedBox.shrink();
    final l = AppLocalizations.of(context);
    final label = l.traceRefLabel(shortTraceId(shown));
    final toCopy = s.resolve(shown) ?? shown;
    return Semantics(
      button: true,
      label: label,
      hint: l.traceRefCopyTooltip,
      excludeSemantics: true,
      child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: () async {
          await Clipboard.setData(ClipboardData(text: toCopy));
          if (!context.mounted) return;
          HexToast.show(
            context,
            l.traceRefCopied,
            icon: Icons.check_circle_outline,
            duration: const Duration(seconds: 2),
          );
        },
        child: Padding(
          // 44pt-high tap target around a caption-sized line.
          padding: const EdgeInsets.symmetric(
              horizontal: AmiSpacing.s, vertical: AmiSpacing.s),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: AmiTypography.caption.copyWith(
                  color: AmiColors.slate500,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(width: AmiSpacing.xs),
              const Icon(Icons.copy, size: 12, color: AmiColors.slate500),
            ],
          ),
        ),
      ),
    );
  }
}

/// An error message with its trailing trace reference rendered as a
/// [TraceRefLine] rather than running text. A message without one is just a
/// [Text], so adopting this widget never changes a screen that has no ref.
class AmiErrorMessage extends StatelessWidget {
  const AmiErrorMessage(
    this.message, {
    super.key,
    this.style,
    this.textAlign,
    this.store,
  });

  final String message;
  final TextStyle? style;
  final TextAlign? textAlign;
  final TraceIdStore? store;

  @override
  Widget build(BuildContext context) {
    final parts = splitTraceRef(message);
    final text = Text(
      parts.message,
      style: style ?? AmiTypography.body,
      textAlign: textAlign,
    );
    final ref = parts.ref;
    if (ref == null) return text;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: textAlign == TextAlign.center
          ? CrossAxisAlignment.center
          : CrossAxisAlignment.start,
      children: [text, TraceRefLine(ref, store: store)],
    );
  }
}
