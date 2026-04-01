#!/usr/bin/env python3
"""DELTA25 v7 Full Test — 44 PDFs, complete year data"""
import sys, os, json, time, glob, requests, psycopg2
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api/v1"
PDF_DIR = "C:/Users/yk1e25/AppData/Local/Temp/delta25_v9/DELTA25"
EMAIL = "delta25@test.taxja.at"
PASSWORD = "Test1234!@#$"
UID = 191

GOLDEN = {
    "revenue_netto": 180000, "afa": 20350, "ifb": 850,
    "material": 12000, "miete": 15600, "svs": 14901.36,
    "versicherung": 920, "ba_total": 64621.36,
    "gewinn": 115378.64, "vv": 35000, "gfb": 11109.22, "est": 19280.34,
}

def db():
    return psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')

def clean():
    conn = db()
    cur = conn.cursor()
    for sql in [
        "DELETE FROM transaction_line_items WHERE transaction_id IN (SELECT id FROM transactions WHERE user_id=%s)",
        "DELETE FROM transactions WHERE user_id=%s",
        "DELETE FROM recurring_transactions WHERE user_id=%s",
        "DELETE FROM asset_events WHERE user_id=%s",
    ]:
        cur.execute(sql, (UID,))
    cur.execute("DELETE FROM asset_policy_snapshots WHERE property_id IN (SELECT id FROM properties WHERE user_id=%s)", (UID,))
    cur.execute("DELETE FROM properties WHERE user_id=%s", (UID,))
    cur.execute("DELETE FROM documents WHERE user_id=%s", (UID,))
    cur.execute("UPDATE credit_balances SET plan_balance=99999,topup_balance=99999,updated_at=NOW() WHERE user_id=%s", (UID,))
    conn.commit(); conn.close()

def main():
    print("=" * 70)
    print("  DELTA25 v7 — 44 PDFs, complete year")
    print("=" * 70)

    clean()
    print("Cleaned")

    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Upload PDFs one at a time — wait for each to finish before next
    # This avoids Groq API rate limits and ensures stable AI classification
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"\nUploading {len(pdfs)} PDFs (sequential, wait for each)...")
    conn2 = db()
    cur2 = conn2.cursor()
    for i, pdf in enumerate(pdfs):
        fname = os.path.basename(pdf)
        with open(pdf, "rb") as f:
            r = requests.post(f"{BASE}/documents/upload",
                files={"file": (fname, f, "application/pdf")},
                data={"tax_year": "2025"}, headers=h)
        status = "OK" if r.status_code in (200, 201) else f"FAIL({r.status_code})"
        # Wait for this doc to be processed
        for _ in range(60):  # max 60s per doc
            time.sleep(2)
            cur2.execute("SELECT count(*) FROM documents WHERE user_id=%s AND processed_at IS NULL", (UID,))
            if cur2.fetchone()[0] == 0:
                break
        print(f"  [{i+1:2d}/{len(pdfs)}] {status} {fname}")
    conn2.close()
    print(f"  Done ({len(pdfs)} uploaded and processed)")

    # Check classification
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT d.file_name, d.ocr_result FROM documents d WHERE d.user_id=%s ORDER BY d.id", (UID,))
    docs = cur.fetchall()

    income_count = 0; income_total = 0
    expense_count = 0; asset_count = 0
    print(f"\n=== CLASSIFICATION ({len(docs)} docs) ===")
    for fn, ocr in docs:
        ai = (ocr or {}).get("_ai_first", {})
        tax = ai.get("tax_treatment", {}) or {}
        dir_ = tax.get("expense_or_income", "?")
        amounts = ai.get("amounts", {}) or {}
        total = amounts.get("total_amount") or amounts.get("annual_amount") or 0
        creates = ai.get("creates", [])

        if dir_ == "income":
            income_count += 1
            income_total += float(total) if total else 0
        elif "asset" in (creates if isinstance(creates, list) else []):
            asset_count += 1
        elif dir_ == "expense":
            expense_count += 1

    print(f"  Income: {income_count} docs, total={income_total:,.0f} (target 216,000 brutto / 180,000 netto)")
    print(f"  Expense: {expense_count} docs  |  Asset: {asset_count} docs")

    # Confirm pending asset suggestions (user action: click "Create Asset" button)
    # Only confirm actual asset documents (PKW, LKW, Kreissäge, Laptop, E-Auto) — NOT ARs
    h2 = {**h, "Content-Type": "application/json"}
    cur.execute("""SELECT d.id, d.file_name FROM documents d
        WHERE d.user_id=%s AND d.ocr_result->'import_suggestion'->>'status' = 'pending'
        AND d.ocr_result->'import_suggestion'->>'type' = 'create_asset'
        AND d.ocr_result->'_ai_first'->'_rule_engine'->>'direction' != 'income'""", (UID,))
    pending_assets = cur.fetchall()
    for doc_id, fn in pending_assets:
        r = requests.post(f"{BASE}/documents/{doc_id}/confirm-asset", headers=h2)
        if r.status_code == 200:
            print(f"  Confirmed asset: {fn}")
        else:
            print(f"  WARN: confirm-asset failed for {fn}: {r.status_code} {r.text[:100]}")
    if pending_assets:
        conn.commit()
        time.sleep(2)  # Let DB settle

    # Check assets
    cur.execute("SELECT id, sub_category, purchase_price, income_tax_depreciable_base, useful_life_years FROM properties WHERE user_id=%s ORDER BY purchase_price DESC", (UID,))
    assets = cur.fetchall()
    print(f"\n=== ASSETS ({len(assets)}) ===")
    for a in assets:
        print(f"  {str(a[1] or '?'):15s} price={a[2] or 0:>10} base={a[3] or 0:>10} life={a[4] or '?'}")

    # Set PKW business_use_percentage = 70% (user action: from Fahrtenbuch)
    # NOTE: Using direct DB update because PUT API has a bug (field not applied)
    h2 = {**h, "Content-Type": "application/json"}
    pkw_id = None
    for a in assets:
        asset_id, sub_cat = a[0], a[1]
        if sub_cat == "pkw":
            pkw_id = asset_id
            cur.execute("UPDATE properties SET business_use_percentage = 70 WHERE id = %s", (asset_id,))
            conn.commit()
            print(f"  Set PKW business_use=70% (direct DB)")

    # Delete old PKW AfA transaction so it gets regenerated with 70%
    if pkw_id:
        cur.execute("DELETE FROM transactions WHERE property_id=%s AND expense_category='DEPRECIATION_AFA'", (pkw_id,))
        conn.commit()
        print(f"  Deleted old PKW AfA (will regenerate with 70%)")
    conn.close()

    # Re-fetch after property update
    conn = db()
    cur = conn.cursor()

    # Check transactions summary
    cur.execute("""
        SELECT type::text, expense_category::text, sum(amount), count(*)
        FROM transactions WHERE user_id=%s AND extract(year from transaction_date)=2025
        GROUP BY type::text, expense_category::text ORDER BY sum(amount) DESC
    """, (UID,))
    print(f"\n=== TRANSACTION SUMMARY ===")
    total_inc = 0; total_exp = 0; total_afa = 0
    for typ, cat, amt, cnt in cur.fetchall():
        amt = float(amt)
        if typ == 'INCOME': total_inc += amt
        elif typ == 'EXPENSE': total_exp += amt
        if cat == 'DEPRECIATION_AFA': total_afa += amt
        print(f"  {typ:20s} {(cat or ''):25s} {amt:>12,.2f} ({cnt} txns)")
    print(f"  Total: Inc={total_inc:,.2f} Exp={total_exp:,.2f} AfA={total_afa:,.2f}")

    # Reports
    h2 = {**h, "Content-Type": "application/json"}
    print(f"\n=== REPORTS ===")

    e1a = requests.post(f"{BASE}/reports/tax-form-e1a", json={"tax_year": 2025}, headers=h2).json().get("summary", {})
    e1 = requests.post(f"{BASE}/reports/tax-form", json={"tax_year": 2025, "form_type": "E1"}, headers=h2).json().get("summary", {})
    ea = requests.post(f"{BASE}/reports/ea-report", json={"tax_year": 2025, "language": "de"}, headers=h2).json().get("summary", {})
    sl = requests.post(f"{BASE}/reports/saldenliste", json={"tax_year": 2025, "language": "de"}, headers=h2).json().get("summary", {})
    u1 = requests.post(f"{BASE}/reports/tax-form-u1", json={"tax_year": 2025}, headers=h2).json().get("summary", {})

    e1a_rev = e1a.get("business_income", 0)
    e1a_exp = e1a.get("total_expenses", 0)
    e1a_profit = e1a.get("profit", 0)

    print(f"  E1a: Rev={e1a_rev:>12,.2f} (target {GOLDEN['revenue_netto']:>12,.2f})")
    print(f"        Exp={e1a_exp:>12,.2f} (target {GOLDEN['ba_total']:>12,.2f})")
    print(f"        Profit={e1a_profit:>12,.2f} (target {GOLDEN['gewinn']:>12,.2f})")
    print(f"  E1:  Gesamtbetrag={e1.get('gesamtbetrag_einkuenfte',0):>12,.2f}")
    print(f"  EA:  Inc={ea.get('total_income',0):>12,.2f} Exp={ea.get('total_expenses',0):>12,.2f}")
    print(f"  SL:  Ertrag={sl.get('ertrag_current',0):>12,.2f} Aufwand={sl.get('aufwand_current',0):>12,.2f}")
    print(f"  U1:  Rev20={u1.get('revenue_20',0):>12,.2f} VAT={u1.get('total_vat',0):>12,.2f} VSt={u1.get('vorsteuer',0):>12,.2f}")

    # Consistency checks
    print(f"\n=== CONSISTENCY ===")
    tests = [
        ("E1a Rev-Exp=Profit", abs(e1a_rev - e1a_exp - e1a_profit) < 1),
        ("E1 uses E1a", abs(e1.get("gewerbebetrieb_gewinn", 0) - e1a_profit) < 1),
        ("EA=SL Income", abs(sl.get("ertrag_current", 0) - ea.get("total_income", 0)) < 1),
        ("EA=SL Expense", abs(sl.get("aufwand_current", 0) - ea.get("total_expenses", 0)) < 1),
        ("U1 VAT-VSt=Zahllast", abs(u1.get("zahllast", 0) - (u1.get("total_vat", 0) - u1.get("vorsteuer", 0))) < 1),
        ("ASSET not in EA", ea.get("total_expenses", 0) < 155000),
        ("AfA in E1a", e1a_exp > 15000),
    ]
    all_pass = True
    for name, ok in tests:
        if not ok: all_pass = False
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    # Accuracy vs golden
    print(f"\n=== ACCURACY vs GOLDEN ===")
    accuracy = [
        ("Revenue netto", e1a_rev, GOLDEN["revenue_netto"], 500),
        ("Total BA", e1a_exp, GOLDEN["ba_total"], 2000),
        ("Gewinn", e1a_profit, GOLDEN["gewinn"], 2000),
    ]
    for name, actual, expected, tol in accuracy:
        diff = abs(actual - expected)
        status = "CLOSE" if diff < tol else "DIFF"
        print(f"  [{status}] {name}: actual={actual:,.2f} expected={expected:,.2f} diff={diff:,.2f}")

    print(f"\n{'=' * 70}")
    print(f"  CONSISTENCY: {'ALL PASS' if all_pass else 'ISSUES'} ({sum(1 for _,ok in tests if ok)}/{len(tests)})")
    print(f"{'=' * 70}")

    conn.close()

if __name__ == "__main__":
    main()
