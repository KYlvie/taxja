# Taxja Engineering Task Plan

**Execution-oriented companion to the repo-aligned adjusted spec**

- Baseline spec: `docs/taxja-complete-spec-all-5-parts.adjusted-2026-03-19.md`
- Purpose: convert the adjusted spec into work packages that are ready for assignment, sequencing, and acceptance review
- Date: `2026-03-19`

---

## 1. What this document is for

This is not a new architecture spec.

It is the engineering version of the adjusted spec:

- what must be done now
- what can be deferred
- what should be deleted or retired
- what counts as "done"
- what order the work should happen in

---

## 2. Baseline decisions

These decisions are treated as active until explicitly changed:

1. Credit billing already exists and is the strategic billing model.
2. The current problem is billing convergence, not billing greenfield implementation.
3. Asset recognition and tax policy engines already exist.
4. The current problem in the asset path is input reliability and integration cleanup, not rule-engine creation.
5. The document pipeline is still monolithic and the modular pipeline remains a real refactor target.
6. `Property` remains the canonical persistence layer for non-real-estate assets for now.

### Temporary architecture guardrail

While `Property` remains the canonical persistence layer for non-real-estate assets, all new asset-tax behavior must be exposed through asset-domain contracts and services rather than leaking `Property` semantics upward into orchestration and UI layers.

---

## 3. Priority buckets

## Must-do now

1. Persist `vat_status` and `gewinnermittlungsart` on `users`.
2. Validate those fields in profile update flows.
3. Remove production decision-path reliance on heuristic profile inference.
4. Converge quota + credit into a single billing source of truth.
5. Define Step 2A-min and use it as the first pipeline refactor milestone.

## Can defer

1. Separate `asset_master` table migration.
2. Full service-boundary split for all pipeline modules.
3. Broader benchmark and observability pack after the core contracts land.
4. Deep UI refinement of every asset decision interaction.

## Do not combine in one release

1. Billing convergence
2. Pipeline modular refactor
3. Asset storage migration

At most one of those should be the primary release-risk item in a given milestone.

---

## 4. Delete / Retire List

These are explicit cleanup targets, not just background debt:

1. Old quota gate in AI assistant request path.
2. Old quota gate in document OCR request path.
3. Old quota gate in transaction creation/import path.
4. Legacy usage progress UI once credit is the only billing source of truth.
5. Implicit `vat_status` inference from VAT number in production asset recognition path.
6. Default `gewinnermittlungsart = UNKNOWN` in production decision path when the profile should instead be incomplete.
7. Suggestion serialization that makes `CREATE_ASSET_AUTO` behave like a pending suggestion path.

---

## 5. Work packages

## WP-1: User Tax Profile Source of Truth

### Why this exists

The asset engine already exists, but critical inputs are still inferred or defaulted. That blocks reliable automation.

### Current status

- `vat_status`: enum exists in schemas, not persisted on `users`
- `gewinnermittlungsart`: enum exists in schemas, not persisted on `users`
- profile update: still too loose
- OCR asset input builder: still applies heuristic fallback

### Done definition

WP-1 is complete only when all of the following are true:

1. `users` table persists `vat_status`.
2. `users` table persists `gewinnermittlungsart`.
3. profile update request uses explicit schema validation rather than open-ended dict mutation.
4. OCR asset input builders read both values from persisted profile data.
5. production asset decision paths no longer infer `vat_status` from `vat_number`.
6. production asset decision paths no longer silently default `gewinnermittlungsart` to `UNKNOWN` when the user should instead be marked incomplete.
7. end-to-end tests cover profile save -> OCR input -> asset recognition.

### Task breakdown

Backend:

- add DB fields and migration
- update profile schemas
- update profile endpoint validation
- update user read/write serialization
- update OCR asset input builder
- add incomplete-profile handling contract

Frontend:

- add `vat_status` field to profile UI
- add `gewinnermittlungsart` field to profile UI
- add validation and save error messaging
- conditionally show fields only where relevant

Acceptance checks:

- user can save valid values
- invalid enum payload is rejected
- OCR asset recognition input reflects stored values
- self-employed/mixed users cannot silently enter automation with missing required tax-profile state

---

## WP-2: Billing Convergence and Credit Cutover

### Why this exists

Credits are already implemented, but the repo still runs a quota + usage + credit hybrid model.

### Current status

- credit balance, overage, top-up, settlement: present
- `usage_record`, `usage.py`, `usage_tracker_service`, `check_quota(...)`: still active
- several entrypoints still depend on old quota checks

### Cutover definition

Billing convergence is complete only when all of the following are true:

1. New requests no longer write `usage_record` for billing enforcement.
2. Major product entrypoints no longer call `check_quota(...)` for billing enforcement.
3. Frontend primary billing and subscription views no longer depend on quota percentages or legacy usage counters.
4. The usage API is either removed or clearly demoted to non-billing compatibility/read-only status.
5. Remaining balance, overage, top-up, settlement, and payment recovery all resolve from the credit system as the sole billing source of truth.

### Task breakdown

Backend:

- inventory every `check_quota(...)` callsite
- remove or bypass quota enforcement where credit already enforces billing
- stop writing new billing-critical usage records
- decide whether `usage.py` becomes read-only compatibility or is removed
- align docs and subscription responses to credit-only language

Frontend:

- remove quota fallback UI where credit balance exists
- stop using old usage mental model in plan/status displays
- ensure AI/OCR/transactions all communicate billing via credits only

Acceptance checks:

- AI assistant, OCR upload, and transaction creation work without quota checks
- billing failure behavior is governed by credits/overage only
- no billing-critical path depends on `usage_record`

---

## WP-3: Asset Engine Input Hardening

### Why this exists

The rule engine is mostly present. The remaining work is to make its decisions reliable and explainable end to end.

### Current status

- recognition service: present
- tax policy service: present
- snapshot and event models: present
- input sourcing: incomplete
- downstream semantics for auto-create vs suggestion: incomplete

### Done definition

WP-3 is complete only when:

1. asset recognition consumes persisted tax-profile inputs
2. duplicate detector outcomes are explicitly surfaced downstream
3. `create_asset_auto` is a terminal persistence path rather than a pending suggestion serialization
4. `create_asset_suggestion` always requires explicit user confirmation
5. downstream UI state, DB state, and audit log clearly distinguish auto-created outcomes from suggestion-required outcomes
6. `create_asset_auto` and `create_asset_suggestion` have different persistence behavior
7. required-field absence blocks silent auto-create
8. policy confidence, reason codes, review reasons, and missing fields remain traceable from OCR to final asset record or suggestion

### Task breakdown

- align OCR suggestion builder behavior to decision semantics
- separate auto-create path from pending-suggestion path
- ensure put-into-use date rules are respected
- expand audit payloads where needed
- add E2E tests from document -> recognition -> confirmation/creation

Acceptance checks:

- auto path does not degrade into a pending suggestion unless explicitly forced by quality gate
- missing profile data causes controlled incompleteness, not hidden heuristics
- created asset retains traceable recognition and policy context

---

## WP-4: Step 2A-min Pipeline Contract

### Why this exists

Step 2A is the biggest refactor risk. It should not start with a full service split.

### Goal

Land the semantic contracts first, while keeping the orchestrator mostly intact.

### Step 2A-min definition

Step 2A-min is complete when:

1. a stable `NormalizedDocument` contract exists
2. `NormalizedDocument` is the only business-decision input type
3. a stable quality-gate decision contract exists
4. quality-gate output is the only persistence-branching decision contract
5. the current orchestrator calls extracted modules for normalization and quality-gate logic
6. first-result persistence and final persistence boundaries are explicitly defined
7. metering semantics are defined, even if not yet a separate service

### Step 2A-min tasks

- define `NormalizedDocument`
- extract normalization logic from ad hoc pipeline code into a dedicated module
- define quality-gate decision types and priority order
- define first-result checkpoint contract
- define finalization checkpoint contract
- update tests to assert contract outputs instead of internal implementation details

### Acceptance checks

- normalization output shape is stable and tested
- quality-gate output shape is stable and tested
- business decision logic no longer consumes ad hoc pre-normalized structures
- persistence branching no longer bypasses the quality-gate contract
- orchestrator remains functional while delegating to extracted modules
- UI can show first-result data without waiting for full auto-create completion

---

## WP-5: Step 2A-full Modular Pipeline Refactor

### Why this exists

This is the full target architecture from the adjusted spec, but it should happen after Step 2A-min.

### Step 2A-full definition

Step 2A-full is complete when:

1. `processing_decision_service` exists
2. `document_normalization_service` exists
3. `document_quality_gate_service` exists
4. metering is isolated in a bounded sidecar/service contract
5. orchestrator responsibility is reduced to orchestration rather than embedded business logic
6. Phase 1 and Phase 2 checkpointing are explicit and observable

### Task breakdown

- introduce processing decision contract
- introduce dedicated normalization service
- introduce dedicated quality-gate service
- isolate metering
- reduce orchestrator business logic
- add observability for first-result and total pipeline latency

### Acceptance checks

- module boundaries are explicit
- checkpoint behavior is observable
- call-count limits can be measured and tested
- orchestrator no longer owns hidden normalization or quality-gate rules

---

## WP-6: Asset Storage Decision

### Why this exists

The current repo uses `Property` for non-real-estate assets. That is workable, but it must be an explicit decision.

### Decision options

Option A: keep `Property` as canonical asset persistence for now.

Option B: introduce dedicated `asset_master` storage later.

### Recommendation

Use Option A for the next milestone.

### Done definition

This work package is complete when the team explicitly records one of the two decisions and updates the spec language accordingly.

### Acceptance checks

- no active implementation task assumes a dedicated asset table unless that migration is approved
- higher-level services use asset-domain contracts regardless of the persistence model

---

## 6. Suggested sequencing

## Milestone 1

1. WP-1 User Tax Profile Source of Truth
2. WP-2 Billing Convergence and Credit Cutover

## Milestone 2

1. WP-3 Asset Engine Input Hardening
2. WP-4 Step 2A-min Pipeline Contract

## Milestone 3

1. WP-5 Step 2A-full Modular Pipeline Refactor
2. WP-6 Asset Storage Decision, only if still needed

---

## 7. Acceptance pack by milestone

## Milestone 1 acceptance

- profile persistence works
- OCR and asset recognition stop using heuristic production defaults
- major billing paths no longer depend on quota enforcement
- credit is the only billing source of truth in primary flows

## Milestone 2 acceptance

- asset recognition behaves consistently with persisted inputs
- `create_asset_auto` and suggestion paths are meaningfully separated
- normalized document contract exists and is stable
- quality-gate contract exists and is stable

## Milestone 3 acceptance

- modular pipeline services exist and are wired
- checkpointing is explicit
- observability is present
- performance guardrails can be measured

---

## 8. Assignment-ready task labels

Suggested labels for issue tracking:

- `P0-profile-source-of-truth`
- `P0-billing-cutover`
- `P1-asset-hardening`
- `P1-pipeline-2a-min`
- `P2-pipeline-2a-full`
- `Decision-asset-storage`
- `Cleanup-delete-legacy-usage`

---

## 9. One-line management summary

Taxja should not spend the next cycle rebuilding billing or rebuilding the asset engine from scratch. The correct next cycle is to finish tax-profile source-of-truth, complete billing convergence, harden the existing asset pipeline, and only then start the modular pipeline refactor in a staged way.
