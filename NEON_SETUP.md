# Neon Setup

1. Create a project in `Neon`.
2. Open the project dashboard.
3. Copy the `Direct connection` string, not the pooled one.
4. Make sure the string contains `sslmode=require`.
5. Put it into `.env` as:

```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

6. Keep `MINI_APP_URL` pointed to your deployed Mini App, for example:

```env
MINI_APP_URL=https://your-domain.com/app/
```

7. Run dependency install:

```bash
python -m pip install -r requirements.txt
```

8. Run one-time migration from local SQLite to Neon:

```bash
python migrate_sqlite_to_postgres.py
```

9. Verify that the app sees Postgres:

```bash
python -c "import database; print(database.backend_name())"
```

Expected output:

```text
postgres
```

10. Start API:

```bash
python api.py
```

11. Check health endpoint:

```text
GET /healthz
```

Expected response:

```json
{"ok": true, "db": "postgres"}
```

12. Start bot:

```bash
python main.py
```

Notes:

- Migration is idempotent for existing rows: duplicate IDs are skipped.
- If you stay without `DATABASE_URL`, the project continues to use local `SQLite`.
- For this project `Neon` is used only as managed `Postgres`; API remains in your codebase.
