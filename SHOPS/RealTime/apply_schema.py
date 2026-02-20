"""
Применение schema.sql к базе данных
"""

import os
import psycopg2

# Конфигурация БД
DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_greenspark")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")


def main():
    # Читаем SQL файл
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Подключаемся к БД
    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("Applying schema...")
        cur.execute(sql)
        print("Schema applied successfully!")

        # Проверяем результат
        cur.execute("SELECT shop_code, parser_type FROM shop_parser_configs")
        rows = cur.fetchall()
        print(f"\nConfigs in database: {len(rows)}")
        for row in rows:
            print(f"  - {row[0]}: {row[1]}")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
