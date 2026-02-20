"""Check recent updates"""
import sys
sys.path.insert(0, '.')
from parser_v3 import get_db

conn = get_db()
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*)
    FROM greenspark_nomenclature
    WHERE updated_at > NOW() - INTERVAL '2 minutes'
    AND article IS NOT NULL AND article != ''
""")
count = cur.fetchone()[0]
print(f"Обновлено за 2 минуты: {count}")

cur.execute("""
    SELECT name, article, updated_at
    FROM greenspark_nomenclature
    WHERE updated_at > NOW() - INTERVAL '2 minutes'
    AND article IS NOT NULL AND article != ''
    ORDER BY updated_at DESC
    LIMIT 5
""")
print("\nПоследние:")
for row in cur.fetchall():
    print(f"  {row[0][:40]} | {row[1]} | {row[2]}")

cur.close()
conn.close()
