# Onboarding and first-launch direction

Recorded 2026-11-14 before any implementation, as the handoff (`docs/onboarding-design-handoff.md` §6.1) requires.
Checkout verified at `4a401b3` on `m1-iphone`. The only tracked change is `docs/06-decision-log.md`,
which differs in line endings only (CRLF, no content diff).

Copy: `onboarding_en.arb` and `onboarding_de.arb` in this folder (114 keys each after round 3, with matching placeholders).
They are **not** merged into `app/lib/l10n/`, because implementation isn't authorised yet.

Designs: https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr (20 artboards at 390×844, plus 5 logo drafts; each has Tweaks for locale, dark and, where relevant, state).

Current state: sign-in → **6 onboarding steps** → consent → Projects. §2–§6 record round 1, when there were 5 steps. Rounds 2 and 3 (§8, §9) supersede them where they differ. Critique scores: 26/40 after round 1, 35/40 after round 2.

## 1. Owner decisions (2026-11-14, answering handoff §5)

| # | Question | Decision | Consequence |
|---|---|---|---|
| 1 | Where "onboarding seen" lives | **On the account, server-side** | Once per account, not per device. AC-25 stays as written. Needs a small API field, for example `onboarding_completed_at` on the `POST /session` response plus a `PUT` to set it. This is an explicit backend dependency, not a UI mock |
| 2 | Example content | **Allowed, labelled "Example"** | Synthetic Cedar quotes appear only on onboarding screen 3, inside an "Example" frame, rendered with the real evidence components |
| 3 | Analytics consent (D-18 tier B) | **Its own screen after onboarding** | Sign-in → onboarding → consent → Projects. Replay doesn't show it |
| 4 | Replay | **Yes, "How ChangeLens works"** | Reached from the Projects overflow menu. Same screens, without Skip and consent, ending in "Done" |

Accepted by the owner and recorded as O-23 in `docs/06-decision-log.md` (2026-11-14), with the saved
onboarding step added as a second account field. The original draft row:

> | O-23 | First-launch details | **Decided 2026-11-14 (owner):** the "onboarding seen" state is stored on the account (once per account; AC-25 unchanged; needs an API field). Onboarding may show synthetic example quotes labelled "Example". The D-18 tier B opt-in is its own screen after onboarding, before Projects. Onboarding can be replayed from Projects as "How ChangeLens works". | I-18, D-18 |

## 2. Flow

| Situation | Sequence |
|---|---|
| First launch | Sign-in → onboarding (5 screens, skippable) → consent → Projects |
| First sign-in on a second device | Sign-in → Projects (the flag is on the account). Consent is per account as well, so it isn't asked again |
| Returning user, valid session | Projects |
| Expired session | A sign-in sheet over the current screen, then the same screen. No onboarding and no consent |
| Signed out by the user | Sign-in |
| Replay | Projects ⋯ → "How ChangeLens works" → 5 screens → "Done" → Projects |

**Expired session as a sheet, not a route reset.** AC-25 forbids persisting document content, so a
half-filled compare form (pasted text) can survive re-authentication only in memory. A modal sheet
over the current route keeps it. Resetting the navigation stack would silently discard it. The
sheet can't be dismissed without signing in, and "Sign out" is its secondary action.

**Skip** marks onboarding as seen and goes to consent. Consent is a legal question, not
onboarding content, so it can't be skipped. Both answers are equally easy to give.

## 3. Onboarding: 5 screens (from the 7 brief beats; round 1, now 6 steps, see §8)

| # | Screen | Brief beats | Visual | Main action |
|---|---|---|---|---|
| 1 | What changed, and which changes matter? | 1, part of 4 (topics) | The six topic chips in their topic colours. Pastel = topic, so allowed | Next |
| 2 | You set the order and the scope | 2 + 3 | Static Earlier/Newer slots (newer in `marker`, as in the app) and the three scope rows, unselected | Next |
| 3 | Every change shows its source | 4 + 5 | "Example" frame: one finding card with Earlier/Newer quotes, plus one dashed needs-review card with the ? disc | Next |
| 4 | Your review isn't client approval | 6 | Confirm / Correct / Dismiss, then the separate approval record line | Next |
| 5 | What you need | 7 (as expectations) | Four rows: input, limits, online, language | Continue (first run) / Done (replay) |

Why 5 and not 7: beats 2 and 3 are both product principle 1 ("let the user establish context"), and beats
4 and 5 are both principle 2 ("uncertainty and evidence as accessible as the finding"). Splitting
them added two screens without adding a new idea.

Why the last screen doesn't start a comparison: consent must come before Projects (decision 3), and
Compare needs a project. Projects already has "Compare two briefs" as its one main action, so the
user is one tap from starting either way, and O-22's "then Projects" holds literally.

Every claim traces to brief §1–§6. Nothing from §7 appears. In particular, the fair-use allowance (I-14)
isn't mentioned, because it isn't implemented.

Limits (`onbStartLimits`) are placeholders. The values must come from the server's parse limits.
Hard-coding "15,000 / 20 / 10" in the copy would drift silently when the config changes.

## 4. Sign-in

- **One screen, three equal buttons.** App Review guideline 4.8 (checked 2026-11-14) doesn't strictly require
  Sign in with Apple. When Google is used for the primary account, it requires *an equivalent option*: a login
  service that limits data to name and email, lets the user hide their email, and doesn't track for ads without consent.
  Email one-time code doesn't meet that test, because the email can't be hidden, so Sign in with Apple is the practical way
  to comply. The handoff's wording ("Apple requires Sign in with Apple") overstates this, but the outcome is the same.
  "Equivalent" is why the buttons are equal in size and weight. Order: iOS Apple, Google, email; Android Google, Apple,
  email. Apple and Google use their own branded buttons (system `ASAuthorizationAppleIDButton` style,
  Google's branding assets). The email button is a Calm Bold outlined ink pill at the same height.
- **Calm Bold exception:** the provider buttons replace the black main pill on this screen. The Apple button
  in its black style looks like the main action, but the three are deliberately equal. This is the only
  screen without a single main action, and it should be recorded as such in DESIGN.md.
- **Android and Apple:** native Sign in with Apple doesn't exist on Android, so it needs a web flow
  (Logto social connector or the backend code exchange). It's still required, because an account created
  on iOS with Apple must be able to sign in on Android. This needs confirming against I-8.
- States designed: signed out, loading (buttons disabled, `signInLoading` announced), cancelled (back to
  signed out; announcement only, no banner, because cancelling isn't an error), error (a `CalmWarning`
  above the buttons), email entry, code entry with a resend cooldown, wrong or expired code,
  MFA challenge, `link_required`, and expired session (a sheet).
- **`link_required`** shows only the methods in `link_required.methods` (03a P1). After that sign-in,
  plus MFA when it's on, succeeds, the backend links and the app announces `linkDone`. No linking from a
  matching email alone.
- **MFA** appears only as a challenge, when the account has it on. No authenticator setup in first launch.
- Legal links (Terms, Privacy, Imprint) are ink text links in the footer. Targets are placeholders until
  the I-20 texts are reviewed. No "by continuing you agree" wording: that's for the lawyer to set.

## 5. Consent screen

Equal-weight **Allow** / **Don't allow**: two identical outlined ink pills, with no black main
pill. The DSK and EDPB position is that refusal must be as easy as acceptance. Legal requirement
overrides Calm Bold's one-main-action rule here, and this exception should be recorded in DESIGN.md too.
Nothing is selected by default, and nothing is sent before an answer.

## 6. In-context definition sheets

An info button (Lucide `info`, 48 px target, label `defInfo`) opens a `CalmSheet`:

| Where | Sheet | Content |
|---|---|---|
| Compare, beside "What is the newer version?" | Scope | Three `CalmRadioRow`-styled read-only rows: existing hint + `defScope*` |
| Finding, beside the change type | Change types | Six rows: existing `type*` label + `def*` |
| Finding, beside the evidence mode | How a passage was found | Three rows: existing `evidenceMode*` label + `defMode*` |
| Report, at the selected-summary line | Selected summary | `defSummaryBody`, with "Show all differences" as the sheet's main pill |

Labels are reused from `app_en.arb` (`scope*`, `type*`, `evidenceMode*`), so the sheet matches the
screen word for word. Only the explanations are new.

## 7. Open dependencies and risks

1. **API field for the seen flag** (decision 1). Without it, every first sign-in on a new device would show onboarding again, or the client would need local storage, which AC-25 excludes.
2. **Settings screen.** `consentDefault` promises "change this later in Settings". There's no production Settings screen yet (only Developer settings). It must ship with the consent screen, or the string must change.
3. **Consent storage.** It's per account, server-side, for the same reason as the seen flag. Tier B events must not be sent before the answer arrives.
4. **Where the MFA challenge is rendered** (native vs Logto hosted page). This depends on I-8. If it's hosted, the `mfa*` strings belong to Logto's sign-in experience, not the app.
5. **Drift between the Calm Bold design-system artifact and the app.** The artifact's content rules say "need a second look" and "Start comparing", but the app says "Needs your review" and "Start comparison". The app wins (DESIGN.md), and this copy follows the app. The artifact should be re-synced.
6. **Stale PRODUCT.md line.** "Account linking behavior (D-8 C2): owner decision pending" was decided as O-19 on 2026-11-10.

## 8. Round 2 (2026-11-14): critique fixes

Applied handoff §9.2 to the existing canvas in order. The owner's in-thread comments on sign-in
(Logo A, and no separate "Sign in to ChangeLens" headline) came after the handoff and are kept: the
logo is a lockup above the promise.

| Artboard | Change |
|---|---|
| Onb2Context | Scope radio rows replaced by a static three-line list. Slots are one illustration (`role=img` + `onbContextAlt`). New state `resumed` (`onbResumed`) |
| Onb3Evidence | Now only "Every change shows its source". The example is the real report card (`report_widgets.dart` FindingTile): type · category, Earlier/Newer label + exact quote, explanation, "Not reviewed yet". The value headline is gone, and there's no lime on the card, because the app shows the marker only on the evidence screen |
| Onb3Uncertain (new, step 4) | "When ChangeLens can't tell": *Needs your review* group header, a dashed uncertain card with the ? disc, and the selected-summary line |
| Onb4Review (step 5) | Confirm/Correct/Dismiss are one illustration (`onbReviewAlt`). The approval label stays readable text |
| Onb5Start (step 6) | "Before your first comparison": one input line, the language line, and a "What can I import?" link. Main button "Start" → consent → Projects. No Skip; replay keeps Close |
| ImportSheet (new) | Full list of inputs and limits (an intentional repeat) |
| Onb1Promise | Trimmed to "Compare two versions of a brief" plus an illustration. The promise question moved to sign-in |
| Main | Logo A lockup, the promise heading, one line and topic chips. Top-aligned, so the heading never moves. States: signed out, loading, cancelled (quiet line), network error, server error (an error replaces the chips) |
| SignInEmail | "We'll email you a 6-digit code." State `invalid` |
| SignInCode | States `cooldown`, `wrong` ("Check it and try again"), `expired` ("Request a new one"). Paste/autofill hint |
| SignInMfa | "Use a backup code" (D-8 C1) |
| LinkRequired | Dev annotation moved to a canvas note |
| SessionExpired | Last-used method first ("You last signed in with Google."), other methods behind a text button. Lime block removed |
| ProjectsReplay | The menu adds Settings |
| Settings (new) | Account (signed in with, Sign out, Delete account → destructive dialog, 03a P8 wording), the usage-events switch, legal links |
| DefSummary | "Close", like the other sheets |

**Measured** in headless Chrome with the bundled Roboto. The preview pages are built from the
same markup as the artboards, but they are not the canvas runtime itself.
- 390×844, 1×: `main` content ≤ viewport on all 20 artboards, in every state, EN and DE, light and
  dark. Before: step 3 overflowed by +234 px (EN) and +280 px (DE), and step 2 by +96 / +119 px.
- 390×844, 2× (fonts and line heights doubled): only the step body scrolls. The footer and Next stay pinned.
- 320×568, 1×: steps 1–5 and sign-in scroll in the body (by +160 to +500 px). The footer stays pinned.

**New dependencies:** account field for the saved onboarding step (resume) next to the seen flag,
and Settings and account deletion (I-18).

## 9. Round 3 (2026-11-14): polish

Applied handoff §10.1 in order. The flow, the step count and the sign-in layout are unchanged.

| Artboard | Change |
|---|---|
| Onb4Review (step 5) | The Confirm/Correct/Dismiss rows are gone. The illustration now sits in the same "Example" frame as steps 3 and 4 and shows the finding screen's own two sections: "Your review" with the lime `CalmReviewMark` ("Confirmed by you"), then "Client approval: No client approval recorded." (`finding_screen.dart`). These are outcomes, not controls. `role=img` with `onbReviewAlt` (reworded). The verbatim label is now in the body: `onbReviewApprovalLabel` |
| Onb5Start (step 6) | First run opens with `onbStartNext` ("Next: create a project and compare two briefs."), which matches Start → consent → Projects. The limits are two short lines plus the import link. Replay has its own title, `onbStartTitleReplay` ("Before you compare"), and no next line |
| SignInCode, SignInMfa | `autocomplete="one-time-code"` and `inputmode="numeric"` on the mock inputs. A canvas note covers Flutter (`AutofillHints.oneTimeCode`, `TextInputType.number`) and the text keyboard for backup codes |
| Settings | The section header is now `settingsPrivacy` ("Privacy"), so it no longer repeats the row title |
| ImportSheet | Icons at 22 px, `flex: none`, aligned to the first text line (they were shrinking to about 12 px) |
| Onb2Context, Onb3Evidence, Onb3Uncertain, DefSummary, DefScope | App labels quoted in body copy now use “…” in English, matching „…“ in German |

**Measured** with the same preview method as §8:
- 390×844, 1×: 0 px overflow on all 20 artboards and every state, EN/DE, light and dark. Step 5's first draft,
  which drew the full report card, overflowed by +77 px (EN) and +123 px (DE). That's why it now uses the
  finding-screen sections.
- 2× text and 320×568: only the step body scrolls, and Next stays pinned.

Claims re-checked against brief §1–§6. Nothing from §7 appears. Step 6 doesn't say that Start opens a
comparison. A new `/impeccable critique` wasn't run: Impeccable isn't available in this session.

## 10. Round 4 (2026-11-14): German overflow on iOS

The implemented app (`6a3791a`) scrolled on German steps 2 (+46 px) and 5 (+12 px) on iOS, where body
text is 17 px with a 24.65 px line height. This round is copy only: same steps, type, spacing and layout.

| Key | Locale | Before | After |
|---|---|---|---|
| `onbContextScope` | EN | Then say what the newer version is. That decides how missing items are reported: | Then say what the newer version is: |
| `onbScopeLineComplete` | EN | Complete replacement: what's missing is reported as “Not in the replacement”. | Complete replacement: what's missing counts as “Not in the replacement”. |
| `onbScopeLinePartial` | EN | Partial update: what it doesn't mention is “Not addressed”. | Partial update: what it doesn't mention counts as “Not addressed”. |
| `onbScopeLineUnknown` | EN | Not sure: missing items go to “Needs your review”. | Not sure: what's missing goes to “Needs your review”. |
| `onbContextNote` | EN | Something missing from the newer version is never reported as cancelled. | Missing items are never reported as cancelled. |
| `onbContextScope` | DE | Gib dann an, was die neuere Version ist. Das bestimmt, wie fehlende Punkte gemeldet werden: | Gib dann an, was die neuere Version ist: |
| `onbScopeLineComplete` | DE | Vollständiger Ersatz: Fehlendes wird als „In der Ersatzversion nicht enthalten“ gemeldet. | Vollständiger Ersatz: Fehlendes gilt als „In der Ersatzversion nicht enthalten“. |
| `onbScopeLineUnknown` | DE | Nicht sicher: Fehlende Punkte landen unter „Von dir zu prüfen“. | Nicht sicher: Fehlendes landet unter „Von dir zu prüfen“. |
| `onbContextNote` | DE | Was in der neueren Version fehlt, wird nie als gestrichen gemeldet. | Fehlendes gilt nie als gestrichen. |
| `onbReviewBody` | DE | Bestätige, korrigiere oder verwirf jeden Befund. Damit hältst du fest, dass du ihn geprüft hast, mehr nicht. | Bestätige, korrigiere oder verwirf jeden Befund. Das heißt nur: Du hast ihn geprüft. |
| `onbReviewApproval` | DE | Wenn der Kunde etwas freigibt, dokumentiere das getrennt in seinen Worten, zum Beispiel mit einer eingefügten E-Mail. ChangeLens überprüft das nicht. | Gibt der Kunde etwas frei, dokumentiere es getrennt in seinen Worten, etwa als eingefügte E-Mail. ChangeLens überprüft das nicht. |

Why these cuts:
- On step 2, the three scope lines now share one pattern: "Fehlendes gilt als …" / "what's missing counts as …".
  The quoted app labels are unchanged, word for word. `onbContextScope` loses its second sentence, because each
  line now says what missing items count as.
- English only follows where the parallel wording is also clearer, and to gain the margin that EN iOS step 2
  needed (it had 4 px to spare).
- `confirmIntro` (the compare screen's text) and the app strings inside the step 5 example are untouched.

**Measurement.** Flutter can't run in either environment: the SDK isn't installed, and its downloads are blocked
by the network allowlist. So I measured a replica of steps 2 and 5, built from `onboarding_screen.dart` and
`calm_theme.dart` metrics, in headless Chrome with the bundled Roboto:
- Viewport: 643 px (844 − 47 − 48 − 106).
- Spare: viewport − column − 24, as in `onboarding_test.dart`.

I calibrated it against the four app values the test reports. On step 5 the replica matches the app within 2 px.
On step 2 it is one line more generous than the app (offset 29 px on iOS, 21 px on Android), most likely because
Flutter wraps one line differently. The estimates below subtract those offsets.

| Step | Platform | EN before → after | DE before → after |
|---|---|---|---|
| 2 | iOS (17 px) | +4 → ≈ +29 | −46 → ≈ +25 |
| 2 | Android (16 px) | ≈ +26 → ≈ +49 | +3 → ≈ +48 |
| 5 | iOS (17 px) | ≈ +62 → ≈ +62 (unchanged) | −12 → ≈ +37 |
| 5 | Android (16 px) | ≈ +74 (unchanged) | ≈ +27 → ≈ +74 |

German step 2 on iOS is the tight one: about 25 px against the 24 px target, inside the estimate's error. The
implementing agent's `onboarding_test.dart` run is the real check.

**Owner option (not applied): a new key `onbContextBody`.** It replaces `confirmIntro` on step 2 only and gives
roughly 25 px more room on German iOS (≈ +50 px):
- EN: "You set the order. ChangeLens never guesses it from upload time or file names."
- DE: "Die Reihenfolge legst du fest. ChangeLens rät sie nie aus Upload-Zeit oder Dateinamen."

The trade-off: step 2 would no longer repeat the compare screen's wording word for word. Take this if the
test still reports less than 24 px for iOS DE step 2.

## 11. Round 5 (2026-11-14): the 24 px margin

The app measurement after round 4 (`c33bee7`): no step scrolls, but the tightest spare room is 13 px. That's
step 3 on iOS in EN and DE, and step 5 on iOS in DE, against the 24 px target. Each needs one line fewer at the
iOS body (17 px, 24.65 px line height).

Round 4's replica estimate for step 5 DE (≈ +37 px) was about one line too optimistic, the same kind of
offset as step 2. So this round doesn't estimate spare room. It changes line counts and checks the slack
on the last line, so that Flutter's slightly different line breaking can't add the line back.

| Key | Locale | Before | After |
|---|---|---|---|
| `onbEvidenceBody` | EN | Each finding quotes the passage from both versions. “Show in document” opens the source, and on a PDF page the passage is highlighted. Quotes are checked against the source before they're shown. | Each finding quotes both versions. “Show in document” opens the source, with the passage highlighted on PDF pages. Quotes are checked against the source first. |
| `onbEvidenceBody` | DE | Jeder Befund zitiert die Textstelle aus beiden Versionen. „Im Dokument anzeigen“ öffnet die Quelle, und auf einer PDF-Seite ist die Stelle markiert. Zitate werden vor der Anzeige mit der Quelle abgeglichen. | Jeder Befund zitiert beide Versionen. „Im Dokument anzeigen“ öffnet die Quelle, bei PDFs mit markierter Stelle. Zitate werden vorher mit der Quelle abgeglichen. |
| `onbReviewApproval` | DE | Gibt der Kunde etwas frei, dokumentiere es getrennt in seinen Worten, etwa als eingefügte E-Mail. ChangeLens überprüft das nicht. | Gibt der Kunde etwas frei, dokumentiere es getrennt, etwa als eingefügte E-Mail. |

| Key | Lines at 350 px, iOS 17 px (Chrome, bundled Roboto) | Last line after |
|---|---|---|
| EN `onbEvidenceBody` | 5 → 4 | 281 of 350 px |
| DE `onbEvidenceBody` | 5 → 4 | 265 of 350 px |
| DE `onbReviewApproval` | 3 → 2 | 282 of 350 px |

Android (16 px) drops the same line in each case. The expected result is +24.65 px on each tight step,
so about 37 px of spare room.

Why the meaning is unchanged:
- "Each finding quotes both versions" keeps brief §2 idea 3. "Quotes are checked against the source first"
  is brief §4.
- On step 5, German drops "ChangeLens überprüft das nicht", because the label right below says it verbatim:
  „Kundenfreigabe dokumentiert (von ChangeLens nicht überprüft)“. English step 5 is unchanged, since it had room.
