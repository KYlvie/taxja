# Requirements Document: Property Asset Management

## Introduction

This document specifies requirements for property asset management functionality in the Taxja Austrian tax management platform. The feature enables landlords to track rental properties, calculate depreciation (AfA - Absetzung für Abnutzung), link properties to rental income/expenses, and import historical property data for accurate multi-year tax calculations.

The feature addresses a critical gap for landlords who need to track long-term assets and their associated depreciation according to Austrian tax law. It integrates with existing E1/Bescheid import functionality and supports historical data import for new users.

## Glossary

- **Property_Management_System**: The subsystem responsible for managing rental property assets
- **AfA_Calculator**: The component that calculates annual depreciation (Absetzung für Abnutzung)
- **Property**: A rental real estate asset tracked in the system
- **Building_Value**: The depreciable portion of property purchase price (excludes land value)
- **Depreciation_Rate**: Annual percentage for AfA calculation (1.5% or 2%)
- **E1_Import_Service**: Existing service that imports E1 tax declaration forms
- **Bescheid_Import_Service**: Existing service that imports tax assessment documents
- **Transaction_Linker**: Component that associates transactions with properties
- **Historical_Import_Service**: Service that backfills depreciation for previous years
- **Kaufvertrag**: Purchase contract document
- **Mietvertrag**: Rental contract document
- **KZ_350**: Tax form field code for rental income (Vermietung und Verpachtung)
- **OCR_Service**: Optical Character Recognition service for extracting text from documents
- **Property_Type**: Classification of property usage (Rental, Owner-Occupied, Mixed-Use)
- **Rental_Percentage**: For mixed-use properties, the percentage used for rental vs personal use
- **Grunderwerbsteuer**: Property transfer tax (real estate purchase tax in Austria)
- **ImmoESt**: Immobilienertragsteuer (real estate capital gains tax in Austria)
- **Owner-Occupied**: Property used as primary residence (Eigennutzung)
- **Mixed-Use**: Property with both rental and personal use portions (Gemischt)

## Requirements

### Requirement 1: Property Registration

**User Story:** As a landlord, I want to register my rental properties with purchase details, so that the system can calculate depreciation and track property-related expenses.

#### Acceptance Criteria

1. THE Property_Management_System SHALL accept property registration with address, purchase_date, purchase_price, and building_value
2. WHEN building_value is not provided, THE Property_Management_System SHALL accept total purchase_price and calculate building_value as 80% of purchase_price
3. THE Property_Management_System SHALL validate that purchase_date is not in the future
4. THE Property_Management_System SHALL validate that building_value is less than or equal to purchase_price
5. THE Property_Management_System SHALL validate that building_value is greater than zero
6. THE Property_Management_System SHALL store property ownership linked to the authenticated user
7. THE Property_Management_System SHALL assign a unique identifier to each registered property

### Requirement 2: Depreciation Rate Determination

**User Story:** As a landlord, I want the system to automatically determine the correct depreciation rate based on building age, so that my AfA calculations comply with Austrian tax law.

#### Acceptance Criteria

1. WHEN a property has construction_year before 1915, THE AfA_Calculator SHALL use a depreciation_rate of 1.5%
2. WHEN a property has construction_year of 1915 or later, THE AfA_Calculator SHALL use a depreciation_rate of 2.0%
3. WHEN construction_year is not provided, THE AfA_Calculator SHALL use a default depreciation_rate of 2.0%
4. THE AfA_Calculator SHALL allow manual override of depreciation_rate with values between 0.5% and 10%
5. THE AfA_Calculator SHALL store the depreciation_rate with each property record

### Requirement 3: Annual Depreciation Calculation

**User Story:** As a landlord, I want the system to automatically calculate annual depreciation for my properties, so that I can claim the correct AfA deduction on my tax return.

#### Acceptance Criteria

1. FOR ALL properties with purchase_date in current or previous years, THE AfA_Calculator SHALL calculate annual_depreciation as building_value multiplied by depreciation_rate
2. WHEN purchase_date is in the current year, THE AfA_Calculator SHALL calculate pro_rated_depreciation based on months_owned divided by 12
3. THE AfA_Calculator SHALL round depreciation amounts to 2 decimal places
4. FOR ALL properties, THE AfA_Calculator SHALL ensure that total_accumulated_depreciation does not exceed building_value
5. WHEN total_accumulated_depreciation equals building_value, THE AfA_Calculator SHALL set annual_depreciation to zero
6. THE AfA_Calculator SHALL generate depreciation as an expense transaction with category "Depreciation_AfA"

### Requirement 4: Property-Transaction Linking

**User Story:** As a landlord, I want to link rental income and expenses to specific properties, so that I can track profitability per property and generate accurate tax reports.

#### Acceptance Criteria

1. THE Transaction_Linker SHALL allow associating a transaction with a property_id
2. WHEN a transaction has category "Rental_Income", THE Transaction_Linker SHALL require property_id assignment
3. WHEN a transaction has category matching property expense types, THE Transaction_Linker SHALL allow optional property_id assignment
4. THE Transaction_Linker SHALL validate that property_id belongs to the authenticated user
5. THE Transaction_Linker SHALL allow updating property_id on existing transactions
6. THE Transaction_Linker SHALL allow removing property_id from transactions (set to null)

### Requirement 5: Property List and Details

**User Story:** As a landlord, I want to view all my registered properties with key details, so that I can manage my rental portfolio.

#### Acceptance Criteria

1. THE Property_Management_System SHALL display a list of all properties owned by the authenticated user
2. FOR ALL properties in the list, THE Property_Management_System SHALL display address, purchase_date, building_value, and depreciation_rate
3. THE Property_Management_System SHALL calculate and display total_accumulated_depreciation for each property
4. THE Property_Management_System SHALL calculate and display remaining_depreciable_value for each property
5. WHEN a user selects a property, THE Property_Management_System SHALL display detailed property information including all linked transactions
6. THE Property_Management_System SHALL allow editing property details except purchase_date and purchase_price

### Requirement 6: E1 Import Integration

**User Story:** As a landlord importing my E1 tax declaration, I want the system to detect rental income and prompt me to link it to properties, so that my property records are complete.

#### Acceptance Criteria

1. WHEN E1_Import_Service extracts income from KZ_350, THE Property_Management_System SHALL prompt the user to link income to existing property or create new property
2. WHEN Bescheid_Import_Service extracts rental income with property addresses, THE Property_Management_System SHALL attempt to auto-match addresses to existing properties
3. WHEN auto-matching finds a unique property match, THE Property_Management_System SHALL suggest the match to the user for confirmation
4. WHEN auto-matching finds multiple possible matches, THE Property_Management_System SHALL present all matches for user selection
5. WHEN auto-matching finds no matches, THE Property_Management_System SHALL prompt the user to create a new property
6. THE Property_Management_System SHALL allow users to skip property linking during import and link later

### Requirement 7: Historical Depreciation Backfill

**User Story:** As a new user with existing rental properties, I want to import historical property data and backfill depreciation, so that my loss carryforward and accumulated depreciation are accurate.

#### Acceptance Criteria

1. WHEN a property has purchase_date in a previous year, THE Historical_Import_Service SHALL calculate depreciation for all years from purchase_date to current year
2. FOR ALL historical years, THE Historical_Import_Service SHALL create depreciation expense transactions dated December 31 of each year
3. THE Historical_Import_Service SHALL mark historical depreciation transactions with a flag indicating they are system-generated
4. THE Historical_Import_Service SHALL validate that backfill does not create duplicate depreciation transactions for the same property and year
5. WHEN backfilling depreciation, THE Historical_Import_Service SHALL respect the total building_value limit
6. THE Historical_Import_Service SHALL allow users to review and confirm historical depreciation before finalizing

### Requirement 8: Property Expense Categories

**User Story:** As a landlord, I want the system to recognize property-related expense categories, so that I can properly categorize and deduct rental property expenses.

#### Acceptance Criteria

1. THE Property_Management_System SHALL support expense categories: "Loan_Interest", "Maintenance_Repairs", "Property_Management_Fees", "Property_Insurance", "Property_Tax", "Utilities", "Depreciation_AfA"
2. WHEN a transaction is categorized with a property expense category, THE Property_Management_System SHALL suggest linking to a property
3. THE Property_Management_System SHALL allow filtering transactions by property_id
4. THE Property_Management_System SHALL calculate total expenses per property per year
5. THE Property_Management_System SHALL calculate net rental income as rental_income minus total_expenses per property

### Requirement 9: Property Deletion and Archival

**User Story:** As a landlord who has sold a property, I want to archive or delete the property record, so that my active property list remains current while preserving historical data.

#### Acceptance Criteria

1. THE Property_Management_System SHALL allow marking a property as "Sold" with a sale_date
2. WHEN a property is marked as "Sold", THE Property_Management_System SHALL stop generating depreciation transactions after sale_date
3. THE Property_Management_System SHALL allow archiving sold properties to hide them from the active property list
4. WHEN a property is archived, THE Property_Management_System SHALL preserve all historical transactions and depreciation records
5. THE Property_Management_System SHALL allow viewing archived properties in a separate list
6. THE Property_Management_System SHALL prevent deletion of properties that have linked transactions
7. WHEN a property has no linked transactions, THE Property_Management_System SHALL allow permanent deletion

### Requirement 10: Multi-Property Support

**User Story:** As a landlord with multiple rental properties, I want to manage all properties in one system, so that I can track my entire rental portfolio.

#### Acceptance Criteria

1. THE Property_Management_System SHALL allow unlimited properties per user
2. THE Property_Management_System SHALL calculate total portfolio metrics including total_building_value, total_annual_depreciation, and total_rental_income
3. THE Property_Management_System SHALL display a portfolio summary dashboard with key metrics
4. THE Property_Management_System SHALL allow comparing performance across properties
5. THE Property_Management_System SHALL support bulk operations for generating annual depreciation across all active properties

### Requirement 11: Depreciation Calculation Correctness

**User Story:** As a landlord, I want depreciation calculations to be mathematically correct and compliant with Austrian tax law, so that my tax returns are accurate.

#### Acceptance Criteria

1. FOR ALL properties, THE AfA_Calculator SHALL satisfy the invariant: total_accumulated_depreciation <= building_value
2. FOR ALL properties, THE AfA_Calculator SHALL satisfy the round-trip property: sum of all annual_depreciation transactions equals total_accumulated_depreciation
3. FOR ALL properties with full years of ownership, THE AfA_Calculator SHALL satisfy: annual_depreciation = building_value * depreciation_rate (within rounding tolerance of 0.01)
4. FOR ALL properties purchased mid-year, THE AfA_Calculator SHALL satisfy: first_year_depreciation = (building_value * depreciation_rate * months_owned) / 12 (within rounding tolerance of 0.01)
5. FOR ALL properties, THE AfA_Calculator SHALL satisfy the idempotence property: calculating depreciation twice for the same year produces the same result
6. FOR ALL properties, THE AfA_Calculator SHALL satisfy the metamorphic property: changing depreciation_rate proportionally changes annual_depreciation

### Requirement 12: Property Data Validation

**User Story:** As a landlord, I want the system to validate property data entry, so that I avoid errors that could affect my tax calculations.

#### Acceptance Criteria

1. THE Property_Management_System SHALL reject property registration with missing required fields: address, purchase_date, purchase_price
2. THE Property_Management_System SHALL reject purchase_price values less than or equal to zero
3. THE Property_Management_System SHALL reject purchase_price values greater than 100,000,000 EUR
4. THE Property_Management_System SHALL reject building_value greater than purchase_price
5. THE Property_Management_System SHALL reject depreciation_rate less than 0.1% or greater than 10%
6. THE Property_Management_System SHALL validate address format includes street, city, and postal_code
7. WHEN validation fails, THE Property_Management_System SHALL return descriptive error messages indicating which fields are invalid

### Requirement 13: Transaction-Property Consistency

**User Story:** As a landlord, I want the system to maintain consistency between properties and linked transactions, so that my financial reports are accurate.

#### Acceptance Criteria

1. WHEN a property is archived, THE Property_Management_System SHALL preserve all transaction links
2. WHEN a transaction is deleted, THE Property_Management_System SHALL remove the property_id link
3. THE Property_Management_System SHALL prevent setting property_id to a non-existent property
4. THE Property_Management_System SHALL prevent setting property_id to a property owned by a different user
5. FOR ALL transactions with property_id, THE Property_Management_System SHALL ensure the property exists and belongs to the transaction owner
6. THE Property_Management_System SHALL maintain referential integrity between transactions and properties

### Requirement 14: Depreciation Transaction Generation

**User Story:** As a landlord, I want the system to automatically generate depreciation transactions at year-end, so that my expense records are complete for tax filing.

#### Acceptance Criteria

1. WHEN the calendar year ends, THE AfA_Calculator SHALL generate depreciation transactions for all active properties
2. THE AfA_Calculator SHALL create depreciation transactions dated December 31 of the tax year
3. THE AfA_Calculator SHALL set transaction category to "Depreciation_AfA"
4. THE AfA_Calculator SHALL set transaction amount to the calculated annual_depreciation
5. THE AfA_Calculator SHALL link depreciation transactions to the corresponding property_id
6. THE AfA_Calculator SHALL mark depreciation transactions as system-generated
7. THE AfA_Calculator SHALL prevent duplicate depreciation transactions for the same property and year

### Requirement 15: Property Report Generation

**User Story:** As a landlord, I want to generate property-specific reports, so that I can analyze rental income and expenses per property for tax purposes.

#### Acceptance Criteria

1. THE Property_Management_System SHALL generate a property income statement showing rental_income, expenses by category, and net_income
2. THE Property_Management_System SHALL generate a depreciation schedule showing annual_depreciation, accumulated_depreciation, and remaining_depreciable_value by year
3. THE Property_Management_System SHALL allow filtering reports by date range
4. THE Property_Management_System SHALL allow generating reports for a single property or all properties
5. THE Property_Management_System SHALL export reports in PDF and CSV formats
6. THE Property_Management_System SHALL include property details (address, purchase_date, building_value) in report headers

## Correctness Properties

### Property 1: Depreciation Accumulation Invariant
FOR ALL properties p, at any point in time:
- sum(depreciation_transactions.amount WHERE property_id = p.id) <= p.building_value

### Property 2: Depreciation Rate Consistency
FOR ALL properties p with full year of ownership:
- annual_depreciation = p.building_value * p.depreciation_rate (within 0.01 EUR tolerance)

### Property 3: Pro-Rata Calculation Correctness
FOR ALL properties p purchased in year Y:
- first_year_depreciation = (p.building_value * p.depreciation_rate * months_owned_in_Y) / 12 (within 0.01 EUR tolerance)

### Property 4: Historical Backfill Completeness
FOR ALL properties p with purchase_date in year Y:
- depreciation_transactions exist for all years from Y to current_year
- OR total_accumulated_depreciation = p.building_value (fully depreciated)

### Property 5: Transaction-Property Referential Integrity
FOR ALL transactions t where t.property_id IS NOT NULL:
- EXISTS property p WHERE p.id = t.property_id AND p.user_id = t.user_id

### Property 6: Depreciation Idempotence
FOR ALL properties p and year Y:
- Calculating depreciation for year Y multiple times produces identical results
- No duplicate depreciation transactions are created

### Property 7: Portfolio Aggregation Consistency
FOR ALL users u:
- sum(p.building_value WHERE p.user_id = u.id) = total_portfolio_building_value
- sum(annual_depreciation WHERE property.user_id = u.id) = total_portfolio_depreciation

### Property 8: Depreciation Rate Metamorphic Property
FOR ALL properties p:
- IF depreciation_rate is doubled, THEN annual_depreciation is doubled (within rounding tolerance)
- IF depreciation_rate is halved, THEN annual_depreciation is halved (within rounding tolerance)

## Additional Requirements (Phase 3)

### Requirement 16: Contract Document OCR and Import

**User Story:** As a landlord, I want to upload my property purchase contract (Kaufvertrag) and rental contract (Mietvertrag) and have the system automatically extract key information, so that I can quickly register properties without manual data entry.

#### Acceptance Criteria

1. THE Property_Management_System SHALL accept PDF uploads of Kaufvertrag (purchase contracts) and Mietvertrag (rental contracts)
2. WHEN a Kaufvertrag is uploaded, THE OCR_Service SHALL extract the following fields: property address, purchase_date, purchase_price, buyer name, seller name, notary information
3. WHEN a Mietvertrag is uploaded, THE OCR_Service SHALL extract the following fields: property address, rental_start_date, monthly_rent, tenant name, landlord name
4. THE Property_Management_System SHALL use extracted Kaufvertrag data to pre-fill property registration form fields
5. THE Property_Management_System SHALL allow users to review and correct OCR-extracted data before finalizing property registration
6. WHEN OCR extraction confidence is below 80% for critical fields (purchase_price, purchase_date), THE Property_Management_System SHALL flag those fields for manual review
7. THE Property_Management_System SHALL store uploaded contract documents linked to the property record for future reference
8. THE Property_Management_System SHALL support both German and English language contracts
9. WHEN building_value is not explicitly stated in Kaufvertrag, THE Property_Management_System SHALL calculate it as 80% of purchase_price per Austrian tax convention
10. THE Property_Management_System SHALL validate extracted data against the same validation rules as manual property registration (Requirement 12)

### Requirement 17: Property Purchase Tax Deductions for Owner-Occupied Properties

**User Story:** As a homeowner who purchased a property for personal residence, I want to understand what purchase-related costs I can deduct from my taxes, so that I can maximize my tax benefits.

#### Acceptance Criteria

1. THE Property_Management_System SHALL support a property_type field with values: "Rental" (Vermietung), "Owner-Occupied" (Eigennutzung), "Mixed-Use" (Gemischt)
2. WHEN property_type is "Owner-Occupied", THE Property_Management_System SHALL NOT calculate depreciation (AfA), as owner-occupied properties are not depreciable
3. WHEN property_type is "Owner-Occupied", THE Property_Management_System SHALL track the following deductible purchase costs: Grunderwerbsteuer (property transfer tax), Eintragungsgebühr (land registry fee), Notary fees, Real estate agent commission (if applicable)
4. THE Property_Management_System SHALL inform users that for owner-occupied properties, purchase costs are generally NOT deductible in the year of purchase, but may be relevant for capital gains tax calculation upon future sale
5. WHEN property_type is "Mixed-Use" (e.g., owner lives in one unit, rents out another), THE Property_Management_System SHALL allow specifying the rental_percentage (e.g., 50% rental, 50% personal use)
6. FOR Mixed-Use properties, THE AfA_Calculator SHALL calculate depreciation only on the rental_percentage portion of building_value
7. FOR Mixed-Use properties, THE Property_Management_System SHALL allow allocating expenses proportionally between rental and personal use based on rental_percentage
8. THE Property_Management_System SHALL provide educational tooltips explaining that Austrian tax law generally does NOT allow deductions for owner-occupied property purchase costs, except in specific scenarios (e.g., home office deductions for self-employed individuals)
9. WHEN a user registers an Owner-Occupied property, THE Property_Management_System SHALL display a disclaimer: "Hinweis: Kosten für selbstgenutzte Immobilien sind in der Regel nicht steuerlich absetzbar. Konsultieren Sie einen Steuerberater für spezifische Fragen."
10. THE Property_Management_System SHALL track Grunderwerbsteuer (property transfer tax) as a separate field, as it may be relevant for future capital gains calculations

#### Austrian Tax Law Context

- **Owner-Occupied Properties**: Generally, purchase costs and ongoing expenses for owner-occupied properties are NOT tax-deductible in Austria
- **Exceptions**: 
  - Home office (Arbeitszimmer) expenses for self-employed individuals (limited deduction)
  - Energy-efficient renovation costs (Sanierungskosten) may qualify for specific tax credits
  - Capital gains tax (Immobilienertragsteuer - ImmoESt) calculation upon sale considers original purchase costs
- **Rental Properties**: Purchase costs are capitalized and depreciated over time (AfA), ongoing expenses are fully deductible
- **Mixed-Use**: Expenses must be allocated proportionally between rental (deductible) and personal use (non-deductible)

### Requirement 18: E1 and Bescheid as Primary Data Sources

**User Story:** As a user importing historical tax data, I want the system to prioritize E1 tax declarations and Bescheid (tax assessments) as the primary data sources, so that my imported data matches official tax records.

#### Acceptance Criteria

1. THE Historical_Import_Service SHALL prioritize E1 form data and Bescheid data over other document types for extracting historical tax information
2. WHEN both E1 and Bescheid are available for the same tax year, THE Historical_Import_Service SHALL use Bescheid data as the authoritative source, as it represents the final tax assessment
3. THE Property_Management_System SHALL extract the following property-related information from E1 forms: KZ_350 (rental income), KZ_351 (rental expenses), property addresses from Beilage sections
4. THE Property_Management_System SHALL extract the following property-related information from Bescheid: confirmed rental income amounts, confirmed expense deductions, property addresses if listed
5. THE Historical_Import_Service SHALL NOT require users to upload annual financial reports (Jahresabschluss) for basic property tracking, as E1 and Bescheid contain sufficient information for rental income/expense tracking
6. WHEN E1 or Bescheid data is incomplete or unclear, THE Property_Management_System SHALL prompt users to provide additional details rather than requiring full financial reports
7. THE Property_Management_System SHALL provide an optional upload field for supporting documents (Kaufvertrag, Mietvertrag, invoices) to supplement E1/Bescheid data, but SHALL NOT require these documents for basic functionality
8. THE Historical_Import_Service SHALL validate that imported rental income from E1/Bescheid matches the sum of rental income transactions for the same period (within a tolerance of 5%)
9. WHEN validation fails, THE Historical_Import_Service SHALL flag the discrepancy and prompt the user to review and reconcile the data
10. THE Property_Management_System SHALL store references to source documents (E1, Bescheid) for audit trail purposes

#### Rationale

- E1 forms and Bescheid documents contain the essential information needed for property tracking: rental income, expenses, and property identification
- Requiring annual financial reports (Jahresabschluss) would create unnecessary complexity for individual landlords who may not prepare formal financial statements
- Kaufvertrag and Mietvertrag are useful for initial property registration but not required for ongoing tracking
- This approach balances data accuracy with user convenience

## Implementation Notes

### Phase 1 (MVP) Scope
- Manual property registration (Requirement 1)
- Depreciation rate determination (Requirement 2)
- Annual depreciation calculation (Requirement 3)
- Property-transaction linking (Requirement 4)
- Property list and details (Requirement 5)
- Property expense categories (Requirement 8)
- Data validation (Requirement 12)

### Phase 2 Scope
- E1 import integration (Requirement 6)
- Historical depreciation backfill (Requirement 7)
- Property deletion and archival (Requirement 9)
- Multi-property support (Requirement 10)
- Transaction-property consistency (Requirement 13)
- Depreciation transaction generation (Requirement 14)

### Phase 3 (Future) Scope
- Contract OCR extraction (Kaufvertrag, Mietvertrag) - See Requirement 16
- Loan interest tracking per property
- Tenant management
- Property report generation (Requirement 15)
- Advanced portfolio analytics
- Property purchase tax deductions - See Requirement 17

### Database Model Requirements

The Property model SHALL include:
- id (UUID, primary key)
- user_id (foreign key to User)
- property_type (enum: rental, owner_occupied, mixed_use, required, default: rental)
- rental_percentage (decimal, 0-100, required for mixed_use, default: 100 for rental)
- address (text, required)
- street (text, required)
- city (text, required)
- postal_code (text, required)
- purchase_date (date, required)
- purchase_price (decimal, required)
- building_value (decimal, required)
- land_value (decimal, calculated as purchase_price - building_value)
- grunderwerbsteuer (decimal, optional, property transfer tax paid)
- notary_fees (decimal, optional)
- registry_fees (decimal, optional, Eintragungsgebühr)
- construction_year (integer, optional)
- depreciation_rate (decimal, required for rental properties, default based on construction_year)
- status (enum: active, sold, archived)
- sale_date (date, optional)
- kaufvertrag_document_id (foreign key to Document, optional)
- mietvertrag_document_id (foreign key to Document, optional)
- created_at (timestamp)
- updated_at (timestamp)

The Transaction model SHALL be extended with:
- property_id (foreign key to Property, nullable)

### Integration Points

1. E1FormImportService: Add property linking prompt after KZ_350 extraction, prioritize E1 as primary data source
2. BescheidImportService: Add address matching and property suggestion, use Bescheid as authoritative source when available
3. OCRService: Add Kaufvertrag and Mietvertrag document type recognition and field extraction
4. TransactionClassifier: Recognize property expense categories
5. TaxCalculationEngine: Include depreciation in expense calculations, handle mixed-use property allocation
6. DashboardService: Add property portfolio metrics
7. DocumentUpload: Support contract document uploads with property linking

### Austrian Tax Law References

- AfA rates: § 8 EStG (Einkommensteuergesetz)
- Rental income: § 28 EStG (Einkünfte aus Vermietung und Verpachtung)
- Depreciable assets: § 7 EStG
- Building vs land value: BMF guidelines on property valuation
