import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db

conn = get_db()
cur = conn.cursor()

# Orizhka: parser expects different columns than what exists
# Drop and recreate to match parser
cur.execute("DROP TABLE IF EXISTS orizhka_staging CASCADE")
cur.execute("""
    CREATE TABLE orizhka_staging (
        id SERIAL PRIMARY KEY,
        outlet_code VARCHAR(50),
        name TEXT,
        article VARCHAR(100),
        category TEXT,
        brand VARCHAR(100),
        price NUMERIC(12,2),
        old_price NUMERIC(12,2),
        quantity INTEGER,
        url TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
""")
print("Recreated: orizhka_staging")

conn.commit()
conn.close()
print("Done")
