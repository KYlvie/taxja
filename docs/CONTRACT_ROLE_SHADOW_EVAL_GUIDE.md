# Contract Role Shadow Evaluation Guide

## Purpose

Use this guide to evaluate the new contract-side resolution logic while
`CONTRACT_ROLE_MODE=shadow`.

In shadow mode, the system should:

- infer the user's likely side in a contract
- show candidate, source, confidence, and evidence in review
- keep current legacy flows mostly usable for evaluation
- show when strict mode would block the current action

This guide focuses on the first rollout scope only:

- rental contracts (`Mietvertrag`)
- purchase contracts (`Kaufvertrag`) for property and assets

## Current Mode

Local default is currently:

```env
CONTRACT_ROLE_MODE=shadow
```

Configured in:

- `backend/.env`

If the backend was already running before this change, restart it before
starting the evaluation round.

## What To Check On Every File

For every relevant test file, verify these six points:

1. The document type is correct.
2. The new `我的身份` selector appears.
3. The `合同身份判断` card appears.
4. The card shows:
   - candidate role
   - source
   - confidence
   - evidence
5. The suggested downstream action matches the user's actual side.
6. If the side is wrong for auto-action, shadow mode shows a warning about
   what strict mode would block.

## Scenario Matrix

### Rental contracts

#### A. User is the landlord

Expected:

- candidate should usually resolve to `landlord`
- source should ideally be `party_name_match` or `property_context`
- recurring income suggestion may remain available
- no strict-block warning should appear

#### B. User is the tenant

Expected:

- candidate should usually resolve to `tenant`
- recurring income should **not** be treated as the correct final direction
- shadow warning should appear, indicating strict mode would block landlord-side automation

#### C. User side is unclear

Expected:

- candidate should be `unknown` or visibly uncertain
- confidence should be lower
- evidence should explain ambiguity or lack of party match
- shadow warning should appear

### Purchase contracts - property

#### D. User is the buyer

Expected:

- candidate should usually resolve to `buyer`
- property suggestion can remain available
- no strict-block warning should appear

#### E. User is the seller

Expected:

- candidate should usually resolve to `seller`
- system should not silently behave like this is a purchase on the user's side
- shadow warning should appear

#### F. Buyer/seller unclear

Expected:

- candidate should be `unknown` or low-confidence
- evidence should explain ambiguity
- shadow warning should appear

### Purchase contracts - asset or vehicle

#### G. User is the buyer

Expected:

- candidate should resolve to `buyer`
- asset path should behave normally

#### H. User is the seller

Expected:

- candidate should resolve to `seller`
- asset creation should be treated as the wrong side
- shadow mode should clearly show strict-mode blocking

#### I. Buyer/seller unclear

Expected:

- candidate should be `unknown`
- evidence should explain why
- shadow warning should appear

## Manual Override Check

For at least one file in each family:

1. Open review.
2. Change `我的身份`.
3. Save the correction.
4. Verify the suggestion is rebuilt immediately.

Expected:

- role fields in OCR state should update
- evidence/source should reflect override where appropriate
- if the overridden role would block strict mode, the warning should update too

## Recommended Evaluation Pass

### Pass 1: Clean matches

Use files where:

- the user name clearly appears as `Vermieter` or `Käufer`
- the opposite side is a different person/company

Goal:

- validate that straightforward party matches are stable

### Pass 2: Opposite-side files

Use files where:

- the user is clearly `tenant` or `seller`

Goal:

- validate that the system does not keep pretending these are landlord/buyer flows

### Pass 3: Ambiguous files

Use files where:

- party names are abbreviated
- both sides are companies
- names are OCR-noisy
- the document is incomplete

Goal:

- validate that the system degrades to uncertainty instead of confidently choosing the wrong side

### Pass 4: Manual override

Use a subset of failed or ambiguous examples.

Goal:

- confirm manual correction makes the system recover cleanly

## Suggested Recording Template

Use a simple table while reviewing:

| File | Contract family | Real user side | Candidate | Confidence | Source | Shadow warning | Final suggestion acceptable? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| example.pdf | rental | tenant | tenant | 0.87 | party_name_match | yes | yes | good |

## Suggested Exit Criteria Before `strict`

Do not switch to strict mode until all of these are true:

1. No critical wrong-side automation remains in the evaluated sample set.
2. Straightforward landlord/buyer files are consistently recognized.
3. Straightforward tenant/seller files are consistently surfaced as opposite-side cases.
4. Ambiguous files tend to fall back to uncertainty instead of a confident wrong guess.
5. Manual override reliably updates downstream suggestions.

Recommended practical threshold:

- zero critical wrong-side auto-actions in the reviewed sample
- strong accuracy on clear-name matches
- acceptable ambiguity handling on OCR-noisy contracts

## After Evaluation

If the sample behavior looks good:

1. switch `CONTRACT_ROLE_MODE` to `strict`
2. restart backend
3. run one short smoke pass on the same contract families

If the sample behavior is not good enough:

1. keep `shadow`
2. collect the failure examples
3. refine:
   - party extraction
   - user-name matching
   - confidence calibration
   - upload-context weighting
