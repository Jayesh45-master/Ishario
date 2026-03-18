#!/usr/bin/env python3
"""
Initialize MySQL for Ishario.

Creates the two databases (ishario_db + signease by default) and applies schemas
from db/*.sql. Optionally seeds an admin account.

Run (from any working directory, inside the conda env):
  python scripts/init_mysql.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import mysql.connector


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _connect_admin():
    host = _env("MYSQL_ADMIN_HOST", _env("ISHARIO_DB_HOST", "localhost"))
    port = int(_env("MYSQL_ADMIN_PORT", "3306") or "3306")
    user = _env("MYSQL_ADMIN_USER", _env("ISHARIO_DB_USER", "root"))
    password = _env("MYSQL_ADMIN_PASS", _env("ISHARIO_DB_PASS", ""))
    return mysql.connector.connect(host=host, port=port, user=user, password=password)


def _execute_sql(conn, sql: str) -> None:
    cur = conn.cursor()
    try:
        for _ in cur.execute(sql, multi=True):
            pass
    finally:
        cur.close()


def _ensure_database(conn, db_name: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    finally:
        cur.close()


def _is_safe_mysql_user(value: str) -> bool:
    # Very small allowlist: avoid SQL injection when interpolating user identifiers.
    # Allows typical local dev usernames like root, ishario, app_user, etc.
    return bool(value) and all(c.isalnum() or c in {"_", "-", "."} for c in value)


def _ensure_user_and_grants(conn, *, db_name: str, user: str | None, password: str | None, host: str) -> None:
    if not user or user.lower() == "root":
        return
    if not _is_safe_mysql_user(user) or not _is_safe_mysql_user(host):
        raise SystemExit(f"Unsafe MySQL user/host value. user={user!r} host={host!r}")

    cur = conn.cursor()
    try:
        # MySQL does not allow parameterizing identifiers reliably; validate then interpolate.
        cur.execute(f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY %s", (password or "",))
        cur.execute(f"GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{user}'@'{host}'")
        cur.execute("FLUSH PRIVILEGES")
        conn.commit()
        print(f"[OK] Ensured MySQL user + grants: {user}@{host} -> {db_name}")
    finally:
        cur.close()


def _seed_admin(conn, db_name: str) -> None:
    email = _env("ISHARIO_SEED_ADMIN_EMAIL")
    password = _env("ISHARIO_SEED_ADMIN_PASSWORD")
    if not email or not password:
        return

    cur = conn.cursor()
    try:
        cur.execute(f"USE `{db_name}`")
        cur.execute(
            "INSERT INTO admin (email, password) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE password = VALUES(password)",
            (email, password),
        )
        conn.commit()
        print(f"[OK] Seeded admin: {email}")
    finally:
        cur.close()


def main(argv: Iterable[str] | None = None) -> int:
    repo = _repo_root()
    ishario_db_name = _env("ISHARIO_DB_NAME", "ishario_db") or "ishario_db"
    signease_db_name = _env("SIGNEASE_DB_NAME", "signease") or "signease"
    app_user_host = _env("MYSQL_APP_USER_HOST", "localhost") or "localhost"

    ishario_sql = repo / "db" / "ishario_db.sql"
    signease_sql = repo / "db" / "signease.sql"

    if not ishario_sql.exists() or not signease_sql.exists():
        raise SystemExit(f"Schema files not found under: {repo / 'db'}")

    print("[..] Connecting to MySQL (admin connection)...")
    conn = _connect_admin()
    try:
        print(f"[..] Ensuring databases: {ishario_db_name}, {signease_db_name}")
        _ensure_database(conn, ishario_db_name)
        _ensure_database(conn, signease_db_name)

        # Optional: create a non-root app user and grant privileges (recommended for local dev).
        _ensure_user_and_grants(
            conn,
            db_name=ishario_db_name,
            user=_env("ISHARIO_DB_USER"),
            password=_env("ISHARIO_DB_PASS", ""),
            host=app_user_host,
        )
        _ensure_user_and_grants(
            conn,
            db_name=signease_db_name,
            user=_env("SIGNEASE_DB_USER", _env("ISHARIO_DB_USER")),
            password=_env("SIGNEASE_DB_PASS", _env("ISHARIO_DB_PASS", "")),
            host=app_user_host,
        )

        print(f"[..] Applying schema: {ishario_sql.name} -> {ishario_db_name}")
        _execute_sql(conn, f"USE `{ishario_db_name}`;\n{_read_sql(ishario_sql)}\n")
        conn.commit()

        print(f"[..] Applying schema: {signease_sql.name} -> {signease_db_name}")
        _execute_sql(conn, f"USE `{signease_db_name}`;\n{_read_sql(signease_sql)}\n")
        conn.commit()

        _seed_admin(conn, ishario_db_name)

        print("[OK] MySQL initialization complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

