import sys
sys.path.insert(0, "/mnt/projects/repos/ZipMobile/SHOPS")
from db_wrapper import get_db
conn = get_db()
cur = conn.cursor()

shops = [
    ('signal23', 'Signal23', 'retailer'),
    ('liberti', 'Liberti', 'distributor'),
    ('orizhka', 'Orizhka', 'retailer'),
    ('lcdstock', 'LCD-Stock', 'retailer'),
    ('moba', 'Moba', 'distributor'),
]

for code, name, stype in shops:
    cur.execute("""
        INSERT INTO zip_shops (code, name, shop_type, is_active)
        VALUES (%s, %s, %s, true)
        ON CONFLICT (code) DO NOTHING
    """, (code, name, stype))
    print("Added: {}".format(code))

conn.commit()
conn.close()
print("Done")
