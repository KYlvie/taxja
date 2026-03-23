# Design: OCR Pipeline Accuracy Fix

## 1. Architecture Principle

The fix follows a **"defense in depth"** approach with 3 layers:

```
Layer 1: Classifier (pattern matching + early detection)
    ↓ if confidence < 0.75
Layer 2: LLM Arbitration (GPT-4o structured output)
    ↓ always
Layer 3: Suggestion Guarantee (every document gets feedback)
```

No single layer is expected to be perfect. The goal is that the **combination** of all three layers produces correct output for every document.

## 2. Classifier Fixes

### 2.1 Early Detection Rewrite

Current early detection is a sequential if/else chain that returns immediately on first match. This causes false positives when broad markers (e.g., "arbeitnehmer") match non-target documents.

**New approach**: Score ALL early detection candidates, pick the best, with exclusion rules.

```python
def _early_detect(self, text: str, text_lower: str) -> Optional[Dict]:
    """Multi-candidate early detection with exclusion rules."""
    candidates = []

    # Check each family
    for detector in self._EARLY_DETECTORS:
        score = detector.score(text_lower)
        if score > 0 and not detector.excluded_by(text_lower):
            candidates.append({"type": detector.doc_type, "confidence": score})

    if not candidates:
        return None

    # Return highest scoring candidate
    return max(candidates, key=lambda c: c["confidence"])
```

### 2.2 Exclusion Patterns

```python
EXCLUSION_RULES = {
    DocumentType.LOHNZETTEL: {
        # If any of these appear, DON'T classify as LOHNZETTEL
        "exclude_if_any": [
            "dienstzettel", "arbeitsvertrag", "dienstvertrag",
            "arbeitgeberkündigung", "arbeitszeugnis",
        ]
    },
    DocumentType.RENTAL_CONTRACT: {
        "exclude_if_any": [
            "übergabeprotokoll", "wohnungsübergabe", "rückgabe",
            "abnahmeprotokoll", "zustandsbericht",
        ]
    },
    DocumentType.RECEIPT: {
        # Prefer INVOICE over RECEIPT if invoice markers present
        "exclude_if_any": [
            "rechnungsnummer", "re-nr", "uid", "ust-id",
            "reverse charge", "innergemeinschaftlich",
        ]
    },
}
```

### 2.3 Case-Insensitive Early Detection

All early detection regex patterns must use `re.IGNORECASE` or normalize to lowercase before matching.

```python
# BEFORE (fragile):
if "e1a" in text_lower and "beilage" in text_lower:
    return E1A_BEILAGE

# AFTER (robust):
e1a_patterns = [
    r"e\s*1\s*a[\s\-]*beilage",      # "E1a-Beilage", "E 1 a Beilage"
    r"beilage\s+(?:zur\s+)?e\s*1\s*a", # "Beilage zur E1a"
    r"e1a\s*[-–]\s*beilage",           # "E1A - Beilage"
]
if any(re.search(p, text_lower) for p in e1a_patterns):
    return E1A_BEILAGE
```

### 2.4 New Document Types

Add to classifier patterns:

```python
# K1 — Körperschaftsteuererklärung (unsupported, but should be recognized)
DocumentType.OTHER: {  # K1 detection → classify as OTHER
    "k1_markers": ["körperschaftsteuer", "k1", "körperschaft"],
    "required_any": ["körperschaftsteuer", "k1"],
    "weight": 1.5,
    "message": "K1 (Körperschaftsteuererklärung) is not supported"
}

# Handover protocol
DocumentType.OTHER: {  # Handover → classify as OTHER
    "handover_markers": ["übergabeprotokoll", "wohnungsübergabe", "rückgabeprotokoll"],
    "required_any": ["übergabeprotokoll", "wohnungsübergabe"],
    "weight": 1.5,
    "message": "Handover/return protocol — not a tax document"
}

# Dienstzettel (distinct from Lohnzettel)
DocumentType.OTHER: {
    "dienstzettel_markers": ["dienstzettel", "dienstvertrag", "arbeitsvertrag"],
    "required_any": ["dienstzettel"],
    "weight": 1.8,  # Higher than LOHNZETTEL to win conflict
    "message": "Employment record — not a payslip"
}
```

### 2.5 INVOICE vs RECEIPT Disambiguation

```python
# Stronger INVOICE markers
DocumentType.INVOICE: {
    "keywords": [...existing...],
    "required_any": ["rechnung", "rechnungsnummer", "re-nr", "faktura"],
    "invoice_boost": ["uid", "ust-id", "firmenbuchnummer", "reverse charge"],
    "weight": 1.1,  # Slightly higher than RECEIPT
}

# Stronger RECEIPT markers
DocumentType.RECEIPT: {
    "keywords": [...existing...],
    "required_any": ["kassenbon", "quittung", "beleg", "kassa"],
    "weight": 0.9,  # Lower than INVOICE
}
```

### 2.6 GWG/Asset Flag on Invoices

Instead of changing the document_type, add a metadata flag:

```python
# In _stage_classify, after classification:
if db_type in (DBDocumentType.INVOICE, DBDocumentType.RECEIPT):
    amount = extracted_data.get("amount") or extracted_data.get("total_amount")
    if amount and float(amount) > 800:
        result.extracted_data["_asset_candidate"] = True
        result.extracted_data["_asset_candidate_reason"] = (
            "gwg_boundary" if float(amount) <= 1000 else "asset_threshold_exceeded"
        )
```

## 3. LLM Arbitration Enhancement

### 3.1 Lower Threshold + Structured Output

```python
# In _stage_classify:
LLM_ARBITRATION_THRESHOLD = 0.75  # Was 0.88

if raw_text and len(raw_text) > 50 and (
    ocr_type == DBDocumentType.OTHER or confidence < LLM_ARBITRATION_THRESHOLD
):
    llm_result = self._try_llm_classification_structured(raw_text)
    # llm_result = {"type": "e1a_beilage", "confidence": 0.85, "reasoning": "..."}
```

### 3.2 Structured LLM Classification Prompt

```python
CLASSIFICATION_PROMPT = """
You are an Austrian tax document classifier. Analyze the OCR text and return JSON:

{
  "type": "one of: lohnzettel, l1_form, e1_form, e1a_beilage, e1b_beilage, e1kv_beilage,
          u1_form, u30_form, svs_notice, einkommensteuerbescheid, jahresabschluss,
          kaufvertrag, mietvertrag, kreditvertrag, invoice, receipt, bank_statement,
          betriebskostenabrechnung, versicherungsbestaetigung, kontoauszug,
          spendenbestaetigung, kirchenbeitrag, pendlerpauschale, fortbildungskosten,
          kinderbetreuungskosten, grundbuchauszug, gewerbeschein,
          k1_unsupported, dienstzettel_not_payslip, handover_protocol, other",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}

Rules:
- Dienstzettel (employment record) is NOT a Lohnzettel (payslip)
- Wohnungsübergabeprotokoll (handover) is NOT a Mietvertrag (rental contract)
- K1 (Körperschaftsteuer) is unsupported
- E1a is a SEPARATE type from E1 — look for "Beilage" or "E1a" in the header
- Invoices have Rechnungsnummer/UID; Receipts have Kassenbon/Quittung

OCR text:
{text}
"""
```

### 3.3 LLM + Regex Disagreement Handling

```python
if llm_type != regex_type:
    if llm_confidence > 0.7 and regex_confidence < 0.5:
        # LLM wins — likely a regex misclassification
        final_type = llm_type
        final_confidence = llm_confidence
        method = "llm_override"
    elif regex_confidence > 0.7 and llm_confidence < 0.5:
        # Regex wins — LLM may have hallucinated
        final_type = regex_type
        final_confidence = regex_confidence
        method = "regex"
    else:
        # Both uncertain — needs manual review
        final_type = regex_type  # Default to regex
        final_confidence = max(regex_confidence, llm_confidence) * 0.7  # Penalize
        method = "regex+llm_disagree"
        needs_review = True
```

## 4. Suggestion Generation Guarantee

### 4.1 "Every Document Gets Feedback" Rule

Add a final check at the end of `_stage_suggest`:

```python
def _ensure_suggestion_exists(self, document, result):
    """Guarantee: every completed document has at least one suggestion."""

    if result.suggestions:
        return  # Already has suggestions

    if result.current_state == "phase_2_failed":
        # Error case — generate error suggestion
        result.suggestions.append({
            "type": "processing_error",
            "status": "error",
            "data": {"error": result.error},
            "review_reason": f"Processing failed: {result.error}",
            "confidence": 0,
        })
        return

    # Document completed but no suggestion — generate review suggestion
    db_type = document.document_type

    if db_type in TAX_FORM_TYPES:
        result.suggestions.append({
            "type": f"import_{db_type.value.lower()}",
            "status": "needs_review",
            "data": result.extracted_data or {},
            "review_reason": "Could not extract structured tax data. Please review manually.",
            "confidence": result.classification.confidence if result.classification else 0,
        })
    elif db_type in (DBDocumentType.INVOICE, DBDocumentType.RECEIPT):
        result.suggestions.append({
            "type": "create_transaction",
            "status": "needs_review",
            "data": result.extracted_data or {},
            "review_reason": "Could not extract complete transaction data (amount or merchant missing).",
            "confidence": result.classification.confidence if result.classification else 0,
        })
    else:
        # Unknown or unsupported type
        result.suggestions.append({
            "type": "manual_review",
            "status": "needs_review",
            "data": result.extracted_data or {},
            "review_reason": f"Document classified as {db_type.value} but no automated action available.",
            "confidence": result.classification.confidence if result.classification else 0,
        })
```

### 4.2 Unsupported Type Suggestion

```python
UNSUPPORTED_TYPES = {
    "k1": "K1 (Körperschaftsteuererklärung) — corporate tax forms are not yet supported.",
    "dienstzettel": "Dienstzettel (employment record) — not a tax document. Archived for your records.",
    "handover_protocol": "Wohnungsübergabeprotokoll — not a tax document. Archived for your records.",
}

def _build_unsupported_suggestion(self, db_type_str, reason):
    return {
        "type": "not_supported",
        "status": "dismissed",
        "data": {},
        "review_reason": reason,
        "confidence": 0,
    }
```

## 5. File Change Summary

| File | Change | Scope |
|------|--------|-------|
| `document_classifier.py` | Rewrite early detection + add exclusions + add types | LARGE |
| `document_pipeline_orchestrator.py` | Add `_ensure_suggestion_exists()`, lower LLM threshold, GWG flag | MEDIUM |
| `llm_extractor.py` | New structured classification prompt | SMALL |
| `llm_service.py` | Ensure GPT-4o is used for classification | SMALL |
| `processing_decision_service.py` | Handle `_asset_candidate` flag for GWG | SMALL |
| `tests/test_classifier_accuracy.py` | NEW — 17-document regression test | MEDIUM |

## 6. Risk Mitigation

### Backward Compatibility
- All pattern changes are additive (new patterns, not removing old ones)
- Exclusion rules only activate when both positive AND negative markers are present
- LLM threshold change (0.88→0.75) means MORE documents get LLM verification, not fewer
- Existing correctly-classified documents should not be affected

### Regression Prevention
- The 17-document test corpus becomes a permanent regression test
- Run before every deployment
- CI/CD must pass all 17 test cases

### LLM Cost
- Lowering threshold from 0.88 to 0.75 increases LLM calls by ~20-30%
- Each call costs ~$0.01 (GPT-4o with ~500 tokens)
- Acceptable cost for significant accuracy improvement
