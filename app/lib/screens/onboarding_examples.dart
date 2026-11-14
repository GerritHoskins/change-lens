// Synthetic example content for onboarding and the definition sheets' previews.
//
// DESIGN.md keeps Cedar data out of lib/. This file is the one exception: the owner allowed
// labelled example content in onboarding (docs/onboarding/direction.md §1, decision 2; O-23).
// Every use sits inside a frame announced as "Example" (onbExample), or inside an
// ExcludeSemantics preview. The content is copied verbatim from test/fixtures/calm_scenario.dart.
// Quotes stay English in every locale: they stand for document content.
import '../api.dart';

/// The deadline finding (onboarding step 3).
final deadlineExample = Finding(const {
  'id': 'example-deadline', 'change_type': 'changed', 'category': 'date_deadline',
  'topic': 'deadlines', 'group': 'prioritised', 'revision': 1,
  'explanation': 'Final delivery moved.',
  'evidence': [
    {'side': 'earlier', 'quote': 'Final files are due on 20 November 2026.',
      'locator': {'page': 3, 'char_start': 0, 'char_end': 40}},
    {'side': 'later', 'quote': 'Final files are due on 27 November 2026.',
      'locator': {'page': 3, 'char_start': 0, 'char_end': 40}},
  ],
});

/// The hosting finding (onboarding step 4): uncertain, so it sits under "Needs your review".
final hostingExample = Finding(const {
  'id': 'example-hosting', 'change_type': 'uncertain', 'category': 'responsibility_owner',
  'topic': 'responsibilities', 'group': 'needs_review', 'revision': 1,
  'explanation': 'Responsibility for hosting is unclear.',
  'evidence': [
    {'side': 'earlier', 'quote': 'Hosting is provided by the client.',
      'locator': {'page': 4, 'char_start': 0, 'char_end': 34}},
  ],
});

/// A short neutral sentence for the decorative evidence-mode previews.
const sampleQuote = 'Final files are due on 27 November 2026.';
