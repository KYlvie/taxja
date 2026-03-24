--
-- PostgreSQL database dump
--

\restrict VUCjFFXsxrUWv45rqhoWoCqKITCR2HI2ctvI12lq5y1Bm3cykUagGXcFPCIl5zs

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
-- Data for Name: credit_cost_configs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.credit_cost_configs (id, operation, credit_cost, description, pricing_version, is_active, updated_at) FROM stdin;
1	ocr_scan	5	OCR document scanning	1	t	2026-03-18 23:12:25.804989
2	ai_conversation	10	AI assistant conversation	1	t	2026-03-18 23:12:25.804989
3	transaction_entry	1	Manual transaction entry	1	t	2026-03-18 23:12:25.804989
4	bank_import	3	Bank statement import	1	t	2026-03-18 23:12:25.804989
5	e1_generation	20	E1 tax form generation	1	t	2026-03-18 23:12:25.804989
6	tax_calc	2	Tax calculation	1	t	2026-03-18 23:12:25.804989
\.


--
-- Data for Name: credit_topup_packages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.credit_topup_packages (id, name, credits, price, stripe_price_id, is_active, created_at) FROM stdin;
1	Small Pack	100	4.99	\N	t	2026-03-18 23:12:25.804989
2	Medium Pack	300	12.99	\N	t	2026-03-18 23:12:25.804989
3	Large Pack	1000	39.99	\N	t	2026-03-18 23:12:25.804989
\.


--
-- Data for Name: plans; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.plans (id, plan_type, name, monthly_price, yearly_price, features, quotas, created_at, updated_at, monthly_credits, overage_price_per_credit) FROM stdin;
2	free	Free	0.00	0.00	{"ai_assistant": true, "ocr_scanning": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true}	{}	2026-03-15 16:03:20.113804	2026-03-15 16:03:20.113804	100	\N
3	plus	Plus	4.90	49.00	{"svs_calc": true, "vat_calc": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "full_tax_calc": true, "basic_tax_calc": true, "multi_language": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}	{}	2026-03-15 16:03:20.113804	2026-03-15 16:03:20.113804	500	0.0400
4	pro	Pro	12.90	129.00	{"svs_calc": true, "vat_calc": true, "api_access": true, "bank_import": true, "ai_assistant": true, "ocr_scanning": true, "e1_generation": true, "full_tax_calc": true, "unlimited_ocr": true, "basic_tax_calc": true, "multi_language": true, "advanced_reports": true, "priority_support": true, "transaction_entry": true, "property_management": true, "recurring_suggestions": true, "unlimited_transactions": true}	{}	2026-03-15 16:03:20.113804	2026-03-15 16:03:20.113804	2000	0.0300
\.


--
-- Data for Name: tax_configurations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tax_configurations (id, tax_year, tax_brackets, exemption_amount, vat_rates, svs_rates, deduction_config, created_at, updated_at) FROM stdin;
1	2022	[{"lower": 0, "upper": 11000, "rate": 0.0}, {"lower": 11000, "upper": 18000, "rate": 0.2}, {"lower": 18000, "upper": 31000, "rate": 0.325}, {"lower": 31000, "upper": 60000, "rate": 0.42}, {"lower": 60000, "upper": 90000, "rate": 0.48}, {"lower": 90000, "upper": 1000000, "rate": 0.5}, {"lower": 1000000, "upper": null, "rate": 0.55}]	11000.00	{"standard": 0.2, "residential": 0.1, "small_business_threshold": 35000.0, "tolerance_threshold": 38500.0}	{"pension": 0.185, "health": 0.068, "accident_fixed": 10.09, "supplementary_pension": 0.0153, "gsvg_min_base_monthly": 485.85, "gsvg_min_income_yearly": 5830.2, "neue_min_monthly": 141.79, "max_base_monthly": 6615.0}	{"home_office": 300.0, "child_deduction_monthly": 58.4, "single_parent_deduction": 494.0, "verkehrsabsetzbetrag": 400.0, "werbungskostenpauschale": 132.0, "familienbonus_under_18": 2000.16, "familienbonus_18_24": 650.16, "alleinverdiener_base": 494.0, "alleinverdiener_per_child": 220.0, "commuting_brackets": {"small": {"20": 58.0, "40": 113.0, "60": 168.0}, "large": {"2": 31.0, "20": 123.0, "40": 214.0, "60": 306.0}}, "pendler_euro_per_km": 2.0, "basic_exemption_rate": 0.15, "basic_exemption_max": 4950.0, "self_employed": {"grundfreibetrag_profit_limit": 33000.0, "grundfreibetrag_rate": 0.15, "grundfreibetrag_max": 4950.0, "max_total_freibetrag": 46400.0, "flat_rate_turnover_limit": 220000.0, "flat_rate_general": 0.12, "flat_rate_consulting": 0.06, "kleinunternehmer_threshold": 35000.0, "kleinunternehmer_tolerance": 38500.0, "ust_voranmeldung_monthly_threshold": 100000.0}, "zuschlag_verkehrsabsetzbetrag": 684.0, "zuschlag_income_lower": 15500.0, "zuschlag_income_upper": 24500.0, "pensionisten_absetzbetrag": 868.0, "pensionisten_income_lower": 17000.0, "pensionisten_income_upper": 25000.0, "erhoehter_pensionisten": 1278.0, "erhoehter_pensionisten_upper": 22500.0, "sonderausgabenpauschale": 60.0}	2026-03-15 00:03:52.970178	2026-03-15 00:03:52.970186
2	2023	[{"lower": 0, "upper": 11693, "rate": 0.0}, {"lower": 11693, "upper": 19134, "rate": 0.2}, {"lower": 19134, "upper": 32075, "rate": 0.3}, {"lower": 32075, "upper": 62080, "rate": 0.41}, {"lower": 62080, "upper": 93120, "rate": 0.48}, {"lower": 93120, "upper": 1000000, "rate": 0.5}, {"lower": 1000000, "upper": null, "rate": 0.55}]	11693.00	{"standard": 0.2, "residential": 0.1, "small_business_threshold": 35000.0, "tolerance_threshold": 38500.0}	{"pension": 0.185, "health": 0.068, "accident_fixed": 10.42, "supplementary_pension": 0.0153, "gsvg_min_base_monthly": 485.85, "gsvg_min_income_yearly": 5830.2, "neue_min_monthly": 141.79, "max_base_monthly": 6615.0}	{"home_office": 300.0, "child_deduction_monthly": 58.4, "single_parent_deduction": 520.0, "verkehrsabsetzbetrag": 421.0, "werbungskostenpauschale": 132.0, "familienbonus_under_18": 2000.16, "familienbonus_18_24": 650.16, "alleinverdiener_base": 520.0, "alleinverdiener_per_child": 232.0, "commuting_brackets": {"small": {"20": 58.0, "40": 113.0, "60": 168.0}, "large": {"2": 31.0, "20": 123.0, "40": 214.0, "60": 306.0}}, "pendler_euro_per_km": 2.0, "basic_exemption_rate": 0.15, "basic_exemption_max": 4950.0, "self_employed": {"grundfreibetrag_profit_limit": 33000.0, "grundfreibetrag_rate": 0.15, "grundfreibetrag_max": 4950.0, "max_total_freibetrag": 46400.0, "flat_rate_turnover_limit": 220000.0, "flat_rate_general": 0.12, "flat_rate_consulting": 0.06, "kleinunternehmer_threshold": 35000.0, "kleinunternehmer_tolerance": 38500.0, "ust_voranmeldung_monthly_threshold": 100000.0}, "zuschlag_verkehrsabsetzbetrag": 684.0, "zuschlag_income_lower": 16499.0, "zuschlag_income_upper": 26532.0, "pensionisten_absetzbetrag": 868.0, "pensionisten_income_lower": 18410.0, "pensionisten_income_upper": 27460.0, "erhoehter_pensionisten": 1278.0, "erhoehter_pensionisten_upper": 23580.0, "sonderausgabenpauschale": 60.0}	2026-03-15 00:03:52.970188	2026-03-15 00:03:52.97019
3	2024	[{"lower": 0, "upper": 12816, "rate": 0.0}, {"lower": 12816, "upper": 20818, "rate": 0.2}, {"lower": 20818, "upper": 34513, "rate": 0.3}, {"lower": 34513, "upper": 66612, "rate": 0.4}, {"lower": 66612, "upper": 99266, "rate": 0.48}, {"lower": 99266, "upper": 1000000, "rate": 0.5}, {"lower": 1000000, "upper": null, "rate": 0.55}]	12816.00	{"standard": 0.2, "residential": 0.1, "small_business_threshold": 35000.0, "tolerance_threshold": 38500.0}	{"pension": 0.185, "health": 0.068, "accident_fixed": 10.97, "supplementary_pension": 0.0153, "gsvg_min_base_monthly": 500.91, "gsvg_min_income_yearly": 6010.92, "neue_min_monthly": 146.18, "max_base_monthly": 6825.0}	{"home_office": 300.0, "child_deduction_monthly": 58.4, "single_parent_deduction": 572.0, "verkehrsabsetzbetrag": 463.0, "werbungskostenpauschale": 132.0, "familienbonus_under_18": 2000.16, "familienbonus_18_24": 700.08, "alleinverdiener_base": 572.0, "alleinverdiener_per_child": 256.0, "commuting_brackets": {"small": {"20": 58.0, "40": 113.0, "60": 168.0}, "large": {"2": 31.0, "20": 123.0, "40": 214.0, "60": 306.0}}, "pendler_euro_per_km": 2.0, "basic_exemption_rate": 0.15, "basic_exemption_max": 4950.0, "self_employed": {"grundfreibetrag_profit_limit": 33000.0, "grundfreibetrag_rate": 0.15, "grundfreibetrag_max": 4950.0, "max_total_freibetrag": 46400.0, "flat_rate_turnover_limit": 220000.0, "flat_rate_general": 0.12, "flat_rate_consulting": 0.06, "kleinunternehmer_threshold": 35000.0, "kleinunternehmer_tolerance": 38500.0, "ust_voranmeldung_monthly_threshold": 100000.0}, "zuschlag_verkehrsabsetzbetrag": 684.0, "zuschlag_income_lower": 16293.0, "zuschlag_income_upper": 27420.0, "pensionisten_absetzbetrag": 868.0, "pensionisten_income_lower": 19413.0, "pensionisten_income_upper": 28956.0, "erhoehter_pensionisten": 1278.0, "erhoehter_pensionisten_upper": 24480.0, "sonderausgabenpauschale": 60.0}	2026-03-15 00:03:52.970191	2026-03-15 00:03:52.970193
4	2025	[{"lower": 0, "upper": 13308, "rate": 0.0}, {"lower": 13308, "upper": 21617, "rate": 0.2}, {"lower": 21617, "upper": 35836, "rate": 0.3}, {"lower": 35836, "upper": 69166, "rate": 0.4}, {"lower": 69166, "upper": 103072, "rate": 0.48}, {"lower": 103072, "upper": 1000000, "rate": 0.5}, {"lower": 1000000, "upper": null, "rate": 0.55}]	13308.00	{"standard": 0.2, "residential": 0.1, "small_business_threshold": 55000.0, "tolerance_threshold": 60500.0}	{"pension": 0.185, "health": 0.068, "accident_fixed": 11.35, "supplementary_pension": 0.0153, "gsvg_min_base_monthly": 500.91, "gsvg_min_income_yearly": 6010.92, "neue_min_monthly": 146.18, "max_base_monthly": 7070.0}	{"home_office": 300.0, "child_deduction_monthly": 70.9, "single_parent_deduction": 601.0, "verkehrsabsetzbetrag": 487.0, "werbungskostenpauschale": 132.0, "familienbonus_under_18": 2000.16, "familienbonus_18_24": 700.08, "alleinverdiener_base": 601.0, "alleinverdiener_per_child": 268.0, "commuting_brackets": {"small": {"20": 58.0, "40": 113.0, "60": 168.0}, "large": {"2": 31.0, "20": 123.0, "40": 214.0, "60": 306.0}}, "pendler_euro_per_km": 6.0, "basic_exemption_rate": 0.15, "basic_exemption_max": 4950.0, "self_employed": {"grundfreibetrag_profit_limit": 33000.0, "grundfreibetrag_rate": 0.15, "grundfreibetrag_max": 4950.0, "max_total_freibetrag": 46400.0, "flat_rate_turnover_limit": 320000.0, "flat_rate_general": 0.135, "flat_rate_consulting": 0.06, "kleinunternehmer_threshold": 55000.0, "kleinunternehmer_tolerance": 60500.0, "ust_voranmeldung_monthly_threshold": 100000.0}, "zuschlag_verkehrsabsetzbetrag": 725.0, "zuschlag_income_lower": 16293.0, "zuschlag_income_upper": 27420.0, "pensionisten_absetzbetrag": 924.0, "pensionisten_income_lower": 19583.0, "pensionisten_income_upper": 29987.0, "erhoehter_pensionisten": 1361.0, "erhoehter_pensionisten_upper": 24953.0, "sonderausgabenpauschale": 60.0}	2026-03-15 00:03:52.970195	2026-03-15 00:03:52.970196
5	2026	[{"lower": 0, "upper": 13539, "rate": 0.0}, {"lower": 13539, "upper": 21992, "rate": 0.2}, {"lower": 21992, "upper": 36458, "rate": 0.3}, {"lower": 36458, "upper": 70365, "rate": 0.4}, {"lower": 70365, "upper": 104859, "rate": 0.48}, {"lower": 104859, "upper": 1000000, "rate": 0.5}, {"lower": 1000000, "upper": null, "rate": 0.55}]	13539.00	{"standard": 0.2, "residential": 0.1, "small_business_threshold": 55000.0, "tolerance_threshold": 60500.0}	{"pension": 0.185, "health": 0.068, "accident_fixed": 12.17, "supplementary_pension": 0.0153, "gsvg_min_base_monthly": 551.1, "gsvg_min_income_yearly": 6613.2, "neue_min_monthly": 160.81, "max_base_monthly": 7585.0}	{"home_office": 300.0, "child_deduction_monthly": 70.9, "single_parent_deduction": 612.0, "verkehrsabsetzbetrag": 496.0, "werbungskostenpauschale": 132.0, "familienbonus_under_18": 2000.16, "familienbonus_18_24": 700.08, "alleinverdiener_base": 612.0, "alleinverdiener_per_child": 273.0, "commuting_brackets": {"small": {"20": 58.0, "40": 113.0, "60": 168.0}, "large": {"2": 31.0, "20": 123.0, "40": 214.0, "60": 306.0}}, "pendler_euro_per_km": 6.0, "basic_exemption_rate": 0.15, "basic_exemption_max": 4950.0, "self_employed": {"grundfreibetrag_profit_limit": 33000.0, "grundfreibetrag_rate": 0.15, "grundfreibetrag_max": 4950.0, "max_total_freibetrag": 46400.0, "flat_rate_turnover_limit": 320000.0, "flat_rate_general": 0.135, "flat_rate_consulting": 0.06, "kleinunternehmer_threshold": 55000.0, "kleinunternehmer_tolerance": 60500.0, "ust_voranmeldung_monthly_threshold": 100000.0}, "zuschlag_verkehrsabsetzbetrag": 752.0, "zuschlag_income_lower": 16832.0, "zuschlag_income_upper": 28326.0, "pensionisten_absetzbetrag": 954.0, "pensionisten_income_lower": 20233.0, "pensionisten_income_upper": 30981.0, "erhoehter_pensionisten": 1405.0, "erhoehter_pensionisten_upper": 25774.0, "sonderausgabenpauschale": 60.0}	2026-03-15 00:03:52.970197	2026-03-15 00:03:52.970199
\.


--
-- Name: credit_cost_configs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.credit_cost_configs_id_seq', 6, true);


--
-- Name: credit_topup_packages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.credit_topup_packages_id_seq', 3, true);


--
-- Name: plans_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.plans_id_seq', 4, true);


--
-- Name: tax_configurations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tax_configurations_id_seq', 5, true);


--
-- PostgreSQL database dump complete
--

\unrestrict VUCjFFXsxrUWv45rqhoWoCqKITCR2HI2ctvI12lq5y1Bm3cykUagGXcFPCIl5zs

