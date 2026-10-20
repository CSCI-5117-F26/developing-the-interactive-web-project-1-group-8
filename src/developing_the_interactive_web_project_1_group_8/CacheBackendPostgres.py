"""Postgres cache backend. For usage details, see :ref:`Backends: Postgres <postgres>`.

.. automodsumm:: requests_cache.backends.postgres
   :classes-only:
   :nosignatures:
"""
from psycopg import Connection
from psycopg_pool.abc import CT
import requests
from contextlib import contextmanager
import threading
import requests_cache
from boardgamegeek import BGGValueError
from boardgamegeek.cache import CacheBackend, StrOrPath
from psycopg_pool import ConnectionPool

from logging import getLogger
from typing import Iterable, List, Optional, Iterator


from requests_cache._utils import get_valid_kwargs, decode, encode
from requests_cache.serializers import SerializerType, pickle_serializer, utf8_encoder
from requests_cache import BaseCache, BaseStorage, CachedSession

DEFAULT_TTL_OFFSET = 3600
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
        namespace='http_cache',
        serializer: Optional[SerializerType] = None,
        **kwargs,
    ):
        super().__init__(cache_name=namespace, **kwargs)
        skwargs = {'serializer': serializer, **kwargs} if serializer else kwargs
        self.pool = pool

        self.responses = PostgresDict(pool=self.pool, table_name="responses", **skwargs)
        self.redirects = PostgresDict(pool=self.pool, lock=self.responses._lock, serializer=None, **kwargs)



class PostgresDict(BaseStorage):
    """A dictionary-like interface for Postgres operations.

    **Notes:**
        * All keys will be encoded as bytes, and all values will be serialized
        * Supports TTL
    """

    def __init__(
        self,
        pool: ConnectionPool[CT],
        serializer: Optional[SerializerType] = pickle_serializer,
        **kwargs,
    ):
        super().__init__(serializer=serializer, **kwargs)
        connection_kwargs = get_valid_kwargs(ConnectionPool.__init__, kwargs)
        self.pool = pool
        self._lock = kwargs.pop('lock', threading.RLock())
        self.table_name = kwargs.pop('table_name', 'cache')
        
        self.init_db();

    def init_db(self):
        """Initialize the database, if it hasn't already been"""
        self.close()
        with self.pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS %s (
                    key BYTEA PRIMARY KEY,
                    value BYTEA NOT NULL,
                    expires TIMESTAMPTZ
                );
                """,
                (self.table_name,),
            )
            
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS expires_idx ON %s(expires);
                """,
                (self.table_name,),
                )
            
            conn.commit()
                

    def _bkey(self, key: str) -> bytes:
        return encode(f'{self.table_name}:{key}')

    def _bkeys(self, keys: Iterable[str]) -> List[bytes]:
        return [self._bkey(key) for key in keys]

    def __contains__(self, key) -> bool:
        with self.pool.connection() as con:
            result = con.execute("""SELECT 1 FROM %s WHERE key = %s;""", (self.table_name,self._bkey(key),))
            return bool(result.fetchone())

    def __getitem__(self, key):
        with self.pool.connection() as con:
            result = con.execute("""
                        SELECT value FROM %s WHERE key = %s;
                        """,
                        (self.table_name,self._bkey(key),)
                    ).fetchone()
            if result is None:
                raise KeyError
            return self.deserialize(key, result[0])

    def __setitem__(self, key, item):
        with self.pool.connection() as con:
            expires_delta = getattr(item, 'expires_delta', None)
            if expires_delta is not None:
                con.execute(
                        """
                        INSERT INTO %s (key, value, expires) VALUES (%s, %s, %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires = EXCLUDED.expires;
                        """,
                        (self.table_name, self._bkey(key), self.serialize(item), expires_delta,)
                    )
            return

            

    def __delitem__(self, key):
        # if not self.connection.delete(self._bkey(key)):
        #     raise KeyError
        with self.pool.connection() as con:
            result = con.execute("""DELETE FROM %s WHERE key = %s""", (self.table_name, self._bkey(key),))
            if result.rowcount == 0:
                raise KeyError

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(list(self.keys()))

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache, without raising errors for missing keys"""
        with self.pool.connection() as con:
            con.execute("""DELETE FROM %s WHERE key = ANY(%s)""", (self.table_name, self._bkeys(keys),))

    def clear(self):
        self.bulk_delete(self.keys())

    def close(self):
        # self.connection.close()
        pass

    def keys(self):
        """Return a list of all keys in the cache"""
        with self.pool.connection() as con:
            result = con.execute("""SELECT key FROM %s""", (self.table_name,)).fetchall()
            return [decode(row[0]) for row in result]


    def items(self):
        for k in self.keys():
            yield (k, self[k])

    def values(self):
        for k in self.keys():
            yield self[k]



class CacheBackendPostgres(CacheBackend):
    """Cache HTTP requests in a PostgreSQL database"""
    cache: requests.Session

    def __init__(self, pool: ConnectionPool[CT], ttl: int, fast_save: bool = True):
        try:
            int(ttl)
        except ValueError as e:
            raise BGGValueError from e

        self.cache = CachedSession(backend=PostgresCache(pool=pool, ttl=ttl), fast_save=fast_save, allowable_codes=(200,))