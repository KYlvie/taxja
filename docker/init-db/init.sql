-- =============================================================
-- Taxja Database Initialization Script
-- Generated: 2026-03-25 22:35
-- Latest migration: 073_add_document_year_fields
-- =============================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;

-- =============================================================
-- PART 1: Schema (enums, tables, indexes, constraints)
-- =============================================================

CREATE TYPE vatstatus AS ENUM ('regelbesteuert', 'kleinunternehmer', 'pauschaliert', 'unknown');

CREATE TYPE gewinnermittlungsart AS ENUM ('bilanzierung', 'ea_rechnung', 'pauschal', 'unknown');

CREATE TYPE usertype AS ENUM ('EMPLOYEE', 'SELF_EMPLOYED', 'LANDLORD', 'MIXED', 'GMBH');

CREATE TYPE lineitempostingtype AS ENUM ('income', 'expense', 'private_use', 'asset_acquisition', 'liability_drawdown', 'liability_repayment', 'tax_payment', 'transfer');

CREATE TYPE lineitemallocationsource AS ENUM ('manual', 'ocr_split', 'percentage_rule', 'cap_rule', 'loan_installment', 'mixed_use_rule', 'vat_policy', 'legacy_backfill');

CREATE TYPE transactiontype AS ENUM ('INCOME', 'EXPENSE', 'ASSET_ACQUISITION', 'LIABILITY_DRAWDOWN', 'LIABILITY_REPAYMENT', 'TAX_PAYMENT', 'TRANSFER');

CREATE TYPE incomecategory AS ENUM ('AGRICULTURE', 'SELF_EMPLOYMENT', 'BUSINESS', 'EMPLOYMENT', 'CAPITAL_GAINS', 'RENTAL', 'OTHER_INCOME');

CREATE TYPE expensecategory AS ENUM ('OFFICE_SUPPLIES', 'EQUIPMENT', 'TRAVEL', 'MARKETING', 'PROFESSIONAL_SERVICES', 'INSURANCE', 'MAINTENANCE', 'PROPERTY_TAX', 'LOAN_INTEREST', 'DEPRECIATION', 'GROCERIES', 'UTILITIES', 'COMMUTING', 'HOME_OFFICE', 'VEHICLE', 'TELECOM', 'RENT', 'BANK_FEES', 'SVS_CONTRIBUTIONS', 'cleaning', 'clothing', 'software', 'shipping', 'fuel', 'education', 'PROPERTY_MANAGEMENT_FEES', 'PROPERTY_INSURANCE', 'DEPRECIATION_AFA', 'OTHER');

CREATE TYPE documenttype AS ENUM ('PAYSLIP', 'RECEIPT', 'INVOICE', 'PURCHASE_CONTRACT', 'RENTAL_CONTRACT', 'LOAN_CONTRACT', 'BANK_STATEMENT', 'PROPERTY_TAX', 'LOHNZETTEL', 'SVS_NOTICE', 'EINKOMMENSTEUERBESCHEID', 'E1_FORM', 'L1_FORM', 'L1K_BEILAGE', 'L1AB_BEILAGE', 'E1A_BEILAGE', 'E1B_BEILAGE', 'E1KV_BEILAGE', 'U1_FORM', 'U30_FORM', 'JAHRESABSCHLUSS', 'SPENDENBESTAETIGUNG', 'VERSICHERUNGSBESTAETIGUNG', 'KINDERBETREUUNGSKOSTEN', 'FORTBILDUNGSKOSTEN', 'PENDLERPAUSCHALE', 'KIRCHENBEITRAG', 'GRUNDBUCHAUSZUG', 'BETRIEBSKOSTENABRECHNUNG', 'GEWERBESCHEIN', 'KONTOAUSZUG', 'OTHER');

CREATE TYPE propertytype AS ENUM ('rental', 'owner_occupied', 'mixed_use');

CREATE TYPE buildinguse AS ENUM ('residential', 'commercial');

CREATE TYPE propertystatus AS ENUM ('active', 'sold', 'archived', 'scrapped', 'withdrawn');

CREATE TYPE liabilitytype AS ENUM ('property_loan', 'business_loan', 'owner_loan', 'family_loan', 'other_liability');

CREATE TYPE liabilitysourcetype AS ENUM ('manual', 'document_confirmed', 'document_auto_created', 'system_migrated');

CREATE TYPE liabilityreportcategory AS ENUM ('darlehen_und_kredite', 'sonstige_verbindlichkeiten');

CREATE TYPE bankstatementimportsourcetype AS ENUM ('csv', 'mt940', 'document');

CREATE TYPE bankstatementlinestatus AS ENUM ('pending_review', 'auto_created', 'matched_existing', 'ignored_duplicate');

CREATE TYPE bankstatementsuggestedaction AS ENUM ('create_new', 'match_existing', 'ignore');

CREATE TYPE loaninstallmentsource AS ENUM ('estimated', 'manual', 'bank_statement', 'zinsbescheinigung');

CREATE TYPE loaninstallmentstatus AS ENUM ('scheduled', 'posted', 'reconciled', 'overridden');

CREATE TYPE recurringtransactiontype AS ENUM ('rental_income', 'loan_interest', 'depreciation', 'other_income', 'other_expense', 'manual', 'insurance_premium', 'loan_repayment');

CREATE TYPE recurrencefrequency AS ENUM ('monthly', 'quarterly', 'annually', 'weekly', 'biweekly');

CREATE TYPE auditoperationtype AS ENUM ('create', 'update', 'delete', 'archive', 'link_transaction', 'unlink_transaction', 'backfill_depreciation', 'generate_depreciation');

CREATE TYPE auditentitytype AS ENUM ('property', 'transaction', 'property_loan');

CREATE TYPE messagerole AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');

CREATE TYPE notificationtype AS ENUM ('TAX_RATE_UPDATE', 'TAX_DEADLINE', 'REPORT_READY', 'SYSTEM_ANNOUNCEMENT');

CREATE TYPE importsessionstatus AS ENUM ('ACTIVE', 'COMPLETED', 'FAILED');

CREATE TYPE historicaldocumenttype AS ENUM ('E1_FORM', 'BESCHEID', 'KAUFVERTRAG', 'SALDENLISTE');

CREATE TYPE importstatus AS ENUM ('UPLOADED', 'PROCESSING', 'EXTRACTED', 'REVIEW_REQUIRED', 'APPROVED', 'REJECTED', 'FAILED');

CREATE TYPE plantype AS ENUM ('free', 'plus', 'pro');

CREATE TYPE subscriptionstatus AS ENUM ('active', 'past_due', 'canceled', 'trialing');

CREATE TYPE billingcycle AS ENUM ('monthly', 'yearly');

CREATE TYPE resourcetype AS ENUM ('TRANSACTIONS', 'OCR_SCANS', 'AI_CONVERSATIONS');

CREATE TYPE employermonthstatus AS ENUM ('UNKNOWN', 'PAYROLL_DETECTED', 'MISSING_CONFIRMATION', 'NO_PAYROLL_CONFIRMED', 'ARCHIVED_YEAR_ONLY');

CREATE TYPE employerannualarchivestatus AS ENUM ('PENDING_CONFIRMATION', 'ARCHIVED');

CREATE TYPE asseteventtype AS ENUM ('acquired', 'put_into_use', 'reclassified', 'business_use_changed', 'degressive_to_linear_switch', 'ifb_flagged', 'ifb_claimed', 'sold', 'scrapped', 'private_withdrawal');

CREATE TYPE asseteventtriggersource AS ENUM ('system', 'user', 'policy_recompute', 'import');

CREATE TYPE creditoperation AS ENUM ('deduction', 'refund', 'monthly_reset', 'topup', 'topup_expiry', 'overage_settlement', 'admin_adjustment', 'migration');

CREATE TYPE creditledgerstatus AS ENUM ('settled', 'reserved', 'reversed', 'failed');

CREATE TYPE creditsource AS ENUM ('plan', 'topup', 'overage', 'mixed');

CREATE TYPE taxformtype AS ENUM ('E1', 'E1A', 'E1B', 'L1', 'L1K', 'K1', 'U1', 'UVA');

CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	google_subject VARCHAR(255), 
	name VARCHAR(255) NOT NULL, 
	tax_number VARCHAR(500), 
	vat_number VARCHAR(500), 
	address VARCHAR(1000), 
	vat_status vatstatus, 
	gewinnermittlungsart gewinnermittlungsart, 
	user_type usertype NOT NULL, 
	business_type VARCHAR(50), 
	business_name VARCHAR(255), 
	business_industry VARCHAR(50), 
	employer_mode VARCHAR(20) NOT NULL, 
	employer_region VARCHAR(100), 
	family_info JSON, 
	commuting_info JSON, 
	home_office_eligible BOOLEAN, 
	telearbeit_days INTEGER, 
	employer_telearbeit_pauschale NUMERIC(10, 2), 
	language VARCHAR(5), 
	two_factor_enabled BOOLEAN, 
	two_factor_secret VARCHAR(500), 
	email_verified BOOLEAN NOT NULL, 
	email_verification_token VARCHAR(255), 
	email_verification_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	password_reset_token VARCHAR(255), 
	password_reset_sent_at TIMESTAMP WITHOUT TIME ZONE, 
	disclaimer_accepted_at TIMESTAMP WITHOUT TIME ZONE, 
	onboarding_completed BOOLEAN NOT NULL, 
	onboarding_dismiss_count INTEGER NOT NULL, 
	is_admin BOOLEAN NOT NULL, 
	account_status VARCHAR(20) NOT NULL, 
	deactivated_at TIMESTAMP WITHOUT TIME ZONE, 
	scheduled_deletion_at TIMESTAMP WITHOUT TIME ZONE, 
	deletion_retry_count INTEGER NOT NULL, 
	cancellation_reason VARCHAR(500), 
	bao_retention_expiry TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_login TIMESTAMP WITHOUT TIME ZONE, 
	subscription_id INTEGER, 
	trial_used BOOLEAN NOT NULL, 
	trial_end_date TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_users_email_verification_token ON users (email_verification_token);

CREATE INDEX ix_users_account_status ON users (account_status);

CREATE INDEX ix_users_trial_end_date ON users (trial_end_date);

CREATE UNIQUE INDEX ix_users_google_subject ON users (google_subject);

CREATE INDEX ix_users_subscription_id ON users (subscription_id);

CREATE INDEX ix_users_id ON users (id);

CREATE INDEX ix_users_password_reset_token ON users (password_reset_token);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE transactions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	property_id UUID, 
	liability_id INTEGER, 
	type transactiontype NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	transaction_date DATE NOT NULL, 
	description VARCHAR(500), 
	income_category incomecategory, 
	expense_category expensecategory, 
	is_deductible BOOLEAN, 
	deduction_reason VARCHAR(500), 
	vat_rate NUMERIC(5, 4), 
	vat_amount NUMERIC(12, 2), 
	vat_type VARCHAR(50), 
	document_id INTEGER, 
	classification_confidence NUMERIC(3, 2), 
	classification_method VARCHAR(20), 
	needs_review BOOLEAN, 
	reviewed BOOLEAN NOT NULL, 
	locked BOOLEAN NOT NULL, 
	is_system_generated BOOLEAN NOT NULL, 
	ai_review_notes VARCHAR(500), 
	import_source VARCHAR(50), 
	bank_reconciled BOOLEAN NOT NULL, 
	bank_reconciled_at TIMESTAMP WITHOUT TIME ZONE, 
	is_recurring BOOLEAN NOT NULL, 
	recurring_frequency VARCHAR(20), 
	recurring_start_date DATE, 
	recurring_end_date DATE, 
	recurring_day_of_month INTEGER, 
	recurring_is_active BOOLEAN NOT NULL, 
	recurring_next_date DATE, 
	recurring_last_generated DATE, 
	parent_recurring_id INTEGER, 
	source_recurring_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_transactions_user_id ON transactions (user_id);

CREATE INDEX ix_transactions_source_recurring_id ON transactions (source_recurring_id);

CREATE INDEX ix_transactions_type ON transactions (type);

CREATE INDEX ix_transactions_liability_id ON transactions (liability_id);

CREATE INDEX ix_transactions_transaction_date ON transactions (transaction_date);

CREATE INDEX ix_transactions_id ON transactions (id);

CREATE INDEX ix_transactions_property_id ON transactions (property_id);

CREATE INDEX ix_transactions_parent_recurring_id ON transactions (parent_recurring_id);

CREATE TABLE documents (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	document_type documenttype NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_hash VARCHAR(64), 
	file_size INTEGER, 
	mime_type VARCHAR(100), 
	ocr_result JSON, 
	raw_text TEXT, 
	confidence_score NUMERIC(3, 2), 
	transaction_id INTEGER, 
	parent_document_id INTEGER, 
	is_archived BOOLEAN NOT NULL, 
	archived_at TIMESTAMP WITHOUT TIME ZONE, 
	uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	processed_at TIMESTAMP WITHOUT TIME ZONE, 
	document_date DATE, 
	document_year INTEGER, 
	year_basis VARCHAR(50), 
	year_confidence NUMERIC(3, 2), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_documents_id ON documents (id);

CREATE INDEX ix_documents_file_hash ON documents (file_hash);

CREATE INDEX ix_documents_document_year ON documents (document_year);

CREATE INDEX ix_documents_user_id ON documents (user_id);

CREATE INDEX ix_documents_parent_document_id ON documents (parent_document_id);

CREATE INDEX ix_documents_document_date ON documents (document_date);

CREATE INDEX ix_documents_document_type ON documents (document_type);

CREATE TABLE tax_configurations (
	id SERIAL NOT NULL, 
	tax_year INTEGER NOT NULL, 
	tax_brackets JSON NOT NULL, 
	exemption_amount NUMERIC(12, 2) NOT NULL, 
	vat_rates JSON NOT NULL, 
	svs_rates JSON NOT NULL, 
	deduction_config JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_tax_configurations_tax_year ON tax_configurations (tax_year);

CREATE INDEX ix_tax_configurations_id ON tax_configurations (id);

CREATE TABLE properties (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id INTEGER NOT NULL, 
	asset_type VARCHAR(50) NOT NULL, 
	sub_category VARCHAR(100), 
	name VARCHAR(255), 
	property_type propertytype NOT NULL, 
	rental_percentage NUMERIC(5, 2) NOT NULL, 
	useful_life_years INTEGER, 
	business_use_percentage NUMERIC(5, 2) NOT NULL, 
	supplier VARCHAR(255), 
	accumulated_depreciation NUMERIC(12, 2) NOT NULL, 
	acquisition_kind VARCHAR(30), 
	put_into_use_date DATE, 
	is_used_asset BOOLEAN NOT NULL, 
	first_registration_date DATE, 
	prior_owner_usage_years NUMERIC(5, 2), 
	comparison_basis VARCHAR(10), 
	comparison_amount NUMERIC(12, 2), 
	gwg_eligible BOOLEAN NOT NULL, 
	gwg_elected BOOLEAN NOT NULL, 
	depreciation_method VARCHAR(20), 
	degressive_afa_rate NUMERIC(5, 4), 
	useful_life_source VARCHAR(50), 
	income_tax_cost_cap NUMERIC(12, 2), 
	income_tax_depreciable_base NUMERIC(12, 2), 
	vat_recoverable_status VARCHAR(20), 
	ifb_candidate BOOLEAN NOT NULL, 
	ifb_rate NUMERIC(5, 4), 
	ifb_rate_source VARCHAR(50), 
	recognition_decision VARCHAR(50), 
	policy_confidence NUMERIC(5, 4), 
	address VARCHAR(1000) NOT NULL, 
	street VARCHAR(500) NOT NULL, 
	city VARCHAR(200) NOT NULL, 
	postal_code VARCHAR(10) NOT NULL, 
	purchase_date DATE NOT NULL, 
	purchase_price NUMERIC(12, 2) NOT NULL, 
	building_value NUMERIC(12, 2) NOT NULL, 
	land_value NUMERIC(12, 2), 
	grunderwerbsteuer NUMERIC(12, 2), 
	notary_fees NUMERIC(12, 2), 
	registry_fees NUMERIC(12, 2), 
	construction_year INTEGER, 
	building_use buildinguse NOT NULL, 
	eco_standard BOOLEAN NOT NULL, 
	depreciation_rate NUMERIC(5, 4) NOT NULL, 
	status propertystatus NOT NULL, 
	sale_date DATE, 
	sale_price NUMERIC(12, 2), 
	disposal_reason VARCHAR(30), 
	hauptwohnsitz BOOLEAN NOT NULL, 
	selbst_errichtet BOOLEAN NOT NULL, 
	kaufvertrag_document_id INTEGER, 
	mietvertrag_document_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_rental_percentage_range CHECK (rental_percentage >= 0 AND rental_percentage <= 100), 
	CONSTRAINT check_purchase_price_range CHECK (purchase_price > 0 AND purchase_price <= 100000000), 
	CONSTRAINT check_building_value_range CHECK (building_value > 0 AND building_value <= purchase_price), 
	CONSTRAINT check_depreciation_rate_range CHECK (depreciation_rate >= 0.001 AND depreciation_rate <= 1.00), 
	CONSTRAINT check_construction_year_min CHECK (construction_year IS NULL OR construction_year >= 1800), 
	CONSTRAINT check_sale_date_after_purchase CHECK (sale_date IS NULL OR sale_date >= purchase_date), 
	CONSTRAINT check_sold_has_sale_date CHECK (status != 'sold' OR sale_date IS NOT NULL)
);

CREATE INDEX ix_properties_asset_type ON properties (asset_type);

CREATE INDEX ix_properties_user_id ON properties (user_id);

CREATE INDEX ix_properties_status ON properties (status);

CREATE TABLE property_loans (
	id SERIAL NOT NULL, 
	property_id UUID NOT NULL, 
	user_id INTEGER NOT NULL, 
	loan_amount NUMERIC(12, 2) NOT NULL, 
	interest_rate NUMERIC(5, 4) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE, 
	monthly_payment NUMERIC(12, 2) NOT NULL, 
	lender_name VARCHAR(255) NOT NULL, 
	lender_account VARCHAR(100), 
	loan_type VARCHAR(50), 
	loan_contract_document_id INTEGER, 
	notes VARCHAR(1000), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_loan_amount_positive CHECK (loan_amount > 0), 
	CONSTRAINT check_interest_rate_range CHECK (interest_rate >= 0 AND interest_rate <= 0.20), 
	CONSTRAINT check_monthly_payment_positive CHECK (monthly_payment > 0), 
	CONSTRAINT check_end_date_after_start CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX ix_property_loans_property_id ON property_loans (property_id);

CREATE INDEX ix_property_loans_user_id ON property_loans (user_id);

CREATE INDEX ix_property_loans_id ON property_loans (id);

CREATE TABLE liabilities (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	liability_type liabilitytype NOT NULL, 
	source_type liabilitysourcetype NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	lender_name VARCHAR(255) NOT NULL, 
	principal_amount NUMERIC(12, 2) NOT NULL, 
	outstanding_balance NUMERIC(12, 2) NOT NULL, 
	interest_rate NUMERIC(8, 6), 
	start_date DATE NOT NULL, 
	end_date DATE, 
	monthly_payment NUMERIC(12, 2), 
	tax_relevant BOOLEAN NOT NULL, 
	tax_relevance_reason VARCHAR(500), 
	report_category liabilityreportcategory NOT NULL, 
	linked_property_id UUID, 
	linked_loan_id INTEGER, 
	source_document_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	notes VARCHAR(1000), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_liabilities_source_document_id ON liabilities (source_document_id);

CREATE INDEX ix_liabilities_id ON liabilities (id);

CREATE INDEX ix_liabilities_source_type ON liabilities (source_type);

CREATE INDEX ix_liabilities_linked_loan_id ON liabilities (linked_loan_id);

CREATE INDEX ix_liabilities_linked_property_id ON liabilities (linked_property_id);

CREATE INDEX ix_liabilities_is_active ON liabilities (is_active);

CREATE INDEX ix_liabilities_tax_relevant ON liabilities (tax_relevant);

CREATE INDEX ix_liabilities_liability_type ON liabilities (liability_type);

CREATE INDEX ix_liabilities_user_id ON liabilities (user_id);

CREATE TABLE recurring_transactions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	recurring_type recurringtransactiontype NOT NULL, 
	property_id UUID, 
	loan_id INTEGER, 
	liability_id INTEGER, 
	description VARCHAR(500) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	transaction_type VARCHAR(20) NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	frequency recurrencefrequency NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE, 
	day_of_month INTEGER, 
	is_active BOOLEAN NOT NULL, 
	paused_at TIMESTAMP WITHOUT TIME ZONE, 
	last_generated_date DATE, 
	next_generation_date DATE, 
	template VARCHAR(50), 
	source_document_id INTEGER, 
	unit_percentage NUMERIC(5, 2), 
	notes VARCHAR(1000), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_amount_positive CHECK (amount > 0), 
	CONSTRAINT check_transaction_type_valid CHECK (transaction_type IN ('income', 'expense', 'asset_acquisition', 'liability_drawdown', 'liability_repayment', 'tax_payment', 'transfer')), 
	CONSTRAINT check_end_date_after_start CHECK (end_date IS NULL OR end_date >= start_date), 
	CONSTRAINT check_day_of_month_range CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)), 
	CONSTRAINT check_source_entity_required CHECK ((recurring_type = 'rental_income' AND property_id IS NOT NULL) OR (recurring_type = 'loan_interest' AND (loan_id IS NOT NULL OR liability_id IS NOT NULL)) OR (recurring_type = 'depreciation' AND property_id IS NOT NULL) OR (recurring_type = 'loan_repayment') OR (recurring_type IN ('other_income', 'other_expense', 'manual', 'insurance_premium')))
);

CREATE INDEX ix_recurring_transactions_property_id ON recurring_transactions (property_id);

CREATE INDEX ix_recurring_transactions_recurring_type ON recurring_transactions (recurring_type);

CREATE INDEX ix_recurring_transactions_next_generation_date ON recurring_transactions (next_generation_date);

CREATE INDEX ix_recurring_transactions_is_active ON recurring_transactions (is_active);

CREATE INDEX ix_recurring_transactions_user_id ON recurring_transactions (user_id);

CREATE INDEX ix_recurring_transactions_liability_id ON recurring_transactions (liability_id);

CREATE INDEX ix_recurring_transactions_loan_id ON recurring_transactions (loan_id);

CREATE INDEX ix_recurring_transactions_id ON recurring_transactions (id);

CREATE INDEX ix_recurring_transactions_source_document_id ON recurring_transactions (source_document_id);

CREATE TABLE plans (
	id SERIAL NOT NULL, 
	plan_type plantype NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	monthly_price NUMERIC(10, 2) NOT NULL, 
	yearly_price NUMERIC(10, 2) NOT NULL, 
	features JSONB NOT NULL, 
	quotas JSONB NOT NULL, 
	monthly_credits INTEGER NOT NULL, 
	overage_price_per_credit NUMERIC(6, 4), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_plans_plan_type ON plans (plan_type);

CREATE INDEX ix_plans_id ON plans (id);

CREATE TABLE subscriptions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_id INTEGER NOT NULL, 
	status subscriptionstatus NOT NULL, 
	billing_cycle billingcycle, 
	stripe_subscription_id VARCHAR(255), 
	stripe_customer_id VARCHAR(255), 
	current_period_start TIMESTAMP WITHOUT TIME ZONE, 
	current_period_end TIMESTAMP WITHOUT TIME ZONE, 
	cancel_at_period_end BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_subscriptions_id ON subscriptions (id);

CREATE UNIQUE INDEX ix_subscriptions_stripe_subscription_id ON subscriptions (stripe_subscription_id);

CREATE INDEX ix_subscriptions_status ON subscriptions (status);

CREATE INDEX ix_subscriptions_current_period_end ON subscriptions (current_period_end);

CREATE INDEX ix_subscriptions_plan_id ON subscriptions (plan_id);

CREATE INDEX ix_subscriptions_stripe_customer_id ON subscriptions (stripe_customer_id);

CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id);

CREATE TABLE account_deletion_logs (
	id SERIAL NOT NULL, 
	anonymous_user_hash VARCHAR(64) NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	data_types_deleted JSON, 
	deletion_method VARCHAR(20), 
	initiated_by VARCHAR(20), 
	PRIMARY KEY (id)
);

CREATE TABLE credit_cost_configs (
	id SERIAL NOT NULL, 
	operation VARCHAR(50) NOT NULL, 
	credit_cost INTEGER NOT NULL, 
	description VARCHAR(200), 
	pricing_version INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_credit_cost_configs_id ON credit_cost_configs (id);

CREATE UNIQUE INDEX ix_credit_cost_configs_operation ON credit_cost_configs (operation);

CREATE TABLE credit_topup_packages (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	credits INTEGER NOT NULL, 
	price NUMERIC(10, 2) NOT NULL, 
	stripe_price_id VARCHAR(255), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_credit_topup_packages_id ON credit_topup_packages (id);

CREATE TABLE tax_form_templates (
	id SERIAL NOT NULL, 
	tax_year INTEGER NOT NULL, 
	form_type taxformtype NOT NULL, 
	display_name VARCHAR(200), 
	pdf_template BYTEA NOT NULL, 
	field_mapping JSON NOT NULL, 
	original_filename VARCHAR(255), 
	file_size_bytes INTEGER, 
	page_count INTEGER, 
	source_url VARCHAR(500), 
	bmf_version VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_tax_form_template_year_type UNIQUE (tax_year, form_type)
);

CREATE INDEX ix_tax_form_templates_id ON tax_form_templates (id);

CREATE INDEX ix_tax_form_templates_tax_year ON tax_form_templates (tax_year);

CREATE TABLE transaction_line_items (
	id SERIAL NOT NULL, 
	transaction_id INTEGER NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	quantity INTEGER NOT NULL, 
	posting_type lineitempostingtype NOT NULL, 
	allocation_source lineitemallocationsource NOT NULL, 
	category VARCHAR(100), 
	is_deductible BOOLEAN NOT NULL, 
	deduction_reason VARCHAR(500), 
	vat_rate NUMERIC(5, 4), 
	vat_amount NUMERIC(12, 2), 
	vat_recoverable_amount NUMERIC(12, 2) NOT NULL, 
	rule_bucket VARCHAR(100), 
	classification_method VARCHAR(20), 
	classification_confidence NUMERIC(3, 2), 
	sort_order INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE CASCADE
);

CREATE INDEX ix_transaction_line_items_transaction_id ON transaction_line_items (transaction_id);

CREATE INDEX ix_transaction_line_items_id ON transaction_line_items (id);

CREATE TABLE loss_carryforwards (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	loss_year INTEGER NOT NULL, 
	loss_amount NUMERIC(12, 2) NOT NULL, 
	used_amount NUMERIC(12, 2) NOT NULL, 
	remaining_amount NUMERIC(12, 2) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_loss_year UNIQUE (user_id, loss_year), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_loss_carryforwards_id ON loss_carryforwards (id);

CREATE INDEX ix_loss_carryforwards_loss_year ON loss_carryforwards (loss_year);

CREATE INDEX ix_loss_carryforwards_user_id ON loss_carryforwards (user_id);

CREATE TABLE tax_reports (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	tax_year INTEGER NOT NULL, 
	income_summary JSON NOT NULL, 
	expense_summary JSON NOT NULL, 
	tax_calculation JSON NOT NULL, 
	deductions JSON NOT NULL, 
	net_income NUMERIC(12, 2) NOT NULL, 
	pdf_file_path VARCHAR(500), 
	xml_file_path VARCHAR(500), 
	generated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_tax_reports_user_id ON tax_reports (user_id);

CREATE INDEX ix_tax_reports_tax_year ON tax_reports (tax_year);

CREATE INDEX ix_tax_reports_id ON tax_reports (id);

CREATE TABLE classification_corrections (
	id SERIAL NOT NULL, 
	transaction_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	original_category VARCHAR NOT NULL, 
	original_confidence VARCHAR, 
	correct_category VARCHAR NOT NULL, 
	source VARCHAR(30), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_classification_corrections_id ON classification_corrections (id);

CREATE TABLE bank_statement_imports (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	source_type bankstatementimportsourcetype NOT NULL, 
	source_document_id INTEGER, 
	bank_name VARCHAR(255), 
	iban VARCHAR(64), 
	statement_period JSON, 
	tax_year INTEGER, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE INDEX ix_bank_statement_imports_user_id ON bank_statement_imports (user_id);

CREATE INDEX ix_bank_statement_imports_tax_year ON bank_statement_imports (tax_year);

CREATE INDEX ix_bank_statement_imports_id ON bank_statement_imports (id);

CREATE INDEX ix_bank_statement_imports_source_document_id ON bank_statement_imports (source_document_id);

CREATE INDEX ix_bank_statement_imports_source_type ON bank_statement_imports (source_type);

CREATE TABLE reminder_states (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	reminder_kind VARCHAR(80) NOT NULL, 
	bucket VARCHAR(40) NOT NULL, 
	fingerprint VARCHAR(128) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	snoozed_until TIMESTAMP WITHOUT TIME ZONE, 
	last_seen_at TIMESTAMP WITHOUT TIME ZONE, 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_reminder_state_user_kind_fingerprint UNIQUE (user_id, reminder_kind, fingerprint), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_reminder_states_reminder_kind ON reminder_states (reminder_kind);

CREATE INDEX ix_reminder_states_status ON reminder_states (status);

CREATE INDEX ix_reminder_states_user_id ON reminder_states (user_id);

CREATE INDEX ix_reminder_states_fingerprint ON reminder_states (fingerprint);

CREATE INDEX ix_reminder_states_id ON reminder_states (id);

CREATE TABLE loan_installments (
	id SERIAL NOT NULL, 
	loan_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	due_date DATE NOT NULL, 
	actual_payment_date DATE, 
	tax_year INTEGER NOT NULL, 
	scheduled_payment NUMERIC(12, 2) NOT NULL, 
	principal_amount NUMERIC(12, 2) NOT NULL, 
	interest_amount NUMERIC(12, 2) NOT NULL, 
	remaining_balance_after NUMERIC(12, 2) NOT NULL, 
	source loaninstallmentsource NOT NULL, 
	status loaninstallmentstatus NOT NULL, 
	source_document_id INTEGER, 
	notes VARCHAR(1000), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_loan_installments_loan_due_date UNIQUE (loan_id, due_date), 
	CONSTRAINT check_installment_payment_positive CHECK (scheduled_payment > 0), 
	CONSTRAINT check_installment_principal_non_negative CHECK (principal_amount >= 0), 
	CONSTRAINT check_installment_interest_non_negative CHECK (interest_amount >= 0), 
	CONSTRAINT check_installment_remaining_balance_non_negative CHECK (remaining_balance_after >= 0), 
	FOREIGN KEY(loan_id) REFERENCES property_loans (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE INDEX ix_loan_installments_due_date ON loan_installments (due_date);

CREATE INDEX ix_loan_installments_user_id ON loan_installments (user_id);

CREATE INDEX ix_loan_installments_loan_id ON loan_installments (loan_id);

CREATE INDEX ix_loan_installments_source_document_id ON loan_installments (source_document_id);

CREATE INDEX ix_loan_installments_tax_year ON loan_installments (tax_year);

CREATE INDEX ix_loan_installments_id ON loan_installments (id);

CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	operation_type auditoperationtype NOT NULL, 
	entity_type auditentitytype NOT NULL, 
	entity_id VARCHAR(100) NOT NULL, 
	details JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ip_address VARCHAR(45), 
	user_agent VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE INDEX ix_audit_logs_entity_id ON audit_logs (entity_id);

CREATE INDEX idx_audit_created_at_desc ON audit_logs (created_at DESC);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE INDEX idx_audit_entity_operation ON audit_logs (entity_type, entity_id, operation_type);

CREATE INDEX ix_audit_logs_operation_type ON audit_logs (operation_type);

CREATE INDEX idx_audit_user_entity ON audit_logs (user_id, entity_type, entity_id);

CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);

CREATE TABLE chat_messages (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	role messagerole NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_messages_user_id ON chat_messages (user_id);

CREATE INDEX ix_chat_messages_id ON chat_messages (id);

CREATE TABLE notifications (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	type notificationtype NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	message TEXT NOT NULL, 
	message_en TEXT, 
	message_zh TEXT, 
	data JSONB, 
	is_read BOOLEAN NOT NULL, 
	read_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE INDEX ix_notifications_id ON notifications (id);

CREATE INDEX ix_notifications_is_read ON notifications (is_read);

CREATE TABLE historical_import_sessions (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id INTEGER NOT NULL, 
	status importsessionstatus NOT NULL, 
	tax_years INTEGER[] NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	total_documents INTEGER NOT NULL, 
	successful_imports INTEGER NOT NULL, 
	failed_imports INTEGER NOT NULL, 
	transactions_created INTEGER NOT NULL, 
	properties_created INTEGER NOT NULL, 
	properties_linked INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_historical_import_sessions_status ON historical_import_sessions (status);

CREATE INDEX ix_historical_import_sessions_user_id ON historical_import_sessions (user_id);

CREATE TABLE usage_records (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	resource_type resourcetype NOT NULL, 
	count INTEGER NOT NULL, 
	period_start TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	period_end TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_usage_records_id ON usage_records (id);

CREATE INDEX ix_usage_records_user_id ON usage_records (user_id);

CREATE INDEX ix_usage_records_resource_type ON usage_records (resource_type);

CREATE TABLE payment_events (
	id SERIAL NOT NULL, 
	stripe_event_id VARCHAR(255) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	user_id INTEGER, 
	payload JSONB NOT NULL, 
	processed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_payment_events_id ON payment_events (id);

CREATE INDEX ix_payment_events_event_type ON payment_events (event_type);

CREATE INDEX ix_payment_events_processed_at ON payment_events (processed_at);

CREATE INDEX ix_payment_events_user_id ON payment_events (user_id);

CREATE UNIQUE INDEX ix_payment_events_stripe_event_id ON payment_events (stripe_event_id);

CREATE TABLE user_classification_rules (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	normalized_description VARCHAR(300) NOT NULL, 
	original_description VARCHAR(500), 
	txn_type VARCHAR(20) NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	hit_count INTEGER NOT NULL, 
	confidence NUMERIC(3, 2) NOT NULL, 
	rule_type VARCHAR(10) NOT NULL, 
	last_hit_at TIMESTAMP WITHOUT TIME ZONE, 
	conflict_count INTEGER NOT NULL, 
	frozen BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_description_type UNIQUE (user_id, normalized_description, txn_type), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_classification_rules_id ON user_classification_rules (id);

CREATE INDEX ix_user_classification_rules_normalized_description ON user_classification_rules (normalized_description);

CREATE INDEX ix_user_classification_rules_user_id ON user_classification_rules (user_id);

CREATE TABLE user_deductibility_rules (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	normalized_description VARCHAR(300) NOT NULL, 
	original_description VARCHAR(500), 
	expense_category VARCHAR(100) NOT NULL, 
	is_deductible BOOLEAN NOT NULL, 
	reason VARCHAR(500), 
	hit_count INTEGER NOT NULL, 
	last_hit_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_deductibility_description_category UNIQUE (user_id, normalized_description, expense_category), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_user_deductibility_rules_expense_category ON user_deductibility_rules (expense_category);

CREATE INDEX ix_user_deductibility_rules_user_id ON user_deductibility_rules (user_id);

CREATE INDEX ix_user_deductibility_rules_normalized_description ON user_deductibility_rules (normalized_description);

CREATE INDEX ix_user_deductibility_rules_id ON user_deductibility_rules (id);

CREATE TABLE tax_filing_data (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	tax_year INTEGER NOT NULL, 
	data_type VARCHAR(50) NOT NULL, 
	source_document_id INTEGER, 
	data JSON NOT NULL, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(source_document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE INDEX ix_tax_filing_data_user_id ON tax_filing_data (user_id);

CREATE INDEX ix_tax_filing_data_data_type ON tax_filing_data (data_type);

CREATE INDEX ix_tax_filing_data_tax_year ON tax_filing_data (tax_year);

CREATE INDEX ix_tax_filing_data_id ON tax_filing_data (id);

CREATE TABLE employer_months (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	year_month VARCHAR(7) NOT NULL, 
	status employermonthstatus NOT NULL, 
	source_type VARCHAR(30), 
	payroll_signal VARCHAR(50), 
	confidence NUMERIC(3, 2), 
	employee_count INTEGER, 
	gross_wages NUMERIC(12, 2), 
	net_paid NUMERIC(12, 2), 
	employer_social_cost NUMERIC(12, 2), 
	lohnsteuer NUMERIC(12, 2), 
	db_amount NUMERIC(12, 2), 
	dz_amount NUMERIC(12, 2), 
	kommunalsteuer NUMERIC(12, 2), 
	special_payments NUMERIC(12, 2), 
	notes TEXT, 
	confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
	last_signal_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_employer_month_user_month UNIQUE (user_id, year_month), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_employer_months_year_month ON employer_months (year_month);

CREATE INDEX ix_employer_months_status ON employer_months (status);

CREATE INDEX ix_employer_months_id ON employer_months (id);

CREATE INDEX ix_employer_months_user_id ON employer_months (user_id);

CREATE TABLE employer_annual_archives (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	tax_year INTEGER NOT NULL, 
	status employerannualarchivestatus NOT NULL, 
	source_type VARCHAR(30), 
	archive_signal VARCHAR(50), 
	confidence NUMERIC(3, 2), 
	employer_name VARCHAR(255), 
	gross_income NUMERIC(12, 2), 
	withheld_tax NUMERIC(12, 2), 
	notes TEXT, 
	confirmed_at TIMESTAMP WITHOUT TIME ZONE, 
	last_signal_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_employer_annual_archive_user_year UNIQUE (user_id, tax_year), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_employer_annual_archives_status ON employer_annual_archives (status);

CREATE INDEX ix_employer_annual_archives_id ON employer_annual_archives (id);

CREATE INDEX ix_employer_annual_archives_user_id ON employer_annual_archives (user_id);

CREATE INDEX ix_employer_annual_archives_tax_year ON employer_annual_archives (tax_year);

CREATE TABLE asset_policy_snapshots (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	property_id UUID NOT NULL, 
	policy_version VARCHAR(50) NOT NULL, 
	jurisdiction VARCHAR(10) NOT NULL, 
	effective_anchor_date DATE NOT NULL, 
	snapshot_payload JSON NOT NULL, 
	rule_ids JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE INDEX ix_asset_policy_snapshots_effective_anchor_date ON asset_policy_snapshots (effective_anchor_date);

CREATE INDEX ix_asset_policy_snapshots_property_id ON asset_policy_snapshots (property_id);

CREATE INDEX ix_asset_policy_snapshots_id ON asset_policy_snapshots (id);

CREATE INDEX ix_asset_policy_snapshots_user_id ON asset_policy_snapshots (user_id);

CREATE TABLE asset_events (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	property_id UUID NOT NULL, 
	event_type asseteventtype NOT NULL, 
	trigger_source asseteventtriggersource NOT NULL, 
	event_date DATE NOT NULL, 
	payload JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE INDEX ix_asset_events_property_id ON asset_events (property_id);

CREATE INDEX ix_asset_events_user_id ON asset_events (user_id);

CREATE INDEX ix_asset_events_id ON asset_events (id);

CREATE INDEX ix_asset_events_event_date ON asset_events (event_date);

CREATE INDEX ix_asset_events_event_type ON asset_events (event_type);

CREATE TABLE credit_balances (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	plan_balance INTEGER NOT NULL, 
	topup_balance INTEGER NOT NULL, 
	overage_enabled BOOLEAN NOT NULL, 
	overage_credits_used INTEGER NOT NULL, 
	has_unpaid_overage BOOLEAN NOT NULL, 
	unpaid_overage_periods INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_credit_balances_plan_balance_non_negative CHECK (plan_balance >= 0), 
	CONSTRAINT ck_credit_balances_topup_balance_non_negative CHECK (topup_balance >= 0), 
	CONSTRAINT ck_credit_balances_overage_credits_used_non_negative CHECK (overage_credits_used >= 0), 
	CONSTRAINT ck_credit_balances_unpaid_overage_periods_non_negative CHECK (unpaid_overage_periods >= 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_credit_balances_id ON credit_balances (id);

CREATE UNIQUE INDEX ix_credit_balances_user_id ON credit_balances (user_id);

CREATE TABLE credit_ledger (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	operation creditoperation NOT NULL, 
	operation_detail VARCHAR(100), 
	status creditledgerstatus NOT NULL, 
	credit_amount INTEGER NOT NULL, 
	source creditsource NOT NULL, 
	plan_balance_after INTEGER NOT NULL, 
	topup_balance_after INTEGER NOT NULL, 
	is_overage BOOLEAN NOT NULL, 
	overage_portion INTEGER NOT NULL, 
	context_type VARCHAR(50), 
	context_id INTEGER, 
	reference_id VARCHAR(255), 
	reservation_id VARCHAR(255), 
	reason VARCHAR(200), 
	pricing_version INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_credit_ledger_amount_nonzero CHECK (credit_amount != 0), 
	CONSTRAINT ck_credit_ledger_plan_balance_after_non_negative CHECK (plan_balance_after >= 0), 
	CONSTRAINT ck_credit_ledger_topup_balance_after_non_negative CHECK (topup_balance_after >= 0), 
	CONSTRAINT ck_credit_ledger_overage_portion_non_negative CHECK (overage_portion >= 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_credit_ledger_context ON credit_ledger (context_type, context_id);

CREATE INDEX ix_credit_ledger_id ON credit_ledger (id);

CREATE UNIQUE INDEX uq_credit_ledger_refund_key ON credit_ledger (user_id, reference_id) WHERE operation = 'refund' AND reference_id IS NOT NULL;

CREATE INDEX ix_credit_ledger_user_created ON credit_ledger (user_id, created_at);

CREATE INDEX ix_credit_ledger_status ON credit_ledger (status);

CREATE INDEX ix_credit_ledger_user_operation ON credit_ledger (user_id, operation);

CREATE INDEX ix_credit_ledger_user_id ON credit_ledger (user_id);

CREATE TABLE topup_purchases (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	credits_purchased INTEGER NOT NULL, 
	credits_remaining INTEGER NOT NULL, 
	price_paid NUMERIC(10, 2) NOT NULL, 
	stripe_payment_id VARCHAR(255), 
	purchased_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_expired BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_topup_purchases_id ON topup_purchases (id);

CREATE INDEX ix_topup_purchases_user_id ON topup_purchases (user_id);

CREATE TABLE dismissed_suggestions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	amount FLOAT NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	dismissed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_dismissed_suggestions_id ON dismissed_suggestions (id);

CREATE INDEX ix_dismissed_suggestions_user_id ON dismissed_suggestions (user_id);

CREATE TABLE disclaimer_acceptances (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	version VARCHAR(20) NOT NULL, 
	language VARCHAR(5) NOT NULL, 
	accepted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ip_address VARCHAR(45), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_disclaimer_acceptances_user_id ON disclaimer_acceptances (user_id);

CREATE INDEX ix_disclaimer_acceptances_id ON disclaimer_acceptances (id);

CREATE TABLE bank_statement_lines (
	id SERIAL NOT NULL, 
	import_id INTEGER NOT NULL, 
	line_date DATE NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	counterparty VARCHAR(255), 
	purpose VARCHAR(1000), 
	raw_reference VARCHAR(255), 
	normalized_fingerprint VARCHAR(255) NOT NULL, 
	review_status bankstatementlinestatus NOT NULL, 
	suggested_action bankstatementsuggestedaction NOT NULL, 
	resolution_reason VARCHAR(64), 
	confidence_score NUMERIC(4, 3) NOT NULL, 
	linked_transaction_id INTEGER, 
	created_transaction_id INTEGER, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	reviewed_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(import_id) REFERENCES bank_statement_imports (id) ON DELETE CASCADE, 
	FOREIGN KEY(linked_transaction_id) REFERENCES transactions (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_transaction_id) REFERENCES transactions (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_bank_statement_lines_created_transaction_id ON bank_statement_lines (created_transaction_id);

CREATE INDEX ix_bank_statement_lines_line_date ON bank_statement_lines (line_date);

CREATE INDEX ix_bank_statement_lines_linked_transaction_id ON bank_statement_lines (linked_transaction_id);

CREATE INDEX ix_bank_statement_lines_review_status ON bank_statement_lines (review_status);

CREATE INDEX ix_bank_statement_lines_import_id ON bank_statement_lines (import_id);

CREATE INDEX ix_bank_statement_lines_id ON bank_statement_lines (id);

CREATE INDEX ix_bank_statement_lines_normalized_fingerprint ON bank_statement_lines (normalized_fingerprint);

CREATE TABLE historical_import_uploads (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	session_id UUID, 
	user_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	document_type historicaldocumenttype NOT NULL, 
	tax_year INTEGER NOT NULL, 
	status importstatus NOT NULL, 
	ocr_task_id VARCHAR(255), 
	extraction_confidence NUMERIC(3, 2), 
	extracted_data JSONB, 
	edited_data JSONB, 
	transactions_created INTEGER[] NOT NULL, 
	properties_created UUID[] NOT NULL, 
	properties_linked UUID[] NOT NULL, 
	requires_review BOOLEAN NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	reviewed_by INTEGER, 
	approval_notes TEXT, 
	errors JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES historical_import_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_historical_import_uploads_user_id ON historical_import_uploads (user_id);

CREATE INDEX ix_historical_import_uploads_tax_year ON historical_import_uploads (tax_year);

CREATE INDEX ix_historical_import_uploads_document_type ON historical_import_uploads (document_type);

CREATE INDEX ix_historical_import_uploads_document_id ON historical_import_uploads (document_id);

CREATE INDEX ix_historical_import_uploads_status ON historical_import_uploads (status);

CREATE INDEX ix_historical_import_uploads_session_id ON historical_import_uploads (session_id);

CREATE TABLE employer_month_documents (
	id SERIAL NOT NULL, 
	employer_month_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	relation_type VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_employer_month_document UNIQUE (employer_month_id, document_id), 
	FOREIGN KEY(employer_month_id) REFERENCES employer_months (id) ON DELETE CASCADE, 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_employer_month_documents_employer_month_id ON employer_month_documents (employer_month_id);

CREATE INDEX ix_employer_month_documents_document_id ON employer_month_documents (document_id);

CREATE INDEX ix_employer_month_documents_id ON employer_month_documents (id);

CREATE TABLE employer_annual_archive_documents (
	id SERIAL NOT NULL, 
	annual_archive_id INTEGER NOT NULL, 
	document_id INTEGER NOT NULL, 
	relation_type VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_employer_annual_archive_document UNIQUE (annual_archive_id, document_id), 
	FOREIGN KEY(annual_archive_id) REFERENCES employer_annual_archives (id) ON DELETE CASCADE, 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_employer_annual_archive_documents_id ON employer_annual_archive_documents (id);

CREATE INDEX ix_employer_annual_archive_documents_annual_archive_id ON employer_annual_archive_documents (annual_archive_id);

CREATE INDEX ix_employer_annual_archive_documents_document_id ON employer_annual_archive_documents (document_id);

CREATE TABLE import_conflicts (
	id SERIAL NOT NULL, 
	session_id UUID NOT NULL, 
	upload_id_1 UUID NOT NULL, 
	upload_id_2 UUID NOT NULL, 
	conflict_type VARCHAR(100) NOT NULL, 
	field_name VARCHAR(255) NOT NULL, 
	value_1 VARCHAR(500), 
	value_2 VARCHAR(500), 
	resolution VARCHAR(100), 
	resolved_at TIMESTAMP WITHOUT TIME ZONE, 
	resolved_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES historical_import_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(upload_id_1) REFERENCES historical_import_uploads (id) ON DELETE CASCADE, 
	FOREIGN KEY(upload_id_2) REFERENCES historical_import_uploads (id) ON DELETE CASCADE, 
	FOREIGN KEY(resolved_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_import_conflicts_id ON import_conflicts (id);

CREATE INDEX ix_import_conflicts_session_id ON import_conflicts (session_id);

CREATE TABLE import_metrics (
	id SERIAL NOT NULL, 
	upload_id UUID NOT NULL, 
	document_type historicaldocumenttype NOT NULL, 
	extraction_confidence NUMERIC(3, 2) NOT NULL, 
	fields_extracted INTEGER NOT NULL, 
	fields_total INTEGER NOT NULL, 
	extraction_time_ms INTEGER NOT NULL, 
	field_accuracies JSONB NOT NULL, 
	fields_corrected INTEGER NOT NULL, 
	corrections JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(upload_id) REFERENCES historical_import_uploads (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_import_metrics_upload_id ON import_metrics (upload_id);

CREATE INDEX ix_import_metrics_document_type ON import_metrics (document_type);

CREATE INDEX ix_import_metrics_id ON import_metrics (id);

ALTER TABLE transactions ADD FOREIGN KEY(parent_recurring_id) REFERENCES transactions (id) ON DELETE SET NULL;

ALTER TABLE recurring_transactions ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE documents ADD FOREIGN KEY(transaction_id) REFERENCES transactions (id) ON DELETE SET NULL;

ALTER TABLE liabilities ADD FOREIGN KEY(linked_loan_id) REFERENCES property_loans (id) ON DELETE SET NULL;

ALTER TABLE transactions ADD FOREIGN KEY(liability_id) REFERENCES liabilities (id) ON DELETE SET NULL;

ALTER TABLE transactions ADD FOREIGN KEY(source_recurring_id) REFERENCES recurring_transactions (id) ON DELETE SET NULL;

ALTER TABLE property_loans ADD FOREIGN KEY(loan_contract_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE liabilities ADD FOREIGN KEY(source_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE subscriptions ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE transactions ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE documents ADD FOREIGN KEY(parent_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE subscriptions ADD FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT;

ALTER TABLE transactions ADD FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE recurring_transactions ADD FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE;

ALTER TABLE properties ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE recurring_transactions ADD FOREIGN KEY(loan_id) REFERENCES property_loans (id) ON DELETE CASCADE;

ALTER TABLE users ADD FOREIGN KEY(subscription_id) REFERENCES subscriptions (id) ON DELETE SET NULL;

ALTER TABLE liabilities ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE recurring_transactions ADD FOREIGN KEY(liability_id) REFERENCES liabilities (id) ON DELETE SET NULL;

ALTER TABLE documents ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE recurring_transactions ADD FOREIGN KEY(source_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE property_loans ADD FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE;

ALTER TABLE properties ADD FOREIGN KEY(kaufvertrag_document_id) REFERENCES documents (id) ON DELETE SET NULL;

ALTER TABLE transactions ADD FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE SET NULL;

ALTER TABLE liabilities ADD FOREIGN KEY(linked_property_id) REFERENCES properties (id) ON DELETE SET NULL;

ALTER TABLE property_loans ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE properties ADD FOREIGN KEY(mietvertrag_document_id) REFERENCES documents (id) ON DELETE SET NULL;

-- =============================================================
-- PART 2: Seed Data
-- =============================================================

-- Plans (Free, Plus, Pro)
INSERT INTO plans (plan_type, name, monthly_price, yearly_price, features, quotas, monthly_credits, overage_price_per_credit, created_at, updated_at)
VALUES
  ('free', 'Free', 0.00, 0.00,
   '{"ai_assistant": true, "ocr_scanning": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true}',
   '{}', 100, NULL, NOW(), NOW()),
  ('plus', 'Plus', 4.90, 49.00,
   '{"svs_calc": true, "vat_calc": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "full_tax_calc": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}',
   '{}', 500, 0.0400, NOW(), NOW()),
  ('pro', 'Pro', 12.90, 129.00,
   '{"svs_calc": true, "vat_calc": true, "api_access": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "e1_generation": true, "full_tax_calc": true, "unlimited_ocr": true, "basic_tax_calc": true, "multi_language": true, "advanced_reports": true, "priority_support": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}',
   '{}', 2000, 0.0300, NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Credit cost configs
INSERT INTO credit_cost_configs (operation, credit_cost, description, pricing_version, is_active, updated_at)
VALUES
  ('ocr_scan', 5, 'OCR document scan', 1, true, NOW()),
  ('ai_conversation', 3, 'AI assistant conversation', 1, true, NOW()),
  ('transaction_entry', 1, 'Transaction entry', 1, true, NOW()),
  ('bank_import', 10, 'Bank statement import', 1, true, NOW()),
  ('e1_generation', 20, 'E1 tax form generation', 1, true, NOW()),
  ('tax_calc', 2, 'Tax calculation', 1, true, NOW())
ON CONFLICT DO NOTHING;

-- Credit topup packages
INSERT INTO credit_topup_packages (name, credits, price, is_active, created_at)
VALUES
  ('Small Pack', 100, 4.99, true, NOW()),
  ('Medium Pack', 300, 12.99, true, NOW()),
  ('Large Pack', 1000, 39.99, true, NOW())
ON CONFLICT DO NOTHING;

-- Tax configurations are seeded by the application on startup.
-- See backend/app/db/seed_tax_config.py

-- =============================================================
-- PART 3: Alembic version stamp
-- =============================================================

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO alembic_version (version_num)
  VALUES ('073_add_document_year_fields')
  ON CONFLICT DO NOTHING;
