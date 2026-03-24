# Requirements: OCR Pipeline Accuracy Fix

## 1. Problem Statement

The document processing pipeline has a **5.9% end-to-end success rate** (1/17 test documents fully correct). Testing with 17 standardized Austrian tax/business documents reveals systemic failures at two levels:

- **Classification layer**: 8/17 documents misclassified (47% error rate)
- **Suggestion generation layer**: 8/17 correctly-classified documents produced no suggestion (100% miss rate for tax forms)

The system correctly processes only one document type end-to-end: vehicle purchase contracts with high OCR confidence (>0.9).

## 2. Test Corpus

17 documents from ChatGPT's "Taxja real-template core pack" covering:
- 7 official Austrian tax forms (L16, L1, E1, E1A, E1B, U1, K1)
- 3 WKO invoice templates (regular, Kleinunternehmer, reverse charge)
- 2 AK employment/landlord documents (Dienstzettel, Wohnungsuebergabeprotokoll)
- 1 Betriebskostenabrechnung (operating cost statement)
- 2 GWG boundary invoices (€999 and €1001)
- 2 vehicle purchase contracts (PKW €35K, EV €38K)

Source provenance: `source_provenance.csv` (all reconstructed from public templates, not real documents)

## 3. Failure Analysis Summary

### 3.1 Classification Failures (8/17)

| # | Expected | Got | Root Cause |
|---|----------|-----|------------|
| 1 | E1A_BEILAGE | E1_FORM | Early detection checks E1A before E1, but OCR may render "E1a" as "E1A"/"Ela" — case/OCR error causes E1A check to miss, falls through to E1 |
| 2 | K1_FORM | JAHRESABSCHLUSS | K1 type has NO pattern in classifier — completely missing |
| 3 | employment_contract/dienstzettel | LOHNZETTEL | Early detection: "arbeitnehmer" triggers LOHNZETTEL before checking for Dienstzettel exclusion |
| 4 | handover_protocol | RENTAL_CONTRACT | "Wohnung"+"Mieter" keywords trigger RENTAL_CONTRACT; handover_protocol type doesn't exist |
| 5 | betriebskostenabrechnung | INVOICE | Pattern exists but low weight; INVOICE scores higher |
| 6-7 | invoice_asset_candidate | RECEIPT | RECEIPT and INVOICE share keywords; RECEIPT wins due to scoring |

### 3.2 Suggestion Generation Failures (8/17)

Even when classification is correct, Phase 2 fails to produce suggestions:

| Type | Count | Root Cause |
|------|-------|------------|
| Tax forms (E1, L1, U1, E1B) | 4 | `_build_tax_form_suggestion()` requires extracted KZ data; OCR doesn't extract structured KZ from scanned forms |
| Invoices (WKO) | 2 | `_build_transaction_suggestions()` requires amount/merchant; extraction may fail silently |
| Vehicle contract (35K PKW) | 1 | Classification correct (0.8) but Phase 2 didn't generate asset suggestion — possibly extraction incomplete |
| L16 (annual payslip) | 1 | Classified as LOHNZETTEL (correct family) but low confidence (0.05) — no suggestion generated |

### 3.3 Processing Failures (1/17)

| Document | Error |
|----------|-------|
| Reverse Charge invoice | `phase_2_failed` — exception during Phase 2 processing |

## 4. Root Cause Architecture Analysis

### Problem A: Classifier Early Detection is Fragile

The `_classify_by_patterns()` method has a rigid early detection chain:
```
1. Check payslip markers → return LOHNZETTEL
2. Check L1 markers → return L1_FORM
3. Check E1a/E1b/E1kv markers → return respective type
4. Check E1 markers → return E1_FORM
```

**Issues:**
- Step 1 uses broad markers ("arbeitnehmer") that match Dienstzettel, employment contracts
- Step 3 checks E1A before E1, but the regex is case-sensitive — OCR errors cause misses
- K1 has no entry at all
- No "negative markers" (exclusion patterns) to reject false positives

### Problem B: Keyword Scoring is Context-Blind

The scoring algorithm counts keyword frequency but has no concept of:
- **Document structure** (header vs body vs footer)
- **Mutually exclusive types** (RECEIPT vs INVOICE share most keywords)
- **Negative evidence** ("Übergabeprotokoll" should actively EXCLUDE RENTAL_CONTRACT)

### Problem C: LLM Arbitration Threshold Too High

The LLM is only called when `confidence < 0.88`. But many misclassified documents have confidence 0.3-0.5 — they DO trigger LLM, but the LLM may not have enough context (OCR text quality is poor for scanned documents).

### Problem D: Suggestion Generation Requires Complete Extraction

`_build_tax_form_suggestion()` checks for extracted KZ numbers. If OCR can't extract structured fields from a scanned tax form (common with image-based PDFs), no suggestion is generated — **the document just disappears into the system with no user feedback**.

### Problem E: No Fallback for Unextractable Documents

When extraction fails, the document gets `pipeline_state = "completed"` with no suggestion. The user sees it in the document list but has no indication that the system couldn't process it. There's no "I couldn't extract data, please review" fallback suggestion.

## 5. Functional Requirements

### 5.1 Classifier Improvements

- **FR-1**: Add case-insensitive matching for all early detection patterns (E1a, E1b, E1kv, etc.)
- **FR-2**: Add negative/exclusion patterns: if "dienstzettel" or "arbeitsvertrag" appears, EXCLUDE LOHNZETTEL
- **FR-3**: Add K1 form pattern (Körperschaftsteuererklärung) — classify as OTHER/UNSUPPORTED with appropriate message
- **FR-4**: Add handover protocol detection ("übergabeprotokoll", "wohnungsübergabe") — classify as OTHER with message
- **FR-5**: Increase BETRIEBSKOSTENABRECHNUNG weight to 1.5 and add "betriebskosten" to required_any
- **FR-6**: Distinguish INVOICE from RECEIPT: add "rechnungsnummer", "uid" to INVOICE required_any; add "kassenbon", "quittung" to RECEIPT required_any
- **FR-7**: For GWG detection: when classified as INVOICE/RECEIPT and amount > €800, flag as `invoice_asset_candidate` in metadata (don't change type, add flag)

### 5.2 LLM Arbitration Enhancement

- **FR-8**: Lower LLM arbitration threshold from 0.88 to 0.75 — more documents get LLM verification
- **FR-9**: Use GPT-4o for classification arbitration (already configured via OPENAI_API_KEY)
- **FR-10**: Add structured output format for LLM classification — return both type AND confidence, not just type string
- **FR-11**: When LLM and regex disagree AND both have low confidence (<0.7), set `needs_review = true` and generate a "manual review required" suggestion

### 5.3 Suggestion Generation Guarantees

- **FR-12**: When a document is classified as a tax form type (E1, L1, U1, etc.) but extraction yields no KZ data, STILL generate a suggestion with type `"import_[type]"` and status `"needs_review"` — the user can then review and manually enter data
- **FR-13**: When a document is classified as INVOICE/RECEIPT but amount extraction fails, generate a suggestion with `"needs_review"` status showing what WAS extracted, asking the user to fill in missing fields
- **FR-14**: Add `"review_reason"` field to all suggestions explaining WHY review is needed (e.g., "Amount could not be extracted", "Tax form KZ numbers not found")
- **FR-15**: Every completed document MUST have either: (a) an auto-created entity, (b) a pending suggestion, OR (c) a "needs_review" suggestion. NO document should complete with zero feedback.

### 5.4 Negative Path Handling

- **FR-16**: Documents detected as unsupported types (K1, Dienstzettel, Übergabeprotokoll) should generate a `"not_supported"` suggestion explaining: "This document type is not currently supported by Taxja. It has been archived for your records."
- **FR-17**: Documents that fail Phase 2 should generate an `"error"` suggestion with retry option, NOT silently set `phase_2_failed`

## 6. Non-Functional Requirements

- **NFR-1**: Classification accuracy must reach ≥80% on the 17-document test corpus (currently 53%)
- **NFR-2**: Suggestion generation rate must reach 100% — every document gets feedback (currently 5.9%)
- **NFR-3**: No regression on existing correctly-classified document types (vehicle contracts, rental contracts, Kaufvertrag)
- **NFR-4**: LLM arbitration latency must not increase total processing time by more than 5 seconds per document
- **NFR-5**: All changes must be backward-compatible — existing documents in the DB are not affected

## 7. Acceptance Criteria

Using the 17-document test corpus, after fixes:

| Document | Expected Classification | Expected Suggestion |
|----------|------------------------|---------------------|
| L16 | LOHNZETTEL | import_lohnzettel (pending) |
| L1 | L1_FORM | import_l1 (pending) |
| E1 | E1_FORM | import_e1 (pending) |
| E1A | E1A_BEILAGE | import_e1a (pending) |
| E1B | E1B_BEILAGE | import_e1b (pending) |
| U1 | U1_FORM | import_u1 (pending) |
| K1 | OTHER (unsupported) | not_supported suggestion |
| WKO Invoice | INVOICE | transaction auto-created OR pending |
| Kleinunternehmer | INVOICE | transaction auto-created OR pending |
| Reverse Charge | INVOICE | transaction pending (needs_review) |
| Dienstzettel | OTHER | not_supported suggestion |
| Übergabeprotokoll | OTHER | not_supported suggestion |
| Betriebskosten | BETRIEBSKOSTENABRECHNUNG | needs_review suggestion |
| GWG T03 (€999) | INVOICE + gwg_flag | gwg_suggestion |
| GWG T04 (€1001) | INVOICE + asset_flag | create_asset suggestion |
| PKW 35K | PURCHASE_CONTRACT | create_asset suggestion |
| EV 38K | PURCHASE_CONTRACT | create_asset suggestion |

**Target: 17/17 documents produce appropriate feedback (100% suggestion rate)**
