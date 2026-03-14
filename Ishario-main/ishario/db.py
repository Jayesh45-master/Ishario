from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import mysql.connector


@dataclass(frozen=True)
class DbUnavailable(RuntimeError):
    db_name: str
    hint: str
    original: BaseException

    def __str__(self) -> str:
        return f"{self.db_name}: {self.original}"


def env_db_config(prefix: str) -> Dict[str, Any]:
    """
    Build a mysql.connector config from env vars.

    Expected vars:
      {prefix}_HOST, {prefix}_USER, {prefix}_PASS, {prefix}_NAME
    """
    host = os.environ.get(f"{prefix}_HOST", "localhost")
    user = os.environ.get(f"{prefix}_USER", "root")
    password = os.environ.get(f"{prefix}_PASS", "")
    database = os.environ.get(f"{prefix}_NAME")
    port_raw = os.environ.get(f"{prefix}_PORT")
    port = int(port_raw) if port_raw else 3306

    cfg: Dict[str, Any] = {"host": host, "port": port, "user": user, "password": password}
    if database:
        cfg["database"] = database
    return cfg


def connect_mysql(cfg: Dict[str, Any], *, db_label: str):
    try:
        return mysql.connector.connect(connect_timeout=5, **cfg)
    except mysql.connector.Error as e:
        raise DbUnavailable(
            db_name=db_label,
            hint="Set *_DB_HOST/_USER/_PASS/_NAME env vars and run: python scripts/init_mysql.py",
            original=e,
        ) from e


def close_quietly(cursor, conn) -> None:
    try:
        if cursor:
            cursor.close()
    finally:
        if conn:
            conn.close()


def is_schema_or_auth_error(err: BaseException) -> bool:
    if not isinstance(err, mysql.connector.Error):
        return False
    errno = getattr(err, "errno", None)
    return errno in {1044, 1045, 1049, 1146}  # access denied / auth / unknown db / no such table


def db_unavailable_json(e: DbUnavailable) -> Dict[str, Any]:
    return {
        "error": "db_unavailable",
        "db": e.db_name,
        "hint": e.hint,
    }
