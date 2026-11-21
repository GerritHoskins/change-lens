# Logto sign-in and sign-up branding: design and implementation plan

Prepared 2026-11-16. Repository `C:\Users\Gerrit\job-search\POCs\change-lens`, branch `m1-iphone`, baseline
`1f11f54`. Check `git status` and HEAD first. The untracked tool folders aren't yours. In a Linux shell over the
Windows checkout, about 400 files show as modified with no content change (CRLF): never stage those.

**Status 2026-11-20:** §4.1–§4.5 and §6 are implemented in the repository (`deploy/ionos/brand/`,
`deploy/ionos/logto/`, `scripts/logto/apply-branding.py`, Caddyfile, compose, runbook). §4.6 (`ui_locales`) is
still open.

**Status 2026-11-21:** applied to `auth.pixeltronic.dev` with `--apply`; the sign-in page was checked in a browser
at phone width, light and dark. The rest of §5 (code and MFA pages, real devices, English) has not been run.

Designs: https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr, row "Logto hosted pages". There are 7 artboards,
each with toggles for locale (en/de), dark and state.

## 1. What this covers, and why

Since I-8 S2 and S4, sign-in is split between two places:

| Where | What | Who draws it |
|---|---|---|
| Native app (I-18) | The sign-in screen, the Google and Apple sheets, `link_required`, the expired-session sheet | Flutter, Calm Bold (canvas row 1) |
| **Logto's hosted page** (`auth.pixeltronic.dev`, in the system browser sheet) | Email sign-in and sign-up, the email code, MFA (authenticator code, backup code), the one-time-token landing after Google or Apple, Logto's error page | **Logto 1.45 OSS**, branded by us |

The canvas's native artboards "Email entry", "Email code" and "MFA challenge" are now marked as superseded:
those steps run in Logto. This plan makes the Logto pages look like ChangeLens.

## 1a. Relation to the app implementation handoff

This plan is part of the wider app handoff,
[ChangeLens · Implementation handoff: complete the Calm Bold app](https://claude.ai/artifact/YLNtzUymXfHK5y5dnJA2Bq), a Claude Doc dated 2026-11-16 with
HEAD `1f11f54`. Read that Doc first for:
- the hard rules;
- the work packages WP-A to WP-G;
- the shared components, backend contracts and definition of done.

The Logto branding belongs to its **WP-A (sign-in and session)**.

Where the two disagree, **this plan wins**. It reflects I-8 S2/S4 as built and the logo decision of 2026-11-16.

| Doc says (WP-A and its tables) | Correct as of 2026-11-16 | Why |
|---|---|---|
| Native `sign_in_email_screen.dart`, `sign_in_code_screen.dart`, `mfa_screen.dart`, with states for invalid email, code cooldown/wrong/expired and MFA | **Don't build them.** "Continue with email" opens Logto's hosted page in the system browser sheet. Email, code, MFA and backup code are the Logto pages in §3 | I-8 S2: the app calls `POST /session` after a Logto browser sign-in. MFA is Logto's (S7: TOTP and backup codes) |
| Open conflict "MFA host: native or Logto-hosted" | **Resolved: Logto-hosted.** The `mfa*`, `email*` and `code*` copy goes to Logto custom phrases (§4.5), not `app/lib/l10n` | As above |
| Component `CalmCodeField` | **Not needed** in the app | Code entry is Logto's |
| `CalmLogoLockup` and every asset: "Logo A" | **Logo D (Aperture).** Lockup and favicon are in `docs/brand/`; the app lockup is the same mark plus the Roboto Bold wordmark | Owner decision 2026-11-16 (draft O-25, §8) |
| App icon and launch screen "regenerate from Logo A" | **Regenerate from Logo D** (mark only for the icon) | Same decision |
| Android Apple: "web flow through Logto or a backend code exchange" | **Backend code exchange** (`POST /session {provider, code, nonce}`). Logto's Google and Apple connectors stay unconfigured | I-8 S4 as built |
| After native Google or Apple: not covered | The app redeems the `one_time_token` in **one automatic Logto browser step** (the landing page in §3), with `login_hint`. Logto applies MFA there | I-8 S4 step 0 |
| Merge "the sign-in, consent, Settings and MFA keys (about 50)" from `docs/onboarding/*.arb` | Merge only the **native** keys: `signIn*`, `link*`, `session*`, `consent*`, `settings*`, `deleteAccount*`, `legal*`, `signOut`, `close`. **Skip** `email*`, `code*` and `mfa*` | Those screens are Logto's |

What stays as the Doc says: everything in WP-B to WP-G, the hard rules, the backend contract table (minus the
MFA row), and the definition of done. The layout matrix, accessibility and privacy checks also apply to the
Logto pages, as far as Logto's structure allows (§5).

The Doc itself still carries these WP-A points. Ask the owner whether to update the Doc too, so the two don't drift.

## 2. Decisions

| # | Decision | Status |
|---|---|---|
| 1 | **Logo D (Aperture)** is the ChangeLens logo | Owner, 2026-11-16. Recorded as O-29 in 06 |
| 2 | Stay on **free Logto OSS branding**: brand colour, logos, favicon, dark mode, custom CSS, custom phrases. No "Bring your UI" | Recommended. Since 1.45, a custom sign-in UI and removing Logto branding need a paid Self-Hosted Pro licence |
| 3 | **"Powered by Logto" stays** in the footer | Follows from 2. Don't hide it with CSS: it's a licensed feature |
| 4 | Fonts and logos come from **our own origin** (`auth.pixeltronic.dev/changelens-brand/`), never Google Fonts or a CDN | Privacy: no third-party request that reveals visitors' IP addresses. Same origin also avoids any CSP question |
| 5 | Terms and privacy: a **checkbox on Create account only** (Logto's "manual, registration only" agreement) | **Owner and lawyer** (I-20). The texts are unreviewed drafts. Until then the links point to the draft pages |

## 3. Design

Calm Bold inside Logto's structure. Logto draws the layout: logo and headline at the top, the form, the footer.
We change tokens, type and a few shapes.

| Element | Logto default | ChangeLens |
|---|---|---|
| Logo | none | Logo D lockup, 40 px tall, light and dark files (`docs/brand/`) |
| Favicon | Logto | Logo D mark, light and dark |
| Code, MFA and error pages (no logo slot in Logto) | none | Logo D mark, top right in the back-arrow row (owner, 2026-11-21; not on the canvas) |
| Brand colour (buttons, links, focus) | purple | ink `#111114`; dark `#F3F3EF` |
| Background, surfaces, text, borders, error | Logto neutrals | ground, surface, ink, muted, control-border, line, error (DESIGN.md) |
| Font | system stack | Roboto 400/600/700, self-hosted |
| Headline | 20 px, centred | 32/35 px bold, left-aligned (Calm Bold headline) |
| Primary button | 44 px, 8 px radius | 60 px pill (one black pill per screen) |
| Fields, code boxes | 8 px radius | 18 px radius; code boxes unchanged in shape |
| Links | brand colour | ink, underlined (Calm Bold secondary actions are ink) |
| Copy | Logto phrases | Logto phrases plus our overrides (§4.5), "du" throughout in German |

Accepted differences from Calm Bold:
- Focus rings use the brand colour (ink), not `link`. Logto ties focus to the brand colour, and a 2 px ink ring meets contrast.
- Logto's field style (label inside a notched outline) stays.
- The verification code uses Logto's six boxes.

## 4. Implementation

### 4.1 Brand assets

- Copy `docs/brand/changelens-logo-{light,dark}.svg` and `changelens-favicon-{light,dark}.svg` into a new
  `deploy/ionos/brand/`.
- These SVGs carry a provenance (C2PA) metadata block from the tool that wrote them. Keep it, or strip the
  `<metadata>` element; either is fine.
- Convert `app/assets/fonts/Roboto-{Regular,SemiBold,Bold}.ttf` to `deploy/ionos/brand/fonts/roboto-{400,600,700}.woff2`,
  for example with `fonttools ttLib.woff2 compress`. Bundle `OFL.txt` next to them, because the SIL OFL requires it.

### 4.2 Caddy

In `deploy/ionos/Caddyfile`, serve the folder on the Logto site, before the proxy:

```
auth.pixeltronic.dev {
	import common
	handle_path /changelens-brand/* {
		root * /srv/changelens-brand
		header Cache-Control "public, max-age=86400"
		file_server
	}
	reverse_proxy logto:3001
}
```

In `compose.yaml`, mount the folder into the caddy service: `- ./brand:/srv/changelens-brand:ro`.
`/changelens-brand/` isn't a Logto route. Check that with `curl -I` after deploy.

### 4.3 Logto branding (Console values, applied by script)

Use one script, for example `scripts/logto/apply-branding.py`, that calls the Management API with the
existing M2M app credentials, so the setup is repeatable and reviewable (03 §6: config in the repository,
secrets in files). It sets `PATCH /api/sign-in-exp` with:
- `color`: `primaryColor #111114`, `isDarkModeEnabled true`, `darkPrimaryColor #F3F3EF`.
- `branding`: `logoUrl` / `darkLogoUrl` = `https://auth.pixeltronic.dev/changelens-brand/changelens-logo-{light,dark}.svg`,
  `favicon` / `darkFavicon` likewise.
- `customCss`: the content of `deploy/ionos/logto/custom.css` (§4.4).
- `termsOfUseUrl`, `privacyPolicyUrl` and `agreeToTermsPolicy` (§2, row 5).

Keep the desired values in `deploy/ionos/logto/sign-in-experience.json`. The script only applies that file.

### 4.4 Custom CSS

The stylesheet is `deploy/ionos/logto/custom.css` (moved from `docs/logto-branding/` on 2026-11-20). It has three tiers:
1. **Theme variables** (`--color-*`, `--font-*`, `--radius`) under `html[data-theme] body`. Robust.
2. **Stable hooks**: Logto's own unhashed `logto_*` classes.
3. **FRAGILE**: four CSS-module suffix selectors, for the headline, the pill button, the focused code box and
   the mark in the back-arrow row.

Notes:
- The brand colour isn't in the CSS: Logto sets it inline on `<body>` from §4.3.
- In dark mode the CSS turns `--color-static-white` (the primary button label) to ink. Otherwise the label
  would be white on `#F3F3EF`.

### 4.5 Custom phrases

Apply `deploy/ionos/logto/custom-phrases.{en,de}.json` with `PUT /api/custom-phrases/en` and `/de`, from the same
script. Only the overridden keys are listed; the rest stay Logto's.

What they fix:
- **Calm Bold wording:** "Sign in with email" to match the native "Continue with email" button; "Terms of use"
  and "Privacy policy" in sentence case; "Confirm it's you" as in the app's MFA copy.
- **German spelling:** "Email" becomes "E-Mail-Adresse", and "Datenschutzrichtlinien" becomes
  "Datenschutzerklärung", the title of our draft legal text.
- **German "du":** Logto's German MFA texts switch to the formal "Sie".

Check every key path against the 1.45 phrase files (`packages/phrases-experience/src/locales/{en,de}`) before applying.

### 4.6 App side (I-18, for later)

- Open Logto with `ui_locales` set to the app's language. Otherwise Logto picks the browser's language, which can
  differ from the app's.
- The page follows the system light or dark setting. The app follows the system too, so they match.
- Nothing else changes: the native screen keeps Google, Apple and "Continue with email".

## 5. Verification

1. **Live preview** (Console → Sign-in experience). Check every page in EN and DE, light and dark:
   - sign in;
   - create account, with and without the checkbox ticked;
   - code entry, including the invalid-code and resend states;
   - authenticator code and backup code (needs a test user with TOTP);
   - the error page;
   - a toast in dark mode (the `--color-static-white` override).
2. **Network:** in the browser DevTools, Roboto and the logos load from `auth.pixeltronic.dev`. There are no
   requests to other hosts and no CSP errors in the console.
3. **Real devices:** iOS (ASWebAuthenticationSession) and Android (Custom Tab), each in EN and DE, light and dark,
   at the largest text size. Check that the page also works at 320 px width.
4. **Contrast:**
   - text on ground and on surface meets 4.5:1;
   - the button label meets 4.5:1 on ink (light) and on `#F3F3EF` (dark);
   - focus rings are visible.
5. **Compare with the canvas.** Report any deviation, with a screenshot.

## 6. Upgrade guard

Add one line to the "Logto upgrade" section of `deploy/ionos/README.md` (S7 runbook): after each upgrade, open the
Live preview and check the headline (left, 32 px) and the primary button (60 px pill). Those are the two
FRAGILE selectors. If they stop matching, the page falls back to Logto's layout with our colours and font, which is
ugly but still usable.

## 7. Out of scope

- "Bring your UI": a custom sign-in UI, Self-Hosted Pro only.
- Hiding "Powered by Logto".
- Google and Apple buttons on the Logto page: they're native, and Logto's connectors stay unconfigured (S4).
- The legal texts themselves (I-20).
- The app's launcher icon with Logo D: a separate task.

## 8. Records

- **Decision log:** the logo is recorded as O-29 in `06-decision-log.md` (2026-11-16).
- **PRODUCT.md:** "No logo was supplied" replaced with Logo D (2026-11-20). DESIGN.md already names Logo D
  (sign-in lockup, `CalmLogoMark`, `CalmLogoLockup`); it never carried the "no mark yet" line.
- **Calm Bold design-system page:** Logo section rewritten and a Logos group added with the `docs/brand/` files
  (2026-11-20).
- **Still open:** add the Logto branding to DESIGN.md as an implemented surface once §5 passes.

## 9. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD, and ignore line-ending-only changes.
> Read the app handoff Doc https://claude.ai/artifact/YLNtzUymXfHK5y5dnJA2Bq for the hard rules and the definition of done, then
> `docs/logto-branding-plan.md` (its §1a corrects the Doc's WP-A), then `deploy/ionos/README.md` and `deploy/ionos/Caddyfile`. Implement §4.1–§4.5:
> - copy the brand assets and convert Roboto to woff2 (with the OFL);
> - serve them through Caddy;
> - write `deploy/ionos/logto/sign-in-experience.json` and a script that applies branding, custom CSS and custom phrases
>   through the Management API.
>
> Check each custom-phrase key against Logto 1.45's phrase files. Don't deploy, apply to the live Logto, commit or push
> unless the owner says so. Run the script against the local Logto in `scripts/d8-logto` first. Return the diff stat,
> the script's dry-run output, and screenshots from the local Live preview in EN/DE, light and dark, compared with the
> canvas row "Logto hosted pages".

Related: [App implementation handoff (Claude Doc)](https://claude.ai/artifact/YLNtzUymXfHK5y5dnJA2Bq).

Sources: [Match your brand](https://docs.logto.io/customization/match-your-brand),
[Custom CSS](https://docs.logto.io/customization/custom-css),
[Bring your UI](https://docs.logto.io/customization/bring-your-ui),
[Logto v1.45.0 release](https://newreleases.io/project/github/logto-io/logto/release/v1.45.0),
Logto 1.45.0 source (`packages/experience`, `packages/phrases-experience`).
