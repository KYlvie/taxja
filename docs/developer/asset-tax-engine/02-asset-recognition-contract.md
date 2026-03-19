# Asset Recognition Service Contract

## Purpose

Define the service contract for recognition-stage classification of uploaded documents into:

- non-asset expense path
- GWG suggestion
- asset suggestion
- high-confidence auto-create
- duplicate warning
- manual review

This contract is for pre-creation decisioning. It does not issue final statutory tax advice.

## Service Boundary

Suggested service name: `asset_recognition_service`

This service answers:

1. Does this document represent an asset-relevant acquisition candidate?
2. If yes, what is the most likely tax treatment class?
3. What information is still missing before safe creation?
4. Is duplicate risk high enough to block or downgrade automation?

## Inputs

### A. OCR Extracted Inputs

| Field | Type | Required | Notes |
|---|---|---:|---|
| `extracted_amount` | decimal | yes | Fallback gross if structure weak |
| `extracted_net_amount` | decimal | no | If available |
| `extracted_vat_amount` | decimal | no | If available |
| `extracted_date` | date | no | Invoice/receipt/contract date |
| `extracted_vendor` | string | no | Supplier |
| `extracted_invoice_number` | string | no | Invoice or contract number |
| `extracted_line_items` | array | no | OCR line items |
| `document_language` | string | no | OCR language guess |
| `raw_text` | string | yes | Full OCR text |
| `document_type` | string | yes | Existing classifier output |
| `ocr_confidence` | decimal | no | OCR confidence if available |

### B. User Tax Profile Inputs

| Field | Type | Required | Notes |
|---|---|---:|---|
| `vat_status` | enum | yes | `regelbesteuert`, `kleinunternehmer`, `pauschaliert`, `unknown` |
| `gewinnermittlungsart` | enum | yes | `bilanzierung`, `ea_rechnung`, `pauschal`, `unknown` |
| `business_type` | string | yes | Current user business profile |
| `industry_code` | string | no | For subtype hints |
| `default_business_use_percentage` | decimal | no | Optional heuristic |

### C. Document Metadata Inputs

| Field | Type | Required | Notes |
|---|---|---:|---|
| `source_document_id` | int | yes | Origin document |
| `upload_timestamp` | datetime | yes | Useful for audit only |
| `file_hash` | string | no | Strong duplicate signal |
| `mime_type` | string | no | PDF/image/etc |
| `page_count` | int | no | Useful for contracts |

### D. Existing Data Inputs

| Field | Type | Required | Notes |
|---|---|---:|---|
| `duplicate_document_candidates` | array | no | Hash/vendor/date amount matches |
| `duplicate_asset_candidates` | array | no | Existing assets with similar facts |
| `related_transactions` | array | no | Optional linkage |

## Interaction Model

The service input contract must not be confused with user-facing forms.

### System-first Collection

The system should populate first:

- OCR values
- document metadata
- VAT comparison basis candidate
- duplicate candidates
- asset subtype heuristics

### User-confirmed Inputs

Only ask the user for facts that materially change the tax result:

- `put_into_use_date`
- `business_use_percentage`
- `is_used_asset`
- `first_registration_date` or `prior_owner_usage_years` for used vehicles
- `gwg_elected`
- `depreciation_method`
- `degressive_afa_rate`

### Progressive Disclosure

Default UX:

1. system shows suggestion
2. system shows reason summary
3. user confirms only the missing tax-critical facts
4. advanced section exposes optional edits

## Output Decision Enum

### 1. `expense_only`

Trigger when:

- clearly service, repair, maintenance, subscription, training, consulting, shipping-only, consumable, or inventory
- or not plausibly a long-lived acquisition and confidence is high

### 2. `gwg_suggestion`

Trigger when:

- item is plausibly a depreciable asset
- expected useful life > 1 year
- comparison amount is within active GWG threshold for the relevant time window
- user should be offered Wahlrecht when appropriate

### 3. `create_asset_suggestion`

Trigger when:

- item is a likely depreciable fixed asset
- comparison amount exceeds active GWG threshold
- duplicate risk is low or manageable
- no blocking rule conflict exists

### 4. `create_asset_auto`

Trigger only when all are true:

- structured document type with high recognition quality
- `policy_confidence >= 0.95`
- structural completeness is sufficient
- duplicate risk is low
- no blocking review reasons
- no required user-only facts are missing, unless policy explicitly allows safe defaults

### 5. `duplicate_warning`

Trigger when:

- `file_hash` matches a known document
- or vendor/date/amount/invoice combo strongly matches
- or a high-confidence existing asset/document duplicate exists

### 6. `manual_review`

Trigger when:

- tax rules conflict
- confidence is below threshold
- `abnutzbar` status is unclear
- amount is near relevant threshold boundary with ambiguous VAT basis
- duplicate signals are conflicting
- missing user facts are too important to proceed safely

## Output Payload

```json
{
  "decision": "create_asset_suggestion",
  "asset_candidate": {
    "asset_type": "computer",
    "asset_subtype": "computer",
    "asset_name": "MacBook Pro",
    "vendor_name": "Example Supplier GmbH"
  },
  "tax_flags": {
    "depreciable": true,
    "gwg_eligible": false,
    "gwg_default_selected": false,
    "gwg_election_required": false,
    "comparison_basis": "net",
    "comparison_amount": 1499.00,
    "vat_recoverable_status": "likely_yes",
    "ifb_candidate": true,
    "ifb_rate": 0.20,
    "half_year_rule_applicable": false,
    "allowed_depreciation_methods": ["linear", "degressive"],
    "suggested_depreciation_method": "linear",
    "suggested_useful_life_years": 3
  },
  "reason_codes": [
    "durable_equipment_detected",
    "useful_life_gt_1y",
    "amount_above_gwg_threshold"
  ],
  "review_reasons": [],
  "missing_fields": ["put_into_use_date"],
  "requires_user_confirmation": true,
  "policy_confidence": 0.91,
  "duplicate": {
    "duplicate_status": "none",
    "duplicate_match_type": null,
    "matched_asset_id": null,
    "matched_document_id": null,
    "duplicate_reason_codes": []
  }
}
```

## Output Field Definitions

### Core

| Field | Type | Required | Notes |
|---|---|---:|---|
| `decision` | enum | yes | One of the six decision states |
| `policy_confidence` | decimal | yes | Used for gating, not user-facing alone |
| `requires_user_confirmation` | bool | yes | Whether UI must collect user confirmation |

### Candidate

| Field | Type | Required | Notes |
|---|---|---:|---|
| `asset_candidate.asset_type` | string | no | Schema type |
| `asset_candidate.asset_subtype` | string | no | More specific subtype |
| `asset_candidate.asset_name` | string | no | Suggested name |
| `asset_candidate.vehicle_category` | string | no | For vehicle rules |
| `asset_candidate.is_used_asset` | bool | no | Inferred if possible |

### Tax Flags

| Field | Type | Required | Notes |
|---|---|---:|---|
| `tax_flags.depreciable` | bool | yes | Core policy flag |
| `tax_flags.gwg_eligible` | bool | yes | Policy result |
| `tax_flags.gwg_default_selected` | bool | yes | Default recommendation |
| `tax_flags.gwg_election_required` | bool | yes | Whether UI must ask |
| `tax_flags.comparison_basis` | enum | yes | `net` or `gross` |
| `tax_flags.comparison_amount` | decimal | yes | Amount used in threshold check |
| `tax_flags.vat_recoverable_status` | enum | yes | `likely_yes`, `likely_no`, `partial`, `unclear` |
| `tax_flags.ifb_candidate` | bool | yes | Candidate only |
| `tax_flags.ifb_rate` | decimal | no | Current policy-derived rate |
| `tax_flags.allowed_depreciation_methods` | array | yes | Valid methods |
| `tax_flags.suggested_depreciation_method` | enum | no | Default suggestion |
| `tax_flags.suggested_useful_life_years` | decimal | no | Suggestion only |
| `tax_flags.half_year_rule_applicable` | bool | yes | Based on `put_into_use_date` once known |

### Explainability

| Field | Type | Required | Notes |
|---|---|---:|---|
| `reason_codes` | array | yes | Why the system decided this |
| `review_reasons` | array | yes | Why stronger automation was blocked |
| `missing_fields` | array | yes | Facts needed from user |

### Duplicate

| Field | Type | Required | Notes |
|---|---|---:|---|
| `duplicate.duplicate_status` | enum | yes | `none`, `suspected`, `high_confidence` |
| `duplicate.duplicate_match_type` | enum | no | `same_document`, `same_invoice`, `similar_asset` |
| `duplicate.matched_asset_id` | int | no | Existing asset |
| `duplicate.matched_document_id` | int | no | Existing document |
| `duplicate.duplicate_reason_codes` | array | yes | Explanation |

## Confidence and Review Thresholds

Frozen baseline:

- `create_asset_auto` requires `policy_confidence >= 0.95`
- `create_asset_suggestion` generally requires `policy_confidence >= 0.65`
- below `0.65`, prefer `manual_review` unless a hard negative path clearly applies

These thresholds may later be versioned by policy configuration, but must be explicit.

## Non-Goals

The recognition service does not:

- file tax returns
- make final legal conclusions for VAT or IFB claims
- post accounting journal entries
- replace downstream lifecycle computations
- silently override user-supplied tax-critical facts
