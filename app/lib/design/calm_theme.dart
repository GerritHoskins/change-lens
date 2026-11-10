import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Semantic colours for the approved Calm Bold direction. No meaning relies on colour alone.
@immutable
class CalmColors extends ThemeExtension<CalmColors> {
  const CalmColors({required this.dark, required this.muted, required this.line,
    required this.soft, required this.marker, required this.onMarker,
    required this.warning, required this.warningSurface, required this.quote});

  final bool dark;
  final Color muted, line, soft, marker, onMarker, warning, warningSurface, quote;

  static CalmColors of(BuildContext context) =>
      Theme.of(context).extension<CalmColors>() ?? light;

  static const light = CalmColors(dark: false, muted: Color(0xff60615b),
    line: Color(0xffd2d4ca), soft: Color(0xffe6e9dc), marker: Color(0xffe4f78d),
    onMarker: Color(0xff20211e), warning: Color(0xff794300),
    warningSurface: Color(0xfffff1d9), quote: Colors.white);
  static const night = CalmColors(dark: true, muted: Color(0xffb8bdb2),
    line: Color(0xff4d5247), soft: Color(0xff303728), marker: Color(0xff4a5825),
    onMarker: Color(0xfff3f4ec), warning: Color(0xffffd49b),
    warningSurface: Color(0xff3f301b), quote: Color(0xff242821));

  Color topicSurface(String topic) => switch (topic) {
    'budget' => dark ? const Color(0xff454024) : const Color(0xfff4edb8),
    'deadlines' => dark ? const Color(0xff372c49) : const Color(0xffece4fb),
    'deliverables' => dark ? const Color(0xff26463a) : const Color(0xffd9f2e4),
    _ => quote,
  };

  Color topicForeground(String topic) => switch (topic) {
    'budget' => dark ? const Color(0xfff6edb7) : const Color(0xff4a4219),
    'deadlines' => dark ? const Color(0xffe8dcff) : const Color(0xff39275c),
    'deliverables' => dark ? const Color(0xffd3efde) : const Color(0xff204932),
    _ => dark ? const Color(0xfff3f4ec) : const Color(0xff20211e),
  };

  @override
  CalmColors copyWith({bool? dark, Color? muted, Color? line, Color? soft,
    Color? marker, Color? onMarker, Color? warning, Color? warningSurface, Color? quote}) =>
    CalmColors(dark: dark ?? this.dark, muted: muted ?? this.muted, line: line ?? this.line,
      soft: soft ?? this.soft, marker: marker ?? this.marker, onMarker: onMarker ?? this.onMarker,
      warning: warning ?? this.warning, warningSurface: warningSurface ?? this.warningSurface,
      quote: quote ?? this.quote);

  @override
  CalmColors lerp(covariant CalmColors? other, double t) {
    if (other == null) return this;
    return CalmColors(dark: t < .5 ? dark : other.dark,
      muted: Color.lerp(muted, other.muted, t)!, line: Color.lerp(line, other.line, t)!,
      soft: Color.lerp(soft, other.soft, t)!, marker: Color.lerp(marker, other.marker, t)!,
      onMarker: Color.lerp(onMarker, other.onMarker, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningSurface: Color.lerp(warningSurface, other.warningSurface, t)!,
      quote: Color.lerp(quote, other.quote, t)!);
  }
}

ThemeData calmTheme(Brightness brightness, {TargetPlatform? platform}) {
  final dark = brightness == Brightness.dark;
  final colors = dark ? CalmColors.night : CalmColors.light;
  final ink = dark ? const Color(0xfff3f4ec) : const Color(0xff20211e);
  final background = dark ? const Color(0xff171916) : const Color(0xfff4f4ef);
  final surface = dark ? const Color(0xff232621) : Colors.white;
  final primary = dark ? const Color(0xffe5f78e) : const Color(0xff25261f);
  final onPrimary = dark ? const Color(0xff20251a) : Colors.white;
  final target = platform ?? defaultTargetPlatform;
  final bodySize = target == TargetPlatform.iOS ? 17.0 : 16.0;
  final scheme = ColorScheme.fromSeed(seedColor: primary, brightness: brightness).copyWith(
    primary: primary, onPrimary: onPrimary, primaryContainer: colors.soft, onPrimaryContainer: ink,
    secondary: primary, onSecondary: onPrimary, secondaryContainer: colors.soft, onSecondaryContainer: ink,
    tertiary: colors.warning, onTertiary: colors.warningSurface,
    tertiaryContainer: colors.warningSurface, onTertiaryContainer: colors.warning,
    surface: background, onSurface: ink, onSurfaceVariant: colors.muted,
    surfaceContainerLowest: background, surfaceContainerLow: surface,
    surfaceContainer: surface, surfaceContainerHigh: colors.soft, surfaceContainerHighest: colors.soft,
    outline: colors.line, outlineVariant: colors.line,
    error: dark ? const Color(0xffffb8ad) : const Color(0xffa12e2e),
  );
  TextStyle role(double size, FontWeight weight, double height, {Color? color, double? tracking}) =>
      TextStyle(fontFamily: 'Roboto', fontSize: size, fontWeight: weight, height: height,
        color: color ?? ink, letterSpacing: tracking);
  final text = TextTheme(
    displayLarge: role(32, FontWeight.w700, 1.16, tracking: -.64),
    displayMedium: role(30, FontWeight.w700, 1.16, tracking: -.6),
    displaySmall: role(28, FontWeight.w700, 1.2, tracking: -.56),
    headlineLarge: role(30, FontWeight.w700, 1.16, tracking: -.6),
    headlineMedium: role(28, FontWeight.w700, 1.2, tracking: -.56),
    headlineSmall: role(24, FontWeight.w700, 1.2, tracking: -.36),
    titleLarge: role(20, FontWeight.w700, 1.3),
    titleMedium: role(17, FontWeight.w600, 1.4),
    titleSmall: role(16, FontWeight.w600, 1.4),
    bodyLarge: role(17, FontWeight.w400, dark ? 1.65 : 1.58, tracking: dark ? .085 : 0),
    bodyMedium: role(bodySize, FontWeight.w400, 1.5),
    bodySmall: role(14, FontWeight.w400, 1.5, color: colors.muted),
    labelLarge: role(16, FontWeight.w600, 1.4),
    labelMedium: role(14, FontWeight.w600, 1.5),
    labelSmall: role(14, FontWeight.w400, 1.5, color: colors.muted),
  );
  final rounded = RoundedRectangleBorder(borderRadius: BorderRadius.circular(14));
  return ThemeData(
    useMaterial3: true, platform: target, brightness: brightness, colorScheme: scheme,
    fontFamily: 'Roboto', textTheme: text, scaffoldBackgroundColor: background,
    extensions: [colors], materialTapTargetSize: MaterialTapTargetSize.padded,
    appBarTheme: AppBarTheme(backgroundColor: background, foregroundColor: ink,
      elevation: 0, scrolledUnderElevation: 0, centerTitle: false, titleTextStyle: text.titleMedium),
    cardTheme: CardThemeData(color: surface, elevation: 0, margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
    filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(
      minimumSize: const Size(48, 52), padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      textStyle: text.labelLarge, shape: rounded)),
    outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(
      minimumSize: const Size(48, 48), padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      side: BorderSide(color: colors.line), textStyle: text.labelLarge, shape: rounded)),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(
      minimumSize: const Size(48, 48), padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      textStyle: text.labelMedium)),
    iconButtonTheme: IconButtonThemeData(style: IconButton.styleFrom(minimumSize: const Size(48, 48))),
    chipTheme: ChipThemeData(backgroundColor: surface, selectedColor: primary,
      secondarySelectedColor: primary, labelStyle: text.labelMedium,
      secondaryLabelStyle: text.labelMedium?.copyWith(color: onPrimary),
      side: BorderSide(color: colors.line), padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 9),
      shape: const StadiumBorder(), showCheckmark: false),
    inputDecorationTheme: InputDecorationTheme(filled: true, fillColor: surface,
      labelStyle: text.bodySmall, hintStyle: text.bodySmall,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: colors.line)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: colors.line)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: primary, width: 2))),
    dividerTheme: DividerThemeData(color: colors.line, thickness: 1, space: 32),
    listTileTheme: ListTileThemeData(contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 6),
      titleTextStyle: text.titleMedium, subtitleTextStyle: text.bodySmall, minVerticalPadding: 12),
    dialogTheme: DialogThemeData(backgroundColor: surface, titleTextStyle: text.titleLarge,
      contentTextStyle: text.bodyMedium, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20))),
    bottomSheetTheme: BottomSheetThemeData(backgroundColor: surface, showDragHandle: true),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, backgroundColor: ink,
      contentTextStyle: text.bodyMedium?.copyWith(color: background)),
    textSelectionTheme: TextSelectionThemeData(cursorColor: primary,
      selectionColor: colors.marker, selectionHandleColor: primary),
    progressIndicatorTheme: ProgressIndicatorThemeData(color: primary, linearTrackColor: colors.soft),
  );
}
