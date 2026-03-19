# Asset Tax Engine Specifications

## Purpose

This folder freezes the first implementation baseline for Taxja's Austrian asset tax engine.

The goal is not to build a simple OCR add-on. The goal is to define a complete subdomain:

1. document recognition
2. tax policy classification
3. user-facing suggestion and confirmation
4. asset master creation
5. lifecycle handling for AfA, GWG, IFB, VAT, and disposal events

## Frozen Documents

1. `01-asset-master-schema.md`
2. `02-asset-recognition-contract.md`
3. `03-tax-policy-rules-matrix.md`

## Scope

This spec set covers Austrian business assets used by:

- Einzelunternehmer
- Freiberufler
- mixed users with business activity
- small businesses that need asset handling without full accounting ERP complexity

It explicitly supports the system strategy:

- system extracts first
- system classifies first
- user only confirms missing tax-critical facts
- silent auto-creation is limited to very high-confidence structured cases

## Non-Goals

- Not a complete statutory tax filing engine
- Not a full accounting ledger replacement
- Not a full payroll or HR module
- Not a final legal/tax opinion generator
- Not a full inventory management system

## Legal Anchor

This specification is aligned to Austrian tax treatment for:

- GWG / geringwertige Wirtschaftsgueter
- AfA / depreciation
- Halbjahres-AfA
- degressive AfA
- vehicle-specific treatment
- VAT / Vorsteuer relevance
- Investitionsfreibetrag
- duplicate and review risk handling

Primary official references used while drafting:

- [USP: Geringwertige Wirtschaftsgueter](https://www.usp.gv.at/themen/steuern-finanzen/steuerliche-gewinnermittlung/weitere-informationen-zur-steuerlichen-gewinnermittlung/betriebseinnahmen-und-ausgaben/geringwertige-wirtschaftsgueter.html)
- [USP: Abschreibung](https://www.usp.gv.at/themen/steuern-finanzen/steuerliche-gewinnermittlung/weitere-informationen-zur-steuerlichen-gewinnermittlung/betriebseinnahmen-und-ausgaben/abschreibung.html)
- [USP: Gesetzliche AfA-Saetze](https://www.usp.gv.at/themen/steuern-finanzen/steuerliche-gewinnermittlung/weitere-informationen-zur-steuerlichen-gewinnermittlung/betriebseinnahmen-und-ausgaben/gesetzliche-afa-saetze.html)
- [USP: Investitionsfreibetrag](https://www.usp.gv.at/themen/steuern-finanzen/steuerliche-gewinnermittlung/weitere-informationen-zur-steuerlichen-gewinnermittlung/betriebseinnahmen-und-ausgaben/investitionsfreibetrag.html)
- [USP: Vorsteuerabzug](https://www.usp.gv.at/themen/steuern-finanzen/umsatzsteuer-ueberblick/vorsteuerabzug.html)
- [USP: Formerfordernisse einer Rechnung](https://www.usp.gv.at/themen/steuern-finanzen/umsatzsteuer-ueberblick/weitere-informationen-zur-umsatzsteuer/vorsteuerabzug-und-rechnung/formerfordernisse.html)
- [USP: Kleinunternehmen](https://www.usp.gv.at/themen/steuern-finanzen/umsatzsteuer-ueberblick/weitere-informationen-zur-umsatzsteuer/weitere-steuertatbestaende-und-befreiungen/kleinunternehmen.html)

## Design Principles

1. Hard tax rules must be distinguishable from system defaults and heuristics.
2. The system must preserve explainability for every decision.
3. Tax policy must be versionable across time.
4. Recognition uncertainty must be explicit, not hidden.
5. User interaction must stay lightweight and progressive.
6. Lifecycle handling starts at creation time, not as an afterthought.
