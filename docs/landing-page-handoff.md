# ChangeLens · Implementation handoff: web landing page

Nov 22, 2026 · @Gerrit

## Summary

Nothing is built. This handoff records the owner's decisions of 2026-11-22 for the public landing page and for the demo period it announces, and the order to build the page in.

- **What:** a static landing page in English and German at `changelens.pixeltronic.dev`, served by the existing Caddy on the IONOS server.
- **Structure (owner's choice):** "Answer the scope question". The first screen shows two versions of a sample brief and asks the app's own question; the visitor's answer changes the findings shown.
- **Main action (owner's choice):** an email form for the early-bird list. It needs a new public backend endpoint with a confirmation mail before the page can go live.
- **State:** the working tree on `m1-iphone` is clean at `63036c6`. No page file, no Caddy change, no endpoint exists.
- **Not part of this handoff:** the in-app demo limit and wall. Their decisions are recorded below because the page's copy depends on them; they are built after the page.

## Decisions (owner, 2026-11-22)

| Topic | Decision |
| --- | --- |
| Demo limit | Three comparisons per account for its **lifetime**. Failed runs do not count |
| Wall | After the third comparison, new comparisons are blocked. Existing reports stay readable |
| Discount | One **early-bird discount**, no percentage or price stated. Signing up for the list and giving feedback each qualify; they **do not stack** |
| Feedback content | Decided in the interview of 2026-11-22: one form per account with a choice of what is missing ("Other" with text), an optional "Anything else?" field and a monthly price choice. All required parts filled in earn the discount. The form is specified in [`demo-wall-handoff.md`](demo-wall-handoff.md) |
| Demo distribution | **Test channels:** TestFlight and a Play closed test for the demo period; the store release follows with the full version. Whether a discount for feedback is allowed on TestFlight (its rule against distributing to testers "in exchange for compensation of any kind") goes to the legal review before the wall is built |
| Landing page host | `changelens.pixeltronic.dev` |
| Page structure | "Answer the scope question" (see The design) |
| Main action | Early-bird email form |
| Build order | Landing page first, then the demo limit and wall |

These decisions change earlier records, which are not yet updated:

- `PRODUCT.md` (kept private, not in the repository) records a free tier of three comparisons **per month**; [`api-contracts-draft.md`](api-contracts-draft.md) section B specifies 20 units a month with a ledger (T8 to T12). The lifetime cap replaces both for the demo period.
- The same draft, section C2, makes feedback codes only with no free text. The feedback interview may change that.
- [`tasks/plan.md`](../tasks/plan.md) Gate 0 says allowance and feedback work is not authorised. The owner's "build the landing page first" covers the page; ask before starting the demo limit.

## Constraints that shape the copy

Apple's App Review Guidelines were read on 2026-11-22. Google Play's policies were not checked.

- **2.2:** "Demos, betas, and trial versions of your app don't belong on the App Store – use TestFlight instead." The demo runs on the test channels, so the page may say "demo period". It shows no App Store or Google Play badge and does not say the app is in the stores; a test invitation link is added only when the owner supplies one.
- **5.1.1:** features must not depend on giving contact details. The email earns the discount and nothing else. Never write that signing up unlocks more comparisons.
- **3.1.3:** the app must not steer users to buy outside in-app purchase. The landing page is outside the app, so it may talk about the future paid version; the in-app wall has to be worded separately.
- **2.3.1:** no false price. The page states no price, no percentage and no launch date. "The full version is coming soon" is the whole claim.
- **`PRODUCT.md` (private), Positioning:** no customer proof, time savings, accuracy guarantees or comparisons with other tools. German extraction quality is unmeasured, so the German page must not promise it.
- **Marketing email in Germany:** the list needs a confirmed opt-in (double opt-in) and a line saying what the address is used for. The wording goes to the legal review that is already open (L4, L23 in [`tasks/launch-todo.md`](../tasks/launch-todo.md)).
- **Imprint:** [`docs/legal/imprint.md`](legal/imprint.md) is a draft with unfilled placeholders. A German site needs a filled imprint before it is public. The privacy text must name the early-bird list.

## The design

The visual system is Calm Bold, unchanged: read [`DESIGN.md`](../DESIGN.md) before any markup. The page uses its colour tokens, Roboto 400/600/700, the radii, one black main pill per view, and topic colours only for topics. Light and dark follow the system setting.

**The idea.** The page asks the visitor the one question the app insists on before it interprets anything: is the newer version a complete replacement, a partial update, or unknown? The answer changes what is reported. This shows the rule that silence is not a change, which a screenshot cannot show.

**First viewport, desktop (1440 wide).**

- Top bar: the Logo D lockup at the left; the language switch (EN / DE) and one ink text link to the early-bird form at the right. No other navigation.
- Headline in the `display` role: the product question from the README, "What changed since the last version of the brief, and which changes matter?"
- Under it, two brief cards side by side: the earlier version as a `surface` card, the newer version filled with `marker`, as on the app's Compare screen. Each shows a short excerpt of the sample brief. The newer excerpt is silent about one item the earlier one names.
- Under the cards, the scope question with three radio rows, nothing preselected, in the app's wording (`scopeComplete`, `scopePartial`, `scopeUnknown` in `app/lib/l10n/app_en.arb` and `app_de.arb`).
- Choosing an answer reveals the findings for that scope below the question: the changed items as topic-coloured tiles with their quoted passages, and for the silent item a different result per scope. Complete replacement: the item is no longer in the brief, shown as needing review, never as cancelled. Partial update: it is reported as "Not addressed", neither removed nor reconfirmed, on a plain card (the app's `defScopePartial`). Unknown: it stays uncertain, with the dashed `review` border and the "?" disc.
- The early-bird pill is visible without scrolling at 1440 × 900.

**First viewport, phone (390 wide).** The same order in one column. The two brief cards stack, earlier above newer. The scope rows keep a 48 px minimum target.

**Below the first viewport, in this order.**

1. How it works: the four steps from the README, in its words.
2. What ChangeLens does not do: the three points from the README.
3. The app: the screenshots in `docs/screenshots/`, light, with the README's alt texts. The German page uses `finding-de.png` where one exists.
4. Demo period and early bird: the demo allows three comparisons per account; the full version is coming soon; people on the list get an early-bird discount on it; one discount per person. The sentence that giving feedback in the app also qualifies is added only after the legal review clears it for TestFlight testers.
5. The early-bird form.
6. Footer: imprint, privacy policy, terms, the language switch, and the line that the example is synthetic.

**Rules for the example.**

- The sample brief is synthetic and labelled as an example next to it. Use the "Cedar website" scenario the screenshots show, so the page and the screenshots agree.
- Quotes in findings match the excerpts on the page word for word. No invented absence quote: the silent item's result shows the earlier passage only.
- The three results are authored in the page, not computed. The page must not suggest that the visitor's own text is being compared, and it sends nothing anywhere when a scope is chosen.
- The findings area works without scripting: the scope rows are real radio inputs and CSS shows the result for the checked one. Nothing is preselected.

**Motion.** Findings enter over 180 ms with the small translation `DESIGN.md` describes. With reduced motion they appear at once. Nothing loops.

**Copy rules.** Sentence case, no exclamation marks, no emoji, calm factual wording. Take sentences from [`README.md`](../README.md) where it already says the thing.

The chosen layout, measures, wording and results are in [`landing-page-direction-a-handoff.md`](landing-page-direction-a-handoff.md) (direction A, "Question first"), which adds to this handoff.

## Technical decisions

- **Static files, no framework and no build step.** Plain HTML, one CSS file and one small script for the scope answer and the form. Not a Flutter web build.
- **Location in the repository:** a new top-level folder `web/` with `index.html` (English), `de/index.html` (German), `site.css`, `site.js` and `assets/`. Each file stays under 500 lines (project rule; `scripts/ci.ps1` checks files under `docs` and `scripts` and all Markdown).
- **No third-party requests.** Roboto and the logos are self-hosted: copy the three `woff2` files, `OFL.txt` and the SVGs from `deploy/ionos/brand/`. No cookies. Measurement is first-party only (see Measurement); the Umami tracker is served from the page's own host.
- **Language:** two separate documents with `lang`, `hreflang` links and a visible switch. No automatic redirect by browser language.
- **Legal pages:** the five texts in `docs/legal/` are published under the same host once L23 fills and reviews them. Until then the footer links are placeholders and the site is not public.
- **Caddy:** a new site block `changelens.pixeltronic.dev` in `deploy/ionos/Caddyfile` with `import common`, a `file_server` on a new read-only mount, and a cache header for `assets/`. The `/changelens-brand/` block on the auth host is the pattern. Add the mount to the `caddy` service in `deploy/ionos/compose.yaml`.
- **DNS:** an A record (and AAAA if the server has IPv6) for `changelens.pixeltronic.dev` to the IONOS server. Caddy gets the certificate by itself. This is an owner step.

## The early-bird endpoint (backend, needed before go-live)

The page ships with the form; the form posts to an endpoint that does not exist yet.

- `POST https://api.pixeltronic.dev/early-bird`, unauthenticated, JSON `{"email": "…", "locale": "en" | "de"}`, `extra="forbid"`. Always answers `202` with the same body, whether or not the address is already known, so the endpoint can't be used to test for addresses.
- Rate-limited per IP with the existing limiter (`limit_ip` in `backend/changelens/api/limits.py`). Add a stricter per-day scope for this route, like `limit_signup`. Since the security review of 2026-11-22 (`docs/security-review.md`, EB-1 to EB-13) there are also caps on mails per hour and day overall, per address and per pending row, and IPv6 clients are counted by network.
- CORS: allow `POST` from `https://changelens.pixeltronic.dev` only. The API has no CORS configuration today; check `backend/changelens/api/app.py` before adding it.
- Double opt-in: store the address as pending with a hashed single-use token, send one confirmation mail. Its link opens a small page with one button (`GET /early-bird/confirm?token=…` changes nothing, so a mail scanner can't confirm); pressing it (`POST`) confirms once and redirects to a confirmation section of the landing page. Unconfirmed rows are deleted after a short period; state the period in the privacy text.
- **Mail:** the API has no SMTP configuration. Logto sends the sign-in mails and the host monitor has its own (`deploy/ionos/env/monitor.env.example`). The API needs its own SMTP settings, and in `logto` mode a missing one must stop the process at start (the rule L11 set).
- Storage: a new table with a migration after `0008_consent_events`. It has no tenant: follow `rate_limit_counters` in `0005_limits.py` (RLS forced, no policy, access through functions only) and make `test_rls_static.py` pass.
- An address on the list is not an account. Matching a confirmed address to an account's discount and the "does not stack" rule belong to the demo-wall work. Unsubscribing exists (2026-11-22): every mail to the list must carry the removal link from `python -m changelens.early_bird_export` (`backend/README.md` §14).
- Add the record to `docs/data-inventory.md` and both privacy texts in the same change.

Until the endpoint is deployed, the form's script shows a plain message that the list is not open yet. It must not pretend the address was saved.

## Measurement

Decided by the owner on 2026-11-22: **Umami**, self-hosted, for visits and click events. Researched the same day; nothing is installed. Umami's facts below are from its documentation and release notes as read that day; check them against the pinned version when you build.

**Open before the tracker may run: consent.** Umami's tracker is a script that sends requests. The EDPB (Guidelines 2/2023) treats that as device access, the DSK guidance (v1.2, November 2024) does not say reach measurement is consent-free, and [`docs/legal/README.md`](legal/README.md) says to follow the EDPB where the two differ. Whether the tracker may run without consent goes to the legal review (L4). Until it is answered, the tracker stays off behind a build flag, and only the server-side counts below run.

**Server-side counts (no tracker, always on).** These count requests the page and the form make anyway, the project's tier A.

- The API counts early-bird submissions and confirmed addresses, per day and language. No address and no IP is part of the count.
- **Page-view log for the landing host (owner's decision, 2026-11-22).** Caddy writes no access log today; this adds one for `changelens.pixeltronic.dev` only. The API and Logto hosts stay without one.
  - **Kept per page request:** time, path, status, the three `utm_*` parameters, the referrer's host name, and a `bot` mark when the user agent is missing or names a crawler. Only the two pages are logged, not assets.
  - **Never written:** the client address and port, every header (so no user agent, cookie, language or referrer path), the rest of the query string, and TLS details.
  - **Built and tested locally on 2026-11-22** in the pinned Caddy image: the site block in `deploy/ionos/Caddyfile` drops all headers and adds the kept values as separate fields; `deploy/ionos/landing-stats.py` writes the daily totals and empties the raw log after 30 days. Not yet run on the server.
  - **Counted from it:** page views per day by language, referrer host and campaign. No unique visitors: that would need the address.
  - **Retention (owner, 2026-11-22):** raw lines for 30 days, daily totals after that.
  - **Records:** this changes the rule that Caddy writes no access log (03a P9, the comment at the top of the `Caddyfile`). Update that comment, `docs/data-inventory.md`, both privacy texts and `deploy/ionos/README.md` in the same change.

**Umami setup.**

- **One container** on the existing server, image pinned by digest like the others, with a `mem_limit`. Umami is MIT-licensed and needs Node and PostgreSQL only.
- **Database:** its own database and role on the existing Postgres 16, as Logto has. `postgres/init/10-logto-database.sh` runs only on an empty volume, so on the running server the role and database are created once by hand; write that step into `deploy/ionos/one-off-releases.md`. The database joins the nightly backup.
- **Settings:** `DATABASE_URL`, `APP_SECRET` (must be set explicitly since v3.5.0), `TRUSTED_PROXIES` for Caddy's fixed address, and the salt rotation set to daily (the default is monthly; the setting is `SALT_ROTATION`). A missing setting stops the container at start. Add an `env/umami.env.example`.
- **No third-party request.** Caddy serves the tracker script and its collect endpoint (`/api/send`) under a path of `changelens.pixeltronic.dev`, so the page still talks to its own host only. Nothing else of Umami is public.
- **Dashboard:** bound to `127.0.0.1` and reached through an SSH tunnel, like Logto's admin console. Change the default admin password at first start.
- **Do Not Track:** switch on the tracker's option to honour it (recalled as `data-do-not-track`; not checked on 2026-11-22, so confirm it in the pinned version's documentation). The tracker does not load without scripting. The page works the same without it.

**Events.** Names are at most 50 characters. Set them with `data-umami-event` and `data-umami-event-*` attributes; no document content, no email address and no free text goes into an event.

| Event | When | Properties |
| --- | --- | --- |
| page view | Automatic | language, referrer, `utm_*` |
| `scope-answer` | A scope row is chosen | `answer`: complete, partial or unknown |
| `list-cta` | The early-bird pill or the top-bar link is used | `place`: top, hero or form |
| `lang-switch` | The language switch is used | `to`: en or de |
| `list-submit` | The form is sent and the API accepted it | none |
| `list-confirmed` | The confirmation link is opened | none; sent by the API to Umami's `/api/send`, with no visitor data |

**What to read from it:** visits by source and language; the share of visitors who answer the scope question, and which answer; the funnel from visit to answer to submit to confirmed.

**Records to update with it:** `docs/data-inventory.md`, both privacy texts (name Umami, the daily-rotating hash and the retention period), and `deploy/ionos/README.md`.

## Work to do, in order

1. Write `web/index.html`, `web/de/index.html`, `web/site.css` and `web/site.js` to The design above. Author the Cedar excerpts and the three scope results once, in both languages for the interface text; the quoted brief text stays English, as in the screenshots.
2. Look at the rendered page at 1440 × 900, 1280 wide and 390 × 844, light and dark, in English and German, with each scope chosen and with scripting off. Check German headings for mid-word breaks.
3. Check keyboard use and a screen reader's reading order: the scope question is a radio group, the revealed findings are announced, the form has a label and reports errors in text.
4. Add the Caddy site block and the compose mount. Don't deploy.
5. Build the early-bird endpoint with its tests, the migration, the data-inventory row and the privacy-text lines.
6. Add the event attributes and the tracker tag behind its build flag (Measurement), then the Umami service, its Caddy path and its env example. Don't deploy, and don't switch the tracker on.
7. Owner steps: the DNS record, the filled imprint, the legal review of the list wording and of the tracker's consent question, the deploy.

## Open items for the owner

- **Legal review:** whether a discount for in-app feedback is allowed for TestFlight testers. The page mentions the feedback route to the discount only once this is answered.
- **Test invitation links** (TestFlight, Play closed test), if the page should offer them.
- **Imprint details and a contact address** for the footer and the confirmation mail's sender.
- **Sample brief:** whether the Cedar scenario is the right public example for freelancers and studios.
- **Tracker consent:** the legal answer on whether the Umami tracker may run without consent, or whether it needs an opt-in.
- **Records to update** once the demo limit is authorised: `PRODUCT.md`, `docs/api-contracts-draft.md`, `tasks/plan.md` and the private decision log.

## Definition of done

- [ ] The page renders without overflow at 1440, 1280 and 390 wide, light and dark, English and German
- [ ] Each scope answer shows its own result, and the silent item is never shown as cancelled
- [ ] With scripting off, each scope still shows its result and the form's state is honest
- [ ] The network panel shows requests to `changelens.pixeltronic.dev` only (and `api.pixeltronic.dev` on submit)
- [ ] No price, percentage, date, customer claim or store badge appears on the page
- [ ] Every file under `web/` has fewer than 500 lines and `scripts/ci.ps1` passes
- [ ] The early-bird endpoint has unit and integration tests, including the rate limit, the same answer for a known address, and token reuse
- [ ] Imprint, privacy policy and terms open from the footer in both languages
- [ ] Nothing is committed, pushed or deployed without the owner's word

Report back with: screenshots of the six views in step 2, the diff stat, the test output, and anything in the copy that needed a claim this handoff does not allow.

## Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Check `git status` and HEAD first. Read `docs/landing-page-handoff.md`, then `DESIGN.md` and `README.md`. Build the static landing page in a new `web/` folder: English at `web/index.html`, German at `web/de/index.html`, plain HTML, CSS and one small script, Calm Bold tokens, self-hosted Roboto and logos copied from `deploy/ionos/brand/`, no third-party requests.
>
> The first screen shows two excerpts of the synthetic Cedar brief and asks the scope question; each of the three answers reveals its own authored result. The item the newer version doesn't mention is never shown as cancelled. State no price, percentage, date or customer claim. The early-bird form posts to `POST /early-bird` on the API, which doesn't exist yet: until it does, the form says the list is not open.
>
> Render the page at 1440 × 900, 1280 and 390 × 844 in light and dark, in both languages, and with scripting off, and fix what you see. Then add the Caddy site block and the compose mount without deploying. Don't commit, push or deploy. Return the screenshots, the diff stat and the open questions.
