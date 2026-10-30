# ADR 0007: Same PDF engine (PDFium) on the backend and the device

**Status:** Accepted, verified by D-15 (2026-10-30)

## Context

Evidence highlights on the phone must line up with locators computed on the server. Different engines can order and position text differently.

## Decision

Parse PDFs with `pypdfium2` on the backend and render with `pdfrx` (PDFium-based) on the device.

## Consequences

One text engine on both sides. If coordinates still diverge, the parsed-text evidence view is the fallback.

## Links

03 §1.1; 05 D-15. Process for changing this record: `docs/SOP.md`.
