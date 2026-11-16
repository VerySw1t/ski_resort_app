"""Доступ к PostgreSQL. На каждый запрос открывается своё соединение."""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/ski_resort"
)


@contextmanager
def connect():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql, params=()):
    """SELECT: возвращает список словарей."""
    with connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def execute(sql, params=()):
    """INSERT / UPDATE / DELETE."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def rows(sql, params=()):
    """SELECT: возвращает список кортежей (для списков выбора и отчётов)."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
