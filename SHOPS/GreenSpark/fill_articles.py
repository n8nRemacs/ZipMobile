"""
Скрипт заполнения артикулов в greenspark_nomenclature
Берёт товары с пустыми артикулами и получает их через HTML парсинг
(API не возвращает артикул, артикул есть только на HTML странице)
"""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(line_buffering=True)

import psycopg2
import time

from parser_v3 import GreenSparkParser, get_db

def main():
    print("=" * 60)
    print("Заполнение артикулов в greenspark_nomenclature")
    print("=" * 60)

    # Создаём парсер и инициализируем клиент
    parser = GreenSparkParser(shop_id=16344)
    parser.init_client()
    print("Клиент парсера инициализирован")

    # Получаем товары без артикулов
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, product_url
        FROM greenspark_nomenclature
        WHERE (article IS NULL OR article = '')
        AND product_url LIKE 'https://green-spark.ru/catalog/%'
        ORDER BY id
    """)

    products = cur.fetchall()
    total = len(products)
    print(f"\nТоваров без артикула: {total}")

    if total == 0:
        print("Все артикулы заполнены!")
        return

    found = 0
    errors = 0

    print(f"\nНачинаю обработку...\n")

    for idx, (prod_id, name, url) in enumerate(products):
        # Rate limit
        time.sleep(0.3)

        # Получаем артикул (API + HTML fallback)
        article = parser.fetch_article_from_page(url)

        if article:
            # Сохраняем в БД
            cur.execute("""
                UPDATE greenspark_nomenclature
                SET article = %s, updated_at = NOW()
                WHERE id = %s
            """, (article, prod_id))
            conn.commit()
            found += 1
            status = f"[OK] {article}"
        else:
            errors += 1
            status = "[--]"

        # Прогресс каждые 100 или первые 20
        if (idx + 1) % 100 == 0 or idx < 20:
            print(f"[{idx+1}/{total}] {name[:45]}... {status}")

    cur.close()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"Готово!")
    print(f"  Найдено артикулов: {found}")
    print(f"  Не найдено: {errors}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
