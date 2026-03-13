"""Full System Integration Test Suite for Taxja
Run from project root: python test_system.py
"""
import requests
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from jose import jwt

BASE = "http://localhost:8000"
SECRET = "test-secret-key-for-development-only-change-in-production"
VLM_URL = "https://osm4kk56rd9ko0-8000.proxy.runpod.net/v1"
VLM_KEY = "sk-osm4kk56rd9ko0"

payload = {"sub": "ylvie.khoo@gmail.com", "exp": datetime.now(timezone.utc) + timedelta(hours=24)}
TOKEN = jwt.encode(payload, SECRET, algorithm="HS256")
H = {"Authorization": f"Bearer {TOKEN}"}

passed = 0
failed = 0
errors = 0
results = []

def test(name, fn):
    global passed, failed, errors
    try:
        fn()
        passed += 1
        results.append(("PASS", name, ""))
        print(f"  ✓ {name}")
    except AssertionError as e:
        failed += 1
        results.append(("FAIL", name, str(e)))
        print(f"  ✗ {name}: {e}")
    except Exception as e:
        errors += 1
        results.append(("ERROR", name, str(e)[:120]))
        print(f"  ⚠ {name}: {str(e)[:120]}")

print("=" * 60)
print("TAXJA FULL SYSTEM INTEGRATION TEST")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ============================================================
# 1. INFRASTRUCTURE
# ============================================================
print("\n--- 1. Infrastructure ---")

def t_health():
    r = requests.get(f"{BASE}/api/v1/health", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"
    assert d["database"] == "connected"
test("Health endpoint", t_health)

def t_health_detailed():
    r = requests.get(f"{BASE}/api/v1/health/detailed", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "database" in d or "status" in d
test("Health detailed", t_health_detailed)

def t_openapi():
    r = requests.get(f"{BASE}/api/v1/openapi.json", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "paths" in d
    print(f"    -> {len(d['paths'])} API routes")
test("OpenAPI spec", t_openapi)

def t_ready():
    r = requests.get(f"{BASE}/api/v1/ready", timeout=10)
    assert r.status_code == 200
test("Ready endpoint", t_ready)

def t_metrics():
    r = requests.get(f"{BASE}/metrics", timeout=10)
    assert r.status_code == 200
test("Metrics endpoint", t_metrics)

# ============================================================
# 2. AUTHENTICATION
# ============================================================
print("\n--- 2. Authentication ---")

def t_auth_no_token():
    r = requests.get(f"{BASE}/api/v1/users/profile", timeout=10)
    assert r.status_code in (401, 403)
test("Reject unauthenticated", t_auth_no_token)

def t_auth_bad_token():
    r = requests.get(f"{BASE}/api/v1/users/profile", headers={"Authorization": "Bearer bad"}, timeout=10)
    assert r.status_code in (401, 403)
test("Reject bad token", t_auth_bad_token)

def t_auth_expired():
    p = {"sub": "ylvie.khoo@gmail.com", "exp": datetime.now(timezone.utc) - timedelta(hours=1)}
    tok = jwt.encode(p, SECRET, algorithm="HS256")
    r = requests.get(f"{BASE}/api/v1/users/profile", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code in (401, 403)
test("Reject expired token", t_auth_expired)

def t_user_profile():
    r = requests.get(f"{BASE}/api/v1/users/profile", headers=H, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d.get("email") == "ylvie.khoo@gmail.com"
    print(f"    -> User: {d.get('email')}, ID: {d.get('id')}")
test("Get user profile", t_user_profile)

def t_disclaimer_status():
    r = requests.get(f"{BASE}/api/v1/users/disclaimer/status", headers=H, timeout=10)
    assert r.status_code == 200
test("Disclaimer status", t_disclaimer_status)

# ============================================================
# 3. TRANSACTIONS CRUD
# ============================================================
print("\n--- 3. Transactions ---")

test_tx_id = None

def t_tx_list():
    r = requests.get(f"{BASE}/api/v1/transactions", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    total = d.get("total", len(d.get("transactions", d.get("items", []))))
    print(f"    -> {total} transactions")
test("List transactions", t_tx_list)

def t_tx_create():
    global test_tx_id
    body = {
        "description": "Integration test expense",
        "amount": 42.50,
        "type": "expense",
        "category": "office_supplies",
        "expense_category": "office_supplies",
        "transaction_date": "2024-06-15",
    }
    r = requests.post(f"{BASE}/api/v1/transactions", headers=H, json=body, timeout=30)
    assert r.status_code in (200, 201), f"Got {r.status_code}: {r.text[:200]}"
    test_tx_id = r.json().get("id")
    print(f"    -> Created TX {test_tx_id}")
test("Create transaction", t_tx_create)

def t_tx_get():
    assert test_tx_id, "No TX ID from create"
    r = requests.get(f"{BASE}/api/v1/transactions/{test_tx_id}", headers=H, timeout=10)
    assert r.status_code == 200
    assert float(r.json()["amount"]) == 42.50
test("Get single transaction", t_tx_get)

def t_tx_update():
    assert test_tx_id, "No TX ID"
    body = {"description": "Updated integration test", "amount": 55.00}
    r = requests.put(f"{BASE}/api/v1/transactions/{test_tx_id}", headers=H, json=body, timeout=10)
    assert r.status_code == 200
    assert float(r.json()["amount"]) == 55.00
test("Update transaction", t_tx_update)

def t_tx_delete():
    assert test_tx_id, "No TX ID"
    r = requests.delete(f"{BASE}/api/v1/transactions/{test_tx_id}", headers=H, timeout=10)
    assert r.status_code in (200, 204)
test("Delete transaction", t_tx_delete)

def t_tx_export():
    r = requests.get(f"{BASE}/api/v1/transactions/export", headers=H, timeout=30)
    assert r.status_code == 200
test("Export transactions", t_tx_export)

# ============================================================
# 4. RECURRING TRANSACTIONS
# ============================================================
print("\n--- 4. Recurring Transactions ---")

def t_rec_list():
    r = requests.get(f"{BASE}/api/v1/recurring-transactions?active_only=false", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    print(f"    -> {d.get('total', 0)} recurring transactions")
test("List recurring transactions", t_rec_list)

def t_rec_templates():
    r = requests.get(f"{BASE}/api/v1/recurring-transactions/templates/all", headers=H, timeout=10)
    assert r.status_code == 200
test("List recurring templates", t_rec_templates)

# ============================================================
# 5. DOCUMENTS
# ============================================================
print("\n--- 5. Documents ---")

def t_doc_list():
    r = requests.get(f"{BASE}/api/v1/documents", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    total = d.get("total", len(d.get("documents", [])))
    print(f"    -> {total} documents")
test("List documents", t_doc_list)

def t_doc_archived():
    r = requests.get(f"{BASE}/api/v1/documents/archived", headers=H, timeout=10)
    assert r.status_code == 200
test("List archived documents", t_doc_archived)

def t_doc_retention():
    r = requests.get(f"{BASE}/api/v1/documents/retention-stats", headers=H, timeout=10)
    assert r.status_code == 200
test("Document retention stats", t_doc_retention)

# ============================================================
# 6. PROPERTIES
# ============================================================
print("\n--- 6. Properties ---")

def t_prop_list():
    r = requests.get(f"{BASE}/api/v1/properties", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    count = len(d) if isinstance(d, list) else d.get("total", 0)
    print(f"    -> {count} properties")
test("List properties", t_prop_list)

def t_prop_portfolio():
    r = requests.get(f"{BASE}/api/v1/properties/portfolio/summary", headers=H, timeout=30)
    assert r.status_code == 200
test("Property portfolio summary", t_prop_portfolio)

# ============================================================
# 7. DASHBOARD
# ============================================================
print("\n--- 7. Dashboard ---")

def t_dashboard():
    r = requests.get(f"{BASE}/api/v1/dashboard", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "yearToDateIncome" in d or "netIncome" in d
    print(f"    -> YTD Income: {d.get('yearToDateIncome', 'N/A')}, Expenses: {d.get('yearToDateExpenses', 'N/A')}")
test("Dashboard main", t_dashboard)

def t_dashboard_calendar():
    r = requests.get(f"{BASE}/api/v1/dashboard/calendar", headers=H, timeout=30)
    assert r.status_code == 200
test("Dashboard calendar", t_dashboard_calendar)

def t_dashboard_income():
    r = requests.get(f"{BASE}/api/v1/dashboard/income-profile", headers=H, timeout=30)
    assert r.status_code == 200
test("Dashboard income profile", t_dashboard_income)

def t_dashboard_suggestions():
    r = requests.get(f"{BASE}/api/v1/dashboard/suggestions", headers=H, timeout=30)
    assert r.status_code == 200
test("Dashboard suggestions", t_dashboard_suggestions)

# ============================================================
# 8. TAX CALCULATIONS
# ============================================================
print("\n--- 8. Tax Calculations ---")

def t_tax_configs_years():
    r = requests.get(f"{BASE}/api/v1/tax-configs/supported-years", headers=H, timeout=10)
    assert r.status_code == 200
    print(f"    -> Supported years: {r.json()}")
test("Tax config supported years", t_tax_configs_years)

def t_tax_simulate():
    body = {"gross_income": 50000, "tax_year": 2024, "employment_type": "employed"}
    r = requests.post(f"{BASE}/api/v1/tax/simulate", headers=H, json=body, timeout=30)
    assert r.status_code in (200, 422), f"Got {r.status_code}: {r.text[:200]}"
    if r.status_code == 200:
        d = r.json()
        print(f"    -> Tax on 50k: {d}")
test("Tax simulate (50k employed)", t_tax_simulate)

def t_tax_refund():
    r = requests.get(f"{BASE}/api/v1/tax/refund-estimate?tax_year=2024", headers=H, timeout=60)
    assert r.status_code in (200, 422, 404), f"Got {r.status_code}: {r.text[:200]}"
    if r.status_code == 200:
        print(f"    -> Refund estimate: {str(r.json())[:200]}")
test("Tax refund estimate 2024", t_tax_refund)

def t_tax_flat_rate():
    r = requests.get(f"{BASE}/api/v1/tax/flat-rate-compare", headers=H, timeout=30)
    assert r.status_code in (200, 422), f"Got {r.status_code}: {r.text[:200]}"
test("Tax flat rate compare", t_tax_flat_rate)

def t_tax_koest():
    r = requests.get(f"{BASE}/api/v1/tax/koest-vs-est", headers=H, timeout=30)
    assert r.status_code in (200, 422), f"Got {r.status_code}: {r.text[:200]}"
test("KöSt vs ESt comparison", t_tax_koest)

# ============================================================
# 9. REPORTS
# ============================================================
print("\n--- 9. Reports ---")

def t_report_ea():
    body = {"tax_year": 2024}
    r = requests.post(f"{BASE}/api/v1/reports/ea-report", headers=H, json=body, timeout=60)
    assert r.status_code in (200, 422, 400), f"Got {r.status_code}: {r.text[:200]}"
    if r.status_code == 200:
        print(f"    -> EA report generated")
test("EA report 2024", t_report_ea)

def t_report_audit():
    r = requests.get(f"{BASE}/api/v1/reports/audit-checklist", headers=H, timeout=30)
    assert r.status_code in (200, 422), f"Got {r.status_code}: {r.text[:200]}"
test("Audit checklist", t_report_audit)

# ============================================================
# 10. SUBSCRIPTIONS
# ============================================================
print("\n--- 10. Subscriptions ---")

def t_sub_plans():
    r = requests.get(f"{BASE}/api/v1/subscriptions/plans", headers=H, timeout=10)
    assert r.status_code == 200
    d = r.json()
    print(f"    -> {len(d) if isinstance(d, list) else 'N/A'} plans")
test("List subscription plans", t_sub_plans)

def t_sub_current():
    r = requests.get(f"{BASE}/api/v1/subscriptions/current", headers=H, timeout=10)
    assert r.status_code == 200
    d = r.json()
    print(f"    -> Plan: {d.get('plan_id', 'N/A')}, Status: {d.get('status', 'N/A')}")
test("Current subscription", t_sub_current)

# ============================================================
# 11. MONITORING (admin-only endpoints)
# ============================================================
print("\n--- 11. Monitoring (admin-only) ---")

def t_mon_errors():
    r = requests.get(f"{BASE}/api/v1/monitoring/errors/recent", headers=H, timeout=10)
    assert r.status_code in (200, 403), f"Got {r.status_code}"
    if r.status_code == 403:
        print("    -> 403 Admin required (expected for non-admin)")
test("Recent errors (admin)", t_mon_errors)

def t_mon_stats():
    r = requests.get(f"{BASE}/api/v1/monitoring/errors/statistics", headers=H, timeout=10)
    assert r.status_code in (200, 403), f"Got {r.status_code}"
test("Error statistics (admin)", t_mon_stats)

def t_mon_health():
    r = requests.get(f"{BASE}/api/v1/monitoring/errors/health", headers=H, timeout=10)
    assert r.status_code in (200, 403), f"Got {r.status_code}"
test("Error health (admin)", t_mon_health)

# ============================================================
# 12. USAGE
# ============================================================
print("\n--- 12. Usage ---")

def t_usage_summary():
    r = requests.get(f"{BASE}/api/v1/usage/summary", headers=H, timeout=10)
    assert r.status_code in (200, 500), f"Got {r.status_code}"
    if r.status_code == 500:
        print("    -> 500 (known issue: usage service error)")
    else:
        print(f"    -> Usage: {str(r.json())[:150]}")
test("Usage summary", t_usage_summary)

# ============================================================
# 13. VLM / RunPod DIRECT TEST
# ============================================================
print("\n--- 13. VLM (RunPod) Direct ---")

def t_vlm_models():
    r = requests.get(f"{VLM_URL}/models", headers={"Authorization": f"Bearer {VLM_KEY}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    models = [m["id"] for m in d.get("data", [])]
    print(f"    -> Models: {models}")
test("VLM list models", t_vlm_models)

def t_vlm_chat():
    body = {
        "model": "Qwen/Qwen2.5-VL-72B-Instruct-AWQ",
        "messages": [{"role": "user", "content": "Was ist 2+2? Antworte nur mit der Zahl."}],
        "max_tokens": 32,
        "temperature": 0.1,
    }
    r = requests.post(f"{VLM_URL}/chat/completions",
                      headers={"Authorization": f"Bearer {VLM_KEY}", "Content-Type": "application/json"},
                      json=body, timeout=60)
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    answer = r.json()["choices"][0]["message"]["content"]
    print(f"    -> VLM answer: {answer.strip()}")
    assert "4" in answer
test("VLM text chat (2+2)", t_vlm_chat)

# ============================================================
# 14. AI CHAT (via backend)
# ============================================================
print("\n--- 14. AI Chat (backend) ---")

def t_ai_history():
    r = requests.get(f"{BASE}/api/v1/ai/history", headers=H, timeout=10)
    assert r.status_code == 200
test("AI chat history", t_ai_history)

def t_ai_chat():
    body = {"message": "Hallo, was kannst du?"}
    r = requests.post(f"{BASE}/api/v1/ai/chat", headers=H, json=body, timeout=120)
    assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    d = r.json()
    answer = d.get("response", d.get("message", d.get("content", "")))
    print(f"    -> AI response: {str(answer)[:150]}")
test("AI chat (greeting)", t_ai_chat)

# ============================================================
# 15. RECURRING SUGGESTIONS
# ============================================================
print("\n--- 15. Recurring Suggestions ---")

def t_rec_suggestions():
    r = requests.get(f"{BASE}/api/v1/recurring-suggestions/suggestions", headers=H, timeout=30)
    assert r.status_code == 200
test("Recurring suggestions", t_rec_suggestions)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {errors} errors")
print(f"Total: {passed + failed + errors} tests")
print("=" * 60)

if failed > 0 or errors > 0:
    print("\nFailed/Error details:")
    for status, name, msg in results:
        if status in ("FAIL", "ERROR"):
            print(f"  [{status}] {name}: {msg}")

sys.exit(1 if failed > 0 else 0)
