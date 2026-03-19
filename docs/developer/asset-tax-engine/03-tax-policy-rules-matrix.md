# Tax Policy Rules Matrix

## Purpose

Provide a versionable rules matrix for Austrian asset tax policy decisions used by:

- `asset_recognition_service`
- `asset_tax_policy_service`
- `asset_lifecycle_service`

## Matrix Structure

Every rule entry must support:

| Field | Meaning |
|---|---|
| `rule_id` | Stable identifier |
| `rule_level` | `hard`, `default`, `heuristic` |
| `jurisdiction` | `AT` |
| `valid_from` | Effective date |
| `valid_until` | End date or null |
| `inputs` | Required input facts |
| `outputs` | Policy outputs |
| `reason_codes` | Explainability |
| `source_reference` | Legal/business source |
| `override_allowed` | Whether user override is permitted |

## Section A. VAT Basis Selection

### VAT-001

- `rule_level`: `hard`
- `valid_from`: `2025-01-01`
- `valid_until`: null
- `inputs`:
  - `vat_status`
- `outputs`:
  - if `vat_status = regelbesteuert`, use `comparison_basis = net`
  - if `vat_status = kleinunternehmer`, use `comparison_basis = gross`
  - if `vat_status = unknown`, set `comparison_basis = gross`, `review_reason = vat_status_unknown`
- `override_allowed`: no

## Section B. GWG Eligibility and Election

### GWG-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `depreciable`
  - `expected_useful_life_gt_1y`
- `outputs`:
  - if not depreciable, `gwg_eligible = false`
  - if useful life not greater than 1 year, `gwg_eligible = false`
- `source_reference`: USP GWG
- `override_allowed`: no

### GWG-002

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: `2022-12-31`
- `inputs`:
  - `comparison_amount`
- `outputs`:
  - threshold = `800.00`
- `override_allowed`: no

### GWG-003

- `rule_level`: `hard`
- `valid_from`: `2023-01-01`
- `valid_until`: null
- `inputs`:
  - `comparison_amount`
- `outputs`:
  - threshold = `1000.00`
- `override_allowed`: no

### GWG-004

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `gwg_eligible`
  - `comparison_amount`
- `outputs`:
  - if within threshold, `decision_candidate = gwg_suggestion`
  - set `gwg_election_required = true`
- `source_reference`: GWG is a Wahlrecht
- `override_allowed`: yes

### GWG-005

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `gewinnermittlungsart`
  - `payment_date`
  - `put_into_use_date`
- `outputs`:
  - for `ea_rechnung`, GWG expense belongs to payment year
  - for `bilanzierung`, GWG expense belongs to acquisition/production year
- `override_allowed`: no

## Section C. Depreciability

### DEP-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - asset nature
- `outputs`:
  - land is not depreciable
  - artworks/collectibles default to `manual_review`
- `override_allowed`: no

### DEP-002

- `rule_level`: `heuristic`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - OCR text
  - line items
  - document type
- `outputs`:
  - service/repair/subscription/training/consulting/inventory -> `expense_only`
  - low-confidence ambiguous cases -> `manual_review`
- `override_allowed`: no

## Section D. Useful Life Defaults

These are default suggestions unless a stronger legal/tax-practice rule applies.

### LIFE-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = pkw`
- `outputs`:
  - `useful_life_years >= 8`
  - `useful_life_source = law`
- `override_allowed`: limited

### LIFE-002

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = electric_pkw`
- `outputs`:
  - `useful_life_years >= 8`
  - `useful_life_source = law`
- `override_allowed`: limited

### LIFE-003

- `rule_level`: `default`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = truck_van or fiscal_truck`
- `outputs`:
  - default `useful_life_years = 5`
  - `useful_life_source = tax_practice`
- `override_allowed`: yes

### LIFE-004

- `rule_level`: `default`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = computer or phone or perpetual_license`
- `outputs`:
  - default `useful_life_years = 3`
- `override_allowed`: yes

### LIFE-005

- `rule_level`: `default`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = office_furniture or machinery`
- `outputs`:
  - default `useful_life_years = 10`
- `override_allowed`: yes

## Section E. Depreciation Method

### DEP-METH-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `put_into_use_date`
- `outputs`:
  - linear method is always permitted unless explicitly excluded
- `override_allowed`: yes

### DEP-METH-002

- `rule_level`: `hard`
- `valid_from`: `2020-07-01`
- `valid_until`: null
- `inputs`:
  - `put_into_use_date`
  - `is_used_asset`
  - `asset_subtype`
- `outputs`:
  - degressive only available for qualifying new assets
  - default max rate `0.30`
  - used assets excluded
  - ordinary `pkw` excluded
- `override_allowed`: yes

### DEP-METH-003

- `rule_level`: `hard`
- `valid_from`: `2020-07-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = electric_pkw`
  - `is_used_asset = false`
- `outputs`:
  - include `degressive` in allowed methods
- `override_allowed`: yes

## Section F. Halbjahres-AfA / Put into Use

### HJ-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `put_into_use_date`
- `outputs`:
  - if put into use in second half of year, `half_year_rule_applicable = true`
- `override_allowed`: no

### HJ-002

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - missing `put_into_use_date`
- `outputs`:
  - add `missing_fields = put_into_use_date`
  - block `create_asset_auto`
- `override_allowed`: no

## Section G. PKW / EV / Truck Rules

### VEH-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = pkw`
- `outputs`:
  - income-tax cap applies
  - ordinary Vorsteuer recovery likely no
- `override_allowed`: no

### VEH-002

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = pkw or electric_pkw`
- `outputs`:
  - `income_tax_cost_cap = 40000.00`
- `override_allowed`: no

### VEH-003

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = electric_pkw`
- `outputs`:
  - VAT treatment follows EV rules, not ordinary PKW default
- `override_allowed`: no

### VEH-004

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = fiscal_truck`
- `outputs`:
  - do not apply ordinary PKW restrictions by default
- `override_allowed`: no

### VEH-005

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = pkw`
  - `is_used_asset = true`
  - `prior_owner_usage_years` or `first_registration_date`
- `outputs`:
  - compute remaining useful life based on prior use, but never below credible expected remaining life
- `override_allowed`: yes

## Section H. IFB Eligibility and Rates

### IFB-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `depreciable`
  - `gwg_eligible`
  - `useful_life_years`
  - `is_used_asset`
- `outputs`:
  - require useful life at least 4 years
  - exclude GWG
  - exclude used assets
- `override_allowed`: no

### IFB-002

- `rule_level`: `hard`
- `valid_from`: `2023-01-01`
- `valid_until`: `2025-10-31`
- `inputs`:
  - `put_into_use_date`
  - `ifb_category`
- `outputs`:
  - standard rate `0.10`
  - eco rate `0.15`
- `override_allowed`: no

### IFB-003

- `rule_level`: `hard`
- `valid_from`: `2025-11-01`
- `valid_until`: `2026-12-31`
- `inputs`:
  - `put_into_use_date`
  - `ifb_category`
- `outputs`:
  - standard rate `0.20`
  - eco rate `0.22`
- `override_allowed`: no

### IFB-004

- `rule_level`: `hard`
- `valid_from`: `2027-01-01`
- `valid_until`: null
- `inputs`:
  - `put_into_use_date`
  - `ifb_category`
- `outputs`:
  - fallback rate configuration required
  - if not configured, mark `review_reason = ifb_future_window_unknown`
- `override_allowed`: no

### IFB-005

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype`
  - `is_used_asset`
  - `depreciable`
- `outputs`:
  - exclude ordinary non-qualifying intangibles
  - exclude used assets
  - exclude ordinary PKW/Kombi
- `override_allowed`: no

### IFB-006

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `ifb_claimed`
- `outputs`:
  - set `ifb_hold_until = put_into_use_date + 4 years`
- `override_allowed`: no

## Section I. Software and Intangible Handling

### SW-001

- `rule_level`: `heuristic`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - OCR text and line items
- `outputs`:
  - if monthly/subscription/cloud/hosting indicators are strong, route to `expense_only`
- `override_allowed`: no

### SW-002

- `rule_level`: `heuristic`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - OCR text and line items
- `outputs`:
  - perpetual one-time license candidate -> `perpetual_license`
- `override_allowed`: yes

### SW-003

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `asset_subtype = perpetual_license`
  - digital/eco/health qualification markers
- `outputs`:
  - IFB only as candidate if qualifying intangible exception applies
- `override_allowed`: no

## Section J. Duplicate Detection

### DUP-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `file_hash`
- `outputs`:
  - exact hash match -> `duplicate_status = high_confidence`
  - decision downgraded to `duplicate_warning`
- `override_allowed`: no

### DUP-002

- `rule_level`: `heuristic`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - vendor
  - date
  - amount
  - invoice number
- `outputs`:
  - similar match -> `duplicate_status = suspected`
- `override_allowed`: no

## Section K. Manual Review Triggers

### MR-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - missing tax-critical fields
- `outputs`:
  - block `create_asset_auto`
- `override_allowed`: no

### MR-002

- `rule_level`: `heuristic`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - confidence near threshold
  - ambiguous subtype
  - ambiguous VAT basis
- `outputs`:
  - prefer `manual_review`
- `override_allowed`: no

### MR-003

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - amount at or near threshold boundary with missing VAT status
- `outputs`:
  - `manual_review`
- `override_allowed`: no

## Section L. Auto-Create Gate

### AUTO-001

- `rule_level`: `hard`
- `valid_from`: `1900-01-01`
- `valid_until`: null
- `inputs`:
  - `policy_confidence`
  - `missing_fields`
  - `duplicate_status`
  - `review_reasons`
  - structured document completeness
- `outputs`:
  - `create_asset_auto` only if:
    - confidence >= `0.95`
    - no missing critical fields
    - duplicate status `none`
    - no blocking review reasons
    - structured completeness satisfied
- `override_allowed`: no

## Rule Level Definitions

### `hard`

Derived from law, official tax treatment, or frozen business policy needed for compliance.

### `default`

System suggestion that can be overridden when facts justify it.

### `heuristic`

Recognition or suspicion logic based on OCR patterns, text clues, or matching rules. Never present as final legal truth.

## Non-Goals

- This matrix does not replace final tax filing logic.
- This matrix does not define every journal-entry outcome.
- This matrix does not encode all future Austrian law changes automatically.
- This matrix does not remove the need for user confirmation in ambiguous cases.
