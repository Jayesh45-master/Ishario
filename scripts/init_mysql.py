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

