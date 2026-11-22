# ChangeLens · Implementation handoff: demo limit, wall and feedback

Nov 22, 2026 · @Gerrit

## Summary

**Built on 2026-11-22, not committed, not deployed, not checked on a device** (backend, migration `0012_demo_limit`, app; details in [`../backend/README.md`](../backend/README.md) §15). The rest of this summary is the brief as it was written. This handoff records the owner's decisions of 2026-11-22 for the demo period inside the app: a lifetime limit of three comparisons, the wall that follows, and the feedback form on it. The landing page is a separate piece ([`landing-page-handoff.md`](landing-page-handoff.md)).

- **Gate 0 is lifted** for this work (owner, 2026-11-22): build it.
- **It replaces three planned designs for the demo period:** the monthly allowance with a ledger ([`api-contracts-draft.md`](api-contracts-draft.md) section B), the codes-only feedback (C2) and the price-range survey (C3). Those sections now say so.
- **One rule changes:** feedback had no free text, so that no document content could end up in it (AC-23). The owner now wants two text fields. The rules under "Free text" keep that risk small.

## Decisions (owner, 2026-11-22)

| Topic | Decision |
| --- | --- |
| Limit | Three comparisons per account for its lifetime. Failed runs do not count |
| Wall | After the third comparison, new comparisons are blocked. Existing reports stay readable |
| Demo channel | TestFlight and a Play closed test. The word "demo" is allowed there |
| What to learn | First: what is missing or should be better, from the user's view. Second: what they would pay per month |
| "What is missing" | A choice from predefined answers plus "Other". "Other" opens a required text field |
| "Anything else?" | An optional text field for everyone, under the choice |
| Price | "What would you pay per month for the full version?" with nothing, €5, €10, €15, more than €15, not sure, under a short plan description |
| Where | At the wall, and in Settings at any time. Once per account |
| Discount | Earned when the choice and the price are filled in ("Other" with its text). One early-bird discount per person; it does not stack with the list sign-up. No percentage or price is stated |
| Not wanted | Thumbs on single findings, the price-range survey, a prompt after every comparison, judging whether an answer is useful |

## Constraints

- **Feedback never unlocks comparisons.** Apple's rule 5.1.1 forbids making features depend on personal details, and the owner wants the wall to be final. The wall has no path back to Compare.
- **The discount for feedback is not promised yet.** TestFlight forbids distributing to testers "in exchange for compensation of any kind"; whether a discount counts goes to the legal review. Until it is cleared, the app collects the feedback and says nothing about a discount for it. A server setting switches the sentence on (Backend, 4).
- **No steering to a purchase outside the app** (Apple 3.1.3). The wall may say the full version is coming; it names no price, no store and no way to buy. The price question is research: the form says so and that nothing is charged.
- **No invented claims** (`PRODUCT.md`, kept private): no date, no percentage, no accuracy or time-saving claim.
- **Google Play's policies were not checked.**

## Backend

### 1. Counting and the limit

- **Setting:** `CHANGELENS_DEMO_COMPARISON_LIMIT`, default `3`; `0` switches the limit off.
- **Used:** one row per comparison that reached `complete` or `partial`, in a new tenant-scoped table (for example `demo_comparisons`: tenant, comparison ID unique, time). The worker writes it in the same transaction that sets the terminal status. It has no foreign key to `comparisons`, so deleting a project or the 30-day retention cannot give comparisons back; `comparison_cost_tombstones` can't serve here because it holds no status. The rows go with the account (`DELETE /me`).
- **In flight:** the tenant's comparisons in `waiting_for_versions`, `queued` or `running`. They hold a place, or three could be started at once and all complete.
- **Admission:** in `create_confirmed` (`backend/changelens/api/comparisons.py`, at the I-14 marker comment), after the idempotent replay has returned and next to the spend-cap check. Under a per-tenant lock: if `used + in flight >= limit`, answer `403 demo_limit_reached` with `{"used", "limit"}` (as built, also `in_flight`). Nothing is written and nothing is charged. `403`, not `429`: waiting does not help.
- **Not counted:** a failed comparison, a rejected input, an idempotent retry. A failed run frees its place.
- **Existing data:** the migration counts existing `complete` and `partial` comparisons, so the owner's test accounts start at their real number.
- **Known gap, accepted:** a deleted account can't be re-created under the same identity, but a new email address gets three new comparisons. The sign-up cap per IP is the only brake.

### 2. Reading the state

`GET /me/demo`, and the same object as `demo` in the `POST /session` response next to `onboarding` and `consent`, so the first screen needs no extra call:

```jsonc
{ "limit": 3, "used": 2, "in_flight": 0, "remaining": 1,   // remaining = max(0, limit - used - in_flight)
  "feedback": { "submitted": false, "discount_offered": false } }
```

With the limit off, `limit` is `null` and the app shows no demo line and no wall.

### 3. Feedback

`POST /me/demo-feedback` → `201`. A second one from the same account → `409 already_answered`.

```jsonc
{ "missing": "share_report",        // required; one of the codes below
  "missing_other": null,            // required text when missing = "other", else must be null
  "anything_else": null,            // optional text
  "price": "eur_10" }               // required; one of the codes below
```

- **`missing` codes:** `screenshot_import`, `more_file_types`, `share_report`, `better_accuracy`, `faster_results`, `team`, `other`.
- **`price` codes:** `eur_0`, `eur_5`, `eur_10`, `eur_15`, `eur_over_15`, `not_sure`.
- **The plan the price refers to** is fixed on the server (`individual_20_v1`, the offer text already written in the contract draft's old C3): one person, 20 comparisons a month, pasted text or PDFs with selectable text, source evidence, review and project history. The response stores that ID with the answer, so later answers to a changed offer aren't pooled with these.
- **Storage:** one row per account in a tenant-scoped table with RLS, deleted with the account.
- Unknown fields and unknown codes are `422 invalid_request`. Error bodies never echo input.

### Free text

- `missing_other`: 20 to 500 characters after trimming. `anything_else`: up to 500.
- Control characters are removed; the text is stored as written otherwise. As built: line breaks are kept (as `\n`), because both fields take several lines.
- It is never logged, never part of an event or a count, and never shown to another user.
- The form asks people not to paste text from their documents. Nothing checks this; the data inventory and the privacy text say that these two fields can hold whatever the person typed.
- Anything at or above the minimum counts. No quality check.

### 4. The discount

- **No new record.** A submitted feedback row is the eligibility. The list sign-up is the other route (`early_bird_signups`, confirmed).
- **"Does not stack" is applied when a discount is redeemed,** which needs billing and does not exist. The backend has no email address for an account (Logto holds it), so nothing can be matched today. Record this as open; build nothing for it.
- **Setting:** `CHANGELENS_DEMO_FEEDBACK_DISCOUNT`, default off. `discount_offered` in the state is its value. Off: the app shows the feedback form with no word about a discount. On, after the legal answer: the app adds the discount sentence.

### 5. Records in the same change

Migration with RLS that passes `test_rls_static.py`; `errors.py` titles for `demo_limit_reached`; `docs/data-inventory.md` (two tables, the two text fields); both privacy texts (the feedback form, its legal basis as a voluntary answer); account deletion covers both tables; the contract draft's route list.

## App

- **Demo line.** Projects and Compare show one quiet `muted` line from the state: "Demo · 2 of 3 comparisons left". It is text, not a badge or a progress bar.
- **At the limit.** With `remaining` at 0, the Compare action on Projects and Project opens the wall instead of the Compare screen. If the API answers `demo_limit_reached` to a start (the state was out of date), Compare opens the wall and keeps the draft in memory as it does for other errors.
- **The wall** is a full screen with Back. Reports, findings and history stay reachable; only new comparisons are blocked.
  - Headline: the three demo comparisons are used.
  - Body: this is the demo period; the full version is coming soon.
  - Main action, the one black pill: "Give feedback". After feedback was sent it is replaced by a line saying so.
  - Secondary, an ink text button: "Join the early-bird list". It opens the landing page's form in the browser. The app handles no email address. Check first whether the app already has a package for opening a URL; a new dependency needs the owner's word.
  - With `discount_offered` on, one more sentence: giving feedback earns the early-bird discount, one per person.
- **The form** is a Calm screen or sheet that scrolls with the keyboard and large text.
  - "What is missing, or what should be better?" The owner said "dropdown"; in Calm Bold a choice opens a sheet of radio rows (`CalmSelectField`), nothing preselected.
  - "Other" shows the text field under it, required, with its minimum stated in a `muted` line.
  - "Anything else?", optional, with the line asking not to paste text from documents.
  - The plan description, then the price as radio rows, nothing preselected, and the line that this is a question, not an offer, and nothing is charged.
  - One main pill, "Send feedback", disabled until the required parts are filled, with a `muted` line saying what is missing.
- **Settings** gets one row, "Demo feedback", that opens the same form, or says that feedback was sent.
- **States:** sending, sent, a failed send (error kind, the entries kept), already answered on another device (treated as sent).
- **Strings** in English and German in the ARB files. German uses "du". New German strings need a native read.

## Tests

- **Limit:** the fourth comparison is refused; a failed third does not count; two starts at two used admit exactly one; an idempotent retry is not refused; deleting a project gives nothing back; limit `0` refuses nothing.
- **State:** `remaining` with in-flight comparisons; the `demo` object in `POST /session`.
- **Feedback:** each required part missing; "other" without text, with 19 and with 20 characters; a second submission; unknown codes; text over the limit; no free text in any log line.
- **Deletion:** `DELETE /me` removes the counted comparisons and the feedback.
- **App:** the demo line at 3, 1 and 0; Compare opens the wall at 0 and on `demo_limit_reached`; the form's disabled and enabled states; the layout matrix at 320 wide, German, largest text.

## Work to do, in order

1. Gate 0 is lifted (owner, 2026-11-22).
2. Backend: the counted-comparisons table and the worker write, the admission check, the state route and the session field. **Done.**
3. Backend: the feedback route and table, the discount setting, account deletion, the records. **Done.**
4. App: the demo line, the wall, the form, the Settings row. **Done**, with one difference: the app has no package that opens a browser, so the wall shows the list's address as selectable text with "Copy link" instead of opening it. A package needs the owner's word.
5. Device check on the iPhone and the Fairphone: reach the wall with three comparisons, send feedback, confirm reports still open.

## Open items for the owner

- **Legal:** whether a discount for feedback is allowed for TestFlight testers.
- **The list of predefined answers** and the plan description are the assistant's proposals, accepted on 2026-11-22; change them before the build if they should differ.
- **In-flight comparisons hold a place.** This is an engineering choice, not an owner decision; say so if a started but unfinished comparison should not count against the three.

## Definition of done

Ticked = built and covered by automated tests on 2026-11-22. Nothing here was checked on a phone.

- [ ] A fourth comparison can't be started, on either platform, and every earlier report still opens (backend and widget tests pass; the device check on both platforms is open)
- [x] A failed comparison leaves the count unchanged
- [ ] The wall offers feedback and the list, and no way back to Compare (built; the list is an address to copy, not a link that opens; opened from Compare after a refused start, Back returns to the draft, where Start opens the wall again)
- [x] Feedback can be sent once per account, from the wall or from Settings
- [x] No sentence about a discount for feedback appears while the setting is off
- [x] Free text appears in no log line and no count
- [x] Account deletion removes the feedback and the counted comparisons
- [x] Data inventory and privacy texts describe the two text fields (drafts, not legally reviewed)
- [x] Nothing is committed, pushed or released without the owner's word

## Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Check `git status` and HEAD first. Read `docs/demo-wall-handoff.md`, then `backend/changelens/api/comparisons.py`, `domain/spend.py`, `worker/__init__.py`, `api/session.py` and `api/consent.py`, and in the app `compare_screen.dart`, `projects_home.dart`, `settings_screen.dart` and `DESIGN.md`.
>
> Build the lifetime limit of three comparisons (completed and partial count, failed don't, in-flight hold a place), the state in `GET /me/demo` and `POST /session`, the feedback route with its two text fields, and in the app the demo line, the wall, the form and the Settings row. The discount sentence stays off behind its server setting. Feedback never unlocks a comparison. Free text is never logged.
>
> Run the backend unit and integration suites and `flutter analyze` and `flutter test`. Don't commit, push or deploy. Return the diff stat, the test output, screenshots of the wall and the form in both languages, and the open questions.
