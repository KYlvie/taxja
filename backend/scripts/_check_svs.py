import psycopg2, json
conn = psycopg2.connect(host='localhost', port=5432, user='taxja', password='taxja_password', dbname='taxja')
cur = conn.cursor()

cur.execute("SELECT id, document_type::text, ocr_result FROM documents WHERE user_id = 189 AND document_type::text = 'SVS_NOTICE' ORDER BY id")
rows = cur.fetchall()
print(f"SVS docs: {len(rows)}")

for doc_id, dtype, ocr in rows:
    ocr = ocr or {}
    vlm_amount = ocr.get('amount')
    svs_subtype = ocr.get('svs_subtype')
    ai = ocr.get('_ai_first', {})
    kf = ai.get('key_fields', {})
    q = kf.get('quarter', '?')
    q_amt = kf.get('quarterly_amount')
    print(f"  doc={doc_id} Q={q} vlm_amount={vlm_amount} svs_sub={svs_subtype} ai_quarterly={q_amt}")

cur.execute("SELECT id, amount, description FROM transactions WHERE user_id = 189 AND description LIKE '%SVS%' ORDER BY id")
print(f"\nSVS txns:")
for r in cur.fetchall():
    print(f"  txn={r[0]} amt={float(r[1]):,.2f} {r[2][:80]}")

conn.close()
