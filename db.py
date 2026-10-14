"""
db.py - ONE place that knows how to talk to the database.

* On your laptop (no DATABASE_URL)  -> SQLite file  inventotrack.db
* On Render (DATABASE_URL is set)   -> PostgreSQL

The rest of the code just calls  db.execute("... WHERE id = ?", (5,))  and never
cares which database is underneath.
"""
import os
import sqlite3

from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):               # older style that Render/Heroku sometimes give
        url = "postgresql://" + url[len("postgres://"):]
    return url


def using_postgres():
    return bool(database_url())


def sqlite_path():
    return os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "inventotrack.db"))


class Database:
    def __init__(self, conn, postgres):
        self.conn = conn
        self.postgres = postgres

    # Postgres can lock the rows we are about to change; SQLite locks the whole file instead.
    @property
    def lock_clause(self):
        return " FOR UPDATE" if self.postgres else ""

    def execute(self, sql, params=()):
        if self.postgres:
            cur = self.conn.cursor()
            cur.execute(sql.replace("?", "%s"), tuple(params))   # SQLite uses ?, PostgreSQL uses %s
            return cur
        return self.conn.execute(sql, tuple(params))

    def insert(self, sql, params, id_column):
        """INSERT and return the new row's id."""
        if self.postgres:
            cur = self.execute(sql + f" RETURNING {id_column}", params)
            return cur.fetchone()[id_column]
        return self.execute(sql, params).lastrowid

    def begin_write(self):
        """Start a transaction that no other writer can enter at the same time."""
        if not self.postgres:
            self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect():
    """Open a NEW connection (used by scripts and by get_db)."""
    if using_postgres():
        import psycopg
        from psycopg.rows import dict_row
        return Database(psycopg.connect(database_url(), row_factory=dict_row), True)
    conn = sqlite3.connect(sqlite_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return Database(conn, False)


def get_db():
    """One connection per request, re-used inside that request."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(error=None):
    database = g.pop("db", None)
    if database is not None:
        try:
            database.rollback()          # anything not committed is thrown away
        finally:
            database.close()


def init_schema(database):
    """Create all tables (safe to run many times)."""
    name = "schema_postgres.sql" if database.postgres else "schema.sql"
    with open(os.path.join(BASE_DIR, name), encoding="utf-8") as f:
        script = f.read()
    if database.postgres:
        for statement in [s.strip() for s in script.split(";") if s.strip()]:
            database.execute(statement)
        database.commit()
    else:
        database.conn.executescript(script)
