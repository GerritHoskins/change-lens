# ChangeLens · Implementation handoff: landing page, direction A (Question first)

Nov 22, 2026 · @Gerrit

## Summary

The owner chose direction A, "Question first", on 2026-11-22. This handoff adds the chosen design to [`landing-page-handoff.md`](landing-page-handoff.md); it does not replace it.

- **The base handoff still governs** the decisions, the constraints on copy, the technical decisions (static files in `web/`, no third-party requests, the Caddy block), the early-bird endpoint and the definition of done. Read it first.
- **This handoff fixes what the base one left open:** the layout, the measures, the example's exact wording in English and German, and the three authored results.
- **Nothing is built.** No file under `web/` exists. The design exists only as artboards on a canvas, and those were never rendered and checked by the designer: treat sizes as intent, and trust what you see in a browser.
- **Eight points depart from the base handoff**. All eight are settled as of 2026-11-22. They are listed under "Points to settle".

## The design reference

The design is on the canvas [ChangeLens landing page: three directions](https://claude.ai/artifact/6CaPbHWts4XeP9AAfLfbPX). Four artboards belong to direction A; the two marked "Not chosen" are B and C and are not to be built.

| Artboard | Width | What it shows |
| --- | --- | --- |
| [Landing A · Question first · EN (chosen)](https://claude.ai/artifact/6CaPbHWts4XeP9AAfLfbPX#artboard-Main) | 1440 | The English page, top to footer |
| [Landing A · DE](https://claude.ai/artifact/6CaPbHWts4XeP9AAfLfbPX#artboard-LandingA-de) | 1440 | The German page |
| [Landing A · phone · EN](https://claude.ai/artifact/6CaPbHWts4XeP9AAfLfbPX#artboard-LandingA-phone) | 390 | The English page in one column |
| [Landing A · phone · DE](https://claude.ai/artifact/6CaPbHWts4XeP9AAfLfbPX#artboard-LandingA-phone-de) | 390 | The German page in one column; the check for long German words |

- **Tweaks on every artboard:** `scope` (none, complete, partial, unknown) shows that answer's result; `dark` switches the theme. The artboards open on "unknown" so the review card is visible. The real page opens with nothing selected.
- **The artboards are fluid pages, not pixel specs.** Columns wrap by available width. The frame heights are estimates, so a frame may end in empty ground.
- **Fonts and images:** the artboards load Roboto from Google Fonts and the logos and screenshots from the canvas. The real page self-hosts all of them (base handoff, Technical decisions).
- **Visual system:** Calm Bold, from [`DESIGN.md`](../DESIGN.md) and the [design system page](https://claude.ai/artifact/V9325dymoruEtTngXEULo5). No new token is introduced.

## Layout

One centred column, at most 1240 px wide, with side padding that grows from 20 px on a phone to 48 px on a desktop. Sections are 80 px apart. Everything sits on `ground`; cards are `surface` with no border and no shadow.

**First viewport, top to bottom.** Each block is 28 px below the one before.

| Block | Desktop (1440) | Phone (390) |
| --- | --- | --- |
| Top bar | Logo D lockup 40 px tall at the left; EN / DE switch and the ink text link "Early-bird list" at the right. 24 px above and below | Same; the links wrap under the logo if they don't fit |
| Headline (`h1`) | 64 px, weight 700, line height 1.02, tracking -0.03em, at most 22 characters per line in English. The German headline has about 97 characters against 76: widen its measure to about 30 characters so it also stays at four lines | Scales down with the width to 34 px; hyphenation on |
| Brief cards | Two columns, 12 px gap. Earlier is `surface`; newer is filled with `marker` and uses `on-marker` text. Radius 28 px, padding 24 by 28 px. Title 17 px semibold, "Example · Brief v2" as the eyebrow, lines at 17 px | One column, earlier above newer |
| Scope question | Legend at 24 px bold. Three radio rows in one line, 12 px gap. Each row: `surface`, radius 24 px, at least 56 px tall, a real radio input, label at 17 px, hint in `muted` 14 px. Selected: 2 px `ink` border and a semibold label | The three rows stack |
| Early-bird pill | The one black pill of this view: 60 px tall, 32 px side padding, label "Join the list". Beside it, one muted line | The line wraps under the pill |
| Findings | Count line at 24 px bold. Three topic tiles in one line (radius 24 px, padding 20 px), then the result for the silent item, then the muted line that the example is synthetic | Tiles stack |

The pill must be visible without scrolling at 1440 by 900. If the rendered page pushes it below the fold, reduce the headline size before anything else.

By the stated measures the English first viewport needs about 860 of the 900 px, and the German one more without the wider headline measure. These are estimates from the numbers above, not a render: check both languages in a browser.

**Below the first viewport, in this order.**

1. **How it works:** four `surface` cards in a row (two by two on a tablet, one column on a phone). Each has the step number in the `display` size, the lead in 20 px bold, the body at 16 px.
2. **What ChangeLens deliberately does not do:** three `surface` cards in a row.
3. **The app:** four screenshots in a row at up to 260 px wide each, two by two on a phone, each with a caption and its alt text. A 1 px `line` border and a 24 px radius on each image.
4. **Demo period and early bird:** two columns. Left, the heading and four lines separated by `line` hairlines. Right, the form on a `surface` card with a 36 px radius: heading, labelled email field (56 px tall, radius 18 px, 1 px `control-border`), the black pill at full width, and the consent line. One column on a phone, the form last.
5. **Footer:** a `line` hairline, then the three legal links and the language switch at the left and the synthetic-example line at the right.

Every link and control is at least 44 px tall; the scope rows at least 56 px. The focus ring is 2 px `link` with a 2 px offset.

## The example and the three results

The example is the Cedar website brief from `app/test/fixtures/calm_scenario.dart`. Its sentences stay English on both pages and carry `lang="en"` on the German one, because they stand for document content.

**The two excerpts.**

| Earlier version · Brief v2 | Newer version · Brief v3 |
| --- | --- |
| The project budget is €4,800 excluding VAT. | The project budget is €6,200 excluding VAT. |
| Final files are due on 20 November 2026. | Final files are due on 27 November 2026. |
| The website includes five pages. | The website includes seven pages. |
| Hosting is provided by the client. | (no line: the newer version is silent about hosting) |

**Shown for every answer:** the count line and three topic tiles. Each tile has the eyebrow "Changed · topic", both quotes with their source labels, and the explanation, as the app's report tile does. There is no extracted value and no strike-through (point 6).

| Topic | Token | Old value | New value |
| --- | --- | --- | --- |
| Budget | `topic-budget` | €4,800 | €6,200 |
| Deadlines | `topic-deadlines` | 20 November | 27 November |
| Deliverables | `topic-deliverables` | five pages | seven pages |

Point 6 is settled: the old and new values in the table above are not shown as a headline; they only say what each tile is about. Each tile's explanation: Budget, "Project budget increased."; Deadlines, "Final delivery moved." (both from the Cedar fixture); Deliverables, "Page count increased." (new, written for this page). Explanations are report text: they stay English on both pages and carry `lang="en"` on the German one, like the quotes.

**The silent item, per answer.** Its card always quotes the earlier passage only, "Hosting is provided by the client.", labelled "Earlier · Brief v2". There is never a newer quote.

| Answer | Count line | Card for hosting | Card style |
| --- | --- | --- | --- |
| Nothing chosen | none | A `surface` line: "Choose an answer above. The findings shown here depend on it." No tiles | Plain |
| Complete replacement | "4 things moved · 1 needs a second look" | Group label "Needs your review"; title "Not in the replacement · Responsibilities"; body "Missing from a complete replacement. This doesn't mean it is cancelled." | 2 px dashed `review` border and the "?" disc |
| Partial update | "3 things moved" | Title "Not addressed · Responsibilities"; body "A partial update didn't mention it. It is neither removed nor reconfirmed." | Plain `surface`, no border, no disc |
| Not sure | "4 things moved · 1 needs a second look" | Group label "Needs your review"; title "Uncertain · Responsibilities"; body "ChangeLens can't tell. Check it yourself." | 2 px dashed `review` border and the "?" disc |

The word "cancelled" appears only in the sentence that denies it. The results are authored markup; nothing is computed and nothing is sent when an answer is chosen. Without scripting the page behaves the same: CSS switches the results (Behaviour and semantics).

## Copy

Interface text is English or German; brief quotes stay English. German uses "du". Every string in both languages is in [`landing-page-copy.json`](landing-page-copy.json). Take a string from the app's catalogue where the source column names a key, so the page and the app say the same thing. Strings marked "new" were written for this page: the German ones are unreviewed translations and need a native read before go-live.

| Where | English | German | Source |
| --- | --- | --- | --- |
| Headline | What changed since the last version of the brief, and which changes matter? | Was hat sich seit der letzten Version des Briefings geändert, und welche Änderungen sind wichtig? | `README.md`; German new |
| Top-bar link | Early-bird list | Early-Bird-Liste | new |
| Brief card titles | Earlier version / Newer version | Frühere Version / Neuere Version | `earlierVersion`, `newerVersion` |
| Brief eyebrow | Example · Brief v2 (earlier card) / Example · Brief v3 (newer card) | Beispiel · Brief v2 / Beispiel · Brief v3 | `onbExample` |
| Scope legend | What is the newer version? | Was ist die neuere Version? | `scopeQuestion` |
| Scope rows | Complete replacement / Partial update / Not sure, each with its hint | Vollständiger Ersatz / Teilweise Aktualisierung / Nicht sicher | `scopeComplete`, `scopePartial`, `scopeUnknown` and their `…Hint` keys |
| Pill and form button | Join the list | Eintragen | new |
| Line beside the pill | The full version is coming soon. People on the early-bird list get a discount on it. | Die Vollversion kommt bald. Wer auf der Early-Bird-Liste steht, bekommt einen Rabatt darauf. | new, from the base handoff's decisions |
| Count line | 3 things moved (partial update) / 4 things moved (complete replacement, not sure) | 3 Änderungen / 4 Änderungen | `reportCount` |
| Count line, second part | 1 needs a second look | 1 braucht einen zweiten Blick | `homeSecondLook` |
| Tile eyebrow | Changed · Budget / Deadlines / Deliverables | Geändert · Budget / Fristen / Leistungen | `typeChanged`, `topic…` |
| Quote labels | Earlier · Brief v2 / Newer · Brief v3 | Früher · Brief v2 / Neuer · Brief v3 | `sideEarlier`, `sideNewer` |
| Result titles | Not in the replacement / Not addressed / Uncertain | In der Ersatzversion nicht enthalten / Nicht angesprochen / Unklar | `typeRemoved`, `typeNotAddressed`, `typeUncertain` |
| Result bodies | See the results table above | Fehlt in einem vollständigen Ersatz. Das heißt nicht, dass es gestrichen ist. / Eine teilweise Aktualisierung erwähnt es nicht. Es ist weder entfernt noch bestätigt. / ChangeLens kann es nicht sicher erkennen. Prüfe es selbst. | `defRemoved`, `defNotAddressed`, `defUncertain` |
| Group label | Needs your review | Von dir zu prüfen | `groupNeedsReview` |
| Nothing chosen | Choose an answer above. The findings shown here depend on it. | Wähle oben eine Antwort. Welche Befunde hier stehen, hängt davon ab. | new |
| Under the findings | The Cedar website brief is a synthetic example. Nothing you choose here is sent anywhere. | Das Briefing „Cedar website“ ist ein erfundenes Beispiel. Deine Auswahl wird nirgendwohin gesendet. | new |
| Section headings | How it works / What ChangeLens deliberately does not do / The app / Demo period and early bird | So funktioniert es / Was ChangeLens bewusst nicht tut / Die App / Demo-Phase und Early Bird | `README.md`; German new |
| Four steps and three "does not" points | The README's sentences, unchanged | New translations, in `landing-page-copy.json` | `README.md`; German new |
| Under the screenshots | For iOS and Android, in English and German. The screens show the same synthetic Cedar brief. So far, comparisons have been tested on English briefs only. | Für iOS und Android, auf Englisch und Deutsch. Die Bildschirme zeigen dasselbe erfundene Cedar-Briefing. Vergleiche wurden bisher nur mit englischen Briefings getestet. | new; last sentence is `onbStartLanguage` |
| Demo lines | The demo allows three comparisons per account. / The full version is coming soon. / People on the early-bird list get a discount on the full version. / One discount per person. | Die Demo erlaubt drei Vergleiche pro Konto. / Die Vollversion kommt bald. / Wer auf der Early-Bird-Liste steht, bekommt einen Rabatt auf die Vollversion. / Ein Rabatt pro Person. | new, from the base handoff's decisions. Held back until the legal review clears a discount for feedback for TestFlight testers: "Giving feedback in the app also qualifies." / „Feedback in der App zählt ebenfalls.“ |
| Form | Join the early-bird list; Email address | Auf die Early-Bird-Liste; E-Mail-Adresse | new |
| Consent line | We send one email with a link to confirm your address. | Wir senden dir eine E-Mail mit einem Link, um deine Adresse zu bestätigen. | Placeholder: the final wording comes from the legal review (L4, L23) |
| Footer links | Imprint / Privacy policy / Terms | Impressum / Datenschutzerklärung / Nutzungsbedingungen | new |
| Footer line | The Cedar website brief on this page is a synthetic example. | Das Cedar-Briefing auf dieser Seite ist ein erfundenes Beispiel. | new |

The German screenshot alt texts are also new translations; they are in `landing-page-copy.json`. The German page uses `finding-de.png` for the fourth screenshot; the other three have no German version and show the English app.

The German step 4 quotes the app's label for a client approval: „Kundenfreigabe dokumentiert (von ChangeLens nicht überprüft)“ (`approvalRecorded`).

## Behaviour and semantics

Added by the audit of 2026-11-22. It settles the fallback, the motion and the language switch from the "Not designed" list, and names the form's states.

- **Switching results.** The three scope rows are real radio inputs in one `fieldset` with the legend. All four result states are in the markup, and CSS shows the one that matches the checked input (`:has(input:checked)`). With nothing checked, the "Choose an answer above" line shows. The page therefore works without scripting, and no fallback sentence is needed; this replaces the base handoff's rule of showing the partial-update result.
- **Announcement.** One polite live region holds the count line only. The script writes it when an answer is chosen, never on load. The tiles and the hosting card are not in the live region.
- **Reading order.** Headline, the two brief cards, the scope group, the count line, the pill, the findings. Each brief card and the findings area has a heading.
- **The "?" disc** is decorative. "Needs your review" carries the meaning in text.
- **Form.** `type="email"`, `autocomplete="email"`, `required`, a visible label. Its states: empty; invalid address (error kind, as text under the field, tied to it with `aria-describedby`); "the list is not open yet" (info kind, the state until the endpoint exists); sending (the pill disabled, its label unchanged); sent (info kind). The visual design of these states is still to do.
- **Language switch.** Two links, EN and DE, each with `lang` and `hreflang`. The current language has `aria-current="page"`. A switch lands on the same section of the other document.
- **Motion.** A result enters over 180 ms with an 8 px translation. With reduced motion it appears at once. Nothing else moves.

## Widths

- **Wrap by minimum width, not by fixed breakpoints.** The scope rows stay three in a line while each is at least 300 px wide and stack below that. The topic tiles follow the same rule at 280 px. The brief cards stay side by side down to 640 px.
- **Check at** 1440, 1280, 1024, 768 and 390 wide, and at 200% text size: nothing clipped, no sideways scroll.
- **Hyphenation** is on for German only. The English headline breaks between words.
- **The selected row** is laid out at its semibold width, so choosing it does not shift the row.

## Colour on fixed surfaces and dark mode

The `marker` card and the topic tiles keep their colour in both themes, so the text on them must not follow the theme.

- **All text on those surfaces is the fixed ink `#111114`** (`on-marker`, `on-topic`): titles, eyebrows, quotes, source labels and explanations. Never `muted` and never the theme's `ink` there. `muted` reads at 3.79:1 on the Deadlines tile in light and at 1.9:1 on the Budget tile in dark.
- **`muted`** is for `ground` and `surface` only: 5.9:1 or more in light, 7.7:1 on dark ground.
- **The review colour `#F05A1E`** is for the dashed border and the disc, not for text: 3.4:1 on light surface, 3.1:1 on light ground, 4.9:1 on dark surface.
- **Focus ring:** `link` reads at 5.7:1 on light ground and 8.1:1 on dark ground. Keep anything focusable off the `marker` card; the dark `link` reads at 2.0:1 there.
- **Unselected scope rows** differ from the ground by 1.1:1, so the radio's own outline in `control-border` (3.6:1) is what shows the control. Don't remove it.
- **Screenshots in dark:** use `report-dark.png` for the report. The other three have no dark version and stay light until they are retaken.
- Dark mode still has to be looked at on a render. These rules don't replace that.

## Loading

- **Fonts:** `font-display: swap` on all three weights, and a preload for the 700 weight only, which carries the headline. Each file is about 70 KB; subset them to Latin if that can be done without changing the glyphs used.
- **Images:** every screenshot has `width` and `height` (the files are 780 by 1688), `loading="lazy"` and `decoding="async"`.
- **Screenshots to retake before go-live:** `compare.png` (the newer slot is now filled) and `report.png` (it shows the old ink-bordered warning banner).

## Points to settle

Eight places where the design differs from the base handoff or from the app. Ask the owner before building them; each has a default if no answer comes. All eight are settled as of 2026-11-22: points 1 and 5 by the audit, and the owner accepted the defaults for 2, 3, 4, 6, 7 and 8. Build them as the table records.

| # | Point | The design shows | Why it differs | Default |
| --- | --- | --- | --- | --- |
| 1 | Partial update, silent item | A plain card titled "Not addressed · Responsibilities" | The base handoff says nothing is reported for it. The app does report it: `defScopePartial` reads "Items it doesn't mention are reported as 'Not addressed'". A page that says "nothing" would contradict the app | Keep the card. Settled 2026-11-22: the base handoff was wrong here and is corrected |
| 2 | Third changed item | A Deliverables tile, five pages to seven pages | The Cedar fixture's report has two prioritised findings (budget, deadline) and hosting. The pages sentence is in the fixture's text but not among its findings | Keep it; it shows a third topic colour. Accepted by the owner, 2026-11-22 |
| 3 | Limit sentence under the screenshots | "So far, comparisons have been tested on English briefs only." on both pages | Not in the base handoff. It states the limit instead of staying silent, in the app's own words (`onbStartLanguage`) | Keep it, on both pages. Accepted by the owner, 2026-11-22 |
| 4 | Result wording | The app catalogue's definitions (`defRemoved`, `defNotAddressed`, `defUncertain`) | The base handoff asks for README sentences. The catalogue has reviewed English and German for exactly these three cases | Keep the catalogue wording. Accepted by the owner, 2026-11-22 |
| 5 | Newer brief card | Filled with `marker` | This follows the base handoff. The app's Compare screen, shown in the screenshot further down the same page, draws the newer slot with a marker outline on `surface` | Keep the fill. Settled 2026-11-22: the app has filled the newer slot since 2026-11-21 (`DESIGN.md`, Compare). Only the `compare.png` screenshot is out of date and must be retaken |
| 6 | Value headline on the finding tiles | The old value struck through, an arrow, and the new value at 28 px bold | The app's report tile shows the two full quotes and the explanation. It has no extracted value and no strike-through (`DESIGN.md`: value headlines were not built; quotes are not struck through). The screenshots lower on the same page would show a different tile | Build the tile as the app draws it: eyebrow, both quotes with their labels, the explanation. No value headline. Accepted by the owner, 2026-11-22 |
| 7 | Count line | "3 things moved · 1 needs a second look" beside three tiles and a fourth card | In the app the item that needs a second look is one of the things counted (the Cedar report counts 3: budget, deadline, hosting). On the page the line reads as three plus one | Count as the app does: "4 things moved · 1 needs a second look" for complete replacement and not sure; "3 things moved" for partial update, with the "Not addressed" card outside the count. Accepted by the owner, 2026-11-22 |
| 8 | Where the result appears | The findings sit under the early-bird pill | At 1440 by 900 the findings start below the fold, so choosing an answer changes nothing the visitor can see | Keep the order. Once an answer is chosen, show the count line directly under the scope rows, above the pill; it is also the live region (Behaviour and semantics). Accepted by the owner, 2026-11-22 |

Decided since this handoff was written (owner, 2026-11-22): the demo runs on TestFlight and a Play closed test; the store release follows with the full version. The page shows no store badge. Still open with the owner: the feedback interview, the imprint details, whether Cedar is the right public example, and the legal answer on a discount for feedback.

## Work to do, in order

1. **Read** `docs/landing-page-handoff.md`, then `DESIGN.md` and `README.md`, then this handoff.
2. **Settle the eight points** as the table records them; the owner has answered all of them.
3. **Build the page** as the base handoff's step 1 says (`web/index.html`, `web/de/index.html`, `web/site.css`, `web/site.js`), to the layout and results in this handoff. All copy in both languages is in `docs/landing-page-copy.json`: use it as the source and delete it or keep it, as the owner prefers.
4. **Write what is not designed** (list below), keeping to Calm Bold and the base handoff's rules.
5. **Look at the rendered page** as the base handoff's step 2 says, and compare each view with its artboard. On the German phone view check these for overflow and mid-word breaks: the headline, "Teilweise Aktualisierung", "In der Ersatzversion nicht enthalten · Zuständigkeiten", "Datenschutzerklärung", "Nutzungsbedingungen".
6. **Get a native German read** of every string marked "new" before the page is public.
7. Continue with the base handoff's steps 3 to 6 (accessibility check, Caddy block, endpoint, owner steps).

**Not designed. You design these, and report them back with screenshots:**

- The form's states: a field error in text, "the list is not open yet" (the state until the endpoint exists), sent, and the confirmation section the email link lands on. Use the message kinds from `DESIGN.md`, "Messages (changed 2026-11-21)": error red, warning amber, info blue, each with its icon.
- The no-JavaScript fallback sentence that names the two other answers.
- The 180 ms entry of the findings, and its reduced-motion variant.
- Hover and pressed states for the pill, the links and the scope rows.
- The 1280-wide view. The layout is fluid, so it should follow, but nobody has looked.
- Dark mode was drawn through the tokens and never looked at. The newer brief card keeps `marker` with `on-marker` text in dark.
- The language switch's target and focus behaviour between the two documents.

Settled by the audit of 2026-11-22 (see "Behaviour and semantics" and "Widths"): the fallback without scripting, the entry motion, the language switch, the list of form states, and the rule for widths between 390 and 1440. Still to design: how the form states look, hover and pressed states, and the confirmation section.

## Definition of done

Everything in the base handoff's list, plus:

- [ ] The page matches the four direction A artboards in order, proportions and wording, in English and German
- [ ] The early-bird pill is visible without scrolling at 1440 by 900
- [ ] Each answer shows the count line, the three tiles and the card this handoff specifies; the hosting card never has a newer quote
- [ ] Brief quotes are English on both pages and marked `lang="en"` on the German one
- [ ] Every string comes from `docs/landing-page-copy.json` or the app catalogue; no claim was added that neither holds
- [ ] The eight points to settle are answered by the owner or reported as built to their defaults
- [ ] The undesigned states are built and shown to the owner as screenshots

- [ ] All text on the `marker` card and the topic tiles is the fixed ink, in light and in dark
- [ ] Choosing an answer is announced once, and the count line appears above the pill
- [ ] The page works with scripting off, with nothing preselected
- [ ] `compare.png` and `report.png` are retaken and show the current app

## Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Check `git status` and HEAD first. Read `docs/landing-page-handoff.md`, `DESIGN.md` and `README.md`, then `docs/landing-page-direction-a-handoff.md`. The owner chose direction A, "Question first": headline, two brief cards side by side (earlier on surface, newer filled with marker), the scope question as three radio rows in one line, the early-bird pill, then the findings as three topic tiles and one card for the item the newer version doesn't mention.
>
> Build the static page in `web/` exactly as the base handoff specifies, with the layout, results and copy from the direction A handoff. All strings in both languages are in `docs/landing-page-copy.json`; brief quotes stay English. The hosting item is never shown as cancelled and never has a newer quote. State no price, percentage, date or customer claim.
>
> Eight points differ from the base handoff: all are settled, so build them as the "Points to settle" table records. Design the states the handoff lists as not designed, using the message kinds in `DESIGN.md`. Render the page at 1440 by 900, 1280 and 390 by 844, light and dark, both languages, each answer chosen, and with scripting off; compare with the four artboards and fix what you see. Don't commit, push or deploy. Return the screenshots, the diff stat and the open questions.
