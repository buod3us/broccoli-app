from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import lru_cache

import aiosqlite
import asyncpg

from catalog import MINI_APP_PRODUCTS, MINI_APP_PRODUCT_IDS
from config import BASE_DIR, DATABASE_URL

DB_PATH = BASE_DIR / "data" / "broccoli.db"

STATUS_PENDING_ADMIN = "pending_admin"
STATUS_PREPARATION = "preparation"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"

_PG_POOL: asyncpg.Pool | None = None
_PG_POOL_LOCK = asyncio.Lock()


def using_postgres() -> bool:
    return DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")


def backend_name() -> str:
    return "postgres" if using_postgres() else "sqlite"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_product_stock_map() -> dict[str, bool]:
    return {product_id: True for product_id, _ in MINI_APP_PRODUCTS}


@lru_cache(maxsize=256)
def _pg_sql(query: str) -> str:
    parts = query.split("?")
    if len(parts) == 1:
        return query
    out = [parts[0]]
    for idx, part in enumerate(parts[1:], start=1):
        out.append(f"${idx}")
        out.append(part)
    return "".join(out)


def _tag_count(tag: str) -> int:
    parts = str(tag or "").strip().split()
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


async def _get_pg_pool() -> asyncpg.Pool:
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    async with _PG_POOL_LOCK:
        if _PG_POOL is None:
            _PG_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _PG_POOL


async def get_postgres_pool() -> asyncpg.Pool:
    return await _get_pg_pool()


async def close_db() -> None:
    global _PG_POOL
    if _PG_POOL is not None:
        await _PG_POOL.close()
        _PG_POOL = None


async def ping_db() -> bool:
    try:
        if using_postgres():
            pool = await _get_pg_pool()
            async with pool.acquire() as conn:
                value = await conn.fetchval("SELECT 1")
            return int(value or 0) == 1

        row = await _fetchone("SELECT 1")
        return bool(row) and int(row[0]) == 1
    except Exception:
        return False


async def _fetchone(query: str, params: tuple = (), *, dict_row: bool = False):
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_pg_sql(query), *params)
        if row is None:
            return None
        return dict(row) if dict_row else tuple(row)

    async with aiosqlite.connect(DB_PATH) as db:
        if dict_row:
            db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        row = await cur.fetchone()
    if row is None:
        return None
    return dict(row) if dict_row else row


async def _fetchall(query: str, params: tuple = (), *, dict_rows: bool = False):
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(_pg_sql(query), *params)
        return [dict(row) if dict_rows else tuple(row) for row in rows]

    async with aiosqlite.connect(DB_PATH) as db:
        if dict_rows:
            db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
    return [dict(row) if dict_rows else row for row in rows]


async def _execute(query: str, params: tuple = ()) -> None:
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(_pg_sql(query), *params)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


async def _execute_count(query: str, params: tuple = ()) -> int:
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            tag = await conn.execute(_pg_sql(query), *params)
        return _tag_count(tag)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return int(cur.rowcount or 0)


async def _executemany(query: str, params_seq: list[tuple]) -> None:
    if not params_seq:
        return
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            await conn.executemany(_pg_sql(query), params_seq)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(query, params_seq)
        await db.commit()


async def _migrate_orders_status_sqlite(db: aiosqlite.Connection) -> None:
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


async def _migrate_orders_columns_sqlite(db: aiosqlite.Connection, extra: list[tuple[str, str, str]]) -> None:
    cur = await db.execute("PRAGMA table_info(orders)")
    rows = await cur.fetchall()
    names = {r[1] for r in rows}
    for col, col_type, default_sql in extra:
        if col not in names:
            await db.execute(
                f"ALTER TABLE orders ADD COLUMN {col} {col_type} DEFAULT {default_sql}"
            )
    await db.commit()


async def _ensure_sqlite_schema() -> None:
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
                promo_used TEXT NOT NULL DEFAULT '',
                discount_amount TEXT NOT NULL DEFAULT '0',
                final_price TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """
        )
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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS product_stock (
                product_id TEXT PRIMARY KEY,
                in_stock INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.commit()
        await _migrate_orders_status_sqlite(db)
        await _migrate_orders_columns_sqlite(
            db,
            [
                ("delivery_type", "TEXT", "''"),
                ("phone", "TEXT", "''"),
                ("comment", "TEXT", "''"),
                ("payment", "TEXT", "''"),
                ("items_json", "TEXT", "'[]'"),
                ("address", "TEXT", "''"),
                ("total_price", "TEXT", "''"),
                ("promo_used", "TEXT", "''"),
                ("discount_amount", "TEXT", "'0'"),
                ("final_price", "TEXT", "''"),
            ],
        )
        ts = _now_iso()
        await db.executemany(
            """
            INSERT INTO product_stock (product_id, in_stock, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id) DO NOTHING
            """,
            [(product_id, 1, ts) for product_id, _ in MINI_APP_PRODUCTS],
        )
        await db.commit()


async def _ensure_postgres_schema() -> None:
    pool = await _get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                goal TEXT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users (user_id),
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
                promo_used TEXT NOT NULL DEFAULT '',
                discount_amount TEXT NOT NULL DEFAULT '0',
                final_price TEXT NOT NULL DEFAULT ''
            )
            """
        )
        for clause in (
            "ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending_admin'",
            "ADD COLUMN IF NOT EXISTS delivery_type TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS phone TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS comment TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS payment TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS items_json TEXT DEFAULT '[]'",
            "ADD COLUMN IF NOT EXISTS address TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS total_price TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS promo_used TEXT DEFAULT ''",
            "ADD COLUMN IF NOT EXISTS discount_amount TEXT DEFAULT '0'",
            "ADD COLUMN IF NOT EXISTS final_price TEXT DEFAULT ''",
        ):
            await conn.execute(f"ALTER TABLE orders {clause}")
        await conn.execute(
            """
            UPDATE orders SET status = $1
            WHERE status IS NULL OR TRIM(COALESCE(status, '')) = ''
            """,
            STATUS_CONFIRMED,
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER NOT NULL,
                ambassador_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_stock (
                product_id TEXT PRIMARY KEY,
                in_stock BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_promo_used ON orders (promo_used)")
        ts = _now_iso()
        await conn.executemany(
            """
            INSERT INTO product_stock (product_id, in_stock, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT(product_id) DO NOTHING
            """,
            [(product_id, True, ts) for product_id, _ in MINI_APP_PRODUCTS],
        )


async def init_db() -> None:
    if using_postgres():
        await _ensure_postgres_schema()
    else:
        await _ensure_sqlite_schema()


async def upsert_user(user_id: int, username: str | None) -> None:
    uname = username or ""
    await _execute(
        """
        INSERT INTO users (user_id, username, goal)
        VALUES (?, ?, NULL)
        ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """,
        (user_id, uname),
    )


async def set_user_goal(user_id: int, goal: str) -> None:
    await _execute(
        "UPDATE users SET goal = ? WHERE user_id = ?",
        (goal, user_id),
    )


async def get_user_goal(user_id: int) -> str | None:
    row = await _fetchone(
        "SELECT goal FROM users WHERE user_id = ?",
        (user_id,),
        dict_row=True,
    )
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
    delivery_type: str,
    payment: str,
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
    query = """
        INSERT INTO orders (
            user_id, product, quantity, city, goal, timestamp, status,
            delivery_type, phone, comment, payment, items_json,
            address, total_price, promo_used, discount_amount, final_price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        user_id,
        product_summary,
        quantity_summary,
        city,
        goal,
        ts,
        STATUS_PENDING_ADMIN,
        delivery_type,
        phone,
        comment,
        payment,
        items_json,
        address,
        total_price,
        promo_used,
        discount_amount,
        final_price,
    )
    if using_postgres():
        pool = await _get_pg_pool()
        async with pool.acquire() as conn:
            row_id = await conn.fetchval(f"{_pg_sql(query)} RETURNING id", *params)
        if row_id is None:
            raise RuntimeError("create_order_webapp: RETURNING id is None")
        return int(row_id)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        row_id = cur.lastrowid
    if row_id is None:
        raise RuntimeError("create_order_webapp: lastrowid is None")
    return int(row_id)


def _normalize_promo_code(code: str) -> str:
    return code.strip().upper()


async def add_new_promo(code: str, discount: int, ambassador_name: str) -> None:
    c = _normalize_promo_code(code)
    if not c:
        raise ValueError("empty code")
    if discount < 1 or discount > 99:
        raise ValueError("discount out of range")
    ts = _now_iso()
    await _execute(
        """
        INSERT INTO promocodes (code, discount_percent, ambassador_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            discount_percent = excluded.discount_percent,
            ambassador_name = excluded.ambassador_name
        """,
        (c, discount, ambassador_name.strip(), ts),
    )


async def get_promo_info(code: str) -> dict | None:
    c = _normalize_promo_code(code)
    if not c:
        return None
    row = await _fetchone(
        """
        SELECT code, discount_percent, ambassador_name, created_at
        FROM promocodes WHERE code = ?
        """,
        (c,),
        dict_row=True,
    )
    if not row:
        return None
    return {
        "code": row["code"],
        "discount_percent": int(row["discount_percent"]),
        "ambassador_name": row["ambassador_name"] or "",
        "created_at": row["created_at"] or "",
    }


async def get_promo_stats(code: str) -> dict:
    c = _normalize_promo_code(code)
    if not c:
        return {"count": 0, "revenue": 0, "total_discount": 0}
    row = await _fetchone(
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
        dict_row=True,
    )
    if not row:
        return {"count": 0, "revenue": 0, "total_discount": 0}
    return {
        "count": int(row["cnt"] or 0),
        "revenue": int(row["rev"] or 0),
        "total_discount": int(row["disc"] or 0),
    }


async def delete_promo(code: str) -> bool:
    c = _normalize_promo_code(code)
    if not c:
        return False
    return await _execute_count("DELETE FROM promocodes WHERE code = ?", (c,)) > 0


async def list_promos() -> list[dict]:
    rows = await _fetchall(
        """
        SELECT code, discount_percent, ambassador_name, created_at
        FROM promocodes
        ORDER BY created_at DESC
        """,
        dict_rows=True,
    )
    return [
        {
            "code": row["code"],
            "discount_percent": int(row["discount_percent"]),
            "ambassador_name": row["ambassador_name"] or "",
            "created_at": row["created_at"] or "",
        }
        for row in rows
    ]


async def get_product_stock_map() -> dict[str, bool]:
    stock_map = _default_product_stock_map()
    rows = await _fetchall(
        "SELECT product_id, in_stock FROM product_stock",
        dict_rows=True,
    )
    for row in rows:
        product_id = str(row["product_id"] or "").strip()
        if product_id in MINI_APP_PRODUCT_IDS:
            stock_map[product_id] = bool(row["in_stock"])
    return stock_map


async def list_product_stock() -> list[dict]:
    stock_map = await get_product_stock_map()
    return [
        {
            "id": product_id,
            "title": title,
            "in_stock": bool(stock_map.get(product_id, True)),
        }
        for product_id, title in MINI_APP_PRODUCTS
    ]


async def set_product_stock(product_id: str, in_stock: bool) -> bool:
    product_id = str(product_id or "").strip()
    if product_id not in MINI_APP_PRODUCT_IDS:
        return False
    ts = _now_iso()
    value = bool(in_stock) if using_postgres() else int(bool(in_stock))
    await _execute(
        """
        INSERT INTO product_stock (product_id, in_stock, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            in_stock = excluded.in_stock,
            updated_at = excluded.updated_at
        """,
        (product_id, value, ts),
    )
    return True


async def get_unavailable_product_ids(product_ids: list[str]) -> set[str]:
    requested_ids = sorted(
        {
            str(product_id).strip()
            for product_id in product_ids
            if str(product_id).strip() in MINI_APP_PRODUCT_IDS
        }
    )
    if not requested_ids:
        return set()
    placeholders = ", ".join("?" for _ in requested_ids)
    if using_postgres():
        query = f"""
            SELECT product_id
            FROM product_stock
            WHERE product_id IN ({placeholders})
              AND COALESCE(in_stock, TRUE) = FALSE
        """
    else:
        query = f"""
            SELECT product_id
            FROM product_stock
            WHERE product_id IN ({placeholders})
              AND COALESCE(in_stock, 1) = 0
        """
    rows = await _fetchall(query, tuple(requested_ids))
    return {str(row[0]) for row in rows}


async def get_order_status(order_id: int) -> str | None:
    row = await _fetchone(
        "SELECT status FROM orders WHERE id = ?",
        (order_id,),
    )
    if not row:
        return None
    return str(row[0])


async def list_orders_by_statuses(
    statuses: list[str],
    *,
    limit: int = 12,
) -> list[dict]:
    clean_statuses = [str(status).strip() for status in statuses if str(status).strip()]
    if not clean_statuses:
        return []
    placeholders = ", ".join("?" for _ in clean_statuses)
    params = tuple(clean_statuses) + (int(limit),)
    rows = await _fetchall(
        f"""
        SELECT
            o.id,
            o.status,
            o.goal,
            o.city,
            o.product,
            o.timestamp,
            o.phone,
            u.username
        FROM orders o
        LEFT JOIN users u ON u.user_id = o.user_id
        WHERE o.status IN ({placeholders})
        ORDER BY o.id DESC
        LIMIT ?
        """,
        params,
        dict_rows=True,
    )
    return [dict(row) for row in rows]


async def get_order_details(order_id: int) -> dict | None:
    row = await _fetchone(
        """
        SELECT
            o.id,
            o.user_id,
            o.product,
            o.quantity,
            o.city,
            o.goal,
            o.timestamp,
            o.status,
            o.delivery_type,
            o.phone,
            o.comment,
            o.payment,
            o.address,
            o.total_price,
            o.promo_used,
            o.discount_amount,
            o.final_price,
            u.username
        FROM orders o
        LEFT JOIN users u ON u.user_id = o.user_id
        WHERE o.id = ?
        """,
        (order_id,),
        dict_row=True,
    )
    return dict(row) if row else None


async def try_update_order_status(order_id: int, new_status: str) -> bool:
    if new_status == STATUS_PREPARATION:
        count = await _execute_count(
            """
            UPDATE orders SET status = ?
            WHERE id = ? AND status = ?
            """,
            (new_status, order_id, STATUS_PENDING_ADMIN),
        )
        return count > 0
    count = await _execute_count(
        """
        UPDATE orders SET status = ?
        WHERE id = ? AND status IN (?, ?)
        """,
        (new_status, order_id, STATUS_PENDING_ADMIN, STATUS_PREPARATION),
    )
    return count > 0


async def count_orders() -> int:
    row = await _fetchone(
        "SELECT COUNT(*) FROM orders WHERE status = ?",
        (STATUS_CONFIRMED,),
    )
    return int(row[0]) if row else 0


async def orders_by_goal() -> dict[str, int]:
    rows = await _fetchall(
        """
        SELECT goal, COUNT(*) AS c FROM orders
        WHERE status = ?
        GROUP BY goal
        """,
        (STATUS_CONFIRMED,),
    )
    return {str(row[0]): int(row[1]) for row in rows}


async def get_all_users_for_promo() -> list[dict]:
    rows = await _fetchall(
        "SELECT user_id, username FROM users",
        dict_rows=True,
    )
    return [{"user_id": row["user_id"], "username": row["username"] or ""} for row in rows]


async def get_user_order_summary(user_id: int) -> str:
    rows = await _fetchall(
        "SELECT product, quantity FROM orders WHERE user_id = ? AND status = ?",
        (user_id, STATUS_CONFIRMED),
    )
    if not rows:
        return "Нет завершенных заказов."
    summary = [f"{row[0]} ({row[1]})" for row in rows]
    return ", ".join(summary)
