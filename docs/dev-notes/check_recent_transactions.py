from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

engine = create_engine('postgresql://taxja:taxja_password@localhost:5432/taxja')
with engine.connect() as conn:
    # 检查最近10分钟创建的交易
    ten_min_ago = datetime.now() - timedelta(minutes=10)
    
    result = conn.execute(text("""
        SELECT id, type, amount, transaction_date, description, import_source, created_at
        FROM transactions
        WHERE created_at > :time_threshold
        ORDER BY created_at DESC
    """), {"time_threshold": ten_min_ago})
    
    rows = result.fetchall()
    print(f'最近10分钟创建的交易数量: {len(rows)}')
    print()
    
    if rows:
        for row in rows:
            print(f'ID:{row[0]} | {row[1]} | €{row[2]} | {row[3]} | {row[4][:50] if row[4] else "无描述"} | 来源:{row[5] or "手动"} | 创建:{row[6]}')
    else:
        print('没有找到最近10分钟创建的交易')
    
    # 检查所有交易
    result2 = conn.execute(text("""
        SELECT COUNT(*) FROM transactions
    """))
    total = result2.fetchone()[0]
    print(f'\n数据库中总交易数: {total}')
