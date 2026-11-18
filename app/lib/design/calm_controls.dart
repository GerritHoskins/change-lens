// Calm Bold controls that Material does not draw on its own: the bottom sheet, radio rows and a
// select field that chooses in a sheet instead of a Material dropdown overlay.
import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import 'calm_icons.dart';
import 'calm_theme.dart';

/// Marks a subtree that sits on `surface` (a sheet), so fields and radio rows flip to `ground`.
class CalmOnSurface extends InheritedWidget {
  const CalmOnSurface({super.key, required super.child});

  static bool of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<CalmOnSurface>() != null;

  @override
  bool updateShouldNotify(CalmOnSurface oldWidget) => false;
}

/// Content placed on a `surface` block (a sheet, a slot card): fields and radio rows use `ground`.
class CalmSurfaceScope extends StatelessWidget {
  const CalmSurfaceScope({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Theme(
      data: theme.copyWith(inputDecorationTheme: theme.inputDecorationTheme.copyWith(
        fillColor: theme.scaffoldBackgroundColor)),
      child: CalmOnSurface(child: child));
  }
}

/// Opens a Calm Bold sheet: `surface`, `radius-sheet` top corners, a handle, the screen dimmed ink 40%.
Future<T?> showCalmSheet<T>(BuildContext context, {required WidgetBuilder builder}) =>
    showModalBottomSheet<T>(context: context, isScrollControlled: true, useSafeArea: true,
      barrierColor: CalmColors.ink.withValues(alpha: .4), builder: builder);

/// The validator of a field that must not be blank: [message] names what is missing. The sheet sits
/// in a [Form], and its main button calls `validate()`: every message shows at its field and the first
/// is announced. Re-checking while typing is set on each field, never on the Form, which would
/// announce the first message again on every rebuild.
FormFieldValidator<String> calmRequired(String message) =>
    (value) => value == null || value.trim().isEmpty ? message : null;

List<Widget> _spaced(List<Widget> children, double gap) => [
  for (var i = 0; i < children.length; i++) ...[if (i > 0) SizedBox(height: gap), children[i]],
];

/// A short decision: a title (a question when it asks one), an optional lead, the content, then one
/// main button with a text Cancel under it, pinned above the keyboard.
class CalmSheet extends StatelessWidget {
  const CalmSheet({super.key, required this.title, this.lead, required this.children,
    this.action, this.actionKey, this.onAction, this.dismissLabel});

  final String title;
  final String? lead;
  final List<Widget> children;
  /// The main button's label; omitted when choosing a row is the decision itself.
  final String? action;
  final Key? actionKey;
  final VoidCallback? onAction;
  /// The text button under the content: Cancel for decisions, Close for read-only sheets.
  final String? dismissLabel;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final colors = CalmColors.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: CalmSurfaceScope(child: Column(mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Flexible(child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Semantics(header: true, namesRoute: true, child: Text(title, style: theme.textTheme.headlineMedium)),
              if (lead != null) Padding(padding: const EdgeInsets.only(top: 8),
                child: Text(lead!, style: theme.textTheme.bodyMedium?.copyWith(color: colors.muted))),
              const SizedBox(height: 20),
              ..._spaced(children, 12),
            ]))),
          SafeArea(top: false, child: Padding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (action != null) FilledButton(key: actionKey, onPressed: onAction, child: Text(action!)),
              TextButton(onPressed: () => Navigator.pop(context), child: Text(dismissLabel ?? l.cancel)),
            ]))),
        ])),
    );
  }
}

/// A full-width radio choice inside a [RadioGroup]: `surface` on `ground` (`ground` inside a sheet).
/// The checked row gets a 2px `ink` border and 600 weight, so selection never relies on the dot alone.
class CalmRadioRow<T> extends StatelessWidget {
  const CalmRadioRow({super.key, required this.value, required this.title, this.subtitle, this.enabled = true});

  final T value;
  final String title;
  final String? subtitle;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = CalmColors.of(context);
    final group = RadioGroup.maybeOf<T>(context);
    final selected = group != null && group.groupValue == value;
    final fill = CalmOnSurface.of(context) ? theme.scaffoldBackgroundColor : theme.colorScheme.surfaceContainerLow;
    return MergeSemantics(child: Material(
      color: fill,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.md),
        side: BorderSide(color: selected ? theme.colorScheme.onSurface : Colors.transparent, width: CalmSize.dash)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: enabled && group != null ? () => group.onChanged(value) : null,
        child: ConstrainedBox(constraints: const BoxConstraints(minHeight: 56),
          child: Padding(padding: const EdgeInsets.fromLTRB(4, 8, 16, 8), child: Row(children: [
            Radio<T>(value: value, enabled: enabled),
            const SizedBox(width: 4),
            Expanded(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: theme.textTheme.bodyLarge?.copyWith(
                fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                color: enabled ? null : colors.muted)),
              if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 2),
                child: Text(subtitle!, style: theme.textTheme.bodySmall)),
            ])),
          ]))),
      ),
    ));
  }
}

/// Radio rows stacked `space-2` apart.
class CalmRadioRows extends StatelessWidget {
  const CalmRadioRows({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch,
    children: _spaced(children, 8));
}

class CalmOption<T> {
  const CalmOption(this.value, this.label, {this.detail, this.enabled = true});
  final T value;
  final String label;
  final String? detail;
  final bool enabled;
}

/// A filled field that chooses one option in a sheet of radio rows.
class CalmSelectField<T> extends StatelessWidget {
  const CalmSelectField({super.key, required this.label, required this.options, this.value, this.onChanged});

  final String label;
  final List<CalmOption<T>> options;
  final T? value;
  final ValueChanged<T>? onChanged;

  Future<void> _choose(BuildContext context) async {
    final picked = await showCalmSheet<T>(context, builder: (context) => CalmSheet(title: label, children: [
      RadioGroup<T>(groupValue: value, onChanged: (v) => Navigator.pop(context, v),
        child: CalmRadioRows(children: [for (final o in options)
          CalmRadioRow<T>(value: o.value, title: o.label, subtitle: o.detail, enabled: o.enabled)])),
    ]));
    if (picked != null) onChanged?.call(picked);
  }

  @override
  Widget build(BuildContext context) {
    final selected = options.where((o) => o.value == value).firstOrNull;
    final enabled = onChanged != null;
    return Semantics(button: true, enabled: enabled, child: GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: enabled ? () => _choose(context) : null,
      child: InputDecorator(
        isEmpty: selected == null,
        decoration: InputDecoration(labelText: label, enabled: enabled,
          suffixIcon: const ExcludeSemantics(child: Icon(CalmIcons.chevronDown, size: 20))),
        child: Text(selected?.label ?? '', style: Theme.of(context).textTheme.bodyLarge,
          maxLines: 2, overflow: TextOverflow.ellipsis),
      ),
    ));
  }
}
