import psycopg2

conn = psycopg2.connect(
    host='85.198.98.104',
    port=5433,
    dbname='db_profi',
    user='postgres',
    password='Mi31415926pSss!'
)
cur = conn.cursor()

print("=== Записи где brand = part_type (проблема) ===")
cur.execute("""
    SELECT id, brand, part_type, part_type_raw, name
    FROM profi_nomenclature_tmp
    WHERE brand = part_type AND part_type IS NOT NULL
    LIMIT 20
""")
for row in cur.fetchall():
    print(f"id={row[0]}: brand='{row[1]}' | part_type='{row[2]}' | part_type_raw='{row[3]}' | {row[4][:50]}")

print("\n=== Записи с brand='АКБ' (нужен бренд) ===")
cur.execute("""
    SELECT id, brand, part_type, part_type_raw, name
    FROM profi_nomenclature_tmp
    WHERE brand = 'АКБ'
    LIMIT 20
""")
for row in cur.fetchall():
    print(f"id={row[0]}: brand='{row[1]}' | part_type='{row[2]}' | part_type_raw='{row[3]}' | {row[4][:50]}")

conn.close()
