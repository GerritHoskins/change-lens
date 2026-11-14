# Onboarding and first-launch design handoff

Prepared 2026-11-14 for the design agent. Repository:
`C:\Users\Gerrit\job-search\POCs\change-lens`, branch `m1-iphone`, baseline commit
`4a401b3`. This is a baseline, not proof that the checkout hasn't changed since:
check `git status` and the current HEAD first.

Goal: design the first-launch experience, **sign-in → onboarding (once) → Projects**,
so a new user understands what ChangeLens is for and how to use it, and feels
confident starting their first comparison.

**Round 2 (2026-11-14):** the first canvas has been critiqued. If you are revising
it, start at [§9](#9-round-2-critique-fixes-2026-11-14). §1–§7 still apply.

**Round 3 (2026-11-14):** round 2 is done and re-scored at 35/40. For the
remaining polish, start at [§10](#10-round-3-polish-2026-11-14).

**Round 4 (2026-11-14):** the implemented app scrolls on two German steps on iOS. Start
at [§11](#11-round-4-german-overflow-on-ios-2026-11-14).

## 1. Start here

Read, in order:

1. [Onboarding feature brief](onboarding-feature-brief.md): the content source. It
   covers what the app is, the four ideas users must understand, the full flow in exact
   in-app wording, trust points, limits, and what must **not** be promised (§7).
2. [PRODUCT.md](../PRODUCT.md): audience, purpose, the rules about meaning and data
   that can't be broken, and the principle "Let the user establish context before
   interpreting a change."
3. [DESIGN.md](../DESIGN.md): the Calm Bold system (tokens, components, motion,
   platform behaviour). Implemented in `app/lib/design/`.
4. [Decision log](06-decision-log.md) **O-22**: the owner's decision on first-launch order.
5. [MVP spec](02-mvp-spec.md) §1 step 1 and AC-25/AC-26;
   [UI/UX handoff](ui-ux-handoff.md) §5 "First use/auth" and §8 checklist.
6. [Design references](ui-ux-references.md): the owner's v1 screens canvas has
   artboards for sign-in, email code and account linking. They are historical evidence
   only. They don't show implemented features and may predate O-20 and O-22.
7. Strings: `app/lib/l10n/app_en.arb` and `app_de.arb`. Screens: `app/lib/screens/`.

## 2. The decided flow (O-22)

| Situation | What the user sees |
|---|---|
| First launch | Sign-in, then onboarding (once), then Projects |
| Returning user, valid session | Projects directly |
| Expired session | Sign-in, then back to where they were. Never onboarding again |
| Signed out by the user | Sign-in |

Sign-in comes first, so onboarding never needs to explain accounts.

## 3. Scope

### 3.1 Sign-in (design only; feature-gated)

Sign-in is **not built** (I-8 backend, I-18 account screens). Development builds
still connect through Developer settings, which must stay development-only. Design
these screens and states, but don't implement fake working sign-in or success states:

- Methods: **email one-time code, Google, Sign in with Apple**. Apple requires Sign
  in with Apple whenever Google is offered. Use each provider's own button rules.
- States: signed out, loading, cancelled, error, expired session, email-code entry
  and resend, and **`link_required`**: an account with this email already exists, so
  "sign in with your usual method to link" (03a P1, O-19). Linking never happens from
  a matching email alone.
- MFA is offered, and enforcement depends on the account setting (AC-26). Don't design
  a mandatory authenticator-app setup into first launch.
- Links to the privacy policy, terms and imprint (I-20). The texts are drafts in
  `docs/legal/` and not legally reviewed, so use placeholders for link targets.

### 3.2 Onboarding (design; implement only if the owner authorises it)

Content comes only from brief §1–§6. Suggested sequence (brief §8), for you to
accept, merge or cut:

1. Promise: "What changed since the last version, and which changes matter?"
2. You set the order: earlier vs newer is your call, never guessed.
3. Tell it the scope: complete replacement / partial update / not sure, and why
   it matters.
4. Read by topic, check the source: topic filters, quoted passages, highlighted page.
5. Uncertain stays visible: *Needs your review* and the "?" disc.
6. Your review isn't client approval.
7. Start: "Compare two briefs" (pasted text or a PDF with selectable text).

Also design how users reach the key definitions later, in context (for example, info
sheets on the compare and finding screens): the scope options, the change types,
the evidence modes, and "Selected summary".

## 4. Constraints that can't be broken

**Truthful copy**
- No claims of time saved, accuracy, customer proof or superiority (PRODUCT.md).
- Never promise brief §7 items: screenshot/camera/share-sheet import, plans or
  allowances, share links, push notifications, teams, DOCX.
- Reviewing a finding is never "approved" or "agreed". Client approval is always
  "Client approval recorded (not verified by ChangeLens)".
- Comparison quality is measured on English briefs only. Don't imply German
  documents work equally well, even in the German UI.

**Calm Bold**
- Pastel blocks mean **one thing only: the finding's topic**. Don't use them as
  decoration on onboarding cards.
- Orange "?" disc = uncertainty only. Lime = new/quoted or personal review.
- One main action (black pill, 60 px) per screen. Secondary actions are ink text
  buttons with targets of at least 48 px.
- Roboto, Lucide icons via `calm_icons.dart`, and the token radii and spacing in DESIGN.md.
- Reuse `CalmSheet`, `CalmPageHeader`, `CalmWarning`, `CalmReviewDisc` and the rest
  before adding components.

**Platform and access**
- iOS and Android, portrait phones, adapted to each OS (Back, swipe, safe areas).
- English and German, light and dark, 1× and 2× text, 320×568 and 390×844. German
  strings run longer, so test with them.
- Onboarding must be skippable, and every screen must work with a screen reader,
  in a sensible reading order.
- Respect reduced motion. Keep motion within DESIGN.md's evidence and marker timings.

**Privacy**
- No document content on the device and none in analytics (AC-23, AC-25).

## 5. Open questions for the owner (don't decide them yourself)

Status 2026-11-14: the owner approved the canvas's answers to questions 2–4
(labelled example content, consent after onboarding, replay from the Projects
menu). Question 1 was answered in the design session: on the account,
server-side (once per account, AC-25 unchanged). This needs an API field for the
seen flag and a second one for the saved step that resume uses
(`docs/onboarding/direction.md` §1 and §8).

1. **Where the "onboarding seen" state lives.** AC-25 says only auth tokens are
   stored on the device. A local flag needs that criterion clarified. Storing it
   on the account means onboarding shows once per account rather than once per device.
2. **Example content in onboarding.** DESIGN.md keeps the synthetic "Cedar website"
   scenario in tests and the preview entry point only. Sample quotes in onboarding
   need owner approval, and must be labelled as examples.
3. **Analytics consent.** The opt-in prompt for app-side events (D-18, tier B) has
   no place in the flow yet. Decide whether it goes after sign-in, inside
   onboarding, or later.
4. **Replay.** Whether onboarding can be reopened later (for example "How
   ChangeLens works" from Projects).

## 6. Deliverables

1. The chosen direction and its reasons, recorded before any implementation.
2. Sign-in screens with every state in §3.1, in EN/DE and light/dark.
3. The onboarding sequence with final EN and DE copy, written as ARB keys and values
   ready for `app_en.arb` / `app_de.arb`.
4. In-context definition sheets (§3.2).
5. If the owner authorises implementation: Flutter onboarding screens with widget
   tests (EN/DE, text scale, skip, screen-reader order), and green `flutter analyze`
   and `flutter test`. Sign-in remains design-only until I-8/I-18.

## 7. Acceptance checklist

- [ ] The order matches O-22 in every situation in §2.
- [ ] Every onboarding claim traces to brief §1–§6. Nothing from §7 appears.
- [ ] Pastel colour appears only as topic meaning. One main action per screen.
- [ ] The four core ideas (order, scope, evidence, review ≠ approval) are covered.
- [ ] Onboarding can be skipped. Screen-reader order and large text work in EN and DE.
- [ ] The `link_required` and expired-session states are designed. No fake sign-in success.
- [ ] Open questions in §5 are listed in the result, not silently decided.

## 8. Receiving-agent prompt

> Work in the current ChangeLens checkout. Read docs/onboarding-design-handoff.md,
> then the onboarding feature brief, PRODUCT.md and DESIGN.md, and verify the Git
> state. Design the first-launch experience: sign-in first, then a one-time
> onboarding, then Projects (O-22). Use Impeccable and the Calm Bold system. Take
> onboarding content only from brief §1–§6 and never promise §7 items. Design the
> sign-in states without implementing fake sign-in. Raise the §5 open questions
> with the owner instead of deciding them. Record the chosen direction before
> implementing anything. Implement onboarding in Flutter only if the owner
> authorises it. This handoff is not permission to commit, publish, deploy or
> change dependencies. Return the designs, the EN/DE copy, and verified evidence,
> or a precise blocker.

## 9. Round 2: critique fixes (2026-11-14)

**Canvas:** [ChangeLens first launch](https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr)
(17 artboards, 390×844, with locale, dark and state tweaks). **Critique:**
`.impeccable/critique/2026-11-14T10-54-13Z__claude-ai-artifact-nzabbmaxfh1vp7a9v99rmr.md`,
scored 26/40, with four P1 issues, one P2 and nine minor ones. Read it before starting.

### 9.1 Owner answers

- **Order:** fix the step overflow and the fake headline first (§9.2 items 1–2).
- **Scope:** everything, including the minor observations.
- **Approved and not to be redesigned:** consent stays right after onboarding,
  "How ChangeLens works" in the Projects menu replays onboarding, and step 3 keeps a
  synthetic example labelled "Example".

### 9.2 Fixes, in order

Each fix lists the artboards it touches (`project/<name>.dc.html`) and when it counts
as done. Change the English and German branches together, and keep the dark tweak working.

1. **Steps 2 and 3 overflow the screen (P1).** `Onb2Context`, `Onb3Evidence`.
   Measured at 390×844: step 3 needs 870 px in a 636 px viewport (916 px in German),
   and step 2 needs 732 px (755 px in German). Step 3's uncertainty example and its
   "?" rule are hidden in a nested scroll.
   - Split step 3 into two steps: "Every change shows its source" and "When
     ChangeLens can't tell" (the "?" disc, *Needs your review*, and the link to all
     differences). The counter becomes "of 6".
   - On step 2, replace the three radio rows with a static three-line list, so
     nothing looks tappable.
   - **Done when:** no onboarding step scrolls at 390×844 in English or German at
     1× text, and only the step body scrolls at 2× text.
2. **The step 3 example shows UI the app doesn't have (P1).** `Onb3Evidence`.
   The "20 Nov → 27 Nov" headline doesn't exist in the real app. The API returns
   passages, not extracted values (`app/lib/screens/report_widgets.dart:173`;
   DESIGN.md, Direction and scope).
   - Draw the real finding anatomy instead: the topic block with change type, the
     explanation sentence, and the Earlier and Newer quote cards with lime highlights
     and page labels. Compare against `app/lib/screens/finding_screen.dart` and
     `docs/screenshots/finding.png`.
   - **Done when:** every element of the example exists on the real finding screen.
3. **Steps 2 and 4 show controls that do nothing (P2, accessibility).** `Onb2Context`,
   `Onb4Review`. Mark the illustrative earlier/newer slots and the
   Confirm/Correct/Dismiss rows as illustrations (`aria-hidden` on the controls plus
   a one-line text alternative). Screen readers must not announce them as buttons
   or radio buttons.
4. **The sign-in screen makes no promise (P1).** `Main`, all four states. Use the
   empty top half for the question "What changed, and which changes matter?", one
   supporting line, and the static topic chips from step 1. Keep the provider
   buttons and the legal links. Then trim step 1 so it doesn't repeat the same
   promise word for word.
   - **Done when:** someone who has never heard of ChangeLens can say what it does
     from the sign-in screen alone, and the heading doesn't move between states.
5. **Account dead ends (P1).**
   - `SignInMfa`: add "Use a backup code" (D-8 C1 confirmed backup codes work).
   - New artboard `Settings.dc.html`, reached from the Projects menu
     (`ProjectsReplay`): a usage-events switch with the consent wording, "Delete
     account" (a destructive confirmation, as I-18 and App Store 5.1.1(v) require),
     and Sign out. The consent screen's "You can change this later in Settings" must
     now lead somewhere real.
6. **The sequence ends on limitations (P2).** `Onb5Start`.
   - Compress the limits to one line plus a "What can I import?" link that opens a
     sheet with the full list.
   - Make the main button lead towards the first comparison ("Start", followed by
     consent, then Projects).
   - Remove Skip from the last step. Keep the replay state's Close.
   - Add a note on the canvas that the import sheet repeats the limits.
7. **Minor fixes.**
   - `LinkRequired`: move the `link_required.methods = …` line out of the screen
     into a canvas note.
   - `Main` and the canvas note: either make the three sign-in buttons visually
     equal, or reword the note. Today it says "equal" while Apple is filled and the
     others are outlined. Follow Apple's and Google's button rules.
   - `SignInCode`: separate "That code is wrong. Check it and try again." from
     "That code has expired. Request a new one." Add a paste/autofill hint.
   - `Main` error state: give separate messages for a network failure, a cancelled
     provider screen, and a server error.
   - `SignInEmail`: add "We'll email you a 6-digit code." and an invalid-address state.
   - `SessionExpired`: emphasise the method the user last signed in with, and
     remove the decorative lime block from the background mock.
   - `DefSummary`: use "Close" like the other sheets. "Show all differences" stays
     the main action.
   - Add an interrupted-onboarding state: reopening the app resumes at the same step.

### 9.3 Checks before you report back

- Render every changed artboard in English, German and dark. Measure that no step
  overflows (the main area's `scrollHeight` must not exceed its `clientHeight` at
  390×844). Then look at 2× text and 320×568.
- Re-check every onboarding claim against brief §1–§6, and confirm nothing from
  §7 appears.
- Keep the Calm Bold rules from §4. The two exceptions in the canvas notes (equal
  sign-in buttons, and equal Allow / Don't allow) still need to be recorded in DESIGN.md.
- Re-run `/impeccable critique` on the canvas and report the new score next to 26/40.

### 9.4 Round 2 receiving-agent prompt

> Work in the current ChangeLens checkout and revise the existing canvas
> https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr in place. Never create a new
> one. Read docs/onboarding-design-handoff.md §9 and the critique snapshot it
> names, then DESIGN.md and the onboarding feature brief. Apply §9.2 in order,
> starting with items 1 and 2. Change the English and German branches together
> and keep the dark tweak working. Don't redesign the three owner-approved
> choices in §9.1. Don't implement anything in Flutter, commit, or publish
> anywhere other than this canvas. Finish with the §9.3 checks and a fresh
> `/impeccable critique`. Return the canvas link, a list of what changed per
> artboard, the measured overflow results, and the new score.

## 10. Round 3: polish (2026-11-14)

**Canvas:** same link as §9, now 20 artboards. **Critique:**
`.impeccable/critique/2026-11-14T12-08-35Z__claude-ai-artifact-nzabbmaxfh1vp7a9v99rmr.md`,
scored 35/40 (up from 26/40), with no P0 or P1 issues, two P2s, one P3 and six minor
observations. Read it first. Round 2's results are recorded in
`docs/onboarding/direction.md` §8.

Everything decided in §9.1 still holds, and so do the round 2 fixes. This round is
polish only: don't change the flow, the number of steps, or the sign-in layout.

### 10.1 Fixes, in order

Same rules as §9.2: name the artboards you touch, change English and German together,
and keep the dark tweak working.

1. **Step 5's illustration still looks tappable (P2).** `Onb4Review`.
   Confirm, Correct and Dismiss sit as icon rows in a white card, which reads as a
   menu. Screen readers skip it now, but sighted users may still tap it.
   - Put it inside the same "Example" frame that steps 3 and 4 use, or draw the real
     review bar from `app/lib/screens/finding_screen.dart`, scaled down, inside that
     frame. Keep `role="img"` and `onbReviewAlt`.
   - **Done when:** steps 3, 4 and 5 use one illustration style, and nothing on step
     5 looks like a control apart from Back, Skip and Next.
2. **The sequence still ends on limits (P2).** `Onb5Start`, both states.
   Step 6 lists the input type, online-only and English-only, and then consent follows.
   - Open the step with what happens after Start, and keep it true to the flow.
     Start leads to consent, then to Projects, where "Compare two briefs" is the main
     action. Something like "Next: create a project and compare two briefs." It must
     not imply that Start opens a comparison.
   - Keep the limits to at most two short lines plus the "What can I import?" link.
     The English-only line must stay reachable before the first comparison (brief §5),
     either on this step or in the import sheet.
   - **Done when:** the step reads as a starting point, and every limit is still on the
     step or one tap away.
3. **The code fields don't specify autofill (P3).** `SignInCode`, `SignInMfa`.
   - Add `autocomplete="one-time-code"` and `inputmode="numeric"` to the mock inputs.
   - Add a canvas note for implementation: Flutter `AutofillHints.oneTimeCode` with
     `TextInputType.number` (iOS text content type `oneTimeCode`; SMS/email code
     suggestion on Android).
   - The MFA field takes a numeric code. The backup-code route may need letters, so
     note that the backup-code entry uses a text keyboard.
4. **Minor fixes.**
   - `Onb5Start` replay state: the title "Before your first comparison" doesn't fit a
     returning user. Give the replay a neutral title, such as "Before you compare".
     This needs an ARB key.
   - `Settings`: the section header "Share usage events" repeats the row title. Rename
     the section, for example "Privacy", or drop the header.
   - `ImportSheet`: the icons render at about 12 px and sit above the first text line.
     Use 20–24 px Lucide icons aligned to the first line, matching the other sheets.
   - App labels quoted in body copy aren't marked: "Show in document" (step 3), *Needs
     your review* (step 4), "All differences" (step 4, `DefSummary`), and the
     change-type names in `DefScope`. German already uses „…“. Use “…” in English, the
     same way on every artboard, so users can find the label later.

**Leave as is (don't fix):**
- In dark mode the white Apple button reads as the main action. That follows Apple's
  rule, and it's already recorded as an exception in DESIGN.md and in the canvas note.
- The step 3 card says "Date or deadline", while the topic chip says "Deadlines". Both
  come from the app (`catDate` vs `topicDeadlines`).
- The number of screens before Projects (sign-in, 6 steps, consent). The flow is the
  owner's decision (O-22, §9.1), and Skip already shortens it.

### 10.2 Records to update

- `docs/onboarding/direction.md`: the header still describes round 1 (79 keys,
  17 artboards, 5 screens). Update it to the current numbers, and add a Round 3 section
  with the change list and measurements, as §8 does for round 2.
- `docs/onboarding/onboarding_en.arb` / `_de.arb`: add any new or changed keys. Keep
  the two files' key sets and placeholders identical.
- Don't edit `docs/06-decision-log.md`. The O-23 row drafted in direction.md §1 was
  accepted on 2026-11-14 and is now recorded there.

### 10.3 Checks before you report back

- The §9.3 checks again: render every changed artboard in English, German and dark;
  no overflow at 390×844 at 1× text; only the step body scrolls at 2× text and
  320×568.
- Brief §1–§6 still covers every onboarding claim, and nothing from §7 appears. In
  particular, step 6 mustn't promise anything about Start that the flow doesn't do.
- Re-run `/impeccable critique` and report the score next to 35/40. **Target:** no P2
  issues left.

### 10.4 Round 3 receiving-agent prompt

> Work in the current ChangeLens checkout and revise the existing canvas
> https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr in place. Never create a new
> one. Read docs/onboarding-design-handoff.md §10 and the round 2 critique snapshot
> it names, then docs/onboarding/direction.md. Apply §10.1 in order. Don't change
> the flow, the step count, the sign-in layout, or anything §9.1 or §10.1 lists as
> decided or to be left as is. Change English and German together and keep the dark
> tweak working. Update the records in §10.2. Don't implement anything in Flutter,
> commit, or publish anywhere other than this canvas. Finish with the §10.3 checks
> and a fresh `/impeccable critique`. Return the canvas link, a list of what changed
> per artboard, the measured overflow results, and the new score.

## 11. Round 4: German overflow on iOS (2026-11-14)

The onboarding is implemented (commit `6a3791a`, `app/lib/screens/onboarding_screen.dart`).
The no-scroll test (`app/test/onboarding_test.dart`) shows two German steps that don't fit
at 390×844 with text at 1.0 on iOS:

| Step | Locale, platform | Result |
|---|---|---|
| 2 "Du legst Reihenfolge und Umfang fest" | DE, iOS | Body scrolls by **46 px** |
| 5 "Deine Prüfung ist keine Kundenfreigabe" | DE, iOS | Body scrolls by **12 px** |
| 2 | DE, Android | Fits, with 3 px to spare |
| 2 | EN, iOS | Fits, with 4 px to spare |

**Why the canvas missed it.** The canvas measured at a 16 px body. The app's iOS body is
**17 px with a line height of about 25 px** (`calm_theme.dart`, `bodyMedium`), while Android
uses 16 px. The app's top bar, page header and pinned footer also differ slightly from the
artboards. So round 2's "0 px overflow" was true for the canvas, not for the app.

The owner chose to fix the overflow rather than accept a scroll. This round is copy and
layout only: same six steps, same flow, nothing from §9.1 or §10 reopened.

### 11.1 What to change

1. **Step 2 (`Onb2Context`).** Free at least **3 lines (about 75 px)** of German body text at
   17 px. Two lines only clear the overflow, and the third gives a margin, because English
   and Android are within 4 px too.
   - Candidates: `onbContextScope`, the three `onbScopeLine*` keys, `onbContextNote`, or the
     illustration's height (the gap and swap icon between the two slots).
   - The quoted labels inside the scope lines must stay word for word what the app shows:
     „In der Ersatzversion nicht enthalten“, „Nicht angesprochen“, „Von dir zu prüfen“.
     Shorten around them, not inside them.
   - `confirmIntro` is also the compare screen's own text, so don't edit it for onboarding.
     If step 2 needs a shorter opening line, propose a new key (for example
     `onbContextBody`) and say in your report that onboarding then no longer repeats the
     compare screen's wording. That's a trade-off for the owner.
2. **Step 5 (`Onb4Review`).** Free at least **2 lines (about 50 px)** of German text.
   - The main candidate is `onbReviewApproval` (149 characters).
   - `approvalRecorded`, `approvalNone`, `reviewConfirmed` and `yourReview` are app strings
     shown inside the example. Don't change them.
   - The rule from §4 still applies: never "approved" or "agreed", and the review must not
     read as client approval.
3. **English.** Change English only where the same shortening makes it clearer, or where
   English needs the margin too. Step 2 on iOS has 4 px to spare.

**Out of scope:** type size, line height, spacing tokens, the step count and the
illustration style. Don't shrink type to make things fit (§9.2 item 1).

### 11.2 Measure the way the app renders

- Add an iOS-metrics check to your measurement, with a 17 px body and a line height of
  about 25 px, or render with those values. Report both platforms.
- **Done when:** steps 2 and 5 fit at 390×844 and 1.0 in EN and DE on both platforms, with
  at least 24 px to spare.
- Re-check every changed line against brief §1–§6.

### 11.3 Records

- Update `docs/onboarding/onboarding_en.arb` and `_de.arb` (changed keys, any new key with its
  `@` description). Keep the key sets and placeholders identical.
- Add a Round 4 section to `docs/onboarding/direction.md` with the old and new text of every
  changed key and the measurements.
- Update the canvas artboards `Onb2Context` and `Onb4Review` in place.

**Afterwards (not for the design agent):** the implementing agent copies the changed keys into
`app/lib/l10n/`, runs `flutter gen-l10n`, and empties the `reported` ceiling in
`onboarding_test.dart`, so the test then fails on any overflow.

### 11.4 Round 4 receiving-agent prompt

> Work in the current ChangeLens checkout and revise the existing canvas
> https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr in place. Never create a new one.
> Read docs/onboarding-design-handoff.md §11, then app/lib/screens/onboarding_screen.dart,
> app/lib/design/calm_theme.dart and app/test/onboarding_test.dart to see how the app
> renders steps 2 and 5. Shorten the German copy on step 2 by at least three lines and on
> step 5 by at least two, at the iOS 17 px body. Keep the quoted app labels word for word,
> don't edit app strings that other screens use, and don't shrink type. Update the ARB
> fragments, direction.md and the two artboards. Don't edit app code, commit, or publish
> anywhere other than this canvas. Return the old and new text of every changed key, the
> measured spare room per step, locale and platform, and any new key the owner must
> accept.
