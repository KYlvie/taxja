#!/usr/bin/env python3
"""
2025 Test Suite Runner — Profile-by-Profile Testing

Usage:
    python run_2025_profile_test.py ALPHA25
    python run_2025_profile_test.py BETA25
    python run_2025_profile_test.py all
"""
import sys, os, json, time, requests, glob
from decimal import Decimal
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
TEST_SUITE_DIR = "/tmp/test_suite_2025"

GOLDEN = {
    "ALPHA25": {
        "e1a_gew": 14521.21, "e1b_res": -5804.56, "e1_ges": 8716.65,
        "e1_eink": 6478.47, "e1_est": 0.0, "u1_zahl": 1200.0,
        "svs_y": 13559.88, "vers": 1264.92, "gfb": 2178.18, "vv_afa": 3045.0
    },
    "BETA25": {
        "e1b_ein": 13890.0, "e1b_wk": 24946.54, "e1b_res": -11056.54,
        "afa": 3675.0, "hv_n": 510.0, "rep_n": 6900.0,
        "e1_ges": 44943.46, "e1_eink": 44113.46, "e1_est": 9238.48,
        "e1_nachz": -2588.76
    },
    "GAMMA25": {
        "ein": 52000.0, "ba": 8389.04, "gew": 43610.96,
        "est": 7033.48, "svs_q": 479.79
    },
    "DELTA25": {
        "afa": 20350.0, "ifb": 850.0, "gew": 115378.64,
        "vv_v": 35000.0, "gfb": 11109.22, "est": 19280.34,
        "eauto_vst": 6666.67, "lkw_vst": 8333.33
    },
    "EPSILON25": {
        "gew": 2794.24, "eink": 52315.1, "nachz": 4832.14,
        "az_unc": 1588.24, "ho": 255.0
    },
    "ZETA25": {
        "gew": 783.0, "o1_res": -347.89, "o2_res": 1159.88,
        "vv": 811.99, "ges": 66594.99, "verrech": 17000.0,
        "eink": 49417.54, "nachz": -4177.2, "o1_afa": 2625.0, "o2_afa": 3465.0
    },
    "ETA25": {
        "vv_res": 464.33, "ges": 29864.33, "eink": 29454.33,
        "nachz": 2522.36, "afa": 1890.0, "pab": 160.64
    },
    "THETA25": {
        "brutto": 66000.0, "lst": 9150.0, "eink": 65240.0,
        "est": 17689.1, "nachz": 8052.1, "kest_total": 1159.18
    },
}

# Profile configurations
PROFILES = {
    "ALPHA25": {
        "name": "DI Maria Steiner",
        "email": "alpha25@test.taxja.at",
        "user_type": "self_employed",
        "business_type": "consulting",
        "vat_status": "regelbesteuert",
        "tax_number": "99-111/2222",
        "vat_number": "ATU12345678",
        "properties": [{
            "name": "Praterstrasse 40/12",
            "address": "Praterstrasse 40/12, 1020 Wien",
            "purchase_price": 290000,
            "building_percentage": 70,
            "depreciation_rate": 1.5,
            "purchase_date": "2018-06-01",
            "rental_percentage": 100,
        }],
    },
    "BETA25": {
        "name": "Ing. Klaus Bauer",
        "email": "beta25@test.taxja.at",
        "user_type": "employee",
        "vat_status": "not_applicable",
        "tax_number": "99-222/3333",
        "properties": [{
            "name": "Argentinierstr. 21/12",
            "address": "Argentinierstrasse 21/12, 1040 Wien",
            "purchase_price": 350000,
            "building_percentage": 70,
            "depreciation_rate": 1.5,
            "purchase_date": "2019-03-15",
            "rental_percentage": 100,
        }],
    },
    "GAMMA25": {
        "name": "Lisa Wimmer",
        "email": "gamma25@test.taxja.at",
        "user_type": "self_employed",
        "business_type": "consulting",
        "vat_status": "kleinunternehmer",
        "tax_number": "99-333/4444",
        "properties": [],
    },
    "DELTA25": {
        "name": "Markus Hofer",
        "email": "delta25@test.taxja.at",
        "user_type": "self_employed",
        "business_type": "trade",
        "vat_status": "regelbesteuert",
        "tax_number": "99-444/5555",
        "vat_number": "ATU55667788",
        "properties": [],
    },
    "EPSILON25": {
        "name": "Dr. Anna Kovacs",
        "email": "epsilon25@test.taxja.at",
        "user_type": "mixed",  # employee + self-employed
        "business_type": "consulting",
        "vat_status": "kleinunternehmer",
        "tax_number": "99-555/6666",
        "properties": [],
    },
    "ZETA25": {
        "name": "Mag. Thomas Gruber",
        "email": "zeta25@test.taxja.at",
        "user_type": "mixed",
        "business_type": "consulting",
        "vat_status": "regelbesteuert",
        "tax_number": "99-666/7777",
        "vat_number": "ATU66778899",
        "properties": [
            {
                "name": "Schönbrunner Str. 120/5",
                "address": "Schönbrunner Strasse 120/5, 1050 Wien",
                "purchase_price": 250000,
                "building_percentage": 70,
                "depreciation_rate": 1.5,
                "purchase_date": "2017-09-01",
                "rental_percentage": 100,
            },
            {
                "name": "Mariahilfer Str. 88/22",
                "address": "Mariahilfer Strasse 88/22, 1070 Wien",
                "purchase_price": 330000,
                "building_percentage": 70,
                "depreciation_rate": 1.5,
                "purchase_date": "2020-01-15",
                "rental_percentage": 100,
            },
        ],
    },
    "ETA25": {
        "name": "Mag. Helga Schwarz",
        "email": "eta25@test.taxja.at",
        "user_type": "employee",  # pensioner = employee type
        "vat_status": "not_applicable",
        "tax_number": "99-777/8888",
        "properties": [{
            "name": "Annagasse 8/4",
            "address": "Annagasse 8/4, 1010 Wien",
            "purchase_price": 180000,
            "building_percentage": 70,
            "depreciation_rate": 1.5,
            "purchase_date": "2015-04-01",
            "rental_percentage": 100,
        }],
    },
    "THETA25": {
        "name": "Mag. Stefan Eder",
        "email": "theta25@test.taxja.at",
        "user_type": "employee",
        "vat_status": "not_applicable",
        "tax_number": "99-888/9999",
        "properties": [],
    },
}


class ProfileTester:
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.profile_dir = Path(TEST_SUITE_DIR) / profile_name
        self.config = PROFILES[profile_name]
        self.golden = GOLDEN[profile_name]
        self.token = None
        self.user_id = None
        self.property_ids = {}
        self.errors = []
        self.warnings = []

    def run(self):
        print(f"\n{'='*60}")
        print(f"  TESTING PROFILE: {self.profile_name} — {self.config['name']}")
        print(f"{'='*60}")

        self._create_user()
        self._create_properties()
        self._upload_documents()
        self._wait_for_processing()
        self._check_transactions()
        self._generate_and_check_reports()
        self._print_results()

    def _api(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        resp = getattr(requests, method)(
            f"{BASE_URL}{path}", headers=headers, **kwargs
        )
        return resp

    def _create_user(self):
        print("\n[1] Creating user...")
        email = self.config["email"]
        password = "Test1234!@#$"

        # Try to register
        resp = self._api("post", "/auth/register", json={
            "name": self.config["name"],
            "email": email,
            "password": password,
        })
        if resp.status_code == 201:
            data = resp.json()
            self.token = data.get("access_token")
            self.user_id = data.get("user", {}).get("id")
            print(f"  Created user: {email} (id={self.user_id})")
        elif resp.status_code in (400, 409):
            # User exists, login
            resp = self._api("post", "/auth/login", json={
                "email": email, "password": password,
            })
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                print(f"  Logged in: {email} (id={self.user_id})")
            else:
                print(f"  ERROR: Login failed: {resp.status_code} {resp.text[:200]}")
                return
        else:
            print(f"  ERROR: Register failed: {resp.status_code} {resp.text[:200]}")
            return

        # Update user profile
        profile_update = {}
        for key in ["user_type", "business_type", "vat_status", "tax_number", "vat_number"]:
            if key in self.config:
                profile_update[key] = self.config[key]
        if profile_update:
            resp = self._api("patch", "/users/me", json=profile_update)
            if resp.status_code == 200:
                print(f"  Updated profile: {list(profile_update.keys())}")
            else:
                print(f"  WARN: Profile update: {resp.status_code} {resp.text[:200]}")

    def _create_properties(self):
        if not self.config.get("properties"):
            return
        print(f"\n[2] Creating {len(self.config['properties'])} properties...")
        for prop in self.config["properties"]:
            resp = self._api("post", "/properties", json={
                "name": prop["name"],
                "address": prop["address"],
                "purchase_price": prop["purchase_price"],
                "building_percentage": prop["building_percentage"],
                "depreciation_rate": prop["depreciation_rate"],
                "purchase_date": prop["purchase_date"],
                "rental_percentage": prop.get("rental_percentage", 100),
                "status": "active",
            })
            if resp.status_code in (200, 201):
                pid = resp.json().get("id")
                self.property_ids[prop["name"]] = pid
                print(f"  Created property: {prop['name']} (id={pid})")
            elif resp.status_code == 409:
                # Already exists, try to find it
                resp2 = self._api("get", "/properties")
                if resp2.status_code == 200:
                    for p in resp2.json():
                        if prop["name"] in (p.get("name", ""), p.get("address", "")):
                            self.property_ids[prop["name"]] = p["id"]
                            print(f"  Found existing: {prop['name']} (id={p['id']})")
                            break
            else:
                print(f"  WARN: Property creation: {resp.status_code} {resp.text[:200]}")

    def _upload_documents(self):
        pdf_files = sorted(self.profile_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"\n[3] No PDF files found in {self.profile_dir}")
            return
        print(f"\n[3] Uploading {len(pdf_files)} documents...")

        for pdf in pdf_files:
            if pdf.name.startswith("expected"):
                continue
            with open(pdf, "rb") as f:
                resp = self._api("post", "/documents/upload",
                    files={"file": (pdf.name, f, "application/pdf")},
                    data={"tax_year": "2025"},
                )
            if resp.status_code in (200, 201):
                doc_id = resp.json().get("id", resp.json().get("document_id"))
                print(f"  ✓ {pdf.name} → doc_id={doc_id}")
            else:
                print(f"  ✗ {pdf.name}: {resp.status_code} {resp.text[:100]}")
                self.errors.append(f"Upload failed: {pdf.name}")

    def _wait_for_processing(self):
        print("\n[4] Waiting for document processing...")
        for _ in range(60):
            resp = self._api("get", "/documents?tax_year=2025&limit=100")
            if resp.status_code != 200:
                time.sleep(2)
                continue
            docs = resp.json() if isinstance(resp.json(), list) else resp.json().get("documents", resp.json().get("items", []))
            total = len(docs)
            processed = sum(1 for d in docs if d.get("processing_status") in ("completed", "processed", "done", "reviewed"))
            pending = sum(1 for d in docs if d.get("processing_status") in ("pending", "processing", "queued"))
            if pending == 0 and total > 0:
                print(f"  All {total} documents processed ({processed} completed)")
                return
            print(f"  {processed}/{total} processed, {pending} pending...")
            time.sleep(3)
        print("  WARN: Timeout waiting for processing")

    def _check_transactions(self):
        print("\n[5] Checking transactions...")
        resp = self._api("get", "/transactions?tax_year=2025&limit=200")
        if resp.status_code != 200:
            print(f"  ERROR: {resp.status_code}")
            return
        data = resp.json()
        txns = data if isinstance(data, list) else data.get("transactions", data.get("items", []))

        income_total = sum(float(t.get("amount", 0)) for t in txns if t.get("type") == "income")
        expense_total = sum(float(t.get("amount", 0)) for t in txns if t.get("type") == "expense")

        print(f"  Total transactions: {len(txns)}")
        print(f"  Income total: EUR {income_total:,.2f}")
        print(f"  Expense total: EUR {expense_total:,.2f}")

        # Show per-category breakdown
        by_cat = {}
        for t in txns:
            cat = t.get("expense_category") or t.get("income_category") or "unknown"
            by_cat[cat] = by_cat.get(cat, 0) + float(t.get("amount", 0))
        for cat, amt in sorted(by_cat.items(), key=lambda x: -abs(x[1])):
            print(f"    {cat}: EUR {amt:,.2f}")

    def _generate_and_check_reports(self):
        print("\n[6] Generating reports...")

        # E1a (self-employed)
        if self.config.get("user_type") in ("self_employed", "mixed"):
            self._check_e1a()

        # E1b (rental)
        if self.config.get("properties"):
            self._check_e1b()

        # E1 (main tax return)
        self._check_e1()

        # EA (Einnahmen-Ausgaben-Rechnung)
        self._check_ea()

        # Bilanz
        self._check_bilanz()

        # Saldenliste
        self._check_saldenliste()

        # U1 (VAT return)
        if self.config.get("vat_status") == "regelbesteuert":
            self._check_u1()

    def _check_e1a(self):
        resp = self._api("post", "/reports/e1a", json={"tax_year": 2025})
        if resp.status_code != 200:
            self.errors.append(f"E1a generation failed: {resp.status_code}")
            return
        data = resp.json()
        summary = data.get("summary", {})
        print(f"\n  === E1a (Self-Employment) ===")
        print(f"  Revenue: EUR {summary.get('business_income', 0):,.2f}")
        print(f"  Expenses: EUR {summary.get('total_expenses', 0):,.2f}")
        print(f"  Profit: EUR {summary.get('profit', 0):,.2f}")
        gfb = summary.get("gewinnfreibetrag", {})
        if isinstance(gfb, dict):
            print(f"  GFB: EUR {gfb.get('total', 0):,.2f}")

        if "e1a_gew" in self.golden:
            expected = self.golden["e1a_gew"]
            actual = summary.get("profit", 0)
            self._compare("E1a Gewinn", actual, expected)

    def _check_e1b(self):
        resp = self._api("post", "/reports/e1b", json={"tax_year": 2025})
        if resp.status_code != 200:
            self.errors.append(f"E1b generation failed: {resp.status_code}")
            return
        data = resp.json()
        props = data.get("properties", [])
        agg = data.get("aggregate_summary", {})
        print(f"\n  === E1b (Rental Income) — {len(props)} properties ===")
        for p in props:
            s = p.get("summary", {})
            print(f"  {p.get('property_name', '?')}:")
            print(f"    Income: EUR {s.get('rental_income', 0):,.2f}")
            print(f"    Expenses: EUR {s.get('total_expenses', 0):,.2f}")
            print(f"    AfA: EUR {s.get('afa_building', 0):,.2f}")
            print(f"    Interest: EUR {s.get('loan_interest', 0):,.2f}")
            print(f"    Surplus: EUR {s.get('surplus', 0):,.2f}")

        total_surplus = agg.get("total_surplus", 0)
        if "e1b_res" in self.golden:
            self._compare("E1b Result", total_surplus, self.golden["e1b_res"])

    def _check_e1(self):
        resp = self._api("post", "/reports/tax-form", json={"tax_year": 2025, "form_type": "E1"})
        if resp.status_code != 200:
            print(f"  E1 generation failed: {resp.status_code} {resp.text[:200]}")
            self.errors.append(f"E1 generation failed: {resp.status_code}")
            return
        data = resp.json()
        summary = data.get("summary", {})
        print(f"\n  === E1 (Income Tax Return) ===")
        for key in ["employment_income", "self_employment_income", "business_income",
                     "rental_income", "total_income", "gesamtbetrag_einkuenfte",
                     "total_deductible", "gewerbebetrieb_gewinn", "vermietung_einkuenfte",
                     "familienbonus", "alleinerzieher"]:
            val = summary.get(key, 0)
            if val != 0:
                print(f"  {key}: EUR {val:,.2f}")

        if "e1_ges" in self.golden:
            self._compare("E1 Gesamtbetrag", summary.get("gesamtbetrag_einkuenfte", 0), self.golden["e1_ges"])

    def _check_ea(self):
        resp = self._api("post", "/reports/ea", json={"tax_year": 2025, "language": "de"})
        if resp.status_code != 200:
            print(f"  EA failed: {resp.status_code}")
            return
        data = resp.json()
        summary = data.get("summary", {})
        print(f"\n  === EA (Einnahmen-Ausgaben) ===")
        print(f"  Total Income: EUR {summary.get('total_income', 0):,.2f}")
        print(f"  Total Expenses: EUR {summary.get('total_expenses', 0):,.2f}")
        print(f"  Result: EUR {summary.get('result', summary.get('gewinn_verlust', 0)):,.2f}")

    def _check_bilanz(self):
        resp = self._api("post", "/reports/bilanz", json={"tax_year": 2025, "language": "de"})
        if resp.status_code != 200:
            print(f"  Bilanz failed: {resp.status_code}")
            return
        print(f"\n  === Bilanz (Balance Sheet) ===")
        data = resp.json()
        summary = data.get("summary", {})
        print(f"  Aktiva: EUR {summary.get('aktiva_current', 0):,.2f}")
        print(f"  Passiva: EUR {summary.get('passiva_current', 0):,.2f}")
        print(f"  G/V: EUR {summary.get('gewinn_verlust_current', 0):,.2f}")

    def _check_saldenliste(self):
        resp = self._api("post", "/reports/saldenliste", json={"tax_year": 2025, "language": "de"})
        if resp.status_code != 200:
            print(f"  Saldenliste failed: {resp.status_code}")
            return
        data = resp.json()
        summary = data.get("summary", {})
        print(f"\n  === Saldenliste ===")
        print(f"  Ertrag: EUR {summary.get('ertrag_current', 0):,.2f}")
        print(f"  Aufwand: EUR {summary.get('aufwand_current', 0):,.2f}")
        print(f"  G/V: EUR {summary.get('gewinn_verlust_current', 0):,.2f}")

    def _check_u1(self):
        resp = self._api("post", "/reports/uva-annual", json={"tax_year": 2025})
        if resp.status_code != 200:
            print(f"  U1 failed: {resp.status_code}")
            return
        data = resp.json()
        summary = data.get("summary", {})
        print(f"\n  === U1 (Annual VAT) ===")
        print(f"  Revenue 20%: EUR {summary.get('revenue_20', 0):,.2f}")
        print(f"  Total VAT: EUR {summary.get('total_vat', 0):,.2f}")
        print(f"  Vorsteuer: EUR {summary.get('vorsteuer', 0):,.2f}")
        print(f"  Zahllast: EUR {summary.get('zahllast', 0):,.2f}")

        if "u1_zahl" in self.golden:
            self._compare("U1 Zahllast", summary.get("zahllast", 0), self.golden["u1_zahl"])

    def _compare(self, label, actual, expected, tolerance=50.0):
        diff = abs(float(actual) - float(expected))
        status = "✓" if diff <= tolerance else "✗"
        if diff > tolerance:
            self.errors.append(f"{label}: expected {expected:,.2f}, got {float(actual):,.2f} (diff={diff:,.2f})")
        elif diff > 1.0:
            self.warnings.append(f"{label}: minor diff {diff:,.2f}")
        print(f"  {status} {label}: actual={float(actual):,.2f}, expected={expected:,.2f} (diff={diff:,.2f})")

    def _print_results(self):
        print(f"\n{'='*60}")
        print(f"  RESULTS: {self.profile_name}")
        print(f"{'='*60}")
        if self.errors:
            print(f"\n  ERRORS ({len(self.errors)}):")
            for e in self.errors:
                print(f"    ✗ {e}")
        if self.warnings:
            print(f"\n  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"    ⚠ {w}")
        if not self.errors and not self.warnings:
            print(f"\n  ✓ ALL CHECKS PASSED!")
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_2025_profile_test.py <PROFILE|all>")
        print(f"Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)

    target = sys.argv[1].upper()

    if target == "ALL":
        for name in PROFILES:
            tester = ProfileTester(name)
            tester.run()
    elif target in PROFILES:
        tester = ProfileTester(target)
        tester.run()
    else:
        print(f"Unknown profile: {target}")
        print(f"Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
