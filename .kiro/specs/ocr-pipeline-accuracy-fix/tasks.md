# Implementation Tasks: OCR Pipeline Accuracy Fix

## Execution Order

```
1. Task 1: Classifier early detection rewrite (FOUNDATION)
2. Task 2: Add exclusion patterns + new types
3. Task 3: INVOICE vs RECEIPT disambiguation
4. Task 4: LLM arbitration enhancement (threshold + structured output)
5. Task 5: Suggestion generation guarantee
6. Task 6: GWG/asset candidate flag
7. Task 7: Write 17-document regression test
8. Task 8: Run regression + fix remaining failures
```

---

## Task 1: Classifier Early Detection Rewrite

- [ ] Refactor `_classify_by_patterns()` early detection from sequential if/else to multi-candidate scoring
- [ ] Make all pattern matching case-insensitive (E1a, E1b, E1kv, U1, etc.)
- [ ] Add fuzzy matching for OCR variants: `e\s*1\s*a`, `e1a`, `E1A`, `Ela` (common OCR error)
- [ ] E1A detection must check BEFORE E1 generic and use `re.IGNORECASE`
- [ ] L16 detection: add "jahreslohnzettel", "lohnzettel.*jahres" patterns
- [ ] Ensure early detection returns confidence values that reflect match quality

**Files**: `backend/app/services/document_classifier.py`
**Test**: E1A should be classified as E1A_BEILAGE, not E1_FORM

## Task 2: Add Exclusion Patterns + New Types

- [ ] Add EXCLUSION_RULES dict: LOHNZETTEL excludes ["dienstzettel", "arbeitsvertrag", "dienstvertrag"]
- [ ] Add EXCLUSION_RULES: RENTAL_CONTRACT excludes ["übergabeprotokoll", "wohnungsübergabe"]
- [ ] Add K1 detection → classify as OTHER, set `_unsupported_type = "k1"` in metadata
- [ ] Add Dienstzettel detection → classify as OTHER, set `_unsupported_type = "dienstzettel"`
- [ ] Add Übergabeprotokoll detection → classify as OTHER, set `_unsupported_type = "handover_protocol"`
- [ ] Increase BETRIEBSKOSTENABRECHNUNG weight to 1.5, add "betriebskosten" to required_any
- [ ] Apply exclusions BEFORE returning early detection result

**Files**: `backend/app/services/document_classifier.py`
**Test**: Dienstzettel → OTHER (not LOHNZETTEL); Übergabe → OTHER (not RENTAL_CONTRACT)

## Task 3: INVOICE vs RECEIPT Disambiguation

- [ ] Add INVOICE required_any: ["rechnung", "rechnungsnummer", "re-nr", "faktura"]
- [ ] Add INVOICE boost keywords: ["uid", "ust-id", "firmenbuchnummer"]
- [ ] Set INVOICE weight to 1.1 (above RECEIPT's 0.9)
- [ ] Add RECEIPT required_any: ["kassenbon", "quittung", "beleg", "kassa"]
- [ ] Add RECEIPT exclusion: if "rechnungsnummer" or "uid" present → prefer INVOICE
- [ ] Ensure GWG test invoices (€999, €1001) classify as INVOICE not RECEIPT

**Files**: `backend/app/services/document_classifier.py`
**Test**: WKO invoices → INVOICE; GWG invoices → INVOICE

## Task 4: LLM Arbitration Enhancement

- [ ] Lower `LLM_ARBITRATION_THRESHOLD` from 0.88 to 0.75 in `_stage_classify`
- [ ] Create new structured classification prompt (JSON output with type + confidence + reasoning)
- [ ] Parse LLM JSON response with fallback for malformed output
- [ ] Implement disagreement handling: LLM vs regex confidence comparison
- [ ] When both uncertain (<0.7) and disagree → set `needs_review = true`
- [ ] Ensure GPT-4o is used (verify `OPENAI_API_KEY` and model config)
- [ ] Add logging for LLM classification decisions (type, confidence, agree/disagree with regex)

**Files**: `backend/app/services/document_pipeline_orchestrator.py`, `backend/app/services/llm_extractor.py`
**Test**: Low-confidence documents should get LLM arbitration; LLM result should be logged

## Task 5: Suggestion Generation Guarantee

- [ ] Add `_ensure_suggestion_exists()` at end of `_stage_suggest` / Phase 2
- [ ] For tax forms with no KZ data: generate `import_[type]` suggestion with status `needs_review`
- [ ] For invoices/receipts with no amount: generate `create_transaction` suggestion with `needs_review`
- [ ] For unsupported types (K1, Dienstzettel, Übergabe): generate `not_supported` suggestion
- [ ] For `phase_2_failed`: generate `processing_error` suggestion with error details
- [ ] All review suggestions include `review_reason` field (human-readable explanation)
- [ ] Verify: after this change, EVERY document that exits pipeline has ≥1 suggestion

**Files**: `backend/app/services/document_pipeline_orchestrator.py`
**Test**: ALL 17 test documents must have at least one suggestion after processing

## Task 6: GWG/Asset Candidate Flag

- [ ] After classification as INVOICE, check if extracted amount > €800
- [ ] If €800 < amount ≤ €1000: add `_asset_candidate = true`, `_asset_candidate_reason = "gwg_boundary"`
- [ ] If amount > €1000: add `_asset_candidate = true`, `_asset_candidate_reason = "asset_threshold_exceeded"`
- [ ] In `ProcessingDecisionService`: when `_asset_candidate` is true, add `ASSET_SUGGESTION` action
- [ ] Ensure GWG T03 (€999) gets `gwg_suggestion` and T04 (€1001) gets `create_asset` suggestion

**Files**: `backend/app/services/document_pipeline_orchestrator.py`, `backend/app/services/processing_decision_service.py`
**Test**: GWG T03 → gwg_suggestion; GWG T04 → create_asset

## Task 7: Write 17-Document Regression Test

- [ ] Create `backend/tests/test_classifier_17doc_regression.py`
- [ ] Define expected results for all 17 documents (from acceptance criteria table)
- [ ] Test 1: Classification accuracy — verify document_type for each
- [ ] Test 2: Suggestion existence — verify every document has ≥1 suggestion
- [ ] Test 3: Suggestion type correctness — verify suggestion type matches expected
- [ ] Test 4: No regression — existing types (KAUFVERTRAG, MIETVERTRAG) still work
- [ ] Tests use actual OCR text from DB (raw_text column) or mock OCR text
- [ ] Mark test as `@pytest.mark.regression` for CI/CD

**Files**: `backend/tests/test_classifier_17doc_regression.py`

## Task 8: Run Regression + Fix Remaining Failures

- [ ] Run 17-document regression test
- [ ] For each failure: diagnose root cause and fix
- [ ] Re-run until all 17 pass
- [ ] Run existing test suite to verify no regressions
- [ ] Document final accuracy: classification rate, suggestion rate

---

## Estimated Effort

| Task | Effort | Risk |
|------|--------|------|
| Task 1: Early detection rewrite | Medium | Medium — touching core classification logic |
| Task 2: Exclusion patterns | Small | Low — additive patterns |
| Task 3: INVOICE/RECEIPT | Small | Low — weight adjustment |
| Task 4: LLM arbitration | Medium | Medium — LLM response parsing |
| Task 5: Suggestion guarantee | Medium | Low — additive fallback logic |
| Task 6: GWG flag | Small | Low — metadata addition |
| Task 7: Regression test | Medium | Low — test-only |
| Task 8: Fix remaining | Variable | Depends on failure count |

## Acceptance Criteria

**The fix is complete when:**
1. ≥14/17 documents classified correctly (≥82% accuracy, up from 53%)
2. 17/17 documents produce at least one suggestion (100% feedback rate, up from 5.9%)
3. All existing tests pass (no regression)
4. 17-document regression test passes in CI/CD
