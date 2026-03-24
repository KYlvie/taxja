--
-- PostgreSQL database dump
--

\restrict t5WeTTuTMMzmNHJhc4j3G4fiELwIe0xTsh2H0L137A6ylwapDY3gHcyeeeGpm3b

-- Dumped from database version 15.17
-- Dumped by pg_dump version 15.17

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: asseteventtriggersource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asseteventtriggersource AS ENUM (
    'system',
    'user',
    'policy_recompute',
    'import'
);


--
-- Name: asseteventtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asseteventtype AS ENUM (
    'acquired',
    'put_into_use',
    'reclassified',
    'business_use_changed',
    'degressive_to_linear_switch',
    'ifb_flagged',
    'ifb_claimed',
    'sold',
    'scrapped',
    'private_withdrawal'
);


--
-- Name: auditentitytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.auditentitytype AS ENUM (
    'property',
    'transaction',
    'property_loan'
);


--
-- Name: auditoperationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.auditoperationtype AS ENUM (
    'create',
    'update',
    'delete',
    'archive',
    'link_transaction',
    'unlink_transaction',
    'backfill_depreciation',
    'generate_depreciation'
);


--
-- Name: billingcycle; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.billingcycle AS ENUM (
    'monthly',
    'yearly'
);


--
-- Name: buildinguse; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.buildinguse AS ENUM (
    'residential',
    'commercial'
);


--
-- Name: creditledgerstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.creditledgerstatus AS ENUM (
    'settled',
    'reserved',
    'reversed',
    'failed'
);


--
-- Name: creditoperation; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.creditoperation AS ENUM (
    'deduction',
    'refund',
    'monthly_reset',
    'topup',
    'topup_expiry',
    'overage_settlement',
    'admin_adjustment',
    'migration'
);


--
-- Name: creditsource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.creditsource AS ENUM (
    'plan',
    'topup',
    'overage',
    'mixed'
);


--
-- Name: documenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.documenttype AS ENUM (
    'PAYSLIP',
    'RECEIPT',
    'INVOICE',
    'PURCHASE_CONTRACT',
    'RENTAL_CONTRACT',
    'LOAN_CONTRACT',
    'BANK_STATEMENT',
    'PROPERTY_TAX',
    'LOHNZETTEL',
    'SVS_NOTICE',
    'EINKOMMENSTEUERBESCHEID',
    'E1_FORM',
    'OTHER',
    'L1_FORM',
    'L1K_BEILAGE',
    'L1AB_BEILAGE',
    'E1A_BEILAGE',
    'E1B_BEILAGE',
    'E1KV_BEILAGE',
    'U1_FORM',
    'U30_FORM',
    'JAHRESABSCHLUSS',
    'SPENDENBESTAETIGUNG',
    'spendenbestaetigung',
    'VERSICHERUNGSBESTAETIGUNG',
    'versicherungsbestaetigung',
    'KINDERBETREUUNGSKOSTEN',
    'kinderbetreuungskosten',
    'FORTBILDUNGSKOSTEN',
    'fortbildungskosten',
    'PENDLERPAUSCHALE',
    'pendlerpauschale',
    'KIRCHENBEITRAG',
    'kirchenbeitrag',
    'GRUNDBUCHAUSZUG',
    'grundbuchauszug',
    'BETRIEBSKOSTENABRECHNUNG',
    'betriebskostenabrechnung',
    'GEWERBESCHEIN',
    'gewerbeschein',
    'KONTOAUSZUG',
    'kontoauszug',
    'payslip',
    'receipt',
    'invoice',
    'purchase_contract',
    'rental_contract',
    'loan_contract',
    'bank_statement',
    'property_tax',
    'lohnzettel',
    'svs_notice',
    'einkommensteuerbescheid',
    'e1_form',
    'l1_form',
    'l1k_beilage',
    'l1ab_beilage',
    'e1a_beilage',
    'e1b_beilage',
    'e1kv_beilage',
    'u1_form',
    'u30_form',
    'jahresabschluss',
    'other'
);


--
-- Name: employerannualarchivestatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.employerannualarchivestatus AS ENUM (
    'PENDING_CONFIRMATION',
    'ARCHIVED'
);


--
-- Name: employermonthstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.employermonthstatus AS ENUM (
    'UNKNOWN',
    'PAYROLL_DETECTED',
    'MISSING_CONFIRMATION',
    'NO_PAYROLL_CONFIRMED',
    'ARCHIVED_YEAR_ONLY'
);


--
-- Name: expensecategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.expensecategory AS ENUM (
    'OFFICE_SUPPLIES',
    'EQUIPMENT',
    'TRAVEL',
    'MARKETING',
    'PROFESSIONAL_SERVICES',
    'INSURANCE',
    'MAINTENANCE',
    'PROPERTY_TAX',
    'LOAN_INTEREST',
    'DEPRECIATION',
    'GROCERIES',
    'UTILITIES',
    'COMMUTING',
    'HOME_OFFICE',
    'VEHICLE',
    'TELECOM',
    'RENT',
    'BANK_FEES',
    'SVS_CONTRIBUTIONS',
    'PROPERTY_MANAGEMENT_FEES',
    'PROPERTY_INSURANCE',
    'DEPRECIATION_AFA',
    'OTHER',
    'cleaning',
    'clothing',
    'software',
    'shipping',
    'fuel',
    'education'
);


--
-- Name: gewinnermittlungsart; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.gewinnermittlungsart AS ENUM (
    'bilanzierung',
    'ea_rechnung',
    'pauschal',
    'unknown'
);


--
-- Name: historicaldocumenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.historicaldocumenttype AS ENUM (
    'E1_FORM',
    'BESCHEID',
    'KAUFVERTRAG',
    'SALDENLISTE'
);


--
-- Name: importsessionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.importsessionstatus AS ENUM (
    'ACTIVE',
    'COMPLETED',
    'FAILED'
);


--
-- Name: importstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.importstatus AS ENUM (
    'UPLOADED',
    'PROCESSING',
    'EXTRACTED',
    'REVIEW_REQUIRED',
    'APPROVED',
    'REJECTED',
    'FAILED'
);


--
-- Name: incomecategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.incomecategory AS ENUM (
    'AGRICULTURE',
    'SELF_EMPLOYMENT',
    'BUSINESS',
    'EMPLOYMENT',
    'CAPITAL_GAINS',
    'RENTAL',
    'OTHER_INCOME'
);


--
-- Name: liabilityreportcategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.liabilityreportcategory AS ENUM (
    'darlehen_und_kredite',
    'sonstige_verbindlichkeiten'
);


--
-- Name: liabilitysourcetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.liabilitysourcetype AS ENUM (
    'manual',
    'document_confirmed',
    'document_auto_created',
    'system_migrated'
);


--
-- Name: liabilitytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.liabilitytype AS ENUM (
    'property_loan',
    'business_loan',
    'owner_loan',
    'family_loan',
    'other_liability'
);


--
-- Name: lineitemallocationsource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.lineitemallocationsource AS ENUM (
    'manual',
    'ocr_split',
    'percentage_rule',
    'cap_rule',
    'loan_installment',
    'mixed_use_rule',
    'vat_policy',
    'legacy_backfill'
);


--
-- Name: lineitempostingtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.lineitempostingtype AS ENUM (
    'income',
    'expense',
    'private_use',
    'asset_acquisition',
    'liability_drawdown',
    'liability_repayment',
    'tax_payment',
    'transfer'
);


--
-- Name: loaninstallmentsource; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.loaninstallmentsource AS ENUM (
    'estimated',
    'manual',
    'bank_statement',
    'zinsbescheinigung'
);


--
-- Name: loaninstallmentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.loaninstallmentstatus AS ENUM (
    'scheduled',
    'posted',
    'reconciled',
    'overridden'
);


--
-- Name: messagerole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.messagerole AS ENUM (
    'USER',
    'ASSISTANT',
    'SYSTEM'
);


--
-- Name: notificationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.notificationtype AS ENUM (
    'TAX_RATE_UPDATE',
    'TAX_DEADLINE',
    'REPORT_READY',
    'SYSTEM_ANNOUNCEMENT'
);


--
-- Name: plantype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.plantype AS ENUM (
    'free',
    'plus',
    'pro'
);


--
-- Name: propertystatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.propertystatus AS ENUM (
    'active',
    'sold',
    'archived',
    'scrapped',
    'withdrawn'
);


--
-- Name: propertytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.propertytype AS ENUM (
    'rental',
    'owner_occupied',
    'mixed_use'
);


--
-- Name: recurrencefrequency; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recurrencefrequency AS ENUM (
    'monthly',
    'quarterly',
    'annually',
    'weekly',
    'biweekly'
);


--
-- Name: recurringtransactiontype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recurringtransactiontype AS ENUM (
    'rental_income',
    'loan_interest',
    'depreciation',
    'other_income',
    'other_expense',
    'manual',
    'insurance_premium',
    'loan_repayment'
);


--
-- Name: resourcetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.resourcetype AS ENUM (
    'TRANSACTIONS',
    'OCR_SCANS',
    'AI_CONVERSATIONS'
);


--
-- Name: selfemployedtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.selfemployedtype AS ENUM (
    'freiberufler',
    'gewerbetreibende',
    'neue_selbstaendige',
    'land_forstwirtschaft'
);


--
-- Name: subscriptionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.subscriptionstatus AS ENUM (
    'active',
    'past_due',
    'canceled',
    'trialing'
);


--
-- Name: transactiontype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transactiontype AS ENUM (
    'INCOME',
    'EXPENSE',
    'ASSET_ACQUISITION',
    'LIABILITY_DRAWDOWN',
    'LIABILITY_REPAYMENT',
    'TAX_PAYMENT',
    'TRANSFER'
);


--
-- Name: usertype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.usertype AS ENUM (
    'EMPLOYEE',
    'SELF_EMPLOYED',
    'LANDLORD',
    'MIXED',
    'GMBH'
);


--
-- Name: vatstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.vatstatus AS ENUM (
    'regelbesteuert',
    'kleinunternehmer',
    'pauschaliert',
    'unknown'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_deletion_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_deletion_logs (
    id integer NOT NULL,
    anonymous_user_hash character varying(64) NOT NULL,
    deleted_at timestamp without time zone NOT NULL,
    data_types_deleted json,
    deletion_method character varying(20),
    initiated_by character varying(20)
);


--
-- Name: account_deletion_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_deletion_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_deletion_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_deletion_logs_id_seq OWNED BY public.account_deletion_logs.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: asset_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_events (
    id integer NOT NULL,
    user_id integer NOT NULL,
    property_id uuid NOT NULL,
    event_type public.asseteventtype NOT NULL,
    trigger_source public.asseteventtriggersource DEFAULT 'system'::public.asseteventtriggersource NOT NULL,
    event_date date NOT NULL,
    payload json,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: asset_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.asset_events ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.asset_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: asset_policy_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_policy_snapshots (
    id integer NOT NULL,
    user_id integer NOT NULL,
    property_id uuid NOT NULL,
    policy_version character varying(50) DEFAULT 'asset_tax_engine_v1'::character varying NOT NULL,
    jurisdiction character varying(10) DEFAULT 'AT'::character varying NOT NULL,
    effective_anchor_date date NOT NULL,
    snapshot_payload json NOT NULL,
    rule_ids json,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: asset_policy_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.asset_policy_snapshots ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.asset_policy_snapshots_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    user_id integer,
    operation_type public.auditoperationtype NOT NULL,
    entity_type public.auditentitytype NOT NULL,
    entity_id character varying(100) NOT NULL,
    details json,
    created_at timestamp without time zone NOT NULL,
    ip_address character varying(45),
    user_agent character varying(500)
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: bank_statement_imports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_statement_imports (
    id integer NOT NULL,
    user_id integer NOT NULL,
    source_type character varying(20) NOT NULL,
    source_document_id integer,
    bank_name character varying(255),
    iban character varying(64),
    statement_period json,
    tax_year integer,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: bank_statement_imports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bank_statement_imports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bank_statement_imports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bank_statement_imports_id_seq OWNED BY public.bank_statement_imports.id;


--
-- Name: bank_statement_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_statement_lines (
    id integer NOT NULL,
    import_id integer NOT NULL,
    line_date date NOT NULL,
    amount numeric(18,2) NOT NULL,
    counterparty character varying(255),
    purpose text,
    raw_reference text,
    normalized_fingerprint character varying(255) NOT NULL,
    review_status character varying(32) DEFAULT 'pending_review'::character varying NOT NULL,
    suggested_action character varying(32) DEFAULT 'create_new'::character varying NOT NULL,
    confidence_score numeric(5,3),
    linked_transaction_id integer,
    created_transaction_id integer,
    reviewed_at timestamp without time zone,
    reviewed_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: bank_statement_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bank_statement_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bank_statement_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bank_statement_lines_id_seq OWNED BY public.bank_statement_lines.id;


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id integer NOT NULL,
    user_id integer NOT NULL,
    role public.messagerole NOT NULL,
    content text NOT NULL,
    language character varying(5) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_messages_id_seq OWNED BY public.chat_messages.id;


--
-- Name: classification_corrections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.classification_corrections (
    id integer NOT NULL,
    transaction_id integer NOT NULL,
    user_id integer NOT NULL,
    original_category character varying NOT NULL,
    original_confidence character varying,
    correct_category character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    source character varying(30) DEFAULT 'human_verified'::character varying
);


--
-- Name: classification_corrections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.classification_corrections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: classification_corrections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.classification_corrections_id_seq OWNED BY public.classification_corrections.id;


--
-- Name: credit_balances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_balances (
    id integer NOT NULL,
    user_id integer NOT NULL,
    plan_balance integer NOT NULL,
    topup_balance integer NOT NULL,
    overage_enabled boolean NOT NULL,
    overage_credits_used integer NOT NULL,
    has_unpaid_overage boolean NOT NULL,
    unpaid_overage_periods integer NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    CONSTRAINT ck_credit_balances_overage_credits_used_non_negative CHECK ((overage_credits_used >= 0)),
    CONSTRAINT ck_credit_balances_plan_balance_non_negative CHECK ((plan_balance >= 0)),
    CONSTRAINT ck_credit_balances_topup_balance_non_negative CHECK ((topup_balance >= 0)),
    CONSTRAINT ck_credit_balances_unpaid_overage_periods_non_negative CHECK ((unpaid_overage_periods >= 0))
);


--
-- Name: credit_balances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.credit_balances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: credit_balances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.credit_balances_id_seq OWNED BY public.credit_balances.id;


--
-- Name: credit_cost_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_cost_configs (
    id integer NOT NULL,
    operation character varying(50) NOT NULL,
    credit_cost integer NOT NULL,
    description character varying(200),
    pricing_version integer NOT NULL,
    is_active boolean NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: credit_cost_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.credit_cost_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: credit_cost_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.credit_cost_configs_id_seq OWNED BY public.credit_cost_configs.id;


--
-- Name: credit_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_ledger (
    id integer NOT NULL,
    user_id integer NOT NULL,
    operation public.creditoperation NOT NULL,
    operation_detail character varying(100),
    status public.creditledgerstatus NOT NULL,
    credit_amount integer NOT NULL,
    source public.creditsource NOT NULL,
    plan_balance_after integer NOT NULL,
    topup_balance_after integer NOT NULL,
    is_overage boolean NOT NULL,
    overage_portion integer NOT NULL,
    context_type character varying(50),
    context_id integer,
    reference_id character varying(255),
    reservation_id character varying(255),
    reason character varying(200),
    pricing_version integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    CONSTRAINT ck_credit_ledger_amount_nonzero CHECK ((credit_amount <> 0)),
    CONSTRAINT ck_credit_ledger_overage_portion_non_negative CHECK ((overage_portion >= 0)),
    CONSTRAINT ck_credit_ledger_plan_balance_after_non_negative CHECK ((plan_balance_after >= 0)),
    CONSTRAINT ck_credit_ledger_topup_balance_after_non_negative CHECK ((topup_balance_after >= 0))
);


--
-- Name: credit_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.credit_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: credit_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.credit_ledger_id_seq OWNED BY public.credit_ledger.id;


--
-- Name: credit_topup_packages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_topup_packages (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    credits integer NOT NULL,
    price numeric(10,2) NOT NULL,
    stripe_price_id character varying(255),
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: credit_topup_packages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.credit_topup_packages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: credit_topup_packages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.credit_topup_packages_id_seq OWNED BY public.credit_topup_packages.id;


--
-- Name: dismissed_suggestions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dismissed_suggestions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    description character varying(500) NOT NULL,
    amount double precision NOT NULL,
    category character varying(100) NOT NULL,
    dismissed_at timestamp without time zone NOT NULL
);


--
-- Name: dismissed_suggestions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dismissed_suggestions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dismissed_suggestions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dismissed_suggestions_id_seq OWNED BY public.dismissed_suggestions.id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    user_id integer NOT NULL,
    document_type public.documenttype NOT NULL,
    file_path character varying(500) NOT NULL,
    file_name character varying(255) NOT NULL,
    file_size integer,
    mime_type character varying(100),
    ocr_result json,
    raw_text text,
    confidence_score numeric(3,2),
    transaction_id integer,
    is_archived boolean NOT NULL,
    archived_at timestamp without time zone,
    uploaded_at timestamp without time zone NOT NULL,
    processed_at timestamp without time zone,
    parent_document_id integer,
    file_hash character varying(64)
);


--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: employer_annual_archive_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employer_annual_archive_documents (
    id integer NOT NULL,
    annual_archive_id integer NOT NULL,
    document_id integer NOT NULL,
    relation_type character varying(30) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: employer_annual_archive_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employer_annual_archive_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employer_annual_archive_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employer_annual_archive_documents_id_seq OWNED BY public.employer_annual_archive_documents.id;


--
-- Name: employer_annual_archives; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employer_annual_archives (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tax_year integer NOT NULL,
    status public.employerannualarchivestatus NOT NULL,
    source_type character varying(30),
    archive_signal character varying(50),
    confidence numeric(3,2),
    employer_name character varying(255),
    gross_income numeric(12,2),
    withheld_tax numeric(12,2),
    notes text,
    confirmed_at timestamp without time zone,
    last_signal_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: employer_annual_archives_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employer_annual_archives_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employer_annual_archives_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employer_annual_archives_id_seq OWNED BY public.employer_annual_archives.id;


--
-- Name: employer_month_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employer_month_documents (
    id integer NOT NULL,
    employer_month_id integer NOT NULL,
    document_id integer NOT NULL,
    relation_type character varying(30) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: employer_month_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employer_month_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employer_month_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employer_month_documents_id_seq OWNED BY public.employer_month_documents.id;


--
-- Name: employer_months; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employer_months (
    id integer NOT NULL,
    user_id integer NOT NULL,
    year_month character varying(7) NOT NULL,
    status public.employermonthstatus NOT NULL,
    source_type character varying(30),
    payroll_signal character varying(50),
    confidence numeric(3,2),
    employee_count integer,
    gross_wages numeric(12,2),
    net_paid numeric(12,2),
    employer_social_cost numeric(12,2),
    lohnsteuer numeric(12,2),
    db_amount numeric(12,2),
    dz_amount numeric(12,2),
    kommunalsteuer numeric(12,2),
    special_payments numeric(12,2),
    notes text,
    confirmed_at timestamp without time zone,
    last_signal_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: employer_months_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employer_months_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employer_months_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employer_months_id_seq OWNED BY public.employer_months.id;


--
-- Name: historical_import_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historical_import_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    status public.importsessionstatus NOT NULL,
    tax_years integer[] NOT NULL,
    created_at timestamp without time zone NOT NULL,
    completed_at timestamp without time zone,
    total_documents integer NOT NULL,
    successful_imports integer NOT NULL,
    failed_imports integer NOT NULL,
    transactions_created integer NOT NULL,
    properties_created integer NOT NULL,
    properties_linked integer NOT NULL
);


--
-- Name: historical_import_uploads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historical_import_uploads (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid,
    user_id integer NOT NULL,
    document_id integer NOT NULL,
    document_type public.historicaldocumenttype NOT NULL,
    tax_year integer NOT NULL,
    status public.importstatus NOT NULL,
    ocr_task_id character varying(255),
    extraction_confidence numeric(3,2),
    extracted_data jsonb,
    edited_data jsonb,
    transactions_created integer[] NOT NULL,
    properties_created uuid[] NOT NULL,
    properties_linked uuid[] NOT NULL,
    requires_review boolean NOT NULL,
    reviewed_at timestamp without time zone,
    reviewed_by integer,
    approval_notes text,
    errors jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: import_conflicts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.import_conflicts (
    id integer NOT NULL,
    session_id uuid NOT NULL,
    upload_id_1 uuid NOT NULL,
    upload_id_2 uuid NOT NULL,
    conflict_type character varying(100) NOT NULL,
    field_name character varying(255) NOT NULL,
    value_1 character varying(500),
    value_2 character varying(500),
    resolution character varying(100),
    resolved_at timestamp without time zone,
    resolved_by integer
);


--
-- Name: import_conflicts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.import_conflicts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: import_conflicts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.import_conflicts_id_seq OWNED BY public.import_conflicts.id;


--
-- Name: import_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.import_metrics (
    id integer NOT NULL,
    upload_id uuid NOT NULL,
    document_type public.historicaldocumenttype NOT NULL,
    extraction_confidence numeric(3,2) NOT NULL,
    fields_extracted integer NOT NULL,
    fields_total integer NOT NULL,
    extraction_time_ms integer NOT NULL,
    field_accuracies jsonb NOT NULL,
    fields_corrected integer NOT NULL,
    corrections jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: import_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.import_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: import_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.import_metrics_id_seq OWNED BY public.import_metrics.id;


--
-- Name: liabilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.liabilities (
    id integer NOT NULL,
    user_id integer NOT NULL,
    liability_type public.liabilitytype NOT NULL,
    display_name character varying(255) NOT NULL,
    currency character varying(3) DEFAULT 'EUR'::character varying NOT NULL,
    lender_name character varying(255) NOT NULL,
    principal_amount numeric(12,2) NOT NULL,
    outstanding_balance numeric(12,2) NOT NULL,
    interest_rate numeric(8,6),
    start_date date NOT NULL,
    end_date date,
    monthly_payment numeric(12,2),
    tax_relevant boolean DEFAULT false NOT NULL,
    tax_relevance_reason character varying(500),
    report_category public.liabilityreportcategory NOT NULL,
    linked_property_id uuid,
    linked_loan_id integer,
    source_document_id integer,
    is_active boolean DEFAULT true NOT NULL,
    notes character varying(1000),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    source_type public.liabilitysourcetype DEFAULT 'manual'::public.liabilitysourcetype NOT NULL
);


--
-- Name: liabilities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.liabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: liabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.liabilities_id_seq OWNED BY public.liabilities.id;


--
-- Name: loan_installments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loan_installments (
    id integer NOT NULL,
    loan_id integer NOT NULL,
    user_id integer NOT NULL,
    due_date date NOT NULL,
    actual_payment_date date,
    tax_year integer NOT NULL,
    scheduled_payment numeric(12,2) NOT NULL,
    principal_amount numeric(12,2) NOT NULL,
    interest_amount numeric(12,2) NOT NULL,
    remaining_balance_after numeric(12,2) NOT NULL,
    source public.loaninstallmentsource NOT NULL,
    status public.loaninstallmentstatus NOT NULL,
    source_document_id integer,
    notes character varying(1000),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    CONSTRAINT check_installment_interest_non_negative CHECK ((interest_amount >= (0)::numeric)),
    CONSTRAINT check_installment_payment_positive CHECK ((scheduled_payment > (0)::numeric)),
    CONSTRAINT check_installment_principal_non_negative CHECK ((principal_amount >= (0)::numeric)),
    CONSTRAINT check_installment_remaining_balance_non_negative CHECK ((remaining_balance_after >= (0)::numeric))
);


--
-- Name: loan_installments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.loan_installments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: loan_installments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.loan_installments_id_seq OWNED BY public.loan_installments.id;


--
-- Name: loss_carryforwards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loss_carryforwards (
    id integer NOT NULL,
    user_id integer NOT NULL,
    loss_year integer NOT NULL,
    loss_amount numeric(12,2) NOT NULL,
    used_amount numeric(12,2) NOT NULL,
    remaining_amount numeric(12,2) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: loss_carryforwards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.loss_carryforwards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: loss_carryforwards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.loss_carryforwards_id_seq OWNED BY public.loss_carryforwards.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    type public.notificationtype NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    message_en text,
    message_zh text,
    data jsonb,
    is_read boolean NOT NULL,
    read_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: payment_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_events (
    id integer NOT NULL,
    stripe_event_id character varying(255) NOT NULL,
    event_type character varying(100) NOT NULL,
    user_id integer,
    payload jsonb NOT NULL,
    processed_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: payment_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_events_id_seq OWNED BY public.payment_events.id;


--
-- Name: plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plans (
    id integer NOT NULL,
    plan_type public.plantype NOT NULL,
    name character varying(100) NOT NULL,
    monthly_price numeric(10,2) NOT NULL,
    yearly_price numeric(10,2) NOT NULL,
    features jsonb NOT NULL,
    quotas jsonb NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    monthly_credits integer DEFAULT 0 NOT NULL,
    overage_price_per_credit numeric(6,4)
);


--
-- Name: plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.plans_id_seq OWNED BY public.plans.id;


--
-- Name: properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.properties (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id integer NOT NULL,
    asset_type character varying(50) NOT NULL,
    sub_category character varying(100),
    name character varying(255),
    property_type public.propertytype NOT NULL,
    rental_percentage numeric(5,2) NOT NULL,
    useful_life_years integer,
    business_use_percentage numeric(5,2) NOT NULL,
    supplier character varying(255),
    accumulated_depreciation numeric(12,2) NOT NULL,
    address character varying(1000) NOT NULL,
    street character varying(500) NOT NULL,
    city character varying(200) NOT NULL,
    postal_code character varying(10) NOT NULL,
    purchase_date date NOT NULL,
    purchase_price numeric(12,2) NOT NULL,
    building_value numeric(12,2) NOT NULL,
    land_value numeric(12,2),
    grunderwerbsteuer numeric(12,2),
    notary_fees numeric(12,2),
    registry_fees numeric(12,2),
    construction_year integer,
    depreciation_rate numeric(5,4) NOT NULL,
    status public.propertystatus NOT NULL,
    sale_date date,
    kaufvertrag_document_id integer,
    mietvertrag_document_id integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    sale_price numeric(12,2),
    hauptwohnsitz boolean DEFAULT false NOT NULL,
    selbst_errichtet boolean DEFAULT false NOT NULL,
    building_use public.buildinguse DEFAULT 'residential'::public.buildinguse NOT NULL,
    eco_standard boolean DEFAULT false NOT NULL,
    acquisition_kind character varying(30),
    put_into_use_date date,
    is_used_asset boolean DEFAULT false NOT NULL,
    first_registration_date date,
    prior_owner_usage_years numeric(5,2),
    comparison_basis character varying(10),
    comparison_amount numeric(12,2),
    gwg_eligible boolean DEFAULT false NOT NULL,
    gwg_elected boolean DEFAULT false NOT NULL,
    depreciation_method character varying(20) DEFAULT 'linear'::character varying,
    degressive_afa_rate numeric(5,4),
    useful_life_source character varying(50),
    income_tax_cost_cap numeric(12,2),
    income_tax_depreciable_base numeric(12,2),
    vat_recoverable_status character varying(20),
    ifb_candidate boolean DEFAULT false NOT NULL,
    ifb_rate numeric(5,4),
    ifb_rate_source character varying(50),
    recognition_decision character varying(50),
    policy_confidence numeric(5,4),
    disposal_reason character varying(30),
    CONSTRAINT check_building_value_range CHECK (((building_value > (0)::numeric) AND (building_value <= purchase_price))),
    CONSTRAINT check_construction_year_min CHECK (((construction_year IS NULL) OR (construction_year >= 1800))),
    CONSTRAINT check_depreciation_rate_range CHECK (((depreciation_rate >= 0.001) AND (depreciation_rate <= 1.00))),
    CONSTRAINT check_purchase_price_range CHECK (((purchase_price > (0)::numeric) AND (purchase_price <= (100000000)::numeric))),
    CONSTRAINT check_rental_percentage_range CHECK (((rental_percentage >= (0)::numeric) AND (rental_percentage <= (100)::numeric))),
    CONSTRAINT check_sale_date_after_purchase CHECK (((sale_date IS NULL) OR (sale_date >= purchase_date))),
    CONSTRAINT check_sold_has_sale_date CHECK (((status <> 'sold'::public.propertystatus) OR (sale_date IS NOT NULL)))
);


--
-- Name: property_loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_loans (
    id integer NOT NULL,
    property_id uuid NOT NULL,
    user_id integer NOT NULL,
    loan_amount numeric(12,2) NOT NULL,
    interest_rate numeric(5,4) NOT NULL,
    start_date date NOT NULL,
    end_date date,
    monthly_payment numeric(12,2) NOT NULL,
    lender_name character varying(255) NOT NULL,
    lender_account character varying(100),
    loan_type character varying(50),
    loan_contract_document_id integer,
    notes character varying(1000),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    CONSTRAINT check_end_date_after_start CHECK (((end_date IS NULL) OR (end_date >= start_date))),
    CONSTRAINT check_interest_rate_range CHECK (((interest_rate >= (0)::numeric) AND (interest_rate <= 0.20))),
    CONSTRAINT check_loan_amount_positive CHECK ((loan_amount > (0)::numeric)),
    CONSTRAINT check_monthly_payment_positive CHECK ((monthly_payment > (0)::numeric))
);


--
-- Name: property_loans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.property_loans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: property_loans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.property_loans_id_seq OWNED BY public.property_loans.id;


--
-- Name: recurring_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recurring_transactions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    recurring_type public.recurringtransactiontype NOT NULL,
    property_id uuid,
    loan_id integer,
    description character varying(500) NOT NULL,
    amount numeric(12,2) NOT NULL,
    transaction_type character varying(20) NOT NULL,
    category character varying(100) NOT NULL,
    frequency public.recurrencefrequency NOT NULL,
    start_date date NOT NULL,
    end_date date,
    day_of_month integer,
    is_active boolean NOT NULL,
    paused_at timestamp without time zone,
    last_generated_date date,
    next_generation_date date,
    template character varying(50),
    notes character varying(1000),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    unit_percentage numeric(5,2) DEFAULT NULL::numeric,
    source_document_id integer,
    liability_id integer,
    CONSTRAINT check_amount_positive CHECK ((amount > (0)::numeric)),
    CONSTRAINT check_day_of_month_range CHECK (((day_of_month IS NULL) OR ((day_of_month >= 1) AND (day_of_month <= 31)))),
    CONSTRAINT check_end_date_after_start CHECK (((end_date IS NULL) OR (end_date >= start_date))),
    CONSTRAINT check_source_entity_required CHECK ((((recurring_type = 'rental_income'::public.recurringtransactiontype) AND (property_id IS NOT NULL)) OR ((recurring_type = 'loan_interest'::public.recurringtransactiontype) AND (loan_id IS NOT NULL)) OR ((recurring_type = 'depreciation'::public.recurringtransactiontype) AND (property_id IS NOT NULL)) OR (recurring_type = ANY (ARRAY['other_income'::public.recurringtransactiontype, 'other_expense'::public.recurringtransactiontype, 'manual'::public.recurringtransactiontype, 'insurance_premium'::public.recurringtransactiontype, 'loan_repayment'::public.recurringtransactiontype])))),
    CONSTRAINT check_transaction_type_valid CHECK (((transaction_type)::text = ANY ((ARRAY['income'::character varying, 'expense'::character varying, 'asset_acquisition'::character varying, 'liability_drawdown'::character varying, 'liability_repayment'::character varying, 'tax_payment'::character varying, 'transfer'::character varying])::text[])))
);


--
-- Name: recurring_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recurring_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recurring_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recurring_transactions_id_seq OWNED BY public.recurring_transactions.id;


--
-- Name: reminder_states; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reminder_states (
    id integer NOT NULL,
    user_id integer NOT NULL,
    reminder_kind character varying(80) NOT NULL,
    bucket character varying(40) NOT NULL,
    fingerprint character varying(128) NOT NULL,
    status character varying(20) DEFAULT 'active'::character varying NOT NULL,
    snoozed_until timestamp without time zone,
    last_seen_at timestamp without time zone,
    resolved_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: reminder_states_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reminder_states_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reminder_states_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reminder_states_id_seq OWNED BY public.reminder_states.id;


--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    plan_id integer NOT NULL,
    status public.subscriptionstatus NOT NULL,
    billing_cycle public.billingcycle,
    stripe_subscription_id character varying(255),
    stripe_customer_id character varying(255),
    current_period_start timestamp without time zone,
    current_period_end timestamp without time zone,
    cancel_at_period_end boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.subscriptions_id_seq OWNED BY public.subscriptions.id;


--
-- Name: tax_configurations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_configurations (
    id integer NOT NULL,
    tax_year integer NOT NULL,
    tax_brackets json NOT NULL,
    exemption_amount numeric(12,2) NOT NULL,
    vat_rates json NOT NULL,
    svs_rates json NOT NULL,
    deduction_config json NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: tax_configurations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_configurations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_configurations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_configurations_id_seq OWNED BY public.tax_configurations.id;


--
-- Name: tax_filing_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_filing_data (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tax_year integer NOT NULL,
    data_type character varying(50) NOT NULL,
    source_document_id integer,
    data jsonb NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    confirmed_at timestamp without time zone
);


--
-- Name: tax_filing_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_filing_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_filing_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_filing_data_id_seq OWNED BY public.tax_filing_data.id;


--
-- Name: tax_form_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_form_templates (
    id integer NOT NULL,
    tax_year integer NOT NULL,
    form_type character varying(10) NOT NULL,
    display_name character varying(200),
    pdf_template bytea NOT NULL,
    field_mapping jsonb DEFAULT '{}'::jsonb NOT NULL,
    original_filename character varying(255),
    file_size_bytes integer,
    page_count integer,
    source_url character varying(500),
    bmf_version character varying(50),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: tax_form_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_form_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_form_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_form_templates_id_seq OWNED BY public.tax_form_templates.id;


--
-- Name: tax_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_reports (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tax_year integer NOT NULL,
    income_summary json NOT NULL,
    expense_summary json NOT NULL,
    tax_calculation json NOT NULL,
    deductions json NOT NULL,
    net_income numeric(12,2) NOT NULL,
    pdf_file_path character varying(500),
    xml_file_path character varying(500),
    generated_at timestamp without time zone NOT NULL
);


--
-- Name: tax_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_reports_id_seq OWNED BY public.tax_reports.id;


--
-- Name: topup_purchases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.topup_purchases (
    id integer NOT NULL,
    user_id integer NOT NULL,
    credits_purchased integer NOT NULL,
    credits_remaining integer NOT NULL,
    price_paid numeric(10,2) NOT NULL,
    stripe_payment_id character varying(255),
    purchased_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    is_expired boolean NOT NULL
);


--
-- Name: topup_purchases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.topup_purchases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: topup_purchases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.topup_purchases_id_seq OWNED BY public.topup_purchases.id;


--
-- Name: transaction_line_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction_line_items (
    id integer NOT NULL,
    transaction_id integer NOT NULL,
    description character varying(500) NOT NULL,
    amount numeric(12,2) NOT NULL,
    quantity integer DEFAULT 1 NOT NULL,
    category character varying(100),
    is_deductible boolean DEFAULT false NOT NULL,
    deduction_reason character varying(500),
    vat_rate numeric(5,4),
    vat_amount numeric(12,2),
    classification_method character varying(20),
    classification_confidence numeric(3,2),
    sort_order integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    posting_type public.lineitempostingtype DEFAULT 'expense'::public.lineitempostingtype NOT NULL,
    allocation_source public.lineitemallocationsource DEFAULT 'manual'::public.lineitemallocationsource NOT NULL,
    vat_recoverable_amount numeric(12,2) DEFAULT 0 NOT NULL,
    rule_bucket character varying(100)
);


--
-- Name: transaction_line_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaction_line_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaction_line_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaction_line_items_id_seq OWNED BY public.transaction_line_items.id;


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    property_id uuid,
    type public.transactiontype NOT NULL,
    amount numeric(12,2) NOT NULL,
    transaction_date date NOT NULL,
    description character varying(500),
    income_category public.incomecategory,
    expense_category public.expensecategory,
    is_deductible boolean,
    deduction_reason character varying(500),
    vat_rate numeric(5,4),
    vat_amount numeric(12,2),
    document_id integer,
    classification_confidence numeric(3,2),
    needs_review boolean,
    reviewed boolean NOT NULL,
    locked boolean NOT NULL,
    is_system_generated boolean NOT NULL,
    import_source character varying(50),
    is_recurring boolean NOT NULL,
    recurring_frequency character varying(20),
    recurring_start_date date,
    recurring_end_date date,
    recurring_day_of_month integer,
    recurring_is_active boolean NOT NULL,
    recurring_next_date date,
    recurring_last_generated date,
    parent_recurring_id integer,
    source_recurring_id integer,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    vat_type character varying(20),
    ai_review_notes character varying(500),
    classification_method character varying(20),
    liability_id integer,
    bank_reconciled boolean NOT NULL,
    bank_reconciled_at timestamp without time zone
);


--
-- Name: transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transactions_id_seq OWNED BY public.transactions.id;


--
-- Name: usage_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usage_records (
    id integer NOT NULL,
    user_id integer NOT NULL,
    resource_type public.resourcetype NOT NULL,
    count integer NOT NULL,
    period_start timestamp without time zone NOT NULL,
    period_end timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: usage_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usage_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usage_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usage_records_id_seq OWNED BY public.usage_records.id;


--
-- Name: user_classification_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_classification_rules (
    id integer NOT NULL,
    user_id integer NOT NULL,
    normalized_description character varying(300) NOT NULL,
    original_description character varying(500),
    txn_type character varying(20) NOT NULL,
    category character varying(100) NOT NULL,
    hit_count integer NOT NULL,
    confidence numeric(3,2) NOT NULL,
    rule_type character varying(10) NOT NULL,
    last_hit_at timestamp without time zone,
    conflict_count integer NOT NULL,
    frozen boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: user_classification_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_classification_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_classification_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_classification_rules_id_seq OWNED BY public.user_classification_rules.id;


--
-- Name: user_deductibility_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_deductibility_rules (
    id integer NOT NULL,
    user_id integer NOT NULL,
    normalized_description character varying(300) NOT NULL,
    original_description character varying(500),
    expense_category character varying(100) NOT NULL,
    is_deductible boolean NOT NULL,
    reason character varying(500),
    hit_count integer NOT NULL,
    last_hit_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: user_deductibility_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_deductibility_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_deductibility_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_deductibility_rules_id_seq OWNED BY public.user_deductibility_rules.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    tax_number character varying(500),
    vat_number character varying(500),
    address character varying(1000),
    user_type public.usertype NOT NULL,
    family_info json,
    commuting_info json,
    home_office_eligible boolean,
    language character varying(5),
    two_factor_enabled boolean,
    two_factor_secret character varying(500),
    disclaimer_accepted_at timestamp without time zone,
    is_admin boolean NOT NULL,
    account_status character varying(20) NOT NULL,
    deactivated_at timestamp without time zone,
    scheduled_deletion_at timestamp without time zone,
    deletion_retry_count integer NOT NULL,
    cancellation_reason character varying(500),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    last_login timestamp without time zone,
    subscription_id integer,
    trial_used boolean NOT NULL,
    trial_end_date timestamp without time zone,
    email_verified boolean DEFAULT false NOT NULL,
    email_verification_token character varying(255),
    email_verification_sent_at timestamp without time zone,
    bao_retention_expiry timestamp without time zone,
    business_name character varying(255),
    business_industry character varying(50),
    password_reset_token character varying(255),
    password_reset_sent_at timestamp without time zone,
    business_type character varying(50),
    telearbeit_days integer,
    employer_telearbeit_pauschale numeric(10,2),
    employer_mode character varying(20) NOT NULL,
    employer_region character varying(100),
    vat_status public.vatstatus,
    gewinnermittlungsart public.gewinnermittlungsart,
    onboarding_completed boolean DEFAULT false NOT NULL,
    onboarding_dismiss_count integer DEFAULT 0 NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: account_deletion_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_deletion_logs ALTER COLUMN id SET DEFAULT nextval('public.account_deletion_logs_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: bank_statement_imports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_imports ALTER COLUMN id SET DEFAULT nextval('public.bank_statement_imports_id_seq'::regclass);


--
-- Name: bank_statement_lines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines ALTER COLUMN id SET DEFAULT nextval('public.bank_statement_lines_id_seq'::regclass);


--
-- Name: chat_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages ALTER COLUMN id SET DEFAULT nextval('public.chat_messages_id_seq'::regclass);


--
-- Name: classification_corrections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classification_corrections ALTER COLUMN id SET DEFAULT nextval('public.classification_corrections_id_seq'::regclass);


--
-- Name: credit_balances id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_balances ALTER COLUMN id SET DEFAULT nextval('public.credit_balances_id_seq'::regclass);


--
-- Name: credit_cost_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_cost_configs ALTER COLUMN id SET DEFAULT nextval('public.credit_cost_configs_id_seq'::regclass);


--
-- Name: credit_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_ledger ALTER COLUMN id SET DEFAULT nextval('public.credit_ledger_id_seq'::regclass);


--
-- Name: credit_topup_packages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_topup_packages ALTER COLUMN id SET DEFAULT nextval('public.credit_topup_packages_id_seq'::regclass);


--
-- Name: dismissed_suggestions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dismissed_suggestions ALTER COLUMN id SET DEFAULT nextval('public.dismissed_suggestions_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: employer_annual_archive_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archive_documents ALTER COLUMN id SET DEFAULT nextval('public.employer_annual_archive_documents_id_seq'::regclass);


--
-- Name: employer_annual_archives id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archives ALTER COLUMN id SET DEFAULT nextval('public.employer_annual_archives_id_seq'::regclass);


--
-- Name: employer_month_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_month_documents ALTER COLUMN id SET DEFAULT nextval('public.employer_month_documents_id_seq'::regclass);


--
-- Name: employer_months id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_months ALTER COLUMN id SET DEFAULT nextval('public.employer_months_id_seq'::regclass);


--
-- Name: import_conflicts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts ALTER COLUMN id SET DEFAULT nextval('public.import_conflicts_id_seq'::regclass);


--
-- Name: import_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_metrics ALTER COLUMN id SET DEFAULT nextval('public.import_metrics_id_seq'::regclass);


--
-- Name: liabilities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities ALTER COLUMN id SET DEFAULT nextval('public.liabilities_id_seq'::regclass);


--
-- Name: loan_installments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments ALTER COLUMN id SET DEFAULT nextval('public.loan_installments_id_seq'::regclass);


--
-- Name: loss_carryforwards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loss_carryforwards ALTER COLUMN id SET DEFAULT nextval('public.loss_carryforwards_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: payment_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_events ALTER COLUMN id SET DEFAULT nextval('public.payment_events_id_seq'::regclass);


--
-- Name: plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plans ALTER COLUMN id SET DEFAULT nextval('public.plans_id_seq'::regclass);


--
-- Name: property_loans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_loans ALTER COLUMN id SET DEFAULT nextval('public.property_loans_id_seq'::regclass);


--
-- Name: recurring_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions ALTER COLUMN id SET DEFAULT nextval('public.recurring_transactions_id_seq'::regclass);


--
-- Name: reminder_states id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminder_states ALTER COLUMN id SET DEFAULT nextval('public.reminder_states_id_seq'::regclass);


--
-- Name: subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions ALTER COLUMN id SET DEFAULT nextval('public.subscriptions_id_seq'::regclass);


--
-- Name: tax_configurations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_configurations ALTER COLUMN id SET DEFAULT nextval('public.tax_configurations_id_seq'::regclass);


--
-- Name: tax_filing_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_filing_data ALTER COLUMN id SET DEFAULT nextval('public.tax_filing_data_id_seq'::regclass);


--
-- Name: tax_form_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_templates ALTER COLUMN id SET DEFAULT nextval('public.tax_form_templates_id_seq'::regclass);


--
-- Name: tax_reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_reports ALTER COLUMN id SET DEFAULT nextval('public.tax_reports_id_seq'::regclass);


--
-- Name: topup_purchases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topup_purchases ALTER COLUMN id SET DEFAULT nextval('public.topup_purchases_id_seq'::regclass);


--
-- Name: transaction_line_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_line_items ALTER COLUMN id SET DEFAULT nextval('public.transaction_line_items_id_seq'::regclass);


--
-- Name: transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions ALTER COLUMN id SET DEFAULT nextval('public.transactions_id_seq'::regclass);


--
-- Name: usage_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records ALTER COLUMN id SET DEFAULT nextval('public.usage_records_id_seq'::regclass);


--
-- Name: user_classification_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_classification_rules ALTER COLUMN id SET DEFAULT nextval('public.user_classification_rules_id_seq'::regclass);


--
-- Name: user_deductibility_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_deductibility_rules ALTER COLUMN id SET DEFAULT nextval('public.user_deductibility_rules_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: account_deletion_logs account_deletion_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_deletion_logs
    ADD CONSTRAINT account_deletion_logs_pkey PRIMARY KEY (id);


--
-- Name: asset_events asset_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_events
    ADD CONSTRAINT asset_events_pkey PRIMARY KEY (id);


--
-- Name: asset_policy_snapshots asset_policy_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_policy_snapshots
    ADD CONSTRAINT asset_policy_snapshots_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: bank_statement_imports bank_statement_imports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_imports
    ADD CONSTRAINT bank_statement_imports_pkey PRIMARY KEY (id);


--
-- Name: bank_statement_lines bank_statement_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines
    ADD CONSTRAINT bank_statement_lines_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: classification_corrections classification_corrections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classification_corrections
    ADD CONSTRAINT classification_corrections_pkey PRIMARY KEY (id);


--
-- Name: credit_balances credit_balances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_balances
    ADD CONSTRAINT credit_balances_pkey PRIMARY KEY (id);


--
-- Name: credit_cost_configs credit_cost_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_cost_configs
    ADD CONSTRAINT credit_cost_configs_pkey PRIMARY KEY (id);


--
-- Name: credit_ledger credit_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_ledger
    ADD CONSTRAINT credit_ledger_pkey PRIMARY KEY (id);


--
-- Name: credit_topup_packages credit_topup_packages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_topup_packages
    ADD CONSTRAINT credit_topup_packages_pkey PRIMARY KEY (id);


--
-- Name: dismissed_suggestions dismissed_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dismissed_suggestions
    ADD CONSTRAINT dismissed_suggestions_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: employer_annual_archive_documents employer_annual_archive_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archive_documents
    ADD CONSTRAINT employer_annual_archive_documents_pkey PRIMARY KEY (id);


--
-- Name: employer_annual_archives employer_annual_archives_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archives
    ADD CONSTRAINT employer_annual_archives_pkey PRIMARY KEY (id);


--
-- Name: employer_month_documents employer_month_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_month_documents
    ADD CONSTRAINT employer_month_documents_pkey PRIMARY KEY (id);


--
-- Name: employer_months employer_months_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_months
    ADD CONSTRAINT employer_months_pkey PRIMARY KEY (id);


--
-- Name: historical_import_sessions historical_import_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_sessions
    ADD CONSTRAINT historical_import_sessions_pkey PRIMARY KEY (id);


--
-- Name: historical_import_uploads historical_import_uploads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_uploads
    ADD CONSTRAINT historical_import_uploads_pkey PRIMARY KEY (id);


--
-- Name: import_conflicts import_conflicts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts
    ADD CONSTRAINT import_conflicts_pkey PRIMARY KEY (id);


--
-- Name: import_metrics import_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_metrics
    ADD CONSTRAINT import_metrics_pkey PRIMARY KEY (id);


--
-- Name: liabilities liabilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities
    ADD CONSTRAINT liabilities_pkey PRIMARY KEY (id);


--
-- Name: loan_installments loan_installments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_pkey PRIMARY KEY (id);


--
-- Name: loss_carryforwards loss_carryforwards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loss_carryforwards
    ADD CONSTRAINT loss_carryforwards_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: payment_events payment_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_events
    ADD CONSTRAINT payment_events_pkey PRIMARY KEY (id);


--
-- Name: plans plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plans
    ADD CONSTRAINT plans_pkey PRIMARY KEY (id);


--
-- Name: properties properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_pkey PRIMARY KEY (id);


--
-- Name: property_loans property_loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_loans
    ADD CONSTRAINT property_loans_pkey PRIMARY KEY (id);


--
-- Name: recurring_transactions recurring_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_pkey PRIMARY KEY (id);


--
-- Name: reminder_states reminder_states_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminder_states
    ADD CONSTRAINT reminder_states_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: tax_configurations tax_configurations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_configurations
    ADD CONSTRAINT tax_configurations_pkey PRIMARY KEY (id);


--
-- Name: tax_filing_data tax_filing_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_filing_data
    ADD CONSTRAINT tax_filing_data_pkey PRIMARY KEY (id);


--
-- Name: tax_form_templates tax_form_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_templates
    ADD CONSTRAINT tax_form_templates_pkey PRIMARY KEY (id);


--
-- Name: tax_reports tax_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_reports
    ADD CONSTRAINT tax_reports_pkey PRIMARY KEY (id);


--
-- Name: topup_purchases topup_purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topup_purchases
    ADD CONSTRAINT topup_purchases_pkey PRIMARY KEY (id);


--
-- Name: transaction_line_items transaction_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_line_items
    ADD CONSTRAINT transaction_line_items_pkey PRIMARY KEY (id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: employer_annual_archive_documents uq_employer_annual_archive_document; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archive_documents
    ADD CONSTRAINT uq_employer_annual_archive_document UNIQUE (annual_archive_id, document_id);


--
-- Name: employer_annual_archives uq_employer_annual_archive_user_year; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archives
    ADD CONSTRAINT uq_employer_annual_archive_user_year UNIQUE (user_id, tax_year);


--
-- Name: employer_month_documents uq_employer_month_document; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_month_documents
    ADD CONSTRAINT uq_employer_month_document UNIQUE (employer_month_id, document_id);


--
-- Name: employer_months uq_employer_month_user_month; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_months
    ADD CONSTRAINT uq_employer_month_user_month UNIQUE (user_id, year_month);


--
-- Name: loan_installments uq_loan_installments_loan_due_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT uq_loan_installments_loan_due_date UNIQUE (loan_id, due_date);


--
-- Name: reminder_states uq_reminder_state_user_kind_fingerprint; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminder_states
    ADD CONSTRAINT uq_reminder_state_user_kind_fingerprint UNIQUE (user_id, reminder_kind, fingerprint);


--
-- Name: tax_form_templates uq_tax_form_template_year_type; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_form_templates
    ADD CONSTRAINT uq_tax_form_template_year_type UNIQUE (tax_year, form_type);


--
-- Name: user_deductibility_rules uq_user_deductibility_description_category; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_deductibility_rules
    ADD CONSTRAINT uq_user_deductibility_description_category UNIQUE (user_id, normalized_description, expense_category);


--
-- Name: user_classification_rules uq_user_description_type; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_classification_rules
    ADD CONSTRAINT uq_user_description_type UNIQUE (user_id, normalized_description, txn_type);


--
-- Name: loss_carryforwards uq_user_loss_year; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loss_carryforwards
    ADD CONSTRAINT uq_user_loss_year UNIQUE (user_id, loss_year);


--
-- Name: usage_records usage_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records
    ADD CONSTRAINT usage_records_pkey PRIMARY KEY (id);


--
-- Name: user_classification_rules user_classification_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_classification_rules
    ADD CONSTRAINT user_classification_rules_pkey PRIMARY KEY (id);


--
-- Name: user_deductibility_rules user_deductibility_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_deductibility_rules
    ADD CONSTRAINT user_deductibility_rules_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_audit_created_at_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_created_at_desc ON public.audit_logs USING btree (created_at DESC);


--
-- Name: idx_audit_entity_operation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_entity_operation ON public.audit_logs USING btree (entity_type, entity_id, operation_type);


--
-- Name: idx_audit_user_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_user_entity ON public.audit_logs USING btree (user_id, entity_type, entity_id);


--
-- Name: ix_asset_events_event_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_events_event_date ON public.asset_events USING btree (event_date);


--
-- Name: ix_asset_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_events_event_type ON public.asset_events USING btree (event_type);


--
-- Name: ix_asset_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_events_id ON public.asset_events USING btree (id);


--
-- Name: ix_asset_events_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_events_property_id ON public.asset_events USING btree (property_id);


--
-- Name: ix_asset_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_events_user_id ON public.asset_events USING btree (user_id);


--
-- Name: ix_asset_policy_snapshots_effective_anchor_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_policy_snapshots_effective_anchor_date ON public.asset_policy_snapshots USING btree (effective_anchor_date);


--
-- Name: ix_asset_policy_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_policy_snapshots_id ON public.asset_policy_snapshots USING btree (id);


--
-- Name: ix_asset_policy_snapshots_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_policy_snapshots_property_id ON public.asset_policy_snapshots USING btree (property_id);


--
-- Name: ix_asset_policy_snapshots_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_asset_policy_snapshots_user_id ON public.asset_policy_snapshots USING btree (user_id);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_audit_logs_entity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_entity_id ON public.audit_logs USING btree (entity_id);


--
-- Name: ix_audit_logs_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_entity_type ON public.audit_logs USING btree (entity_type);


--
-- Name: ix_audit_logs_operation_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_operation_type ON public.audit_logs USING btree (operation_type);


--
-- Name: ix_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: ix_bank_statement_imports_user_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bank_statement_imports_user_document ON public.bank_statement_imports USING btree (user_id, source_document_id);


--
-- Name: ix_bank_statement_lines_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bank_statement_lines_fingerprint ON public.bank_statement_lines USING btree (normalized_fingerprint);


--
-- Name: ix_bank_statement_lines_import_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bank_statement_lines_import_status ON public.bank_statement_lines USING btree (import_id, review_status);


--
-- Name: ix_chat_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_id ON public.chat_messages USING btree (id);


--
-- Name: ix_chat_messages_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_user_id ON public.chat_messages USING btree (user_id);


--
-- Name: ix_classification_corrections_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_classification_corrections_id ON public.classification_corrections USING btree (id);


--
-- Name: ix_credit_balances_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_balances_id ON public.credit_balances USING btree (id);


--
-- Name: ix_credit_balances_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_credit_balances_user_id ON public.credit_balances USING btree (user_id);


--
-- Name: ix_credit_cost_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_cost_configs_id ON public.credit_cost_configs USING btree (id);


--
-- Name: ix_credit_cost_configs_operation; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_credit_cost_configs_operation ON public.credit_cost_configs USING btree (operation);


--
-- Name: ix_credit_ledger_context; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_context ON public.credit_ledger USING btree (context_type, context_id);


--
-- Name: ix_credit_ledger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_id ON public.credit_ledger USING btree (id);


--
-- Name: ix_credit_ledger_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_status ON public.credit_ledger USING btree (status);


--
-- Name: ix_credit_ledger_user_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_user_created ON public.credit_ledger USING btree (user_id, created_at);


--
-- Name: ix_credit_ledger_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_user_id ON public.credit_ledger USING btree (user_id);


--
-- Name: ix_credit_ledger_user_operation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_ledger_user_operation ON public.credit_ledger USING btree (user_id, operation);


--
-- Name: ix_credit_topup_packages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credit_topup_packages_id ON public.credit_topup_packages USING btree (id);


--
-- Name: ix_dismissed_suggestions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dismissed_suggestions_id ON public.dismissed_suggestions USING btree (id);


--
-- Name: ix_dismissed_suggestions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dismissed_suggestions_user_id ON public.dismissed_suggestions USING btree (user_id);


--
-- Name: ix_documents_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_document_type ON public.documents USING btree (document_type);


--
-- Name: ix_documents_file_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_file_hash ON public.documents USING btree (file_hash);


--
-- Name: ix_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_id ON public.documents USING btree (id);


--
-- Name: ix_documents_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_user_id ON public.documents USING btree (user_id);


--
-- Name: ix_employer_annual_archive_documents_annual_archive_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archive_documents_annual_archive_id ON public.employer_annual_archive_documents USING btree (annual_archive_id);


--
-- Name: ix_employer_annual_archive_documents_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archive_documents_document_id ON public.employer_annual_archive_documents USING btree (document_id);


--
-- Name: ix_employer_annual_archive_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archive_documents_id ON public.employer_annual_archive_documents USING btree (id);


--
-- Name: ix_employer_annual_archives_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archives_id ON public.employer_annual_archives USING btree (id);


--
-- Name: ix_employer_annual_archives_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archives_status ON public.employer_annual_archives USING btree (status);


--
-- Name: ix_employer_annual_archives_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archives_tax_year ON public.employer_annual_archives USING btree (tax_year);


--
-- Name: ix_employer_annual_archives_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_annual_archives_user_id ON public.employer_annual_archives USING btree (user_id);


--
-- Name: ix_employer_month_documents_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_month_documents_document_id ON public.employer_month_documents USING btree (document_id);


--
-- Name: ix_employer_month_documents_employer_month_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_month_documents_employer_month_id ON public.employer_month_documents USING btree (employer_month_id);


--
-- Name: ix_employer_month_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_month_documents_id ON public.employer_month_documents USING btree (id);


--
-- Name: ix_employer_months_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_months_id ON public.employer_months USING btree (id);


--
-- Name: ix_employer_months_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_months_status ON public.employer_months USING btree (status);


--
-- Name: ix_employer_months_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_months_user_id ON public.employer_months USING btree (user_id);


--
-- Name: ix_employer_months_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_employer_months_year_month ON public.employer_months USING btree (year_month);


--
-- Name: ix_historical_import_sessions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_sessions_status ON public.historical_import_sessions USING btree (status);


--
-- Name: ix_historical_import_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_sessions_user_id ON public.historical_import_sessions USING btree (user_id);


--
-- Name: ix_historical_import_uploads_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_document_id ON public.historical_import_uploads USING btree (document_id);


--
-- Name: ix_historical_import_uploads_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_document_type ON public.historical_import_uploads USING btree (document_type);


--
-- Name: ix_historical_import_uploads_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_session_id ON public.historical_import_uploads USING btree (session_id);


--
-- Name: ix_historical_import_uploads_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_status ON public.historical_import_uploads USING btree (status);


--
-- Name: ix_historical_import_uploads_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_tax_year ON public.historical_import_uploads USING btree (tax_year);


--
-- Name: ix_historical_import_uploads_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historical_import_uploads_user_id ON public.historical_import_uploads USING btree (user_id);


--
-- Name: ix_import_conflicts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_import_conflicts_id ON public.import_conflicts USING btree (id);


--
-- Name: ix_import_conflicts_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_import_conflicts_session_id ON public.import_conflicts USING btree (session_id);


--
-- Name: ix_import_metrics_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_import_metrics_document_type ON public.import_metrics USING btree (document_type);


--
-- Name: ix_import_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_import_metrics_id ON public.import_metrics USING btree (id);


--
-- Name: ix_import_metrics_upload_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_import_metrics_upload_id ON public.import_metrics USING btree (upload_id);


--
-- Name: ix_liabilities_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_is_active ON public.liabilities USING btree (is_active);


--
-- Name: ix_liabilities_liability_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_liability_type ON public.liabilities USING btree (liability_type);


--
-- Name: ix_liabilities_linked_loan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_linked_loan_id ON public.liabilities USING btree (linked_loan_id);


--
-- Name: ix_liabilities_linked_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_linked_property_id ON public.liabilities USING btree (linked_property_id);


--
-- Name: ix_liabilities_source_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_source_document_id ON public.liabilities USING btree (source_document_id);


--
-- Name: ix_liabilities_source_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_source_type ON public.liabilities USING btree (source_type);


--
-- Name: ix_liabilities_tax_relevant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_tax_relevant ON public.liabilities USING btree (tax_relevant);


--
-- Name: ix_liabilities_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liabilities_user_id ON public.liabilities USING btree (user_id);


--
-- Name: ix_loan_installments_due_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_due_date ON public.loan_installments USING btree (due_date);


--
-- Name: ix_loan_installments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_id ON public.loan_installments USING btree (id);


--
-- Name: ix_loan_installments_loan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_loan_id ON public.loan_installments USING btree (loan_id);


--
-- Name: ix_loan_installments_source_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_source_document_id ON public.loan_installments USING btree (source_document_id);


--
-- Name: ix_loan_installments_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_tax_year ON public.loan_installments USING btree (tax_year);


--
-- Name: ix_loan_installments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loan_installments_user_id ON public.loan_installments USING btree (user_id);


--
-- Name: ix_loss_carryforwards_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loss_carryforwards_id ON public.loss_carryforwards USING btree (id);


--
-- Name: ix_loss_carryforwards_loss_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loss_carryforwards_loss_year ON public.loss_carryforwards USING btree (loss_year);


--
-- Name: ix_loss_carryforwards_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_loss_carryforwards_user_id ON public.loss_carryforwards USING btree (user_id);


--
-- Name: ix_notifications_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_id ON public.notifications USING btree (id);


--
-- Name: ix_notifications_is_read; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_is_read ON public.notifications USING btree (is_read);


--
-- Name: ix_notifications_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: ix_payment_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_events_event_type ON public.payment_events USING btree (event_type);


--
-- Name: ix_payment_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_events_id ON public.payment_events USING btree (id);


--
-- Name: ix_payment_events_processed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_events_processed_at ON public.payment_events USING btree (processed_at);


--
-- Name: ix_payment_events_stripe_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_payment_events_stripe_event_id ON public.payment_events USING btree (stripe_event_id);


--
-- Name: ix_payment_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_events_user_id ON public.payment_events USING btree (user_id);


--
-- Name: ix_plans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plans_id ON public.plans USING btree (id);


--
-- Name: ix_plans_plan_type; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_plans_plan_type ON public.plans USING btree (plan_type);


--
-- Name: ix_properties_asset_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_properties_asset_type ON public.properties USING btree (asset_type);


--
-- Name: ix_properties_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_properties_status ON public.properties USING btree (status);


--
-- Name: ix_properties_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_properties_user_id ON public.properties USING btree (user_id);


--
-- Name: ix_property_loans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_property_loans_id ON public.property_loans USING btree (id);


--
-- Name: ix_property_loans_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_property_loans_property_id ON public.property_loans USING btree (property_id);


--
-- Name: ix_property_loans_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_property_loans_user_id ON public.property_loans USING btree (user_id);


--
-- Name: ix_recurring_transactions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_id ON public.recurring_transactions USING btree (id);


--
-- Name: ix_recurring_transactions_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_is_active ON public.recurring_transactions USING btree (is_active);


--
-- Name: ix_recurring_transactions_liability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_liability_id ON public.recurring_transactions USING btree (liability_id);


--
-- Name: ix_recurring_transactions_loan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_loan_id ON public.recurring_transactions USING btree (loan_id);


--
-- Name: ix_recurring_transactions_next_generation_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_next_generation_date ON public.recurring_transactions USING btree (next_generation_date);


--
-- Name: ix_recurring_transactions_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_property_id ON public.recurring_transactions USING btree (property_id);


--
-- Name: ix_recurring_transactions_recurring_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_recurring_type ON public.recurring_transactions USING btree (recurring_type);


--
-- Name: ix_recurring_transactions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recurring_transactions_user_id ON public.recurring_transactions USING btree (user_id);


--
-- Name: ix_reminder_states_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminder_states_fingerprint ON public.reminder_states USING btree (fingerprint);


--
-- Name: ix_reminder_states_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminder_states_id ON public.reminder_states USING btree (id);


--
-- Name: ix_reminder_states_reminder_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminder_states_reminder_kind ON public.reminder_states USING btree (reminder_kind);


--
-- Name: ix_reminder_states_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminder_states_status ON public.reminder_states USING btree (status);


--
-- Name: ix_reminder_states_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminder_states_user_id ON public.reminder_states USING btree (user_id);


--
-- Name: ix_subscriptions_current_period_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_current_period_end ON public.subscriptions USING btree (current_period_end);


--
-- Name: ix_subscriptions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_id ON public.subscriptions USING btree (id);


--
-- Name: ix_subscriptions_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_plan_id ON public.subscriptions USING btree (plan_id);


--
-- Name: ix_subscriptions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_status ON public.subscriptions USING btree (status);


--
-- Name: ix_subscriptions_stripe_customer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_stripe_customer_id ON public.subscriptions USING btree (stripe_customer_id);


--
-- Name: ix_subscriptions_stripe_subscription_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_subscriptions_stripe_subscription_id ON public.subscriptions USING btree (stripe_subscription_id);


--
-- Name: ix_subscriptions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_subscriptions_user_id ON public.subscriptions USING btree (user_id);


--
-- Name: ix_tax_configurations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_configurations_id ON public.tax_configurations USING btree (id);


--
-- Name: ix_tax_configurations_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_tax_configurations_tax_year ON public.tax_configurations USING btree (tax_year);


--
-- Name: ix_tax_filing_data_data_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_filing_data_data_type ON public.tax_filing_data USING btree (data_type);


--
-- Name: ix_tax_filing_data_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_filing_data_tax_year ON public.tax_filing_data USING btree (tax_year);


--
-- Name: ix_tax_filing_data_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_filing_data_user_id ON public.tax_filing_data USING btree (user_id);


--
-- Name: ix_tax_form_templates_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_form_templates_tax_year ON public.tax_form_templates USING btree (tax_year);


--
-- Name: ix_tax_reports_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_reports_id ON public.tax_reports USING btree (id);


--
-- Name: ix_tax_reports_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_reports_tax_year ON public.tax_reports USING btree (tax_year);


--
-- Name: ix_tax_reports_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tax_reports_user_id ON public.tax_reports USING btree (user_id);


--
-- Name: ix_topup_purchases_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_topup_purchases_id ON public.topup_purchases USING btree (id);


--
-- Name: ix_topup_purchases_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_topup_purchases_user_id ON public.topup_purchases USING btree (user_id);


--
-- Name: ix_transaction_line_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaction_line_items_id ON public.transaction_line_items USING btree (id);


--
-- Name: ix_transaction_line_items_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaction_line_items_transaction_id ON public.transaction_line_items USING btree (transaction_id);


--
-- Name: ix_transactions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_id ON public.transactions USING btree (id);


--
-- Name: ix_transactions_liability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_liability_id ON public.transactions USING btree (liability_id);


--
-- Name: ix_transactions_parent_recurring_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_parent_recurring_id ON public.transactions USING btree (parent_recurring_id);


--
-- Name: ix_transactions_property_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_property_id ON public.transactions USING btree (property_id);


--
-- Name: ix_transactions_source_recurring_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_source_recurring_id ON public.transactions USING btree (source_recurring_id);


--
-- Name: ix_transactions_transaction_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_transaction_date ON public.transactions USING btree (transaction_date);


--
-- Name: ix_transactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_type ON public.transactions USING btree (type);


--
-- Name: ix_transactions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transactions_user_id ON public.transactions USING btree (user_id);


--
-- Name: ix_usage_records_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_id ON public.usage_records USING btree (id);


--
-- Name: ix_usage_records_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_resource_type ON public.usage_records USING btree (resource_type);


--
-- Name: ix_usage_records_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usage_records_user_id ON public.usage_records USING btree (user_id);


--
-- Name: ix_user_classification_rules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_classification_rules_id ON public.user_classification_rules USING btree (id);


--
-- Name: ix_user_classification_rules_normalized_description; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_classification_rules_normalized_description ON public.user_classification_rules USING btree (normalized_description);


--
-- Name: ix_user_classification_rules_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_classification_rules_user_id ON public.user_classification_rules USING btree (user_id);


--
-- Name: ix_user_deductibility_rules_expense_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_deductibility_rules_expense_category ON public.user_deductibility_rules USING btree (expense_category);


--
-- Name: ix_user_deductibility_rules_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_deductibility_rules_id ON public.user_deductibility_rules USING btree (id);


--
-- Name: ix_user_deductibility_rules_normalized_description; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_deductibility_rules_normalized_description ON public.user_deductibility_rules USING btree (normalized_description);


--
-- Name: ix_user_deductibility_rules_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_deductibility_rules_user_id ON public.user_deductibility_rules USING btree (user_id);


--
-- Name: ix_users_account_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_account_status ON public.users USING btree (account_status);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_email_verification_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_email_verification_token ON public.users USING btree (email_verification_token);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_password_reset_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_password_reset_token ON public.users USING btree (password_reset_token);


--
-- Name: ix_users_subscription_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_subscription_id ON public.users USING btree (subscription_id);


--
-- Name: ix_users_trial_end_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_trial_end_date ON public.users USING btree (trial_end_date);


--
-- Name: uq_credit_ledger_refund_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_credit_ledger_refund_key ON public.credit_ledger USING btree (user_id, reference_id) WHERE ((operation = 'refund'::public.creditoperation) AND (reference_id IS NOT NULL));


--
-- Name: asset_events asset_events_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_events
    ADD CONSTRAINT asset_events_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: asset_events asset_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_events
    ADD CONSTRAINT asset_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: asset_policy_snapshots asset_policy_snapshots_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_policy_snapshots
    ADD CONSTRAINT asset_policy_snapshots_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: asset_policy_snapshots asset_policy_snapshots_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_policy_snapshots
    ADD CONSTRAINT asset_policy_snapshots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: bank_statement_imports bank_statement_imports_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_imports
    ADD CONSTRAINT bank_statement_imports_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: bank_statement_imports bank_statement_imports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_imports
    ADD CONSTRAINT bank_statement_imports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: bank_statement_lines bank_statement_lines_created_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines
    ADD CONSTRAINT bank_statement_lines_created_transaction_id_fkey FOREIGN KEY (created_transaction_id) REFERENCES public.transactions(id) ON DELETE SET NULL;


--
-- Name: bank_statement_lines bank_statement_lines_import_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines
    ADD CONSTRAINT bank_statement_lines_import_id_fkey FOREIGN KEY (import_id) REFERENCES public.bank_statement_imports(id) ON DELETE CASCADE;


--
-- Name: bank_statement_lines bank_statement_lines_linked_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines
    ADD CONSTRAINT bank_statement_lines_linked_transaction_id_fkey FOREIGN KEY (linked_transaction_id) REFERENCES public.transactions(id) ON DELETE SET NULL;


--
-- Name: bank_statement_lines bank_statement_lines_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_statement_lines
    ADD CONSTRAINT bank_statement_lines_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: credit_balances credit_balances_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_balances
    ADD CONSTRAINT credit_balances_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: credit_ledger credit_ledger_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credit_ledger
    ADD CONSTRAINT credit_ledger_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: dismissed_suggestions dismissed_suggestions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dismissed_suggestions
    ADD CONSTRAINT dismissed_suggestions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: chat_messages fk_chat_messages_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT fk_chat_messages_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: classification_corrections fk_classification_corrections_transaction_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classification_corrections
    ADD CONSTRAINT fk_classification_corrections_transaction_id FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE CASCADE;


--
-- Name: classification_corrections fk_classification_corrections_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classification_corrections
    ADD CONSTRAINT fk_classification_corrections_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: documents fk_documents_parent_document_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_parent_document_id FOREIGN KEY (parent_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: documents fk_documents_transaction_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_transaction_id FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE SET NULL;


--
-- Name: documents fk_documents_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT fk_documents_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: employer_annual_archive_documents fk_employer_annual_archive_documents_annual_archive_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archive_documents
    ADD CONSTRAINT fk_employer_annual_archive_documents_annual_archive_id FOREIGN KEY (annual_archive_id) REFERENCES public.employer_annual_archives(id) ON DELETE CASCADE;


--
-- Name: employer_annual_archive_documents fk_employer_annual_archive_documents_document_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archive_documents
    ADD CONSTRAINT fk_employer_annual_archive_documents_document_id FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: employer_annual_archives fk_employer_annual_archives_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_annual_archives
    ADD CONSTRAINT fk_employer_annual_archives_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: employer_month_documents fk_employer_month_documents_document_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_month_documents
    ADD CONSTRAINT fk_employer_month_documents_document_id FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: employer_month_documents fk_employer_month_documents_employer_month_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_month_documents
    ADD CONSTRAINT fk_employer_month_documents_employer_month_id FOREIGN KEY (employer_month_id) REFERENCES public.employer_months(id) ON DELETE CASCADE;


--
-- Name: employer_months fk_employer_months_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employer_months
    ADD CONSTRAINT fk_employer_months_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: loss_carryforwards fk_loss_carryforwards_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loss_carryforwards
    ADD CONSTRAINT fk_loss_carryforwards_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications fk_notifications_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notifications_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tax_filing_data fk_tax_filing_data_source_document_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_filing_data
    ADD CONSTRAINT fk_tax_filing_data_source_document_id FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: tax_filing_data fk_tax_filing_data_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_filing_data
    ADD CONSTRAINT fk_tax_filing_data_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tax_reports fk_tax_reports_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_reports
    ADD CONSTRAINT fk_tax_reports_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: transactions fk_transactions_document_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT fk_transactions_document_id FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: transactions fk_transactions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT fk_transactions_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_classification_rules fk_user_classification_rules_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_classification_rules
    ADD CONSTRAINT fk_user_classification_rules_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_deductibility_rules fk_user_deductibility_rules_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_deductibility_rules
    ADD CONSTRAINT fk_user_deductibility_rules_user_id FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: historical_import_sessions historical_import_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_sessions
    ADD CONSTRAINT historical_import_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: historical_import_uploads historical_import_uploads_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_uploads
    ADD CONSTRAINT historical_import_uploads_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: historical_import_uploads historical_import_uploads_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_uploads
    ADD CONSTRAINT historical_import_uploads_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: historical_import_uploads historical_import_uploads_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_uploads
    ADD CONSTRAINT historical_import_uploads_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.historical_import_sessions(id) ON DELETE CASCADE;


--
-- Name: historical_import_uploads historical_import_uploads_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historical_import_uploads
    ADD CONSTRAINT historical_import_uploads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: import_conflicts import_conflicts_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts
    ADD CONSTRAINT import_conflicts_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: import_conflicts import_conflicts_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts
    ADD CONSTRAINT import_conflicts_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.historical_import_sessions(id) ON DELETE CASCADE;


--
-- Name: import_conflicts import_conflicts_upload_id_1_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts
    ADD CONSTRAINT import_conflicts_upload_id_1_fkey FOREIGN KEY (upload_id_1) REFERENCES public.historical_import_uploads(id) ON DELETE CASCADE;


--
-- Name: import_conflicts import_conflicts_upload_id_2_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_conflicts
    ADD CONSTRAINT import_conflicts_upload_id_2_fkey FOREIGN KEY (upload_id_2) REFERENCES public.historical_import_uploads(id) ON DELETE CASCADE;


--
-- Name: import_metrics import_metrics_upload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.import_metrics
    ADD CONSTRAINT import_metrics_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES public.historical_import_uploads(id) ON DELETE CASCADE;


--
-- Name: liabilities liabilities_linked_loan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities
    ADD CONSTRAINT liabilities_linked_loan_id_fkey FOREIGN KEY (linked_loan_id) REFERENCES public.property_loans(id) ON DELETE SET NULL;


--
-- Name: liabilities liabilities_linked_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities
    ADD CONSTRAINT liabilities_linked_property_id_fkey FOREIGN KEY (linked_property_id) REFERENCES public.properties(id) ON DELETE SET NULL;


--
-- Name: liabilities liabilities_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities
    ADD CONSTRAINT liabilities_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: liabilities liabilities_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liabilities
    ADD CONSTRAINT liabilities_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: loan_installments loan_installments_loan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.property_loans(id) ON DELETE CASCADE;


--
-- Name: loan_installments loan_installments_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: loan_installments loan_installments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payment_events payment_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_events
    ADD CONSTRAINT payment_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: properties properties_kaufvertrag_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_kaufvertrag_document_id_fkey FOREIGN KEY (kaufvertrag_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: properties properties_mietvertrag_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_mietvertrag_document_id_fkey FOREIGN KEY (mietvertrag_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: properties properties_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: property_loans property_loans_loan_contract_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_loans
    ADD CONSTRAINT property_loans_loan_contract_document_id_fkey FOREIGN KEY (loan_contract_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: property_loans property_loans_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_loans
    ADD CONSTRAINT property_loans_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: property_loans property_loans_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_loans
    ADD CONSTRAINT property_loans_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: recurring_transactions recurring_transactions_liability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_liability_id_fkey FOREIGN KEY (liability_id) REFERENCES public.liabilities(id) ON DELETE SET NULL;


--
-- Name: recurring_transactions recurring_transactions_loan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.property_loans(id) ON DELETE CASCADE;


--
-- Name: recurring_transactions recurring_transactions_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: recurring_transactions recurring_transactions_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: recurring_transactions recurring_transactions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_transactions
    ADD CONSTRAINT recurring_transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: reminder_states reminder_states_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminder_states
    ADD CONSTRAINT reminder_states_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: subscriptions subscriptions_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.plans(id) ON DELETE RESTRICT;


--
-- Name: subscriptions subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: topup_purchases topup_purchases_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.topup_purchases
    ADD CONSTRAINT topup_purchases_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: transaction_line_items transaction_line_items_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_line_items
    ADD CONSTRAINT transaction_line_items_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_liability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_liability_id_fkey FOREIGN KEY (liability_id) REFERENCES public.liabilities(id) ON DELETE SET NULL;


--
-- Name: transactions transactions_parent_recurring_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_parent_recurring_id_fkey FOREIGN KEY (parent_recurring_id) REFERENCES public.transactions(id) ON DELETE SET NULL;


--
-- Name: transactions transactions_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE SET NULL;


--
-- Name: transactions transactions_source_recurring_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_source_recurring_id_fkey FOREIGN KEY (source_recurring_id) REFERENCES public.recurring_transactions(id) ON DELETE SET NULL;


--
-- Name: usage_records usage_records_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usage_records
    ADD CONSTRAINT usage_records_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict t5WeTTuTMMzmNHJhc4j3G4fiELwIe0xTsh2H0L137A6ylwapDY3gHcyeeeGpm3b

