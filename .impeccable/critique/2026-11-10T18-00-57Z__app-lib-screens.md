---
target: Flutter app screens (projects, project, compare)
total_score: 25
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens"
timestamp: 2026-11-10T18-00-57Z
slug: app-lib-screens
---
Method: design review only (detector not applicable, native platform). Device screenshots (projects + new-project dialog, project screen + menu, compare screen states) against source at 2bf71f9 and the Calm Bold artifact.

## Calm Bold conformance
Foundations implemented exactly (colour tokens, type scale, radii, 48px targets, marker on newer slot, review disc/dashed border, fallback banner).
Not implemented / off-system:
- Popup menu and dropdown menu use Material elevation shadows (spec: no shadow); 4px/square corners.
- Focused dropdown item filled lavender (focusColor link @24%), not a token.
- Main action not fixed at bottom (Compare two briefs at top of project screen; Start comparison scrolls).
- Secondary actions are white OutlinedButton pills, not ink text buttons; invisible edges inside white slot cards.
- RadioRow not built: stock RadioListTile.
- TextField: Material outlined floating-label fields; New project fields touch.
- BottomSheet not built: AlertDialogs for new project / paste / PDF.
- VersionTimeline not built: separate Comparisons and Versions lists.
- Home bento (marker hero) not built.
- Disabled main button hint is static, button not focusable.
- Material filled/outline icons (filled settings gear) vs stroke icons spec.
Root cause: calmTheme lacks popupMenuTheme/dropdownMenuTheme/radioTheme; calm_widgets.dart lacks CalmButton/CalmRadioRow/CalmField/CalmSheet/CalmTimeline.

## Audit 14/20 (Good)
A11y 3, Performance 3, Theming 3, Platform conformance 2, Adaptivity 3.
P1: unthemed Material components (menus, radios, fields, dialogs). P1: raw exception text shown (projects_screen.dart:64, project_screen.dart:62 error = '$e').
P2: project picker cannot disambiguate duplicate names; disabled Start gives no reason; icon set drift. P3: zero gap between New project fields; 24px empty gap in slot without versions.

## Critique 25/40 (Acceptable)
1 Status 3 · 2 Real world 3 · 3 Control 3 · 4 Consistency 2 · 5 Error prevention 2 · 6 Recognition 2 · 7 Efficiency 2 · 8 Minimalist 3 · 9 Error recovery 2 · 10 Help 3.

Priority issues:
1. [P1] Project screen is two lists, not the VersionTimeline (recall burden, no prefilled "Compare v2 -> v3"). /impeccable shape then layout.
2. [P1] Components off-system: menus, radios, fields, dialogs. /impeccable polish.
3. [P2] Three equal-weight action pills on project screen; main action not pinned. /impeccable distill.
4. [P2] Comparison row wording: "Newer ·" repeated; status "Complete" collides with "Complete replacement"; status outweighs source names. /impeccable clarify.
5. [P2] Silent failures: empty project name closes dialog, duplicate names accepted. /impeccable harden.

Personas: freelancer re-picks both versions (4 decisions for a 1-tap timeline action); VoiceOver hears "Demo, Demo" and cannot focus disabled Start; one-handed user never finds main action in thumb zone.
Minor: dev gear reads as app settings; Delete project not styled destructive; "Start comparison" vs spec "Start comparing".
