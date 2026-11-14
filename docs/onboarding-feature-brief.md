# Onboarding feature brief

Source material for designing ChangeLens onboarding. Extracted 2026-11-13 from
`PRODUCT.md`, `README.md`, `docs/02-mvp-spec.md`, `app/lib/screens/` and the English
string catalog `app/lib/l10n/app_en.arb` (branch `m1-iphone`). Quoted strings are the
exact in-app wording, so onboarding copy can reuse them and match what users see next.

Rule for this brief: **only section 1–6 may appear in onboarding.** Section 7 lists
features that are planned, not built, and must not be promised.

---

## 0. Where onboarding sits (owner, 2026-11-13)

First launch: **Sign-in → Onboarding (once) → Projects.**

- Sign-in is the very first screen, before any onboarding content
  (`docs/02-mvp-spec.md` §1 step 1). Methods: email one-time code, Google, Sign in with Apple.
- Onboarding runs once, right after the first successful sign-in. It shows only after
  sign-in has succeeded, so it doesn't need to explain accounts.
- Returning user with a valid session → straight to Projects.
- Expired session → back to sign-in, not to onboarding.
- Sign-in states to design before onboarding (`docs/ui-ux-handoff.md` §5, I-18): signed out,
  loading, cancelled, error, expired session, and `link_required` ("sign in with your
  usual method to link").
- Sign-in is **not built yet** (I-8, I-18). Development builds still connect through
  Developer settings, which stay development-only.

## 1. What the app is (the one-line answer)

- Core question: **"What changed since the last version of the brief, and which changes matter?"**
- Promise: catch a changed requirement before you deliver the wrong thing.
- Who it is for: web and design freelancers and small studios handling revised client briefs.
- Home screen tagline (in app): **"Compare briefs. Check the source."**
- What it looks at: changes in **deadlines, deliverables, responsibilities, approval
  wording and budget** (plus "Other").

Do not claim time savings, accuracy rates, customer proof or superiority over other
tools (PRODUCT.md, Positioning).

## 2. The mental model users need

Four ideas carry the whole product. Each is a candidate onboarding card.

| # | Idea | What the user should understand | In-app wording to echo |
|---|---|---|---|
| 1 | **You set the context** | You choose which version is earlier and which is newer. The app never guesses the order from upload time or file names. | "ChangeLens never guesses the order from upload time or file names. Choose it yourself." |
| 2 | **Tell it what the newer version is** | Is it a complete replacement, a partial update, or are you not sure? This changes how missing items are reported. | "What is the newer version?" |
| 3 | **Every finding shows its source** | Each change comes with the quoted passages from both versions. You can open the PDF page with the passage highlighted. | "Compare briefs. Check the source." · "Show in document" |
| 4 | **Your review is not client approval** | Confirming a finding means *you* checked it. A client's approval is a separate record you add yourself, and ChangeLens does not verify it. | "Client approval recorded (not verified by ChangeLens)" |

## 3. The core flow, step by step

### 3.1 Projects (home)

- Screen title "Projects", tagline "Compare briefs. Check the source."
- Primary button: **"Compare two briefs"**.
- A project groups the versions, comparisons and reviews for **one client engagement**.
  Empty state: "No projects yet. Create one for each client engagement."
- "New project" asks for "Project name" and "Client (optional)".

### 3.2 Versions (inside a project)

- Two ways to add a version: **"Paste text"** or **"Pick a PDF"**.
- Each version gets a label, e.g. "Brief v1, 3 Oct".
- Empty state: "No versions yet. Import the earlier brief first, then the newer one."
- Versions are frozen: "Imported versions are kept exactly as imported and cannot be
  edited. Import a new version instead."
- Status per version: "Waiting to be read" → "Ready", or "Rejected: {reason}".

### 3.3 Compare (one screen, the only place a comparison starts)

- Two slots: **"Earlier version"** and **"Newer version"**. Each takes an existing
  version or a fresh paste/PDF right there.
- **"Swap earlier and newer"** flips them.
- Scope question **"What is the newer version?"**, nothing preselected:

  | Option | Hint shown | What it means for the report |
  |---|---|---|
  | **Complete replacement** | "A full brief that replaces the earlier one." | Items missing from the new brief are reported as "Not in the replacement". This never means the obligation is cancelled. |
  | **Partial update** | "Unmentioned items are not addressed. This does not confirm whether they still apply." | Items the update does not mention are "Not addressed": neither removed nor reconfirmed. |
  | **Not sure** | "It is unclear whether the rest still stands." | Missing items are marked "Uncertain" and go to *Needs your review*. |

- **"Start comparison"** stays disabled until both slots and the scope are set
  ("Choose both versions and the scope to continue.").
- You don't have to wait: "Start sends both inputs together. You can leave this screen
  once the comparison is reading." A version still being read doesn't block Start.

### 3.4 Processing

- States: "Reading versions" → "Queued" → "Processing" → "Complete".
- Also possible: "Partial: some content could not be processed" or "Failed".
- "You can leave this screen and return to the comparison from its project."
- Updates arrive by polling while the screen is open. There are no push notifications.

### 3.5 Report ("What changed")

- Header shows the version pair ("Brief v2 → Brief v3") and **"Your review · X of Y"** progress.
- **Topic filters**: All topics, Deadlines, Deliverables, Responsibilities, Approval
  wording, Budget, Other, each with a count.
- Groups:
  - **"Changes"**: the material findings.
  - **"Needs your review"**: uncertain findings. Shown across all topics, so a
    filter never hides them.
- **"Selected summary — N other differences, including presentation-only edits"**
  links to **"All differences"**: the full list, including "Other text differences"
  (text no finding explains, such as headings or greetings) and "Moved or reformatted".
- Warnings stay visible at the top when they apply:
  - "Some content could not be processed, so this report may be incomplete."
  - "A document contains hidden text. It was left out of the comparison."
  - "N findings withheld: their evidence could not be checked."
  - "The cost limit was reached; some explanations use standard wording."

### 3.6 Finding

- "Finding X of Y", topic colour block, change type and category.
- **Change types** (glossary for onboarding):

  | Label | Meaning |
  |---|---|
  | Added | New in the newer version |
  | Changed | Different value in both, both values shown |
  | Not in the replacement | Missing from a complete replacement, not cancelled |
  | Not addressed | A partial update didn't mention it |
  | Uncertain | Can't tell. Needs your review |
  | Reworded | Same meaning, different wording |

- **Evidence**: the quoted Earlier and Newer passages, each with how it was located:
  "Highlight located", "Text fallback" or "Text-only source".
- **"Show in document"** opens the source, with a toggle between **"PDF page"** (passage
  highlighted) and **"Readable text"**. If the highlight can't be placed, the app says so:
  "The highlight could not be placed in the PDF, so the parsed text is shown."

### 3.7 Your review

- Actions: **Confirm**, **Correct**, **Dismiss**, **Add note**.
- **"Confirm and next"** moves to the next finding. You don't need to open the page,
  because both quotes are already on screen. Uncertain findings stay put after Confirm.
- If a quote comes from the text fallback, a warning sits above Confirm: "A PDF
  highlight could not be placed. Review the quoted text before confirming."
- **Correct** opens a sheet (change type, category, explanation): "Your correction is
  saved as a new revision. The original finding is kept."
- States shown: "Not reviewed yet", "Confirmed by you", "Corrected by you", "Dismissed by you".
- **History** lists every revision and note.

### 3.8 Client approval (separate record)

- Section "Client approval", button **"Record client approval"**.
- You paste the evidence (e.g. an e-mail excerpt), who stated it, and the date.
- Saved as **"Client approval recorded (not verified by ChangeLens)"**.
- Hint: "Record only what someone stated, for example a pasted e-mail. Reviewing a
  finding never records approval."

### 3.9 Housekeeping

- **Delete project** removes its documents, comparisons and reviews: "This cannot be undone."
- English and German UI; follows the system light/dark theme.

## 4. Trust and privacy points (confidence builders)

All implemented, so all safe to state:

- **No guessing**: order and scope always come from you.
- **Quotes are checked**: every quoted passage is verified against the source before it
  is shown. Findings whose evidence can't be checked are withheld, with a count.
- **No made-up absence quotes**: for a missing item, the app shows the earlier passage.
- **Uncertainty is visible**: uncertain findings get their own group and the orange "?" mark.
- **Nothing hidden**: the summary always links to every other difference.
- **Originals are kept**: imported versions can't be edited, and corrections are new revisions.
- **Instructions inside documents are ignored**, and hidden text is flagged and excluded.
- **No document content on the device**: nothing cached offline, an app-switcher privacy
  cover, and no document text in logs or analytics.

Needs confirmation before use in copy:

- **30-day retention after last use** is built in the backend, but the exact meaning of
  "last use" is an open decision (PRODUCT.md, Open Decisions). Not yet surfaced in the app.

## 5. What users must know to avoid failure (set expectations early)

- **Inputs**: pasted text, or a PDF **with selectable text**. Scanned PDFs are rejected
  ("the PDF has no selectable text. Use a text-based PDF or paste the text.").
- **Limits**: about 15,000 words per input; PDFs up to 20 pages and 10 MB. Over-limit
  inputs are rejected with a message naming the limit.
- **Online only**: evidence loads from the server and isn't stored offline.
- **Language**: the UI is English and German. Comparison quality is measured on English
  briefs only. German extraction is unmeasured, so don't promise it.
- **Not legal advice, not a workflow tool**: no inbox integration, no messages to
  clients, no merged "final spec".

## 6. Design vocabulary (so visuals and copy agree)

From DESIGN.md / README:

- Pastel colour blocks mean **one thing only: the finding's topic**.
- Orange **"?" disc** = uncertainty.
- **Lime marker** = new or quoted.
- **One black button per screen** = the primary action (e.g. Start comparison,
  Confirm and next).
- Short decisions (correct, note, approval) open as **bottom sheets**.

## 7. Do NOT show in onboarding (planned, not built)

| Feature | Status |
|---|---|
| Sign-in (email code, Google, Sign in with Apple), account linking, in-app account deletion | Planned for v1 (I-8, I-18). The app currently uses developer settings. Sign-in comes *before* onboarding (§0), so it is not onboarding content. |
| Screenshot / camera / photo import | Gated on ≥ 95% highlight placement. Not available. |
| Import via the OS share sheet | Planned after launch |
| Free-tier allowance, subscriptions, restore purchases | First release is free (O-20). Allowances aren't implemented. |
| Suggesting an order from dates in the text | In the spec, not built |
| Share links / shared report snapshots | Deferred after v1 |
| Push notifications | Deferred. v1 polls. |
| Teams | Deferred |
| DOCX import | Not supported. Export to PDF. |

## 8. Suggested onboarding beats (derived, for the designer to accept or reject)

1. **Promise**: "What changed since the last version, and which changes matter?"
2. **You set the order**: earlier vs newer is your call, never guessed.
3. **Tell it the scope**: replacement / partial update / not sure, and why it matters
   (partial updates don't cancel what they leave out).
4. **Read by topic, check the source**: topic filters, quoted passages, highlighted page.
5. **Uncertain stays visible**: the *Needs your review* group and the "?" mark.
6. **Your review ≠ client approval**: Confirm/Correct/Dismiss vs the separate,
   unverified approval record.
7. **Start**: "Compare two briefs" (text or text-based PDF).

Key definitions to make reachable after onboarding (e.g. info sheets on the compare
and finding screens): the three scope options, the six change types, the three
evidence modes, and "Selected summary".
