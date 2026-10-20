from datetime import timedelta
from developing_the_interactive_web_project_1_group_8.CacheBackendPostgres import CacheBackendPostgres, PostgresCache, PostgresDict
from boardgamegeek import BGGClient, CacheBackendMemory
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit
from dotenv import load_dotenv

load_dotenv()

pool = ConnectionPool(
    os.environ["DATABASE_URL"], open=True, kwargs={"row_factory": dict_row}
)
atexit.register(pool.close)




bgg = BGGClient(
    os.environ["BGG_API_KEY"],
    cache=CacheBackendPostgres(pool=pool, ttl=timedelta(hours=1000000000)),
    requests_per_minute=120
    # cache=CacheBackendMemory(ttl=3600),
)


for i in range(10):
    
    for game in ["Catan", "Terraforming Mars", "Gloomhaven"]:
        try:
            print(f"Fetching {game}...")
            result = bgg.game(game)
            # bgg.requests_session.
            print(f"Fetched {game}: {result.name}")
        except Exception as e:
            print(f"Error fetching {game}: {e}")



def get_user(user_id):
    with pool.connection() as conn:
        return conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


def get_or_create_user(user_info):
    display_name = user_info.get("name")
    picture = user_info.get("picture")

    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO users (auth0_sub, display_name, profile_pic, auth0_avatar_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (auth0_sub) DO NOTHING
            """,
            (user_info["sub"], display_name[:80], picture, picture),
        )
        return conn.execute(
            "SELECT * FROM users WHERE auth0_sub = %s", (user_info["sub"],)
        ).fetchone()


def get_public_user(user_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT id, display_name, bio, profile_pic
            FROM users WHERE id = %s
            """,
            (user_id,),
        ).fetchone()


def update_profile(user_id, display_name, bio, profile_pic):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE users
            SET display_name = %s, bio = %s, profile_pic = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, auth0_sub, display_name
            """,
            (display_name, bio, profile_pic, user_id),
        ).fetchone()
