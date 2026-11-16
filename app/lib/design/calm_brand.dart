// The ChangeLens logo (Logo D, "Aperture"; owner decision 2026-11-16, docs/brand/): an ink arc open to the
// right around a lime dot, drawn from the same geometry as docs/brand/changelens-logo-*.svg, so the app
// needs no SVG package. The lockup adds the Roboto Bold wordmark, as the logo files do.
import 'package:flutter/material.dart';

import 'calm_theme.dart';

/// The mark alone: arc and dot in a 100-unit box, as in the SVG (viewBox crop 13.5…86.5).
class CalmLogoMark extends StatelessWidget {
  const CalmLogoMark({super.key, this.size = 40});

  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(child: CustomPaint(
    size: Size.square(size),
    painter: _MarkPainter(Theme.of(context).colorScheme.onSurface, CalmColors.of(context).marker)));
}

class _MarkPainter extends CustomPainter {
  _MarkPainter(this.ink, this.dot);

  final Color ink, dot;

  // The SVG draws in a 100-unit box and shows 13.5…86.5 of it (73 units).
  static const _origin = 13.5, _span = 73.0;

  @override
  void paint(Canvas canvas, Size size) {
    final k = size.width / _span;
    canvas.scale(k);
    canvas.translate(-_origin, -_origin);
    // M71.2 28.8 A30 30 0 1 0 71.2 71.2: the long way round, from upper right to lower right.
    final arc = Path()
      ..moveTo(71.2, 28.8)
      ..arcToPoint(const Offset(71.2, 71.2), radius: const Radius.circular(30), largeArc: true, clockwise: false);
    canvas.drawPath(arc, Paint()
      ..color = ink
      ..style = PaintingStyle.stroke
      ..strokeWidth = 13
      ..strokeCap = StrokeCap.round);
    canvas.drawCircle(const Offset(52, 50), 12, Paint()..color = dot);
  }

  @override
  bool shouldRepaint(_MarkPainter old) => old.ink != ink || old.dot != dot;
}

/// Mark plus wordmark, read once as "ChangeLens". A logo is an image: the wordmark keeps its size at
/// any text scale, and the lockup shrinks to fit a narrow screen instead of overflowing.
class CalmLogoLockup extends StatelessWidget {
  const CalmLogoLockup({super.key, this.height = 40});

  final double height;

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'ChangeLens',
    image: true,
    child: ExcludeSemantics(child: FittedBox(fit: BoxFit.scaleDown, alignment: AlignmentDirectional.centerStart,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        CalmLogoMark(size: height),
        SizedBox(width: height * 0.3),
        Text('ChangeLens', textScaler: TextScaler.noScaling, maxLines: 1, softWrap: false,
          style: TextStyle(fontFamily: 'Roboto', fontWeight: FontWeight.w700,
            fontSize: height * 0.6, height: 1, letterSpacing: -0.2,
            color: Theme.of(context).colorScheme.onSurface)),
      ]))),
  );
}
