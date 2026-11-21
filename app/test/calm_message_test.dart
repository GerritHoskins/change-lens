// Message banners (DESIGN.md, "Messages"): error, warning and info each have their own colour and
// their own icon, in both themes, and the text stays ink. Widget tests; not device evidence.
import 'dart:io';
import 'dart:math';
import 'dart:ui' as ui;

import 'package:changelens/design/calm_icons.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/design/calm_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

const captureDirectory = String.fromEnvironment('CALM_CAPTURE_DIR');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final roboto = FontLoader('Roboto');
    for (final weight in ['Regular', 'SemiBold', 'Bold']) {
      roboto.addFont(rootBundle.load('assets/fonts/Roboto-$weight.ttf'));
    }
    await roboto.load();
    await (FontLoader('packages/lucide_icons_flutter/Lucide500')..addFont(rootBundle.load(
      'packages/lucide_icons_flutter/assets/build_font/LucideVariable-w500.ttf'))).load();
  });

  for (final brightness in Brightness.values) {
    testWidgets('Each kind has its own border colour and icon ($brightness)', (tester) async {
      final theme = calmTheme(brightness);
      await tester.pumpWidget(MaterialApp(theme: theme, home: Scaffold(body: Column(children: [
        for (final kind in CalmMessageKind.values) CalmWarning(key: Key(kind.name), kind: kind, text: kind.name),
      ]))));
      final colors = theme.extension<CalmColors>()!;
      final expected = {
        CalmMessageKind.error: (theme.colorScheme.error, colors.errorSurface, CalmIcons.error),
        CalmMessageKind.warning: (colors.caution, colors.cautionSurface, CalmIcons.warning),
        CalmMessageKind.info: (colors.link, colors.infoSurface, CalmIcons.info),
      };
      for (final MapEntry(key: kind, value: (accent, surface, icon)) in expected.entries) {
        final banner = find.byKey(Key(kind.name));
        final box = tester.widget<DecoratedBox>(find.descendant(of: banner, matching: find.byType(DecoratedBox)).first);
        final decoration = box.decoration as BoxDecoration;
        expect(decoration.color, surface, reason: kind.name);
        expect((decoration.border! as Border).top.color, accent, reason: kind.name);
        final drawn = tester.widget<Icon>(find.descendant(of: banner, matching: find.byType(Icon)));
        expect((drawn.icon, drawn.color), (icon, accent), reason: kind.name);
        final text = tester.widget<Text>(find.descendant(of: banner, matching: find.text(kind.name)));
        expect(text.style?.color, theme.colorScheme.onSurface, reason: kind.name);
      }
      // No two kinds share an accent or an icon.
      expect({for (final e in expected.values) e.$1}.length, 3);
      expect({for (final e in expected.values) e.$3}.length, 3);
    });
  }

  // Every kind's snackbar in both themes: fill, label and icon colours, and that the label reads on the
  // fill (4.5:1 or more). Set CALM_CAPTURE_DIR to write a PNG of each.
  for (final brightness in Brightness.values) {
    for (final kind in CalmMessageKind.values) {
      testWidgets('The ${kind.name} snackbar reads on its fill ($brightness)', (tester) async {
        tester.view.physicalSize = const Size(390, 420);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final theme = calmTheme(brightness);
        final colors = theme.extension<CalmColors>()!;
        final boundary = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: boundary, child: MaterialApp(theme: theme,
          debugShowCheckedModeBanner: false,
          home: Scaffold(body: Builder(builder: (context) => ListView(padding: const EdgeInsets.all(16), children: [
            for (final k in CalmMessageKind.values) Padding(padding: const EdgeInsets.only(bottom: 12),
              child: CalmWarning(kind: k, text: 'A ${k.name} message, as the banner draws it.')),
            TextButton(onPressed: () => calmSnack(context, 'Saving failed. Try again.', kind: kind),
              child: const Text('go')),
          ]))))));
        await tester.tap(find.text('go'));
        await tester.pumpAndSettle();
        final bar = find.byType(SnackBar);
        final filled = kind != CalmMessageKind.info;
        final fill = tester.widget<SnackBar>(bar).backgroundColor ?? theme.snackBarTheme.backgroundColor!;
        final accent = switch (kind) {
          CalmMessageKind.error => colors.error,
          CalmMessageKind.warning => colors.caution,
          CalmMessageKind.info => theme.snackBarTheme.backgroundColor!,
        };
        expect(fill, accent);
        final icon = tester.widget<Icon>(find.descendant(of: bar, matching: find.byType(Icon)));
        final label = tester.widget<Text>(find.descendant(of: bar, matching: find.text('Saving failed. Try again.')));
        expect(icon.icon, calmMessageIcon(kind));
        expect(icon.color, label.style!.color);
        if (filled) expect(label.style!.color, brightness == Brightness.dark ? CalmColors.ink : Colors.white);
        expect(contrast(label.style!.color!, fill), greaterThanOrEqualTo(4.5), reason: 'label on fill');

        if (captureDirectory.isNotEmpty) {
          await tester.runAsync(() async {
            final image = await (boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary).toImage(pixelRatio: 2);
            final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
            await Directory(captureDirectory).create(recursive: true);
            await File('$captureDirectory/message-${kind.name}-${brightness.name}.png').writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }
      });
    }
  }

  testWidgets('A long German banner with an action lays out at 320 px and 2x text', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(MaterialApp(theme: calmTheme(Brightness.light), home: Scaffold(body: ListView(
      padding: const EdgeInsets.all(20), children: [
        for (final kind in CalmMessageKind.values) CalmWarning(kind: kind,
          text: 'Die Hervorhebung konnte nicht platziert werden. Vergleichen Sie den Text mit dem Originaldokument.',
          child: TextButton(onPressed: () {}, child: const Text('Erneut versuchen'))),
      ]))));
    expect(tester.takeException(), isNull);
    expect(find.text('Erneut versuchen'), findsWidgets);
  });
}

IconData calmMessageIcon(CalmMessageKind kind) => switch (kind) {
  CalmMessageKind.error => CalmIcons.error,
  CalmMessageKind.warning => CalmIcons.warning,
  CalmMessageKind.info => CalmIcons.info,
};

/// WCAG contrast ratio of two opaque colours.
double contrast(Color a, Color b) {
  final la = a.computeLuminance(), lb = b.computeLuminance();
  return (max(la, lb) + 0.05) / (min(la, lb) + 0.05);
}
