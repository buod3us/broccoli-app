from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

import database as db


async def _table_exists(sqlite_db: aiosqlite.Connection, table_name: str) -> bool:
    cur = await sqlite_db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    row = await cur.fetchone()
    return row is not None


async def _table_rows(sqlite_db: aiosqlite.Connection, table_name: str) -> list[dict]:
    if not await _table_exists(sqlite_db, table_name):
        return []
    sqlite_db.row_factory = aiosqlite.Row
    cur = await sqlite_db.execute(f"SELECT * FROM {table_name}")
    rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def main() -> None:
    if not db.using_postgres():
        raise SystemExit("Укажите DATABASE_URL с postgresql://..., затем повторите запуск.")
    sqlite_path = Path(db.DB_PATH)
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite база не найдена: {sqlite_path}")

    await db.init_db()
    pool = await db.get_postgres_pool()

    async with aiosqlite.connect(sqlite_path) as sqlite_db:
        users = await _table_rows(sqlite_db, "users")
        orders = await _table_rows(sqlite_db, "orders")
        promos = await _table_rows(sqlite_db, "promocodes")
        stock = await _table_rows(sqlite_db, "product_stock")

    async with pool.acquire() as conn:
        if users:
            await conn.executemany(
                """
                INSERT INTO users (user_id, username, goal)
                VALUES ($1, $2, $3)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    goal = EXCLUDED.goal
                """,
                [
                    (
                        int(row["user_id"]),
                        row.get("username") or "",
                        row.get("goal"),
                    )
                    for row in users
                ],
            )

        if promos:
            await conn.executemany(
                """
                INSERT INTO promocodes (code, discount_percent, ambassador_name, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(code) DO UPDATE SET
                    discount_percent = EXCLUDED.discount_percent,
                    ambassador_name = EXCLUDED.ambassador_name,
                    created_at = EXCLUDED.created_at
                """,
                [
                    (
                        str(row["code"]),
                        int(row["discount_percent"]),
                        row.get("ambassador_name") or "",
                        row.get("created_at") or "",
                    )
                    for row in promos
                ],
            )

        if stock:
            await conn.executemany(
                """
                INSERT INTO product_stock (product_id, in_stock, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT(product_id) DO UPDATE SET
                    in_stock = EXCLUDED.in_stock,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    (
                        str(row["product_id"]),
                        bool(row["in_stock"]),
                        row.get("updated_at") or "",
                    )
                    for row in stock
                ],
            )

        if orders:
            await conn.executemany(
                """
                INSERT INTO orders (
                    id, user_id, product, quantity, city, goal, timestamp, status,
                    delivery_type, phone, comment, payment, items_json, address,
                    total_price, promo_used, discount_amount, final_price
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18
                )
                ON CONFLICT(id) DO NOTHING
                """,
                [
                    (
                        int(row["id"]),
                        int(row["user_id"]),
                        row.get("product") or "",
                        row.get("quantity") or "",
                        row.get("city") or "",
                        row.get("goal") or "",
                        row.get("timestamp") or "",
                        row.get("status") or db.STATUS_PENDING_ADMIN,
                        row.get("delivery_type") or "",
                        row.get("phone") or "",
                        row.get("comment") or "",
                        row.get("payment") or "",
                        row.get("items_json") or "[]",
                        row.get("address") or "",
                        row.get("total_price") or "",
                        row.get("promo_used") or "",
                        row.get("discount_amount") or "0",
                        row.get("final_price") or "",
                    )
                    for row in orders
                ],
            )
            await conn.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('orders', 'id'),
                    COALESCE((SELECT MAX(id) FROM orders), 1),
                    TRUE
                )
                """
            )

    print(
        f"Migrated users={len(users)} orders={len(orders)} promos={len(promos)} stock={len(stock)}"
    )
    await db.close_db()


if __name__ == "__main__":
    asyncio.run(main())
