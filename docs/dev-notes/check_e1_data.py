from sqlalchemy import create_engine, text

engine = create_engine('postgresql://taxja:taxja_password@localhost:5432/taxja')
with engine.connect() as conn:
    # 检查是否有E1导入的交易
    result = conn.execute(text("""
        SELECT COUNT(*) as count, 
               MIN(transaction_date) as earliest,
               MAX(transaction_date) as latest
        FROM transactions 
        WHERE import_source = 'e1_import'
    """))
    row = result.fetchone()
    print(f'E1导入的交易数量: {row[0]}')
    if row[0] > 0:
        print(f'最早日期: {row[1]}')
        print(f'最晚日期: {row[2]}')
    else:
        print('没有找到E1导入的交易')
    
    # 检查所有交易的import_source
    result2 = conn.execute(text("""
        SELECT import_source, COUNT(*) as count
        FROM transactions
        GROUP BY import_source
    """))
    print('\n所有交易的来源统计:')
    for row in result2:
        source = row[0] if row[0] else '(手动创建)'
        print(f'  {source}: {row[1]}条')
    
    # 检查最近的交易
    result3 = conn.execute(text("""
        SELECT id, type, amount, transaction_date, description, import_source, created_at
        FROM transactions
        ORDER BY created_at DESC
        LIMIT 5
    """))
    print('\n最近创建的5条交易:')
    for row in result3:
        print(f'  ID:{row[0]} | {row[1]} | €{row[2]} | {row[3]} | {row[4][:30] if row[4] else "无描述"} | 来源:{row[5] or "手动"} | 创建:{row[6]}')
