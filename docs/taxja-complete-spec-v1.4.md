# Taxja Asset Tax Engine & Processing Pipeline

**Version**: v1.4  
**Status**: Repo-aligned baseline / Ready for implementation  
**Jurisdiction**: Austria  
**Last updated**: 2026-03-19

---

## 0. Purpose of v1.4

v1.4 keeps the original target architecture, but corrects the parts of v1.3 that no longer match the repository.

This version is intentionally conservative:

- Parts 1 to 3 remain target-architecture oriented.
- Part 4 is corrected from "introduce credits" to "complete credit/quota convergence".
- Part 5 is corrected to reflect that Step 2A is a real refactor from a monolithic pipeline, not a light wiring task.
- Part 6 is rewritten as a repo-aligned roadmap with explicit status markers.

This document should be read together with:

- `docs/taxja-complete-spec-all-5-parts.adjusted-2026-03-19.md`
- `docs/taxja-engineering-task-plan-2026-03-19.md`

---

## 0.1 Change log from v1.3

### What v1.3 overestimated

- Credit system as greenfield work
- Asset recognition service as greenfield work
- Asset tax policy service as greenfield work
- Policy snapshot and asset event persistence as greenfield work

### What v1.3 underestimated

- Missing persisted user tax-profile fields
- Remaining legacy quota/usage dependencies
- Size of the pipeline modularization effort
- Gap between target `asset_master` terminology and current `Property`-based persistence

---

## 0.2 Terminology policy in v1.4

This version uses a split terminology policy:

### Existing API and payload names

When a public API or persisted payload already exists and is active in the repo, the spec should align to the implemented name unless the team explicitly decides to rename it.

Examples:

- `GET /credits/history` is the current endpoint, so it replaces `GET /credits/ledger` in the baseline spec.
- `POST /credits/topup` is the current endpoint, so it replaces `POST /credits/topups/checkout` in the baseline spec.

### Target architecture service names

For new modular services that do not yet exist, the spec remains normative.

Examples:

- `processing_decision_service`
- `document_normalization_service`
- `document_quality_gate_service`
- `document_metering_service`

These names remain the desired Step 2A target names and do not need to change just because the current repo has not implemented them yet.

---

## Part 1: Asset Master Field Specification

### 1.1 v1.4 status note

The target `asset_master` concept remains valid at the domain level, but the current repo does **not** yet persist non-real-estate assets in a dedicated `asset_master` table.

Current repo reality:

- non-real-estate assets live in `Property`
- `asset_type != "real_estate"` is the current persistence discriminator
- many asset-tax fields already exist on `Property`

### 1.2 Decision record: current asset persistence

For v1.4, the official baseline is:

- `Property` remains the canonical persistence layer for non-real-estate assets in the current implementation.
- A dedicated `asset_master` table remains a future design option, not a Step 2C prerequisite.

### 1.3 Constraint for current implementation

While `Property` remains the persistence layer, new asset-tax behavior must be exposed through asset-domain contracts and services rather than leaking `Property` semantics into higher-level orchestration and UI code.

### 1.4 Deferred decision

The following decision is explicitly deferred:

1. Keep non-real-estate assets in `Property` and continue enriching it.
2. Introduce a dedicated `asset_master` table in a later migration.

This decision must not block Step 2C hardening work.

---

## Part 4: Credit-Driven Processing Strategy

### 4.1 v1.4 baseline

Part 4 is no longer a greenfield design section.

v1.4 treats credits as an implemented system whose next milestone is convergence.

### 4.2 What already exists

The repo already includes:

- `CreditService`
- `CreditBalance`
- credit ledger/history
- top-up flow
- overage enable/disable
- overage estimation
- Stripe-backed overage settlement
- credit-aware subscription payloads

Therefore, Step 1 is **not** "introduce credits".

### 4.3 Step 1 objective, corrected

Step 1 objective in v1.4:

> Complete the convergence from a dual-run quota + credit system to a single credit-based billing source of truth.

### 4.4 Current repo gap

The repo is currently in a dual-run state because these legacy paths still exist:

- `usage.py`
- `usage_record.py`
- `usage_tracker_service.py`
- `check_quota(...)`
- quota enforcement in AI assistant, documents, and transactions flows

### 4.5 API naming alignment

The baseline spec now uses the implemented API names:

| v1.3 name | v1.4 baseline |
|---|---|
| `GET /credits/ledger` | `GET /credits/history` |
| `POST /credits/topups/checkout` | `POST /credits/topup` |

### 4.6 Current business model

The billing model in v1.4 is:

- monthly included credits by plan
- optional top-up credits
- optional overage
- Stripe-backed settlement for overage
- subscription payloads exposing credit state as first-class billing data

### 4.7 Explicitly not yet baseline

The following ideas remain optional future enhancements, not v1.4 baseline requirements:

- `estimated_credit_band` as a first-class domain field
- `auto_charge_cap` as a first-class domain field
- a mandatory X-Y range style display rule for all estimates

### 4.8 Step 1 acceptance criteria

Step 1 is complete only when:

1. new requests no longer depend on quota enforcement for billing
2. billing-critical writes no longer depend on `usage_record`
3. primary frontend billing views use credit as the sole billing model
4. remaining balance, top-up, overage, and settlement all resolve from the credit system as the single billing source of truth
5. any remaining usage endpoint is deprecated or compatibility-only rather than authoritative for billing

### 4.9 Billing convergence cutover definition

Billing convergence is complete only when:

1. new billing writes no longer touch `usage_record`
2. no primary request path uses `check_quota(...)` for billing authorization
3. frontend billing surfaces no longer read quota usage as a primary billing signal
4. remaining balance, overage, top-up, and settlement resolve only from credit state
5. any surviving usage endpoint is deprecated or read-only compatibility rather than a billing source of truth

---

## Part 5: Performance Audit & Fix Specification

### 5.1 v1.4 correction

Step 2A is not a small integration phase.

It is a substantial refactor from the current monolithic pipeline to the target modular architecture.

### 5.2 Current repo reality

The current orchestrator is still effectively a 4-stage monolith:

- `CLASSIFY`
- `EXTRACT`
- `VALIDATE`
- `SUGGEST`

The following target services are not yet present as separate repo services:

- `processing_decision_service`
- `document_normalization_service`
- `document_quality_gate_service`
- `document_metering_service`

### 5.3 v1.4 implementation framing

Part 5 now treats the modular pipeline as a target architecture, not as something that is already mostly in place.

### 5.4 Step 2A scope, corrected

Step 2A must be understood as:

- extracting explicit contracts
- introducing new service boundaries
- reducing embedded business logic inside the orchestrator
- defining checkpoint boundaries
- creating measurable latency and model-call observability

### 5.5 Step 2A-min / Step 2A-full split

#### Step 2A-min

Goal:

- land semantic contracts first, without forcing a full service split

Required outcomes:

- stable `NormalizedDocument`
- `NormalizedDocument` is the sole business-decision input contract
- stable quality-gate contract
- quality-gate output is the sole persistence-branching decision contract
- explicit first-result checkpoint
- explicit finalization checkpoint
- orchestrator delegates to extracted logic where possible

#### Step 2A-full

Goal:

- land the full modular target architecture

Required outcomes:

- `processing_decision_service`
- `document_normalization_service`
- `document_quality_gate_service`
- `document_metering_service`
- explicit Phase 1 / Phase 2 behavior
- orchestrator reduced to orchestration responsibility

### 5.6 v1.4 acceptance principle

Part 5 acceptance is no longer based on "services exist on paper".

It is based on:

- stable contracts
- observable checkpoints
- measurable performance guardrails
- bounded VLM/LLM behavior

---

## Part 6: Implementation Roadmap & Phasing

### 6.1 Status markers

v1.4 introduces the following status markers in the roadmap:

- `[implemented]`
- `[partial]`
- `[not found]`

These markers are normative and should be updated as the repo evolves.

### 6.1.1 Interpretation of `[partial]`

For v1.4, a critical item must not remain permanently in `[partial]` without an explicit completion definition.

Unless a section defines a narrower completion rule, a critical `[partial]` item is complete only when:

1. the persistence layer is updated if the item affects source-of-truth state
2. the write API is validated
3. the read path switches to the new source of truth
4. production fallback logic is removed or clearly demoted
5. regression coverage is added

---

## 6.2 Step 1 checklist

### Backend

- `[partial]` add `vat_status` to `users` with migration
- `[partial]` add `gewinnermittlungsart` to `users` with migration
- `[partial]` replace loose profile updates with explicit schema validation
- `[implemented]` credit APIs already exist
- `[implemented]` credit-aware subscription payload already exists
- `[partial]` retire quota enforcement from AI assistant, documents, and transactions flows
- `[partial]` retire billing-critical dependency on `usage_record` and `usage_tracker_service`

### Frontend

- `[partial]` add `vat_status` form field to profile UI
- `[partial]` add `gewinnermittlungsart` form field to profile UI
- `[implemented]` subscription and pricing surfaces already expose credit language in major areas
- `[partial]` remove legacy usage/quota fallback UI after credit cutover

### Migration

- `[implemented]` `plans.monthly_credits` exists
- `[implemented]` `plans.overage_price_per_credit` exists
- `[partial]` backfill stored tax-profile state for existing users
- `[implemented]` credit balance persistence exists
- `[partial]` define and execute the quota-to-credit cutover path

### Testing

- `[partial]` add profile field validation coverage
- `[implemented]` service-level credit coverage exists
- `[partial]` add cutover regression tests proving credit is the only billing source of truth
- `[partial]` add end-to-end profile -> OCR -> asset recognition tests

---

## 6.3 Step 2A checklist

### Step 2A-min

- `[not found]` define `NormalizedDocument`
- `[not found]` define quality-gate decision contract
- `[not found]` extract normalization logic from the monolithic orchestrator
- `[not found]` define explicit first-result checkpoint
- `[not found]` define explicit finalization checkpoint
- `[not found]` update tests to assert contract outputs

### Step 2A-full

- `[not found]` implement `processing_decision_service`
- `[not found]` implement `document_normalization_service`
- `[not found]` implement `document_quality_gate_service`
- `[not found]` implement `document_metering_service`
- `[not found]` split Phase 1 and Phase 2 execution behavior
- `[not found]` reduce `document_pipeline_orchestrator` to orchestration responsibility

---

## 6.4 Step 2C checklist

### Asset engine hardening

- `[implemented]` `asset_recognition_service` already exists
- `[implemented]` `asset_tax_policy_service` already exists
- `[implemented]` policy snapshot persistence already exists
- `[implemented]` asset event persistence already exists
- `[partial]` replace heuristic profile inference with persisted profile inputs
- `[partial]` tighten duplicate-detector contract surfacing
- `[partial]` separate `create_asset_auto` from pending suggestion semantics
- `[partial]` ensure missing required fields block silent auto-create
- `[partial]` strengthen end-to-end tests from OCR to asset persistence

### Important correction

Step 2C must be treated as hardening and contract cleanup, not as a greenfield service build.

### Auto-path cleanup definition

The `create_asset_auto` cleanup is complete only when:

1. `create_asset_auto` is a terminal persistence path rather than a pending suggestion serialization
2. `create_asset_suggestion` always requires explicit user confirmation
3. downstream UI state, DB state, and audit log clearly distinguish auto-created outcomes from suggestion-required outcomes

---

## 6.5 Hard constraints

1. Step 1 must complete billing convergence before the system can be described as credit-first complete.
2. Step 1 must persist user tax-profile fields before asset automation can be described as profile-grounded.
3. Step 2A should start with Step 2A-min before Step 2A-full.
4. Step 2C must not depend on a dedicated `asset_master` table unless the team explicitly approves that migration.
5. Existing API names should follow implemented repo names unless explicitly renamed.
6. New target services should follow spec names.

---

## 6.6 v1.4 execution priority

1. persist and validate user tax-profile source-of-truth
2. converge billing from quota + credit to pure credit
3. harden the existing asset recognition pipeline
4. execute Step 2A-min
5. execute Step 2A-full
6. revisit asset persistence migration only after the above are stable

---

## 6.7 Management summary

v1.4 does not change the target architecture direction.

It changes the baseline assumptions:

- credit is already here
- the asset engine is already here
- modular pipeline refactor is still ahead
- user tax-profile persistence is now a blocking prerequisite
- asset storage migration is deferred

---

## Appendix A: Mandatory retire list

The following legacy or misleading behaviors must be explicitly retired as the repo converges toward the target architecture:

1. legacy quota-based gating in documents
2. legacy quota-based gating in AI assistant
3. legacy quota-based gating in transaction creation and import
4. usage progress UI as the primary billing display
5. heuristic `vat_status` inference from VAT number in production asset-decision paths
6. default `gewinnermittlungsart = UNKNOWN` in production asset-decision paths where the profile should instead be incomplete
7. pending-suggestion serialization of auto-create outcomes
