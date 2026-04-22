"""
Veritabanı Bağlantısı ve İşlemleri
SQLite backend — MySQL arayüzüyle uyumlu
"""
import re
import sqlite3
from datetime import datetime

from flask import g, current_app


# ─────────────────────────────────────────────────────────────────────────────
# Query dönüştürücü  (MySQL → SQLite sözdizimi)
# ─────────────────────────────────────────────────────────────────────────────

def _adapt(query: str) -> str:
    """MySQL sorgusunu SQLite'a uyarla — hiçbir model/controller değişmez."""
    # %s → ?
    query = query.replace('%s', '?')
    # INSERT IGNORE → INSERT OR IGNORE
    query = re.sub(r'\bINSERT\s+IGNORE\b', 'INSERT OR IGNORE', query, flags=re.IGNORECASE)
    # LIMIT x,y  →  LIMIT y OFFSET x
    query = re.sub(
        r'\bLIMIT\s+(\d+)\s*,\s*(\d+)',
        lambda m: f'LIMIT {m.group(2)} OFFSET {m.group(1)}',
        query, flags=re.IGNORECASE
    )
    return query


# ─────────────────────────────────────────────────────────────────────────────
# Datetime dönüştürücü
# SQLite DATETIME sütunları string döner — MySQL gibi datetime nesnesi yapalım
# ─────────────────────────────────────────────────────────────────────────────

_DT_PATTERNS = [
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d',
]

def _parse_datetime(value):
    """SQLite'ın döndürdüğü datetime string'ini datetime nesnesine çevir."""
    if not isinstance(value, str):
        return value
    # Hızlı ön kontrol: tarih formatına benzemiyor mu?
    if not re.match(r'^\d{4}-\d{2}-\d{2}', value):
        return value
    for fmt in _DT_PATTERNS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return value  # parse edilemezse orijinali döndür


def _coerce_row(row: dict) -> dict:
    """Satırdaki tüm değerleri datetime parse'dan geçir."""
    return {k: _parse_datetime(v) for k, v in row.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Cursor wrapper  — fetchone/fetchall her zaman dict döner
# ─────────────────────────────────────────────────────────────────────────────

class _CursorWrapper:
    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, query, params=None):
        query = _adapt(query)
        if params is not None:
            self._cur.execute(query, params)
        else:
            self._cur.execute(query)
        return self

    def executemany(self, query, seq):
        query = _adapt(query)
        self._cur.executemany(query, seq)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        d = dict(row) if hasattr(row, 'keys') else row
        return _coerce_row(d)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        return [_coerce_row(dict(r) if hasattr(r, 'keys') else r) for r in rows]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()

    def __iter__(self):
        return iter(self.fetchall())

    def __getattr__(self, name):
        return getattr(self._cur, name)


# ─────────────────────────────────────────────────────────────────────────────
# Connection proxy  — mysql.connection.cursor() / commit() / rollback()
# ─────────────────────────────────────────────────────────────────────────────

class _ConnectionProxy:
    """
    mysql.connection ile erişilen nesne.
    base.py ve controller'lardaki doğrudan .cursor() / .commit() çağrılarını karşılar.
    """

    def cursor(self, *args, **kwargs):
        """DictCursor gibi argümanlar yoksayılır; wrapper zaten dict döndürür."""
        return _CursorWrapper(_get_connection().cursor())

    def commit(self):
        conn = g.get('_db')
        if conn:
            conn.commit()

    def rollback(self):
        conn = g.get('_db')
        if conn:
            conn.rollback()

    def close(self):
        pass  # teardown halleder


# ─────────────────────────────────────────────────────────────────────────────
# MySQL proxy  — `from app.utils.database import mysql`  değişmez
# ─────────────────────────────────────────────────────────────────────────────

class _MySQLProxy:
    @property
    def connection(self):
        return _ConnectionProxy()

    def init_app(self, app):
        pass  # init_db halleder


mysql = _MySQLProxy()


# ─────────────────────────────────────────────────────────────────────────────
# SQLite bağlantı yönetimi  (request/context başına tek bağlantı)
# ─────────────────────────────────────────────────────────────────────────────

def _get_connection() -> sqlite3.Connection:
    if '_db' not in g:
        path = current_app.config.get('SQLITE_PATH', 'sqlite.db')
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        g._db = conn
    return g._db


def _teardown(exc):
    conn = g.pop('_db', None)
    if conn is not None:
        if exc:
            conn.rollback()
        else:
            conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Dışa açık API  — imzalar değişmedi
# ─────────────────────────────────────────────────────────────────────────────

def init_db(app):
    """app/__init__.py'de çağrılır — değişmez."""
    app.teardown_appcontext(_teardown)
    app.logger.info('[DB] SQLite  →  %s', app.config.get('SQLITE_PATH', 'sqlite.db'))


def get_dict_cursor() -> _CursorWrapper:
    """Sözlük imleçi döndür"""
    return _CursorWrapper(_get_connection().cursor())


def get_cursor() -> _CursorWrapper:
    """Normal imleç döndür"""
    return _CursorWrapper(_get_connection().cursor())


def commit_db():
    """Değişiklikleri kaydet"""
    try:
        conn = g.get('_db')
        if conn:
            conn.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# MySQLdb uyumluluk katmanı
# `import MySQLdb` veya `import MySQLdb.cursors` olan dosyalar patlamasın
# ─────────────────────────────────────────────────────────────────────────────

try:
    import MySQLdb as _real_mysqldb  # noqa: F401
except ImportError:
    import types as _types
    import sys as _sys

    _mod = _types.ModuleType('MySQLdb')
    _cur_mod = _types.ModuleType('MySQLdb.cursors')

    class _DictCursor:
        pass

    _cur_mod.DictCursor = _DictCursor

    class _DBError(Exception):
        pass

    class _OperationalError(_DBError):
        pass

    class _ProgrammingError(_DBError):
        pass

    _mod.cursors          = _cur_mod
    _mod.Error            = _DBError
    _mod.OperationalError = _OperationalError
    _mod.ProgrammingError = _ProgrammingError

    _sys.modules['MySQLdb']         = _mod
    _sys.modules['MySQLdb.cursors'] = _cur_mod