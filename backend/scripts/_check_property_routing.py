import psycopg2, json
conn = psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')
cur = conn.cursor()

# Check property-related docs
property_types = ['invoice', 'versicherungsbestaetigung', 'grundsteuerbescheid']
cur.execute("""
    SELECT d.id, d.document_type::text, d.ocr_result, d.file_name
    FROM documents d
    WHERE d.user_id = 189
    ORDER BY d.id
""")

print("=== ALL DOCUMENTS ===")
for doc_id, dtype, ocr, fname in cur.fetchall():
    ocr = ocr or {}
    ai = ocr.get('_ai_first', {})
    kf = ai.get('key_fields', {})
    ai_type = ai.get('document_type', '?')
    prop_addr = kf.get('property_address', '')
    tax_form = (ai.get('tax_treatment') or {}).get('tax_form', '?')
    role = (ai.get('role_detection') or {}).get('user_is', '?')
    amounts = ai.get('amounts', {})
    total = amounts.get('total_amount') or amounts.get('annual_amount') or amounts.get('monthly_amount') or '?'

    # Check if transaction was created and linked to property
    cur.execute("""
        SELECT t.id, t.amount, t.type::text, t.property_id, t.income_category::text, t.expense_category::text
        FROM transactions t WHERE t.document_id = %s
    """, (doc_id,))
    txns = cur.fetchall()

    flag = ""
    if prop_addr:
        flag = f" PROP_ADDR=[{prop_addr}]"

    txn_info = ""
    for t in txns:
        pid = t[3]
        txn_info += f"\n    -> txn={t[0]} {t[2]:8s} EUR {float(t[1]):>10,.2f} cat={t[4] or t[5] or '?':20s} prop={pid}"

    if not txns:
        txn_info = "\n    -> NO TRANSACTION"

    print(f"\n  [{doc_id}] {str(dtype):25s} ai={str(ai_type):25s} form={str(tax_form):5s} role={str(role):12s} amt={str(total):>10s}{flag}{txn_info}")

conn.close()
