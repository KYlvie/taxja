# Asset Master Schema Specification

## Purpose

Define the persistent asset model for Austrian tax handling.

This schema is not limited to OCR detection. It must support:

- asset recognition
- tax classification
- user confirmation
- policy snapshotting
- event-driven lifecycle updates

## Core Principles

1. Facts, inferences, policy outputs, and user overrides must be distinguishable.
2. Policy results must be reproducible later.
3. Historical assets must preserve the rule context that applied at `put_into_use_date`.
4. Fields needed for tax policy must exist before lifecycle features are implemented.

## Source Origin Enum

Every mutable tax-relevant field should carry a source tag where practical.

`FieldSource`

- `document_extracted`
- `system_inferred`
- `policy_derived`
- `user_confirmed`
- `user_overridden`
- `system_generated`

## Asset Master Record

Suggested logical model name: `AssetMaster`

### A. Core Identity

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `asset_id` | UUID/int | yes | system_generated | Primary identifier |
| `user_id` | int | yes | system_generated | Owner |
| `asset_type` | enum | yes | system_inferred or user_overridden | High-level schema type used by app |
| `asset_subtype` | enum | yes | system_inferred or user_overridden | Tax-relevant subtype |
| `asset_name` | string | yes | document_extracted or user_confirmed | User-facing name |
| `status` | enum | yes | system_generated | `draft`, `active`, `disposed`, `scrapped`, `withdrawn` |
| `source_document_id` | int | no | system_generated | Main originating document |
| `source_confidence` | decimal | no | system_inferred | Recognition confidence |
| `recognition_decision` | enum | yes | system_generated | Mirrors contract decision used during creation |

### B. Acquisition Facts

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `acquisition_kind` | enum | yes | user_confirmed or system_inferred | `purchase`, `finance_lease`, `operating_lease`, `self_constructed`, `used_asset` |
| `vendor_name` | string | no | document_extracted | Supplier/vendor |
| `vendor_tax_id` | string | no | document_extracted | Optional |
| `invoice_number` | string | no | document_extracted | Optional but useful for duplicate detection |
| `invoice_date` | date | no | document_extracted | Not sufficient for AfA start |
| `purchase_date` | date | no | document_extracted or user_confirmed | Commercial acquisition date |
| `put_into_use_date` | date | no | user_confirmed or document_extracted | Tax anchor for policy snapshot and AfA start |
| `payment_date` | date | no | document_extracted or user_confirmed | Relevant for E/A GWG timing |
| `first_registration_date` | date | no | document_extracted or user_confirmed | Used for vehicles, especially used vehicles |
| `prior_owner_usage_years` | decimal | no | user_confirmed | Used for gebrauchte PKW useful-life logic |
| `is_used_asset` | bool | yes | user_confirmed or system_inferred | Hard IFB/degressive relevance |

### C. Monetary Facts

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `amount_net` | decimal | no | document_extracted | Extracted net amount |
| `amount_gross` | decimal | yes | document_extracted | Fallback base |
| `vat_amount` | decimal | no | document_extracted | Extracted VAT |
| `currency` | string | yes | document_extracted or system_generated | Default EUR |
| `comparison_basis` | enum | yes | policy_derived | `net`, `gross` |
| `comparison_amount` | decimal | yes | policy_derived | Amount used for GWG / thresholds |
| `income_tax_cost_cap` | decimal | no | policy_derived | For PKW/Kombi cap logic |
| `income_tax_depreciable_base` | decimal | no | policy_derived | Base after caps/restrictions |

### D. Tax Policy Fields

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `depreciable` | bool | yes | policy_derived | Whether regular AfA applies |
| `depreciable_reason_code` | string | no | policy_derived | Why yes/no |
| `gwg_eligible` | bool | yes | policy_derived | Threshold + asset nature |
| `gwg_default_selected` | bool | yes | policy_derived | Default recommendation |
| `gwg_elected` | bool | no | user_confirmed | User's actual election |
| `gwg_election_required` | bool | yes | policy_derived | Whether UI must ask |
| `depreciation_method` | enum | no | user_confirmed or policy_derived | `linear`, `degressive` |
| `allowed_depreciation_methods` | json/array | yes | policy_derived | Valid options at creation |
| `degressive_afa_rate` | decimal | no | user_confirmed | Actual selected degressive rate |
| `degressive_elected_at` | datetime | no | system_generated | Audit trail |
| `degressive_switch_to_linear_at` | date | no | system_generated or user_confirmed | Event-triggered |
| `useful_life_years` | decimal | no | user_confirmed or policy_derived | Suggested or overridden |
| `useful_life_source` | enum | no | policy_derived or user_overridden | `law`, `tax_practice`, `system_default`, `user_override` |
| `half_year_rule_applicable` | bool | yes | policy_derived | Based on `put_into_use_date` |
| `vat_recoverable_status` | enum | yes | policy_derived | `likely_yes`, `likely_no`, `partial`, `unclear` |
| `vat_recoverable_reason_codes` | json/array | no | policy_derived | Explanation |
| `ifb_candidate` | bool | yes | policy_derived | Candidate only, not final claim |
| `ifb_rate` | decimal | no | policy_derived | 0.10 / 0.15 / 0.20 / 0.22 etc. |
| `ifb_rate_source` | enum | no | policy_derived | `statutory_window`, `fallback_default`, `not_applicable` |
| `ifb_exclusion_codes` | json/array | no | policy_derived | Used asset, non-qualifying intangible, GWG, etc. |
| `ifb_hold_until` | date | no | policy_derived | Hold period end if IFB claimed |
| `ifb_claimed` | bool | no | user_confirmed or downstream tax flow | Separate from candidate |
| `policy_confidence` | decimal | yes | system_inferred | Used for auto/suggestion gating |

### E. Usage and Mixed Use

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `business_use_percentage` | decimal | no | user_confirmed | Usually required for mixed use |
| `mixed_use` | bool | yes | user_confirmed or policy_derived | Whether private/business mix exists |
| `private_use_notes` | string | no | user_confirmed | Optional explanatory note |
| `location_label` | string | no | user_confirmed | Office, vehicle, workshop, etc. |

### F. Governance and Review

| Field | Type | Required | Source | Notes |
|---|---|---:|---|---|
| `requires_user_confirmation` | bool | yes | system_generated | Should user see confirmation flow |
| `review_reasons` | json/array | no | system_generated | Why manual attention is needed |
| `missing_fields` | json/array | no | system_generated | Missing facts blocking stronger decision |
| `overridden_fields` | json/array | no | system_generated | Audit record of user changes |
| `user_confirmed_at` | datetime | no | system_generated | Confirmation timestamp |
| `user_confirmed_by` | int | no | system_generated | Usually same user |
| `policy_snapshot_id` | int/uuid | yes | system_generated | Links applied rule context |
| `duplicate_status` | enum | yes | system_generated | `none`, `suspected`, `high_confidence` |
| `matched_asset_id` | int | no | system_generated | Duplicate link |
| `matched_document_id` | int | no | system_generated | Duplicate link |

## Asset Subtype Enum

Minimum frozen subtype set:

- `real_estate`
- `pkw`
- `electric_pkw`
- `truck_van`
- `fiscal_truck`
- `motorcycle`
- `special_vehicle`
- `computer`
- `phone`
- `printer_scanner`
- `monitor_av`
- `server_network`
- `office_furniture`
- `machinery`
- `tools`
- `retail_equipment`
- `restaurant_equipment`
- `medical_beauty_equipment`
- `leasehold_improvement`
- `renewable_energy`
- `bike_mobility`
- `perpetual_license`
- `other_equipment`

## Policy Snapshot

Suggested logical model name: `AssetPolicySnapshot`

### Purpose

Freeze the tax policy context used to classify and create the asset.

### Time Anchor

The snapshot is anchored to `put_into_use_date`, not confirmation timestamp.

If `put_into_use_date` is missing at creation time:

- snapshot uses a provisional anchor
- asset remains confirmation-sensitive
- recomputation is required once `put_into_use_date` is known

### Required Fields

| Field | Type | Notes |
|---|---|---|
| `policy_snapshot_id` | UUID/int | Primary key |
| `policy_version` | string | Internal version label |
| `jurisdiction` | string | `AT` |
| `effective_anchor_date` | date | Usually `put_into_use_date` |
| `snapshot_payload` | json | Full policy facts and outputs |
| `rule_ids` | json/array | Referenced matrix rule ids |
| `created_at` | datetime | Timestamp |

## Asset Event Model

Suggested logical model name: `AssetEvent`

### Event Types

- `acquired`
- `put_into_use`
- `reclassified`
- `business_use_changed`
- `degressive_to_linear_switch`
- `ifb_flagged`
- `ifb_claimed`
- `sold`
- `scrapped`
- `private_withdrawal`

### Event Fields

| Field | Type | Notes |
|---|---|---|
| `event_id` | UUID/int | Primary key |
| `asset_id` | int | Foreign key |
| `event_type` | enum | One of the above |
| `event_date` | date | Business-effective date |
| `payload` | json | Event-specific details |
| `trigger_source` | enum | `system`, `user`, `policy_recompute`, `import` |
| `created_at` | datetime | Audit timestamp |

## Recompute Triggers

These changes require recomputation of tax policy or future schedule:

- change to `put_into_use_date`
- change to `asset_subtype`
- change to `business_use_percentage`
- marking asset as used vs new
- change to `first_registration_date` or `prior_owner_usage_years`
- VAT status/profile change affecting comparison basis
- explicit degressive-to-linear switch
- IFB claim activation or revocation
- disposal or withdrawal event

## UI Interaction Implications

The asset master schema must not force users into large forms.

Only these are expected as common user-confirmed facts during creation:

- `put_into_use_date`
- `business_use_percentage`
- `is_used_asset`
- `first_registration_date` or `prior_owner_usage_years` when required
- `gwg_elected`
- `depreciation_method`
- `degressive_afa_rate` when chosen

All other fields should default to extracted, inferred, or policy-derived values whenever possible.

## Non-Goals

- No requirement that every field be present before suggestion generation
- No requirement that all tax outcomes be final at recognition time
- No silent replacement of user overrides during recomputation
