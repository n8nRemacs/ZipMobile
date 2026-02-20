import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()

print("=== zip_outlets columns ===")
cur.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'zip_outlets' ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print("  {}: {}".format(r[0], r[1]))

print("\n=== zip_outlets data ===")
cur.execute("SELECT * FROM zip_outlets ORDER BY id")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print("  Columns:", cols)
for r in rows:
    print("  ", dict(zip(cols, r)))

print("\n=== zip_shops ===")
cur.execute("SELECT * FROM zip_shops ORDER BY id")
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print("  Columns:", cols)
for r in rows:
    print("  ", dict(zip(cols, r)))

# Check what's missing per standard
print("\n=== MISSING TABLES CHECK ===")
shops = [
    ("05GSM", "_05gsm"),
    ("Taggsm", "taggsm"),
    ("memstech", "memstech"),
    ("signal23", "signal23"),
    ("Liberti", "liberti"),
    ("Orizhka", "orizhka"),
    ("lcd-stock", "lcdstock"),
    ("Moba", "moba"),
    ("GreenSpark", "greenspark"),
    ("Profi", "profi"),
    ("Naffas", "moysklad_naffas"),
]

required_suffixes = ["_nomenclature", "_prices", "_staging", "_parse_log"]

for name, prefix in shops:
    missing = []
    for suffix in required_suffixes:
        table = prefix + suffix
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
        """, (table,))
        if not cur.fetchone()[0]:
            missing.append(suffix)
    if missing:
        print("  {} ({}): MISSING {}".format(name, prefix, ", ".join(missing)))
    else:
        print("  {} ({}): OK".format(name, prefix))

conn.close()
