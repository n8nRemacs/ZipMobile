import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

tables = [r[0] for r in cur.fetchall()]

prefixes = ['_05gsm', 'taggsm', 'memstech', 'signal23', 'liberti', 'orizhka', 'lcdstock', 'moba', 'greenspark', 'profi', 'moysklad_naffas', 'moysklad', 'zip_', 'master_']

for prefix in prefixes:
    matching = [t for t in tables if t.startswith(prefix)]
    if matching:
        print("\n=== {} ===".format(prefix))
        for t in matching:
            print("  {}".format(t))

print("\n=== ALL TABLES ===")
for t in tables:
    print("  {}".format(t))

conn.close()
