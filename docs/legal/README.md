# Legal texts (I-20): drafts

**Status: drafts written 2026-11-13 and accepted by the owner as the basis for legal review; not legally reviewed. Do not publish before review.** **Owner's decision, 2026-11-23:** the drafts are published on the landing page as they are, with their placeholders marked and `noindex`, so the footer links lead somewhere while the tracker runs; the review is still open. The pages are built from these files: edit a draft, run `python scripts/build_legal_pages.py`, commit both. Placeholders in `[SQUARE BRACKETS]` must be filled in. The texts describe the free launch (O-20): no in-app purchase, a fair-use allowance, and the analytics design below. If the analytics design, a processor, or a retention period changes, update the texts, `docs/data-inventory.md`, the App Store privacy labels and the Play data-safety form together (I-17).

| File | Content |
|---|---|
| `privacy-en.md` / `privacy-de.md` | Privacy policy (GDPR Art. 13, TDDDG § 25) |
| `terms-en.md` / `terms-de.md` | Terms of use for the free app |
| `imprint.md` | Impressum (§ 5 DDG), German with an English heading |

The German texts are the binding versions for users in Germany; the English texts are translations. The privacy policy and terms must be linked from the app (account screen and sign-up), from both store listings, and published as web pages.

## Analytics consent: research summary (2026-11-13)

Not legal advice. Sources are listed at the end; most commentary is secondary, so the reviewer should confirm against the primary texts.

1. **Two layers apply.** § 25 TDDDG (Germany's implementation of Art. 5(3) ePrivacy Directive) governs storing information on, or accessing information from, the user's device. The GDPR then governs the processing of any personal data that results. They are checked separately.
2. **§ 25 TDDDG has only two routes:** consent, or the exception for what is *strictly necessary* to provide the service the user asked for. Legitimate interest (Art. 6(1)(f) GDPR) cannot replace consent for the device-access step. German supervisory authorities (DSK guidance on digital services) do not treat audience measurement or analytics as strictly necessary.
3. **The EDPB reads "access" broadly.** Guidelines 2/2023 on the technical scope of Art. 5(3) (version 2.0, adopted October 2024) treat an app that is instructed to send information from the device (for example a tracking call or an SDK event) as access. The DSK view is narrower: passive server-side reading of data the device sends anyway falls outside § 25. Where the two differ, the safe path follows the EDPB.
4. **Third-party analytics or crash SDKs** (Firebase, Sentry, and similar) read and write device storage and identifiers, so they need prior consent. Reading the advertising ID always needs consent, and on iOS, tracking across other companies' apps also needs App Tracking Transparency.
5. **Server-side measurement of requests the app already makes to provide the service** (sign-up, creating and completing a comparison, saving a review, reaching the allowance) adds no device access beyond what is strictly necessary. Under the GDPR it can rest on legitimate interest (Art. 6(1)(f)) with a documented balancing test, data minimisation, pseudonymisation, a short retention period and a right to object.
6. **The Consent Management Ordinance (EinwV)**, in force since 1 April 2025, recognises consent-management services (PIMS). It is optional and does not change the rules above; recognised services are listed by the BfDI.

### Recommended design for D-18

| Tier | What | Legal basis | Consent screen |
|---|---|---|---|
| A, always on | Server-side counts derived from API requests the service needs anyway: account created, comparison created and completed, review saved (including `evidence_mode` and `page_opened` from I-26), allowance reached, last active day. Keyed to the account ID inside the backend only; reported in aggregate. No device identifiers, no extra requests from the app, no third parties | GDPR Art. 6(1)(f); no § 25 TDDDG access | No; disclosed in the privacy policy, with a right to object |
| B, opt-in | App-side usage events that exist only for analytics (screens viewed, report filters used, time to first comparison), sent to our own backend | Consent: § 25(1) TDDDG and Art. 6(1)(a) GDPR | Yes, off by default, asked once after sign-up, changeable in settings |
| Survey | The in-app "what is this worth to you" question and feedback form | The user's voluntary answer, Art. 6(1)(a) GDPR | The question itself is the choice; never required |
| Not used | Third-party analytics, advertising or crash SDKs, advertising IDs, cross-app tracking | — | — |

This needs no App Tracking Transparency prompt. App Store privacy label: "Usage Data: Product Interaction", linked to the user, not used for tracking; plus "Contact Info: Email Address" and "User Content: Other User Content" for the account and documents. Play data safety: "App activity" and "Personal info: Email address", collected, not shared, encrypted in transit, deletion on request.

Crash reporting is not in the launch build. If added later, treat it as tier B (opt-in), following CLIENT_TELEMETRY in 03a P10.

### Open points for the legal review

- Whether the tier-A balancing test holds, and the retention period for usage counts (draft: pseudonymous events 12 months, then aggregated).
- Liability wording in the terms for a free service under German law (§§ 307–309 BGB).
- Whether the terms may be changed by notice for existing users of a free service.
- Applicable supervisory authority (depends on the owner's federal state) and whether a data protection officer is required (not for a single operator below the § 38 BDSG threshold).
- The transactional email provider, once chosen (I-8), and its data processing agreement.
- That Apple and Google are currently certified under the EU-US Data Privacy Framework (privacy policy section 5), and the IONOS SE address.
- IONOS AI Model Hub data handling: confirm under the current IONOS DPA that prompts and responses are not stored or used for training.

### Sources

- [EDPB Guidelines 2/2023 on the technical scope of Art. 5(3) ePrivacy Directive, v2.0](https://edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf)
- [DSK guidance for providers of digital services (OH Digitale Dienste)](https://datenschutzkonferenz-online.de/media/oh/OH_Digitale_Dienste.pdf)
- [Covington summary of the EDPB draft guidelines](https://www.covingtonblogs.com/2023/11/20/edpb-issues-draft-guidelines-on-technical-scope-of-eprivacy-directive-storage-and-access-rules/)
- [activemind.legal on EDPB vs DSK on audience measurement](https://www.activemind.legal/de/guides/edsa-reichweitenmessung/)
- [Matomo: configuring analytics for TDDDG](https://matomo.org/faq/new-to-piwik/configure-matomo-analytics-for-tdddg-ttdsg-compliance/)
- [CMS on the Consent Management Ordinance (EinwV)](https://cms.law/de/deu/legal-updates/das-ende-der-cookie-banner-dienste-zur-einwilligungsverwaltung)
