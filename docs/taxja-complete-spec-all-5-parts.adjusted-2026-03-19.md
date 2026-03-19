# Taxja Asset Tax Engine & Processing Pipeline

**Repo-aligned adjusted spec**

- Based on original spec: `C:/Users/yk1e25/Downloads/taxja-complete-spec-all-5-parts.md`
- Adjusted against repository state on `2026-03-19`
- Jurisdiction: Austria
- Purpose: preserve the original target architecture, but correct status, roadmap, naming, and acceptance criteria so they match the current codebase

---

## 0. How to read this revision

The original spec is directionally strong, but several sections no longer match the repo:

- Some items marked as future work are already implemented.
- Some items described as available are only partially integrated.
- Some target services and entities are not found in the repo at all.
- Some naming in the spec diverges from the actual API and model names.

This adjusted version therefore uses four status markers:

- `[implemented]`: found in the repo and materially usable
- `[partial]`: found in the repo, but integration or source-of-truth is incomplete
- `[not found in repo]`: not present as described
- `[rename/alignment]`: the capability exists, but the spec name should be changed to match the code

---

## 1. Executive Summary

### 1.1 What changed versus the original spec

The largest corrections are:

- Credit billing is already a real subsystem and should no longer be treated as Step 1 greenfield work.
- The old usage/quota system still coexists with credits, so the repo is in a dual-run state rather than a completed credit cutover.
- The asset recognition engine and tax policy engine already exist and are wired into OCR, but they still depend on inferred profile inputs because `vat_status` and `gewinnermittlungsart` are not persisted on the user model.
- The repo does not yet contain the spec's proposed modular document pipeline services such as `processing_decision_service`, `document_normalization_service`, `document_quality_gate_service`, or `document_metering_service`.
- The repo does not use a separate `asset_master` table; non-real-estate assets currently live in `properties`.

### 1.2 Current-state summary

| Area | Adjusted status | Notes |
|---|---|---|
| Credit balance, deduction, top-up, overage | `[implemented]` | Real credit service, balance APIs, top-up path, overage billing, Stripe period-end invoice flow |
| Credit-first subscription view | `[implemented]` | Subscription response already includes credit balance fields |
| Legacy usage/quota removal | `[partial]` | Old quota dependencies and usage endpoints still active |
| Asset recognition service | `[implemented]` | Recognition service exists and is used in OCR flow |
| Asset tax policy rules | `[implemented]` | Policy service exists and evaluates GWG, useful life, IFB, VAT recoverability, degressive AfA |
| User tax profile inputs | `[partial]` | `vat_status` and `gewinnermittlungsart` enums exist in schemas, but are not stored on `users` |
| OCR → asset integration | `[partial]` | Asset suggestion path exists, but profile inputs are inferred and auto-create semantics are not fully clean |
| Asset master entity | `[partial]` | Asset fields exist, but storage is via `Property`, not a dedicated asset master model |
| Policy snapshots and asset events | `[implemented]` | Snapshot and event models exist |
| 7-stage modular processing pipeline | `[not found in repo]` | Current orchestrator is still a monolithic 4-stage service |

---

## 2. Part-by-Part Adjustments

## Part 1: Asset Master Field Specification

### Adjusted status

- Asset tax fields: `[implemented]`
- Dedicated `asset_master` entity: `[not found in repo]`
- Policy snapshot: `[implemented]`
- Asset event log: `[implemented]`
- Field source / provenance discipline: `[partial]`

### Repo-aligned interpretation

The repo already contains many of the tax fields described by the original Part 1, but they are currently stored on `Property` for non-real-estate assets rather than on a separate asset master entity.

Current implementation characteristics:

- Non-real-estate assets are created as `Property` rows with `asset_type != "real_estate"`.
- Important tax-related fields already exist, including:
  - `is_used_asset`
  - `business_use_percentage`
  - `gwg_eligible`
  - `gwg_elected`
  - `depreciation_method`
  - `degressive_afa_rate`
  - `vat_recoverable_status`
  - `ifb_candidate`
  - `ifb_rate`
  - `ifb_rate_source`
  - `recognition_decision`
- Frozen policy context is already modeled through `AssetPolicySnapshot`.
- Immutable lifecycle records are already modeled through `AssetEvent`.

### Required spec corrections

Replace the original assumption:

- "Taxja needs to implement an asset master from scratch"

With the repo-aligned statement:

- "Taxja already has most asset-tax fields, but currently uses `properties` as the storage substrate for non-real-estate assets. A dedicated `asset_master` table is a future refactor decision, not the current implementation baseline."

### Adjusted decision

For now, the spec should explicitly support two possible end states:

1. Keep `Property` as the canonical asset store and continue enriching it.
2. Introduce a dedicated `asset_master` entity later and migrate non-real-estate assets out of `properties`.

Until that decision is made, the spec should not require a separate `asset_master` table as an acceptance condition for Step 2C.

---

## Part 2: Asset Recognition Service Contract

### Adjusted status

- `asset_recognition_service`: `[implemented]`
- duplicate detection in recognition flow: `[implemented]`
- OCR integration: `[partial]`
- clean `create_asset_auto` semantics: `[partial]`
- dependency on stored tax profile: `[partial]`

### Repo-aligned interpretation

The recognition service already exists and is not greenfield work.

What is already present:

- `AssetRecognitionService.recognize(...)`
- confidence-driven recognition output
- duplicate-aware decisioning
- asset candidate construction
- expense/service filtering
- tax-policy-driven decision support

What is still incomplete:

- OCR task builders still infer profile inputs instead of reading a complete persisted tax profile.
- `vat_status` is inferred from `vat_number` presence.
- `gewinnermittlungsart` is defaulted to `UNKNOWN`.
- In the OCR integration layer, `CREATE_ASSET_AUTO` is still serialized into a pending suggestion structure instead of representing a clearly separated auto-created terminal path.

### Required spec corrections

Replace the original assumption:

- "Implement `asset_recognition_service` as Step 2C new work"

With:

- "`asset_recognition_service` already exists. Step 2C should focus on completing its inputs, tightening its integration contract, and aligning downstream decision semantics."

### Adjusted acceptance criteria

The recognition layer should be considered complete only when:

- `vat_status` comes from stored user profile state rather than heuristic inference.
- `gewinnermittlungsart` comes from stored user profile state rather than defaulting to `UNKNOWN`.
- `create_asset_auto` and `create_asset_suggestion` have clearly different downstream persistence behavior.
- duplicate warnings, review reasons, missing fields, and policy confidence are preserved end-to-end.

---

## Part 3: Tax Policy Rules Matrix

### Adjusted status

- `asset_tax_policy_service`: `[implemented]`
- GWG handling: `[implemented]`
- useful life / depreciation selection: `[implemented]`
- VAT recoverability handling: `[implemented]`
- IFB handling: `[implemented]`
- frozen policy snapshot write path: `[implemented]`
- legal-data completeness across all source fields: `[partial]`

### Repo-aligned interpretation

The tax policy engine is already present and materially aligned with the original intent of Part 3.

What is already present in the repo:

- comparison basis evaluation
- GWG threshold handling
- useful life determination
- degressive AfA handling
- VAT recoverability status handling
- IFB candidate and rate handling
- policy snapshot persistence
- lifecycle events such as `degressive_to_linear_switch`, `ifb_flagged`, and `ifb_claimed`

### Required spec corrections

Replace:

- "Tax policy rules matrix to be implemented in Step 2C"

With:

- "Tax policy rules matrix already has a service implementation. Remaining work is to harden inputs, test coverage, and integration semantics."

### Adjusted open gaps

The spec should explicitly call out these remaining repo-based gaps:

- user tax profile source data is incomplete
- some recognition inputs are still heuristic
- full benchmark coverage for all rule combinations is not yet demonstrated in one acceptance pack

---

## Part 4: Credit-Driven Processing Strategy

### Adjusted status

- credit model and balance tracking: `[implemented]`
- credit APIs: `[implemented]`
- overage enablement: `[implemented]`
- overage billing settlement: `[implemented]`
- top-up path: `[implemented]`
- credit-first subscription payload: `[implemented]`
- legacy usage/quota retirement: `[partial]`
- estimated credit band / auto charge cap model: `[not found in repo]`

### Repo-aligned interpretation

The original Part 4 is the most outdated section of the spec.

The repo already contains:

- plan-level credit configuration
- credit balances for included credits and top-ups
- credit cost configuration
- read-only estimate flow
- credit ledger/history
- overage enable/disable
- overage estimate
- top-up checkout path
- subscription response fields for credit state
- Stripe-backed overage settlement flow
- unpaid overage handling and suspension logic

### Required naming corrections

The original spec should be updated to match the actual API names:

| Original spec name | Repo-aligned name |
|---|---|
| `GET /credits/ledger` | `GET /credits/history` |
| `POST /credits/topups/checkout` | `POST /credits/topup` |
| "Add credit-first subscription view" | already present in subscription response |

### Critical repo truth the spec must reflect

The system is not yet a pure credit system.

The following legacy quota path still exists:

- `usage.py`
- `usage_record.py`
- `usage_tracker_service.py`
- `check_quota(...)` dependency
- quota checks in AI assistant, documents, and transactions flows

Therefore the spec must change from:

- "Step 1 introduces credits"

To:

- "Step 1 completes the convergence from a dual-run quota + credit system to a single billing model."

### Adjusted overage behavior

The spec should now describe overage as:

- postpaid
- period-settled
- Stripe-invoiced
- automatically charged against the customer's default payment method
- suspended immediately on payment failure
- re-enabled after successful settlement for eligible plans

### What is still missing from the original target model

The following Part 4 items are still not evidenced in the repo:

- `estimated_credit_band` as a dedicated domain field
- `auto_charge_cap` as a dedicated domain field
- explicit customer-facing "X-Y credits" estimation band model

These should remain future work if still desired.

---

## Part 5: Performance Audit & Fix Specification

### Adjusted status

- monolithic orchestrator exists: `[implemented]`
- 7-stage modular architecture: `[not found in repo]`
- Phase 1 / Phase 2 checkpoint split: `[not found in repo]`
- dedicated metering sidecar service: `[not found in repo]`
- some current checkpoint persistence behavior: `[partial]`

### Repo-aligned interpretation

The current document processing implementation is still centered on a monolithic orchestrator.

What the repo actually has:

- `document_pipeline_orchestrator`
- current stage model:
  - `CLASSIFY`
  - `EXTRACT`
  - `VALIDATE`
  - `SUGGEST`
- in-service persistence of extracted data before suggestion generation
- direct coupling between OCR output and suggestion builders

What the repo does not currently contain as separate services:

- `processing_decision_service`
- `document_normalization_service`
- `document_quality_gate_service`
- `document_metering_service`
- the spec's 7-stage pipeline contract
- the spec's clean Phase 1 / Phase 2 checkpoint boundary

### Required spec corrections

Replace:

- "Step 2A implements the proposed modular services on top of an otherwise aligned pipeline"

With:

- "Step 2A is a substantial refactor from the current monolithic orchestrator into the proposed modular pipeline."

### Adjusted acceptance framing

Part 5 should stop assuming the modular services exist and instead define them as a target refactor with measurable exit criteria:

- stable normalized document contract
- explicit quality gate priority chain
- separated persistence checkpoints
- bounded VLM/LLM call counts
- benchmark replay dataset
- instrumentation for first-result latency and full pipeline latency

---

## Part 6: Revised Roadmap & Phasing

## 6.1 Revised implementation logic

The original Step 1 and Step 2 split is still valid, but the content must change.

### Revised Step 1

Step 1 is no longer "introduce credits". It is:

- finish tax profile source-of-truth fields
- complete credit/quota convergence
- align naming and payloads with the actual credit-first system

### Revised Step 2

Step 2 remains:

- pipeline refactor
- performance fixes
- asset-engine integration hardening

But it should explicitly assume that:

- the asset recognition and tax policy engines already exist
- the biggest remaining backend work is orchestration, profile sourcing, and persistence contract cleanup

---

## 6.2 Revised Step 1 checklist

### Backend

- `[partial]` Add `vat_status` and `gewinnermittlungsart` to `users` with migration.
- `[partial]` Replace loose `PUT /users/profile` dict updates with explicit schema validation.
- `[not found in repo]` Add explicit automation eligibility guard tied to missing tax profile fields.
- `[implemented]` Credit APIs already exist: `GET /credits/balance`, `GET /credits/history`, `GET /credits/costs`, `POST /credits/estimate`, `POST /credits/topup`, `PUT /credits/overage`, `GET /credits/overage/estimate`.
- `[implemented]` Subscription endpoint already exposes a credit-first view.
- `[partial]` Retire old quota path from AI, OCR, and transaction entry flows.

### Frontend

- `[partial]` Add tax profile form fields for `vat_status` and `gewinnermittlungsart`.
- `[not found in repo]` Add explicit blocking UX for enabling automation when mandatory tax profile fields are missing.
- `[implemented]` Subscription and pricing UI already use credit language in major places.
- `[partial]` Remove old usage fallback UI once backend cutover is complete.

### Migration

- `[implemented]` `plans.monthly_credits` and `plans.overage_price_per_credit` already exist.
- `[partial]` Initialize missing user tax-profile state without blocking login.
- `[implemented]` `CreditBalance` path already exists for active subscription logic.
- `[not found in repo]` Add an explicit one-time cutover path from quota bookkeeping to pure credit bookkeeping if the business intends full retirement.

### Testing

- `[partial]` Add end-to-end profile validation coverage.
- `[implemented]` Credit balance / estimate / overage core flows have strong service-level coverage.
- `[partial]` Add regression tests proving quota removal does not break existing paths.
- `[not found in repo]` Add end-to-end old-user migration flow covering profile completion and automation enablement.

---

## 6.3 Revised Step 2 checklist

### Step 2A: Pipeline refactor

- `[not found in repo]` Implement `processing_decision_service`.
- `[not found in repo]` Implement `document_normalization_service`.
- `[not found in repo]` Implement `document_quality_gate_service`.
- `[not found in repo]` Refactor `document_pipeline_orchestrator` into the proposed modular pipeline.
- `[not found in repo]` Implement clean Phase 1 / Phase 2 checkpoint split.
- `[not found in repo]` Implement `document_metering_service` as a sidecar or equivalent bounded metering contract.
- `[partial]` Align credit cost configuration to any new pipeline operation model.

### Step 2B: Performance fixes

- `[not verified in repo]` Enforce VLM hard call caps per document type.
- `[not verified in repo]` Replace contract/document fallback paths with deterministic cheaper routing where possible.
- `[not verified in repo]` Add OCR cache and replay benchmarks for scanned PDFs.
- `[not verified in repo]` Move duplicate detection to indexed and delayed evaluation where appropriate.
- `[partial]` Separate auto-create from user-visible first-result timing.
- `[not verified in repo]` Convert retry behavior to field-based triggers and explicit fallback checkpoints.

### Step 2C: Asset engine hardening

- `[rename/alignment]` Do not treat "asset master schema" as entirely missing; clarify whether `Property` remains canonical or a new asset table will be introduced.
- `[implemented]` `asset_recognition_service` exists.
- `[implemented]` `asset_tax_policy_service` exists.
- `[partial]` Ensure duplicate detector contract is explicitly surfaced and tested.
- `[implemented]` policy snapshot write path exists.
- `[implemented]` asset event write path exists.
- `[partial]` Finish frontend asset suggestion card flows and decision UX such as GWG election and depreciation choices where not yet wired.
- `[partial]` Tighten put-into-use date handling for auto paths and missing-field fallbacks.

### Testing

- `[partial]` Add strategy / normalization / quality-gate tests once those services exist.
- `[not found in repo]` Add the matrix test pack for document type x automation level x risk level.
- `[not found in repo]` Add benchmark dataset replay acceptance pack.
- `[partial]` Expand credit estimate and metering tests if pipeline operation taxonomy changes.
- `[partial]` Expand asset recognition end-to-end tests from OCR input through confirmation and persistence.

---

## 6.4 Hard constraints, revised

1. Step 1 should finish profile source-of-truth and quota-credit convergence before Step 2 modular refactor work is considered complete.
2. Step 2A and Step 2B may run in parallel, but Step 2C must build on the actual normalized document contract once that contract exists.
3. Spec terminology should follow repo naming when a capability already exists.
4. The repo must not be described as "credit-first complete" while legacy quota dependencies remain active.
5. The repo must not be described as having a dedicated asset master entity unless such an entity is actually introduced.
6. Acceptance for the asset engine must include persisted tax-profile sourcing, not only rule correctness.

---

## 7. Spec-to-Repo Mapping Table

| Original spec term | Repo-aligned term or status |
|---|---|
| `asset_master` | currently `Property` for non-real-estate assets |
| `processing_decision_service` | not found in repo |
| `document_normalization_service` | not found in repo |
| `document_quality_gate_service` | not found in repo |
| `document_metering_service` | not found in repo |
| `GET /credits/ledger` | `GET /credits/history` |
| `POST /credits/topups/checkout` | `POST /credits/topup` |
| "implement credit-first subscription view" | already present |
| "implement asset recognition service" | already present |
| "implement asset tax policy service" | already present |
| `vat_status` / `gewinnermittlungsart` on user profile | enums exist in schemas, storage missing on `users` |

---

## 8. Recommended next spec version

If this document becomes the new active baseline, the next formal spec version should:

- keep Parts 1 to 3 mostly as target business semantics
- rewrite Part 4 as "credit/quota convergence and billing hardening"
- rewrite Part 5 as "pipeline refactor target architecture" rather than "assumed implementation plan"
- rewrite Part 6 as a repo-based rollout plan with status markers

In short:

- keep the tax logic ambition
- keep the pipeline ambition
- stop pretending credits are missing
- stop pretending profile sourcing and modular orchestration are already close to done
- explicitly decide whether assets continue living in `properties` or get a dedicated store

---

## 9. Proposed implementation priority after this adjustment

1. Add `vat_status` and `gewinnermittlungsart` to persisted user profile data and validate them on profile update.
2. Remove or formally deprecate the legacy quota path so billing has one source of truth.
3. Decide whether `Property` remains the canonical asset store.
4. Refactor the document pipeline into the modular service boundaries proposed by the original spec.
5. Add benchmark-backed observability and acceptance testing around latency, model-call counts, and quality-gate outcomes.

