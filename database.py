import aiosqlite
from datetime import datetime, timezone

from config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "broccoli.db"

STATUS_PENDING_ADMIN = "pending_admin"
STATUS_PREPARATION = "preparation"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _migrate_orders_status(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(orders)")
    rows = await cur.fetchall()
    names = {r[1] for r in rows}
    if "status" in names:
        return
    await db.execute("ALTER TABLE orders ADD COLUMN status TEXT")
    await db.execute(
        """
        UPDATE orders SET status = ?
        WHERE status IS NULL OR TRIM(COALESCE(status, '')) = ''
        """,
        (STATUS_CONFIRMED,),
    )
    await db.commit()


async def _migrate_orders_mini_app_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(orders)")
    rows = await cur.fetchall()
    names = {r[1] for r in rows}
    extra = [
        ("delivery_type", "TEXT", "''"),
        ("phone", "TEXT", "''"),
        ("comment", "TEXT", "''"),
        ("payment", "TEXT", "''"),
        ("items_json", "TEXT", "'[]'"),
        ("address", "TEXT", "''"),
        ("total_price", "TEXT", "''"),
    ]
    for col, col_type, default_sql in extra:
        if col not in names:
            await db.execute(
                f"ALTER TABLE orders ADD COLUMN {col} {col_type} DEFAULT {default_sql}"
            )
    await db.commit()


async def _migrate_orders_promo_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(orders)")
    rows = await cur.fetchall()
    names = {r[1] for r in rows}
    extra = [
        ("promo_used", "TEXT", "''"),
        ("discount_amount", "TEXT", "'0'"),
        ("final_price", "TEXT", "''"),
    ]
    for col, col_type, default_sql in extra:
        if col not in names:
            await db.execute(
                f"ALTER TABLE orders ADD COLUMN {col} {col_type} DEFAULT {default_sql}"
            )
    await db.commit()


async def _ensure_promocodes_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            discount_percent INTEGER NOT NULL,
            ambassador_name TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    await db.commit()


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                goal TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product TEXT NOT NULL,
                quantity TEXT NOT NULL,
                city TEXT NOT NULL,
                goal TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_admin',
                delivery_type TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                comment TEXT NOT NULL DEFAULT '',
                payment TEXT NOT NULL DEFAULT '',
                items_json TEXT NOT NULL DEFAULT '[]',
                address TEXT NOT NULL DEFAULT '',
                total_price TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """
        )
        await db.commit()
        await _migrate_orders_status(db)
        await _migrate_orders_mini_app_columns(db)
        await _migrate_orders_promo_columns(db)
        await _ensure_promocodes_table(db)


async def upsert_user(user_id: int, username: str | None) -> None:
    uname = username or ""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, goal)
            VALUES (?, ?, NULL)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, uname),
        )
        await db.commit()


async def set_user_goal(user_id: int, goal: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET goal = ? WHERE user_id = ?",
            (goal, user_id),
        )
        await db.commit()


async def get_user_goal(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT goal FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return row["goal"]


async def create_order_webapp(
    user_id: int,
    *,
    goal: str,
    phone: str,
    city: str,
    address: str,
    total_price: str,
    promo_used: str,
    discount_amount: str,
    final_price: str,
    comment: str,
    product_summary: str,
    quantity_summary: str,
    items_json: str,
) -> int:
    ts = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO orders (
                user_id, product, quantity, city, goal, timestamp, status,
                delivery_type, phone, comment, payment, items_json,
                address, total_price, promo_used, discount_amount, final_price
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                product_summary,
                quantity_summary,
                city,
                goal,
                ts,
                STATUS_PENDING_ADMIN,
                "",
                phone,
                comment,
                "",
                items_json,
                address,
                total_price,
                promo_used,
                discount_amount,
                final_price,
            ),
        )
        await db.commit()
        return int(cur.lastrowid)


def _normalize_promo_code(code: str) -> str:
    return code.strip().upper()


async def add_new_promo(code: str, discount: int, ambassador_name: str) -> None:
    c = _normalize_promo_code(code)
    if not c:
        raise ValueError("empty code")
    if discount < 1 or discount > 99:
        raise ValueError("discount out of range")
    ts = _now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO promocodes (code, discount_percent, ambassador_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                discount_percent = excluded.discount_percent,
                ambassador_name = excluded.ambassador_name
            """,
            (c, discount, ambassador_name.strip(), ts),
        )
        await db.commit()


async def get_promo_info(code: str) -> dict | None:
    c = _normalize_promo_code(code)
    if not c:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT code, discount_percent, ambassador_name, created_at
            FROM promocodes WHERE code = ?
            """,
            (c,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "code": row["code"],
            "discount_percent": int(row["discount_percent"]),
            "ambassador_name": row["ambassador_name"] or "",
            "created_at": row["created_at"] or "",
        }


async def get_promo_stats(code: str) -> dict:
    """Считает заказы с данным промокодом (все статусы)."""
    c = _normalize_promo_code(code)
    if not c:
        return {"count": 0, "revenue": 0, "total_discount": 0}
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(
                     CASE
                       WHEN TRIM(COALESCE(final_price, '')) != ''
                       THEN CAST(final_price AS INTEGER)
                       ELSE CAST(COALESCE(total_price, '0') AS INTEGER)
                     END
                   ), 0) AS rev,
                   COALESCE(SUM(CAST(COALESCE(NULLIF(TRIM(discount_amount), ''), '0') AS INTEGER)), 0) AS disc
            FROM orders
            WHERE UPPER(TRIM(promo_used)) = ?
            """,
            (c,),
        )
        row = await cur.fetchone()
        if not row:
            return {"count": 0, "revenue": 0, "total_discount": 0}
        return {
            "count": int(row[0] or 0),
            "revenue": int(row[1] or 0),
            "total_discount": int(row[2] or 0),
        }


async def delete_promo(code: str) -> bool:
    c = _normalize_promo_code(code)
    if not c:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM promocodes WHERE code = ?", (c,))
        await db.commit()
        return cur.rowcount > 0


async def list_promos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT code, discount_percent, ambassador_name, created_at
            FROM promocodes
            ORDER BY created_at DESC
            """
        )
        rows = await cur.fetchall()
    return [
        {
            "code": r["code"],
            "discount_percent": int(r["discount_percent"]),
            "ambassador_name": r["ambassador_name"] or "",
            "created_at": r["created_at"] or "",
        }
        for r in rows
    ]


async def get_order_status(order_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT status FROM orders WHERE id = ?",
            (order_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return str(row[0])


async def try_update_order_status(order_id: int, new_status: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        if new_status == STATUS_PREPARATION:
            cur = await db.execute(
                """
                UPDATE orders SET status = ?
                WHERE id = ? AND status = ?
                """,
                (new_status, order_id, STATUS_PENDING_ADMIN),
            )
        else:
            cur = await db.execute(
                """
                UPDATE orders SET status = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    new_status,
                    order_id,
                    STATUS_PENDING_ADMIN,
                    STATUS_PREPARATION,
                ),
            )
        await db.commit()
        return cur.rowcount > 0


async def count_orders() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE status = ?",
            (STATUS_CONFIRMED,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def orders_by_goal() -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT goal, COUNT(*) AS c FROM orders
            WHERE status = ?
            GROUP BY goal
            """,
            (STATUS_CONFIRMED,),
        )
        rows = await cur.fetchall()
    return {str(r[0]): int(r[1]) for r in rows}
