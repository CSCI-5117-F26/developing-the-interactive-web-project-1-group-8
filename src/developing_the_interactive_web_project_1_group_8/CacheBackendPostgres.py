"""Postgres cache backend. For usage details, see :ref:`Backends: Postgres <postgres>`.

.. automodsumm:: requests_cache.backends.postgres
   :classes-only:
   :nosignatures:
"""

from datetime import timedelta
from time import time
from cmath import sqrt
from psycopg import sql
from psycopg import Connection
from psycopg_pool.abc import CT
import requests
from contextlib import contextmanager
import threading

# import requests_cache
from boardgamegeek import BGGValueError
from boardgamegeek.cache import CacheBackend, StrOrPath
from psycopg_pool import ConnectionPool

from logging import getLogger
from typing import Iterable, List, Optional, Iterator, Tuple


from requests_cache._utils import get_valid_kwargs, decode, encode
from requests_cache.serializers import SerializerType, pickle_serializer, utf8_encoder
from requests_cache import BaseCache, BaseStorage, CachedSession

DEFAULT_TTL_OFFSET = 67
logger = getLogger(__name__)


class PostgresCache(BaseCache):
    """Postgres cache backend.

    Args:
        namespace: Postgres namespace
        connection: Postgres pool instance to use instead of creating a new one
        ttl: Use Postgres TTL to automatically delete expired items
        ttl_offset: Additional time to wait before deleting expired items, in seconds
        kwargs: Additional keyword arguments for :py:class:`postgres.client.Postgres`
    """

    def __init__(
        self,
        pool: ConnectionPool[CT],
        namespace="http_cache",
        serializer: Optional[SerializerType] = None,
        ttl: bool = True,
        ttl_offset: timedelta = timedelta(hours=1),
        **kwargs,
    ):
        super().__init__(cache_name=namespace, **kwargs)
        skwargs = {"serializer": serializer, **kwargs} if serializer else kwargs

        self.pool = pool
        self.responses = PostgresDict(
            pool=pool,
            table_name=namespace + "_responses",
            ttl=ttl,
            ttl_offset=ttl_offset,
            **skwargs,
        )
        self.redirects = PostgresDict(
            pool=pool,
            lock=self.responses._lock,
            table_name=namespace + "_redirects",
            serializer=utf8_encoder,
            **kwargs,
        )


class PostgresDict(BaseStorage):
    """A dictionary-like interface for Postgres operations.

    **Notes:**
        * All keys will be encoded as bytes, and all values will be serialized
        * Supports TTL
    """

    def __init__(
        self,
        pool: Optional[ConnectionPool[CT]] = None,
        serializer: Optional[SerializerType] = pickle_serializer,
        ttl: bool = True,
        ttl_offset: timedelta = timedelta(hours=1),
        **kwargs,
    ):
        super().__init__(serializer=serializer, **kwargs)
        connection_kwargs = get_valid_kwargs(ConnectionPool.__init__, kwargs)
        self.pool = pool or ConnectionPool(**connection_kwargs)
        self._lock = kwargs.pop("lock", threading.RLock())
        self.table_name = str(kwargs.pop("table_name", "cache"))

        self.ttl = ttl
        self.ttl_offset = ttl_offset

        self.init_db()

    def init_db(self):
        """Initialize the database, if it hasn't already been"""
        self.close()
        with self.pool.connection() as conn:
            conn.execute(
                sql.SQL(
                    """CREATE TABLE IF NOT EXISTS {0} (
                        key BYTEA PRIMARY KEY,
                        value BYTEA NOT NULL,
                        expires INT NOT NULL
                    );"""
                ).format(sql.Identifier(self.table_name))
            )

            conn.execute(
                sql.SQL(
                    """CREATE INDEX IF NOT EXISTS expires_idx ON {0}(expires);"""
                ).format(sql.Identifier(self.table_name))
            )

            conn.commit()

    def _bkey(self, key: str) -> bytes:
        return encode(f"{self.table_name}:{key}")

    def _bkeys(self, keys: Iterable[str]) -> List[bytes]:
        return [self._bkey(key) for key in keys]

    def __contains__(self, key) -> bool:
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""SELECT 1 FROM {0} WHERE key = {1};""").format(
                    sql.Identifier(self.table_name), sql.Literal(self._bkey(key))
                )
            )
            # print(f"Checking if key {key} exists in table {self.table_name}: {result.fetchone() is not None}")
            return bool(result.fetchone())

    def __getitem__(self, key):
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""
                        SELECT value FROM {0} WHERE key = {1};
                        """).format(
                    sql.Identifier(self.table_name), sql.Literal(self._bkey(key))
                )
            ).fetchone()
            # print(f"Getting item with key {key} from table {self.table_name}: {result != None}")
            if result is None:
                raise KeyError
            return self.deserialize(key, result["value"])

    def __setitem__(self, key, item):
        with self.pool.connection() as con:
            expires_delta = getattr(item, "expires_delta", None)
            # print(f"Setting item with key {key} and expires_delta {expires_delta}")
            expires = int(time() + expires_delta) if expires_delta is not None else 0
            con.execute(
                sql.SQL("""
                    INSERT INTO {0} (key, value, expires) VALUES ({1}, {2}, {3})
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires = EXCLUDED.expires;
                    """).format(
                    sql.Identifier(self.table_name),
                    sql.Literal(self._bkey(key)),
                    sql.Literal(self.serialize(item)),
                    sql.Literal(expires),
                )
            )
            return

    def __delitem__(self, key):
        # if not self.connection.delete(self._bkey(key)):
        #     raise KeyError
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""DELETE FROM {0} WHERE key = {1}""").format(
                    sql.Identifier(self.table_name), sql.Literal(self._bkey(key))
                )
            )
            if result.rowcount == 0:
                raise KeyError

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(list(self.keys()))

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache, without raising errors for missing keys"""
        with self.pool.connection() as con:
            con.execute(
                sql.SQL("""DELETE FROM {0} WHERE key = ANY({1})""").format(
                    sql.Identifier(self.table_name), sql.Literal(self._bkeys(keys))
                )
            )

    def clear(self):
        self.bulk_delete(self.keys())

    def count(self, expired: bool = True) -> int:
        """Count number of responses, optionally excluding expired"""
        # print(f"Counting items in table {self.table_name}, expired={expired}")
        if not expired:
            with self.pool.connection() as con:
                res = con.execute(
                    sql.SQL(
                        """SELECT COUNT(*) FROM {0} WHERE expires = 0 or expires > {1}"""
                    ).format(sql.Identifier(self.table_name), sql.Literal(time()))
                ).fetchone()
                if res is None:
                    return 0
                return res["count"]
        return len(list(self.keys()))

    def close(self):
        # self.connection.close()
        pass

    def keys(self):
        """Return a list of all keys in the cache"""
        # print(f"Fetching all keys from table {self.table_name}")
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""SELECT key FROM {0}""").format(
                    sql.Identifier(self.table_name)
                )
            ).fetchall()
            return [
                decode(row["key"]).removeprefix(f"{self.table_name}:") for row in result
            ]

    def items(self):
        """Return a list of all key-value pairs in the cache"""
        # print(f"Fetching all items from table {self.table_name}")
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""SELECT key, value FROM {0}""").format(
                    sql.Identifier(self.table_name)
                )
            ).fetchall()
            return [
                (
                    decode(row["key"]).removeprefix(f"{self.table_name}:"),
                    self.deserialize(
                        decode(row["key"]).removeprefix(f"{self.table_name}:"),
                        row["value"],
                    ),
                )
                for row in result
            ]

    def values(self):
        """Return a list of all values in the cache"""
        # print(f"Fetching all values from table {self.table_name}")
        with self.pool.connection() as con:
            result = con.execute(
                sql.SQL("""SELECT value FROM {0}""").format(
                    sql.Identifier(self.table_name)
                )
            ).fetchall()
            return [self.deserialize(None, row["value"]) for row in result]


class CacheBackendPostgres(CacheBackend):
    """Cache HTTP requests in a PostgreSQL database"""

    cache: requests.Session

    def __init__(
        self, pool: ConnectionPool[CT], ttl: timedelta, fast_save: bool = True
    ):
        # try:
        #     int(ttl)
        # except ValueError as e:
        #     raise BGGValueError from e
        self.cache = CachedSession(
            backend=PostgresCache(namespace="bgg", pool=pool, ttl_offset=ttl),
            expire_after=ttl,
            fast_save=fast_save,
            allowable_codes=(200,),
        )
