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


def update_profile(user_id, display_name, bio):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE users
            SET display_name = %s, bio = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, auth0_sub, display_name
            """,
            (display_name, bio, user_id),
        ).fetchone()
