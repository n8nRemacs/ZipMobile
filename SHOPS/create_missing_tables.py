import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()

# All shops need _parse_log
all_prefixes = [
    "_05gsm", "taggsm", "memstech", "signal23", "liberti",
    "orizhka", "lcdstock", "moba", "greenspark", "profi", "moysklad_naffas"
]

# === 1. Create _parse_log for ALL shops ===
for prefix in all_prefixes:
    table = "{}_parse_log".format(prefix)
    sql = """
    CREATE TABLE IF NOT EXISTS {} (
        id SERIAL PRIMARY KEY,
        task_id UUID,
        status VARCHAR(20) DEFAULT 'pending',
        stats JSONB,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        error TEXT
    )
    """.format(table)
    cur.execute(sql)
    print("Created: {}".format(table))

# === 2. Naffas: missing _nomenclature ===
cur.execute("""
    CREATE TABLE IF NOT EXISTS moysklad_naffas_nomenclature (
        id SERIAL PRIMARY KEY,
        article VARCHAR(100) UNIQUE,
        name TEXT,
        url TEXT,
        zip_nomenclature_id INTEGER,
        brand_id INTEGER,
        model_ids INTEGER[],
        part_type_id INTEGER,
        color_id INTEGER,
        needs_ai BOOLEAN DEFAULT false,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
""")
print("Created: moysklad_naffas_nomenclature")

# === 3. Naffas: missing _staging ===
cur.execute("""
    CREATE TABLE IF NOT EXISTS moysklad_naffas_staging (
        id SERIAL PRIMARY KEY,
        raw_data JSONB,
        status VARCHAR(20) DEFAULT 'new',
        error TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
""")
print("Created: moysklad_naffas_staging")

# === 4. lcdstock: missing _prices (has _prices_v2 but not _prices) ===
cur.execute("""
    CREATE TABLE IF NOT EXISTS lcdstock_prices (
        id SERIAL PRIMARY KEY,
        nomenclature_id INTEGER,
        price_type_id INTEGER,
        price NUMERIC(12,2),
        currency VARCHAR(10) DEFAULT 'RUB',
        is_active BOOLEAN DEFAULT true,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
""")
print("Created: lcdstock_prices")

conn.commit()
print("\nAll tables created successfully!")

# === Verify ===
print("\n=== VERIFICATION ===")
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

required = ["_nomenclature", "_prices", "_staging", "_parse_log"]

for name, prefix in shops:
    missing = []
    for suffix in required:
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
