import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()

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

header = "{:<15} {:>12} {:>10} {:>10} {:>20}".format(
    "Shop", "Nomenclature", "Prices", "Staging", "Last updated"
)
print(header)
print("-" * 70)

for name, prefix in shops:
    nom = 0
    prices = 0
    staging = 0
    last_update = "-"

    for suffix in ["_nomenclature", "_nomenclature_v2"]:
        try:
            cur.execute("SELECT COUNT(*) FROM {}{}".format(prefix, suffix))
            nom = cur.fetchone()[0]
            break
        except:
            conn.rollback()

    for suffix in ["_prices", "_prices_v2", "_current_prices"]:
        try:
            cur.execute("SELECT COUNT(*) FROM {}{}".format(prefix, suffix))
            prices = cur.fetchone()[0]
            break
        except:
            conn.rollback()

    try:
        cur.execute("SELECT COUNT(*) FROM {}_staging".format(prefix))
        staging = cur.fetchone()[0]
    except:
        conn.rollback()

    for suffix in ["_nomenclature", "_nomenclature_v2"]:
        try:
            cur.execute("SELECT MAX(updated_at)::text FROM {}{}".format(prefix, suffix))
            row = cur.fetchone()
            if row and row[0]:
                last_update = row[0][:16]
            break
        except:
            conn.rollback()

    print("{:<15} {:>12} {:>10} {:>10} {:>20}".format(
        name, nom, prices, staging, last_update
    ))

conn.close()
