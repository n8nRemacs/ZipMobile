"""Quick check of article counts"""
import sys
sys.path.insert(0, '.')
from parser_v3 import get_db

conn = get_db()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM greenspark_nomenclature WHERE article IS NOT NULL AND article != ''")
with_articles = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM greenspark_nomenclature WHERE article IS NULL OR article = ''")
without_articles = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM greenspark_nomenclature")
total = cur.fetchone()[0]

print(f"С артикулами: {with_articles}")
print(f"Без артикулов: {without_articles}")
print(f"Всего: {total}")

# Показать последние 10 обновлённых с артикулами
cur.execute("""
    SELECT name, article, updated_at
    FROM greenspark_nomenclature
    WHERE article IS NOT NULL AND article != ''
    ORDER BY updated_at DESC
    LIMIT 10
""")
print("\nПоследние обновлённые с артикулами:")
for row in cur.fetchall():
    print(f"  {row[0][:50]}... | {row[1]} | {row[2]}")

cur.close()
conn.close()
