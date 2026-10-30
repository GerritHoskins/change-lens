# ADR 0008: No document content stored on the device

**Status:** Accepted (2026-10-30)

## Context

A device cache would put client briefs outside deletion and the data inventory.

## Decision

No offline cache, no copies in the photo library, nothing kept by the share extension. Only auth tokens, in Keychain / Keystore. Push notifications carry IDs only.

## Consequences

No offline use in the MVP. Opening evidence needs a network connection.

## Links

03 §1.1, §6; AC-25. Process for changing this record: `docs/SOP.md`.
