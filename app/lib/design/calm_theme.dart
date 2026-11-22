import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'calm_icons.dart';

/// Radii and sizes from the Calm Bold design-system tokens (radius-*, button-main, target-min).
abstract final class CalmRadius {
  static const sm = 6.0, md = 18.0, lg = 24.0, xl = 28.0, sheet = 36.0;
}

abstract final class CalmSize {
  static const buttonMain = 60.0, targetMin = 48.0, dash = 2.0;
}

/// Semantic colours from the Calm Bold tokens. No meaning relies on colour alone.
@immutable
class CalmColors extends ThemeExtension<CalmColors> {
  const CalmColors({required this.dark, required this.muted, required this.line,
    required this.soft, required this.marker, required this.onMarker,
    required this.warning, required this.warningSurface, required this.quote,
    required this.review, required this.link});

  final bool dark;
  /// [soft] is the `disabled` token; [warning]/[warningSurface] draw the fallback banner
  /// (ink text on surface, 2px solid ink border); [review] is only for "needs a second look".
  final Color muted, line, soft, marker, onMarker, warning, warningSurface, quote, review, link;

  static const ink = Color(0xff111114);
  /// White in both themes: the provider pill (Apple's allowed style) and a PDF page preview.
  static const paper = Color(0xffffffff);
  static const markerFill = Color(0x8cdfff4f);
  /// The dimmed screen behind a sheet: ink at 40% on light. On dark, ink over a near-black ground
  /// changes nothing, so the scrim is black at 60%. Sheets take it from `bottomSheetTheme`.
  static const scrim = Color(0x66111114), scrimDark = Color(0x99000000);

  static CalmColors of(BuildContext context) =>
      Theme.of(context).extension<CalmColors>() ?? light;

  /// Message colours ([CalmMessage]): each kind has an accent (border and icon, 3:1+ on its surface
  /// and on ground) and a tinted surface that ink text reads on at 12:1+. `error` is the scheme's
  /// error colour. Amber is not `review` orange and never dashed; blue is `link`.
  static const errorLight = Color(0xffc81e1e), errorDark = Color(0xffff8a8a);
  Color get error => dark ? errorDark : errorLight;
  Color get errorSurface => dark ? const Color(0xff3a1d1d) : const Color(0xfffdecec);
  Color get caution => dark ? const Color(0xffffc857) : const Color(0xff8a5300);
  Color get cautionSurface => dark ? const Color(0xff33290f) : const Color(0xfffff3d6);
  Color get infoSurface => dark ? const Color(0xff25234a) : const Color(0xffecebff);

  static const light = CalmColors(dark: false, muted: Color(0xff5e5e66),
    line: Color(0xffdcdcd6), soft: Color(0xffe4e4de), marker: Color(0xffdfff4f),
    onMarker: ink, warning: ink, warningSurface: Colors.white, quote: Colors.white,
    review: Color(0xfff05a1e), link: Color(0xff4b3bff));
  static const night = CalmColors(dark: true, muted: Color(0xffa6a6ae),
    line: Color(0xff34343a), soft: Color(0xff2a2a2f), marker: Color(0xffdfff4f),
    onMarker: ink, warning: Color(0xfff3f3ef), warningSurface: Color(0xff1e1e22),
    quote: Color(0xff1e1e22), review: Color(0xfff05a1e), link: Color(0xffa99fff));

  /// Topic blocks keep the same pastel in both themes, always with [topicForeground] text.
  Color topicSurface(String topic) => switch (topic) {
    'deadlines' => const Color(0xffcdbeff),
    'deliverables' => const Color(0xffa8f0c6),
    'responsibilities' => const Color(0xffa9dcff),
    'approval_wording' => const Color(0xffffb3d1),
    'budget' => const Color(0xffffe45c),
    _ => const Color(0xffe4e4de),
  };

  Color topicForeground(String topic) => ink;

  @override
  CalmColors copyWith({bool? dark, Color? muted, Color? line, Color? soft,
    Color? marker, Color? onMarker, Color? warning, Color? warningSurface, Color? quote,
    Color? review, Color? link}) =>
    CalmColors(dark: dark ?? this.dark, muted: muted ?? this.muted, line: line ?? this.line,
      soft: soft ?? this.soft, marker: marker ?? this.marker, onMarker: onMarker ?? this.onMarker,
      warning: warning ?? this.warning, warningSurface: warningSurface ?? this.warningSurface,
      quote: quote ?? this.quote, review: review ?? this.review, link: link ?? this.link);

  @override
  CalmColors lerp(covariant CalmColors? other, double t) {
    if (other == null) return this;
    Color mix(Color a, Color b) => Color.lerp(a, b, t)!;
    return CalmColors(dark: t < .5 ? dark : other.dark,
      muted: mix(muted, other.muted), line: mix(line, other.line), soft: mix(soft, other.soft),
      marker: mix(marker, other.marker), onMarker: mix(onMarker, other.onMarker),
      warning: mix(warning, other.warning), warningSurface: mix(warningSurface, other.warningSurface),
      quote: mix(quote, other.quote), review: mix(review, other.review), link: mix(link, other.link));
  }
}

/// The Calm Bold text field outline: a full rounded rectangle drawn inside the field. It extends the
/// underline border so Material lays the label out inside the block (filled style) instead of
/// notching it into an outline.
class CalmFieldBorder extends UnderlineInputBorder {
  const CalmFieldBorder({super.borderSide = const BorderSide(),
    super.borderRadius = const BorderRadius.all(Radius.circular(CalmRadius.md))});

  @override
  CalmFieldBorder copyWith({BorderSide? borderSide, BorderRadius? borderRadius}) =>
      CalmFieldBorder(borderSide: borderSide ?? this.borderSide, borderRadius: borderRadius ?? this.borderRadius);

  @override
  EdgeInsetsGeometry get dimensions => EdgeInsets.all(borderSide.width);

  @override
  CalmFieldBorder scale(double t) => CalmFieldBorder(borderSide: borderSide.scale(t), borderRadius: borderRadius * t);

  @override
  ShapeBorder? lerpFrom(ShapeBorder? a, double t) => a is CalmFieldBorder
      ? CalmFieldBorder(borderSide: BorderSide.lerp(a.borderSide, borderSide, t),
          borderRadius: BorderRadius.lerp(a.borderRadius, borderRadius, t)!)
      : super.lerpFrom(a, t);

  @override
  ShapeBorder? lerpTo(ShapeBorder? b, double t) => b is CalmFieldBorder
      ? CalmFieldBorder(borderSide: BorderSide.lerp(borderSide, b.borderSide, t),
          borderRadius: BorderRadius.lerp(borderRadius, b.borderRadius, t)!)
      : super.lerpTo(b, t);

  @override
  void paint(Canvas canvas, Rect rect, {double? gapStart, double gapExtent = 0.0,
      double gapPercentage = 0.0, TextDirection? textDirection}) {
    if (borderSide.style == BorderStyle.none || borderSide.width == 0) return;
    canvas.drawRRect(borderRadius.resolve(textDirection).toRRect(rect).deflate(borderSide.width / 2),
      borderSide.toPaint());
  }
}

ThemeData calmTheme(Brightness brightness, {TargetPlatform? platform}) {
  final dark = brightness == Brightness.dark;
  final colors = dark ? CalmColors.night : CalmColors.light;
  final ink = dark ? const Color(0xfff3f3ef) : CalmColors.ink;
  final background = dark ? const Color(0xff121214) : const Color(0xfff5f5f2);
  final surface = dark ? const Color(0xff1e1e22) : Colors.white;
  final primary = ink; // `action`: the one main button, selected chip, progress fill.
  final onPrimary = dark ? CalmColors.ink : Colors.white;
  final disabledText = dark ? const Color(0xff6e6e76) : const Color(0xff8a8a92);
  // `control-border`: field outlines at 3:1+ on surface and ground (WCAG 1.4.11); `line` stays decorative.
  final controlBorder = dark ? const Color(0xff76767e) : const Color(0xff86868e);
  final target = platform ?? defaultTargetPlatform;
  final bodySize = target == TargetPlatform.iOS ? 17.0 : 16.0;
  final scheme = ColorScheme.fromSeed(seedColor: primary, brightness: brightness).copyWith(
    primary: primary, onPrimary: onPrimary, primaryContainer: colors.soft, onPrimaryContainer: ink,
    secondary: primary, onSecondary: onPrimary, secondaryContainer: colors.soft, onSecondaryContainer: ink,
    tertiary: colors.link, onTertiary: onPrimary,
    tertiaryContainer: colors.warningSurface, onTertiaryContainer: colors.warning,
    surface: background, onSurface: ink, onSurfaceVariant: colors.muted,
    surfaceContainerLowest: background, surfaceContainerLow: surface,
    surfaceContainer: surface, surfaceContainerHigh: colors.soft, surfaceContainerHighest: colors.soft,
    // `outline` bounds controls (an unselected switch thumb and track), so it is `control-border`;
    // `outlineVariant` stays the decorative `line`.
    outline: controlBorder, outlineVariant: colors.line,
    // A true red, so it can't be read as `review` orange.
    error: colors.error,
  );
  // Roboto is bundled at 400/600/700 (owner choice over Inter Tight), so the tokens'
  // 800 and 500 weights map to 700 and 400.
  TextStyle role(double size, FontWeight weight, double lineHeight, {Color? color, double? tracking}) =>
      TextStyle(fontFamily: 'Roboto', fontSize: size, fontWeight: weight, height: lineHeight / size,
        // 0, not null: a null would inherit Material's own tracking for the role (body 0.5, labels 0.1 to 0.5).
        color: color ?? ink, letterSpacing: tracking ?? 0);
  final text = TextTheme(
    displayLarge: role(54, FontWeight.w700, 54, tracking: -2),   // display
    displayMedium: role(64, FontWeight.w700, 56, tracking: -2),  // figure
    displaySmall: role(32, FontWeight.w700, 35, tracking: -1.4),  // compact headline (onboarding steps 2 to 6)
    headlineLarge: role(38, FontWeight.w700, 40, tracking: -1.4), // headline
    headlineMedium: role(28, FontWeight.w700, 32, tracking: -.8), // value
    headlineSmall: role(24, FontWeight.w700, 29, tracking: -.4),
    titleLarge: role(20, FontWeight.w700, 26),
    titleMedium: role(17, FontWeight.w600, 22),                   // title
    titleSmall: role(16, FontWeight.w600, 22),
    bodyLarge: role(16, FontWeight.w400, 23),                     // body (quoted passages)
    bodyMedium: role(bodySize, FontWeight.w400, bodySize * 1.45),
    bodySmall: role(14, FontWeight.w400, 20, color: colors.muted), // meta
    labelLarge: role(17, FontWeight.w600, 22),                    // button labels
    labelMedium: role(14, FontWeight.w600, 20),
    labelSmall: role(13, FontWeight.w600, 16, tracking: .4),      // eyebrow
  );
  const pill = StadiumBorder();
  final focusRing = BorderSide(color: colors.link, width: 2);
  CalmFieldBorder field(BorderSide side) => CalmFieldBorder(borderSide: side);
  final isIOS = target == TargetPlatform.iOS || target == TargetPlatform.macOS;
  return ThemeData(
    useMaterial3: true, platform: target, brightness: brightness, colorScheme: scheme,
    fontFamily: 'Roboto', textTheme: text, scaffoldBackgroundColor: background,
    extensions: [colors], materialTapTargetSize: MaterialTapTargetSize.padded,
    focusColor: colors.link.withValues(alpha: .24),
    appBarTheme: AppBarTheme(backgroundColor: background, foregroundColor: ink,
      elevation: 0, scrolledUnderElevation: 0, centerTitle: false, titleTextStyle: text.titleMedium),
    cardTheme: CardThemeData(color: surface, elevation: 0, margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.lg))),
    filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
      minimumSize: const Size(CalmSize.targetMin, CalmSize.buttonMain),
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      disabledBackgroundColor: colors.soft, disabledForegroundColor: disabledText,
      textStyle: text.labelLarge, shape: pill)),
    outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(
      minimumSize: const Size(CalmSize.targetMin, CalmSize.targetMin),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      backgroundColor: surface, side: BorderSide.none, textStyle: text.labelLarge, shape: pill)),
    // Secondary actions are plain `ink` text buttons (cb-btn-text), never filled or outlined pills.
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: ink, iconColor: ink,
      minimumSize: const Size(CalmSize.targetMin, CalmSize.targetMin), iconSize: 20,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      textStyle: text.labelMedium)),
    // Round icon buttons are 48px `surface` discs with a 20px stroke icon.
    iconButtonTheme: IconButtonThemeData(style: IconButton.styleFrom(
      minimumSize: const Size(CalmSize.targetMin, CalmSize.targetMin), iconSize: 20,
      backgroundColor: surface, foregroundColor: ink, shape: const CircleBorder())),
    actionIconTheme: ActionIconThemeData(
      backButtonIconBuilder: (_) => Icon(isIOS ? CalmIcons.backIOS : CalmIcons.back)),
    iconTheme: IconThemeData(color: ink, size: 22),
    // Menus are surfaces: no shadow, soft corners, a hairline edge so they read above the ground.
    popupMenuTheme: PopupMenuThemeData(color: surface, surfaceTintColor: Colors.transparent,
      elevation: 0, shadowColor: Colors.transparent, labelTextStyle: WidgetStatePropertyAll(text.labelLarge),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.md),
        side: BorderSide(color: controlBorder))),
    // A switch that is on is `action`, never the platform's green; off, it is `control-border` on `disabled`.
    switchTheme: SwitchThemeData(
      trackColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? primary : colors.soft),
      thumbColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? onPrimary : controlBorder),
      trackOutlineColor: WidgetStateProperty.resolveWith((states) =>
        states.contains(WidgetState.selected) ? Colors.transparent : controlBorder)),
    radioTheme: RadioThemeData(fillColor: WidgetStateProperty.resolveWith((states) =>
      states.contains(WidgetState.disabled) ? disabledText
        : states.contains(WidgetState.selected) ? ink : controlBorder)),
    chipTheme: ChipThemeData(backgroundColor: surface, selectedColor: primary,
      secondarySelectedColor: primary, labelStyle: text.labelMedium,
      secondaryLabelStyle: text.labelMedium?.copyWith(color: onPrimary),
      side: BorderSide.none, padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 9),
      shape: pill, showCheckmark: false),
    // Text field (cb-field): `surface` fill, label inside the block (eyebrow once filled), 1px
    // `control-border`, replaced by a 2px `link` ring on focus. Placeholders are `muted`.
    inputDecorationTheme: InputDecorationTheme(filled: true, fillColor: surface,
      labelStyle: text.bodyLarge?.copyWith(color: colors.muted),
      floatingLabelStyle: text.labelSmall?.copyWith(color: colors.muted),
      hintStyle: text.bodyLarge?.copyWith(color: colors.muted),
      errorMaxLines: 6, // a field message wraps at large text instead of ending in an ellipsis
      contentPadding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      border: field(BorderSide(color: controlBorder)),
      enabledBorder: field(BorderSide(color: controlBorder)),
      disabledBorder: field(BorderSide(color: colors.line)),
      focusedBorder: field(focusRing),
      errorBorder: field(BorderSide(color: scheme.error)),
      focusedErrorBorder: field(BorderSide(color: scheme.error, width: 2))),
    dividerTheme: DividerThemeData(color: colors.line, thickness: 1, space: 32),
    listTileTheme: ListTileThemeData(contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      titleTextStyle: text.titleMedium, subtitleTextStyle: text.bodySmall, minVerticalPadding: 12),
    dialogTheme: DialogThemeData(backgroundColor: surface, titleTextStyle: text.titleLarge,
      contentTextStyle: text.bodyMedium,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.xl))),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: surface, showDragHandle: true,
      surfaceTintColor: Colors.transparent, elevation: 0, modalElevation: 0,
      dragHandleColor: colors.line, dragHandleSize: const Size(40, 5),
      modalBarrierColor: dark ? CalmColors.scrimDark : CalmColors.scrim,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(
        top: Radius.circular(CalmRadius.sheet)))),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, backgroundColor: ink,
      contentTextStyle: text.bodyMedium?.copyWith(color: background)),
    textSelectionTheme: TextSelectionThemeData(cursorColor: colors.link,
      // Marker behind ink text on light; on dark, selected text stays light, so the selection is `link`.
      selectionColor: dark ? colors.link.withValues(alpha: .4) : colors.marker.withValues(alpha: .55),
      selectionHandleColor: colors.link),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: primary, linearTrackColor: colors.line),
  );
}
