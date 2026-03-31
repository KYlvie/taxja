#!/usr/bin/env python3
"""DELTA25 Test Runner — Markus Hofer (Asset-Heavy Gewerbetreibender / Tischlerei)

Golden Baseline:
  Revenue:  180,000 netto
  AfA:      20,350
  IFB:         850
  SUMME BA:  64,621.36
  Gewinn:  115,378.64
  VV:       35,000
  GFB:      11,109.22
  ESt:      19,280.34
  U1 Zahllast: ~6,000
"""
import os, sys, time, json, requests, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

BASE = "http://localhost:8000/api/v1"
PDF_DIR = r"C:\Users\yk1e25\Downloads\2025_test_suite (9)\DELTA25"

EMAIL = "markus.hofer.delta25@test.com"
PASSWORD = "TestPass123!"
NAME = "Markus Hofer"
TAX_YEAR = 2025

GOLDEN = {
    "revenue": 180_000.00,
    "afa": 20_350.00,
    "ifb": 850.00,
    "summe_ba": 64_621.36,
    "gewinn": 115_378.64,
    "vv": 35_000.00,
    "gfb": 11_109.22,
    "est": 19_280.34,
    "eauto_vst": 6_666.67,
    "lkw_vst": 8_333.33,
}


def main():
    s = requests.Session()

    # 1. Register user
    print("=" * 60)
    print("DELTA25 — Markus Hofer (Tischlerei)")
    print("=" * 60)

    # Try login first (user may already exist)
    token = try_login(s)
    if not token:
        token = register_and_verify(s)

    s.headers["Authorization"] = f"Bearer {token}"

    # 2. Update profile
    print("\n[2] Updating profile...")
    r = s.put(f"{BASE}/users/profile", json={
        "business_type": "gewerbetreibende",
        "business_name": "Tischlerei Hofer",
        "business_industry": "handwerk",
        "vat_status": "regelbesteuert",
        "gewinnermittlungsart": "ea_rechnung",
        "tax_number": "99-234/5678",
        "vat_number": "ATU55667788",
        "address": "Gewerbestrasse 15, 4020 Linz",
        "language": "de",
    })
    if r.ok:
        print(f"  Profile updated: {r.json().get('business_type', '?')}, {r.json().get('vat_status', '?')}")
    else:
        print(f"  Profile update: {r.status_code} {r.text[:200]}")

    # 3. Clean slate via direct DB (more reliable than API)
    print("\n[3] Cleaning existing data via DB...")
    try:
        from app.db.session import SessionLocal
        from app.models.document import Document
        from app.models.transaction import Transaction
        from app.models.property import Property
        from app.models.user import User
        db = SessionLocal()
        user = db.query(User).filter(User.email == EMAIL).first()
        if user:
            uid = user.id
            # Delete transactions first (FK to properties)
            tc = db.query(Transaction).filter(Transaction.user_id == uid).delete()
            # Delete properties
            pc = db.query(Property).filter(Property.user_id == uid).delete()
            # Delete documents
            dc = db.query(Document).filter(Document.user_id == uid).delete()
            db.commit()
            print(f"  Deleted {dc} docs, {tc} transactions, {pc} properties")
        db.close()
    except Exception as e:
        print(f"  DB cleanup failed: {e}")

    # 4. Upload all PDFs
    print("\n[4] Uploading documents...")
    pdf_files = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
    print(f"  Found {len(pdf_files)} PDFs")

    doc_ids = []
    for i, pdf_path in enumerate(pdf_files):
        fname = os.path.basename(pdf_path)
        with open(pdf_path, "rb") as f:
            try:
                r = s.post(f"{BASE}/documents/upload", files={"file": (fname, f, "application/pdf")}, timeout=30)
            except Exception as e:
                print(f"  ✗ {fname} → connection error: {e}")
                time.sleep(5)
                continue
        if r.ok:
            data = r.json()
            did = data.get("document_id") or data.get("id")
            doc_ids.append(did)
            print(f"  ✓ {fname} → doc_id={did}")
        else:
            print(f"  ✗ {fname} → {r.status_code}: {r.text[:100]}")
        # Small delay between uploads to avoid server overload
        if i < len(pdf_files) - 1:
            time.sleep(2)

    # 5. Wait for processing
    print(f"\n[5] Waiting for OCR processing ({len(doc_ids)} docs)...")
    wait_for_processing(s, doc_ids, timeout=300)

    # 6. Check documents
    print("\n[6] Document status:")
    r = s.get(f"{BASE}/documents/", params={"limit": 100})
    if r.ok:
        docs = r.json() if isinstance(r.json(), list) else r.json().get("documents", r.json().get("items", []))
        for doc in docs:
            dtype = doc.get("document_type", "?")
            status = doc.get("processing_status", doc.get("ocr_status", "?"))
            fname = doc.get("file_name", doc.get("original_filename", "?"))
            conf = doc.get("confidence_score", "?")
            print(f"  {fname}: type={dtype}, status={status}, conf={conf}")

    # 7. Check transactions
    print("\n[7] Transactions created:")
    r = s.get(f"{BASE}/transactions/", params={"limit": 500, "year": TAX_YEAR})
    txns = []
    if r.ok:
        txns = r.json() if isinstance(r.json(), list) else r.json().get("transactions", r.json().get("items", []))
        total_income = 0
        total_expense = 0
        for t in txns:
            ttype = t.get("transaction_type", "?")
            amt = float(t.get("amount", 0))
            cat = t.get("expense_category", "?")
            desc = t.get("description", "")[:40]
            ded = t.get("is_deductible", "?")
            if ttype == "INCOME":
                total_income += amt
            else:
                total_expense += amt
            print(f"  {str(ttype):8s} {amt:>12,.2f}  {str(cat):<30s} ded={ded}  {desc}")
        print(f"\n  TOTALS: income={total_income:,.2f}  expense={total_expense:,.2f}  count={len(txns)}")

    # 8. Check properties/assets
    print("\n[8] Properties/Assets:")
    r = s.get(f"{BASE}/properties/")
    if r.ok:
        props = r.json() if isinstance(r.json(), list) else r.json().get("properties", r.json().get("items", []))
        for p in props:
            pname = p.get("name", "?")
            ptype = p.get("property_type", "?")
            sub = p.get("sub_category", "?")
            base = p.get("depreciable_base") or p.get("purchase_price", "?")
            nd = p.get("useful_life_years", "?")
            biz = p.get("business_use_percentage", "?")
            print(f"  {pname}: type={ptype}, sub={sub}, base={base}, ND={nd}, biz%={biz}")

    # 9. Generate reports
    print("\n" + "=" * 60)
    print("REPORT GENERATION")
    print("=" * 60)

    # E1a
    print("\n[9a] E1a Report:")
    r = s.post(f"{BASE}/reports/tax-form-e1a", json={"tax_year": TAX_YEAR, "language": "de"})
    e1a = {}
    if r.ok:
        e1a = r.json()
        print_report(e1a, "E1a")
    else:
        print(f"  E1a failed: {r.status_code} {r.text[:200]}")

    # E1
    print("\n[9b] E1 Report:")
    r = s.post(f"{BASE}/reports/tax-form", json={"tax_year": TAX_YEAR, "language": "de"})
    e1 = {}
    if r.ok:
        e1 = r.json()
        print_report(e1, "E1")
    else:
        print(f"  E1 failed: {r.status_code} {r.text[:200]}")

    # U1
    print("\n[9c] U1 Report:")
    r = s.post(f"{BASE}/reports/tax-form-u1", json={"tax_year": TAX_YEAR, "language": "de"})
    u1 = {}
    if r.ok:
        u1 = r.json()
        print_report(u1, "U1")
    else:
        print(f"  U1 failed: {r.status_code} {r.text[:200]}")

    # EA
    print("\n[9d] EA Report:")
    r = s.post(f"{BASE}/reports/ea-report", json={"tax_year": TAX_YEAR, "language": "de"})
    ea = {}
    if r.ok:
        ea = r.json()
        print_report(ea, "EA")
    else:
        print(f"  EA failed: {r.status_code} {r.text[:200]}")

    # Saldenliste
    print("\n[9e] Saldenliste:")
    r = s.post(f"{BASE}/reports/saldenliste", json={"tax_year": TAX_YEAR, "language": "de"})
    if r.ok:
        sl = r.json()
        print_report(sl, "SL")
    else:
        print(f"  SL failed: {r.status_code} {r.text[:200]}")

    # 10. Golden comparison
    print("\n" + "=" * 60)
    print("GOLDEN BASELINE COMPARISON")
    print("=" * 60)
    compare_golden(e1a, e1, u1, ea)


def try_login(s):
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.ok:
        token = r.json().get("access_token")
        print(f"[1] Logged in as existing user")
        return token
    return None


def register_and_verify(s):
    print("[1] Registering new user...")
    r = s.post(f"{BASE}/auth/register", json={
        "email": EMAIL,
        "password": PASSWORD,
        "name": NAME,
        "user_type": "SELF_EMPLOYED",
        "business_type": "gewerbetreibende",
        "business_name": "Tischlerei Hofer",
        "business_industry": "handwerk",
        "vat_status": "regelbesteuert",
        "gewinnermittlungsart": "ea_rechnung",
        "tax_number": "99-234/5678",
        "vat_number": "ATU55667788",
        "address": "Gewerbestrasse 15, 4020 Linz",
        "language": "de",
    })
    if r.status_code == 201:
        print(f"  Registered: {EMAIL}")
    elif r.status_code == 409:
        print(f"  User exists, logging in...")
        return try_login(s)
    else:
        print(f"  Register failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)

    # Bypass email verification + set Pro plan via direct DB access
    print("  Verifying email + setting Pro plan via DB...")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from app.db.session import SessionLocal
        from app.models.user import User
        from app.models.subscription import Subscription
        from datetime import datetime as dt, timedelta, timezone
        db = SessionLocal()
        user = db.query(User).filter(User.email == EMAIL).first()
        if user:
            user.email_verified = True
            # Give unlimited credits
            from app.models.credit_balance import CreditBalance
            cb = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
            if cb:
                cb.plan_balance = 99999
                cb.topup_balance = 99999
            else:
                db.add(CreditBalance(user_id=user.id, plan_balance=99999, topup_balance=99999))
            # Set Pro subscription
            sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
            if not sub:
                sub = Subscription(
                    user_id=user.id,
                    plan_id=4,  # Pro plan
                    status="active",
                    current_period_start=dt.now(timezone.utc),
                    current_period_end=dt.now(timezone.utc) + timedelta(days=365),
                )
                db.add(sub)
            else:
                sub.plan_id = 4
                sub.status = "active"
                sub.current_period_end = dt.now(timezone.utc) + timedelta(days=365)
            db.commit()
            print(f"  Email verified, Pro plan active, credits=99999")
        db.close()
    except Exception as e:
        print(f"  DB setup failed: {e}")

    # Login
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.ok:
        return r.json()["access_token"]
    print(f"  Login failed: {r.status_code} {r.text[:200]}")
    sys.exit(1)


def wait_for_processing(s, doc_ids, timeout=300):
    start = time.time()
    retries = 0
    while time.time() - start < timeout:
        all_done = True
        pending = 0
        for did in doc_ids:
            try:
                r = s.get(f"{BASE}/documents/{did}", timeout=10)
                if r.ok:
                    status = r.json().get("processing_status", r.json().get("ocr_status", ""))
                    if status in ("pending_ocr", "processing", "queued", "pending"):
                        all_done = False
                        pending += 1
                else:
                    all_done = False
                    pending += 1
            except Exception:
                all_done = False
                pending += 1
                retries += 1
                if retries > 5:
                    print(f"  Server appears down, waiting 15s...")
                    time.sleep(15)
                    retries = 0
        if all_done:
            print(f"  All {len(doc_ids)} docs processed in {time.time()-start:.0f}s")
            return
        print(f"  {pending}/{len(doc_ids)} still processing... ({time.time()-start:.0f}s)")
        time.sleep(8)
    print(f"  TIMEOUT after {timeout}s!")


def print_report(data, label):
    """Print key fields from a report response."""
    if not data:
        print(f"  {label}: No data")
        return

    # Try to extract summary
    summary = data.get("summary", data.get("data", data))
    if isinstance(summary, dict):
        for k, v in summary.items():
            if isinstance(v, (int, float)):
                print(f"  {k}: {v:,.2f}")
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, (int, float)):
                        print(f"  {k}.{k2}: {v2:,.2f}")
            elif isinstance(v, str) and v:
                print(f"  {k}: {v}")

    # Also print fields if present
    fields = data.get("fields", [])
    if fields and isinstance(fields, list):
        for f in fields[:30]:
            fn = f.get("field_name", f.get("code", ""))
            lbl = f.get("label", "")
            val = f.get("value", "")
            if val and val != 0:
                print(f"  {fn}: {lbl} = {val}")


def compare_golden(e1a, e1, u1, ea):
    """Compare report values against golden baseline."""
    results = []

    def check(name, actual, expected, tolerance=0.01):
        if actual is None:
            results.append((name, "MISSING", expected, None))
            print(f"  ✗ {name}: MISSING (expected {expected:,.2f})")
            return
        diff = abs(actual - expected)
        pct = (diff / expected * 100) if expected else 0
        ok = diff <= max(tolerance * expected, 1.0)
        sym = "✓" if ok else "✗"
        results.append((name, actual, expected, pct))
        print(f"  {sym} {name}: {actual:,.2f} vs {expected:,.2f} (diff={diff:,.2f}, {pct:.1f}%)")

    # Extract values from reports
    e1a_s = (e1a or {}).get("summary", e1a or {})
    e1_s = (e1 or {}).get("summary", e1 or {})

    # Revenue
    rev = extract_value(e1a, ["total_income", "revenue", "erloese_20"])
    check("Revenue", rev, GOLDEN["revenue"])

    # AfA
    afa = extract_value(e1a, ["afa", "afa_gesamt", "depreciation"])
    check("AfA", afa, GOLDEN["afa"])

    # IFB
    ifb = extract_value(e1a, ["ifb", "investitionsfreibetrag"])
    check("IFB", ifb, GOLDEN["ifb"])

    # SUMME BA
    ba = extract_value(e1a, ["total_expenses", "summe_ba", "betriebsausgaben"])
    check("SUMME BA", ba, GOLDEN["summe_ba"])

    # Gewinn
    gew = extract_value(e1a, ["gewinn", "net_income", "gewinn_verlust"])
    check("Gewinn", gew, GOLDEN["gewinn"])

    passed = sum(1 for _, a, e, _ in results if a is not None and a != "MISSING" and abs(a - e) <= max(0.01 * e, 1.0))
    total = len(results)
    print(f"\n  RESULT: {passed}/{total} checks passed")


def extract_value(report, keys):
    """Try to extract a numeric value from report using multiple possible key names."""
    if not report:
        return None
    # Check summary
    summary = report.get("summary", report.get("data", report))
    if isinstance(summary, dict):
        for k in keys:
            if k in summary:
                v = summary[k]
                if isinstance(v, (int, float)):
                    return float(v)
    # Check fields
    fields = report.get("fields", [])
    if isinstance(fields, list):
        for f in fields:
            fn = f.get("field_name", "").lower()
            for k in keys:
                if k.lower() in fn:
                    v = f.get("value")
                    if isinstance(v, (int, float)):
                        return float(v)
    return None


if __name__ == "__main__":
    main()
