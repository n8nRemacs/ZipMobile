"""Анализ товаров без артикулов - какие категории?"""
import sys
sys.path.insert(0, '.')
from parser_v3 import get_db

conn = get_db()
cur = conn.cursor()

# Анализ по категориям (из URL)
cur.execute("""
    SELECT
        SPLIT_PART(product_url, '/', 5) as category,
        COUNT(*) as cnt
    FROM greenspark_nomenclature
    WHERE (article IS NULL OR article = '')
    AND product_url LIKE 'https://green-spark.ru/catalog/%'
    GROUP BY SPLIT_PART(product_url, '/', 5)
    ORDER BY cnt DESC
    LIMIT 20
""")

print("Категории товаров без артикулов:")
print("-" * 60)
for row in cur.fetchall():
    print(f"  {row[0][:45]}: {row[1]}")

# Примеры товаров без артикулов
print("\n" + "=" * 60)
print("Примеры товаров без артикулов (первые 30):")
print("-" * 60)

cur.execute("""
    SELECT id, name, product_url
    FROM greenspark_nomenclature
    WHERE (article IS NULL OR article = '')
    AND product_url LIKE 'https://green-spark.ru/catalog/%'
    ORDER BY id
    LIMIT 30
""")

for row in cur.fetchall():
    print(f"[{row[0]}] {row[1][:50]}")
    print(f"     {row[2]}")
    print()

cur.close()
conn.close()
