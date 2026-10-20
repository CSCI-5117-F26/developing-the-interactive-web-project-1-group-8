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
    cache=CacheBackendPostgres(pool=pool, ttl=timedelta(hours=20)),
    requests_per_minute=1200
)


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


# ---------- Profile ----------
def update_profile(user_id, display_name, bio, profile_pic):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE users
            SET display_name = %s, bio = %s, profile_pic = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, auth0_sub, display_name, bio, profile_pic
            """,
            (display_name, bio, profile_pic, user_id,),
        ).fetchone()


# ---------- Event ----------
def get_all_events():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from events")
            return cur.fetchall()


def get_event(id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from events where id = %s", (id,))
            return cur.fetchone()

def get_user_events(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM events
                WHERE hostID = %s
                """,
                (user_id,),
            )
            return cur.fetchall()

def get_user_events_attending(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*
                FROM events e
                JOIN event_participation ea ON e.id = ea.id
                WHERE ea.id = %s
                """,
                (user_id,),
            )
            return cur.fetchall()

def create_event(name, gameID, hostID, calendarID, address, time, expected_duration, max_attendees, description, status):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (name, gameID, hostID, calendarID, address, time, expected_duration, max_attendees, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (name, gameID, hostID, calendarID, address, time, expected_duration, max_attendees, description, status),
            )
            return cur.fetchone()


# ---------- Follow ----------

def get_following(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.display_name, u.profile_pic, u.bio
                FROM users u
                JOIN friends f ON u.id = f.followed
                WHERE f.follower = %s
                """,
                (user_id,),
            )
            return cur.fetchall()

def follow_user(follower_id, followed_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO friends (follower, followed)
                VALUES (%s, %s)
                ON CONFLICT (follower, followed) DO NOTHING
                """,
                (follower_id, followed_id),
            )
            return cur.rowcount > 0  # Returns True if a row was inserted

def unfollow_user(follower_id, followed_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM friends
                WHERE follower = %s AND followed = %s
                """,
                (follower_id, followed_id),
            )
            return cur.rowcount > 0  # Returns True if a row was deleted

def is_following(follower_id, followed_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM friends
                WHERE follower = %s AND followed = %s
                """,
                (follower_id, followed_id),
            )
            return cur.fetchone() is not None


def get_followers(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.display_name, u.profile_pic
                FROM users u
                JOIN friends f ON u.id = f.follower
                WHERE f.followed = %s
                """,
                (user_id,),
            )
            return cur.fetchall()

def get_follower_count(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS follower_count
                FROM friends
                WHERE followed = %s
                """,
                (user_id,),
            )
            result = cur.fetchone()
            return result["follower_count"] if result else 0

# ---------- Block ----------

def get_blocked_users(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.display_name, u.profile_pic
                FROM users u
                JOIN blocked b ON u.id = b.blocked
                WHERE b.blocking = %s
                """,
                (user_id,),
            )
            return cur.fetchall()

def block_user(blocking_id, blocked_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO blocked (blocking, blocked)
                VALUES (%s, %s)
                ON CONFLICT (blocking, blocked) DO NOTHING
                """,
                (blocking_id, blocked_id),
            )
            return cur.rowcount > 0  # Returns True if a row was inserted

def unblock_user(blocking_id, blocked_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM blocked
                WHERE blocking = %s AND blocked = %s
                """,
                (blocking_id, blocked_id),
            )
            return cur.rowcount > 0  # Returns True if a row was deleted

def is_blocked(blocking_id, blocked_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM blocked
                WHERE blocking = %s AND blocked = %s
                """,
                (blocking_id, blocked_id),
            )
            return cur.fetchone() is not None

# ---------- Search ----------

def search_events(name_query):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM events
                WHERE LOWER(name) LIKE LOWER(%s)
                """, 
                (f"%{name_query}%",))
            return cur.fetchall()