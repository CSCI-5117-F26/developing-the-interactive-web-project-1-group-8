from datetime import timedelta
from developing_the_interactive_web_project_1_group_8.CacheBackendPostgres import (
    CacheBackendPostgres,
    PostgresCache,
    PostgresDict,
)
from boardgamegeek import BGGClient, CacheBackendMemory
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit
from dotenv import load_dotenv
import http.client
import random


load_dotenv()

pool: ConnectionPool
bgg: BGGClient


def setup():
    global pool
    global bgg
    # note use of `[]` over `.get()` is intentional here. I want a hard-and-fast crash if environment is not setup right.
    pool = ConnectionPool(
        os.environ["DATABASE_URL"], open=True, kwargs={"row_factory": dict_row}
    )
    bgg = BGGClient(
        os.environ["BGG_API_KEY"],
        cache=CacheBackendPostgres(pool=pool, ttl=timedelta(hours=20)),
        requests_per_minute=1200,
    )
    # I'm not _actually_ convinced this is required, but the docs said to do it!
    atexit.register(pool.close)


# User DB Functions


def get_user_from_id(user_id):
    with pool.connection() as conn:
        return conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


def get_id_for_username(username):
    with pool.connection() as conn:
        return conn.execute(
            "SELECT id FROM users WHERE username = %s", (username,)
        ).fetchone()


def get_sub(login_sub):
    with pool.connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE auth0_sub = %s", (login_sub,)
        ).fetchone()


def get_or_create_user(user_info):
    picture = user_info.get("picture")
    email = user_info.get("email")
    login_sub = user_info.get("sub")
    temp_display_name = "temp-user-" + str(random.randrange(0, 10000))

    with pool.connection() as conn:
        conn.execute(
            """
      INSERT INTO users (display_name, auth0_sub, email, bio, auth0_avatar_url, setup_complete)
      VALUES (%s, %s, %s, %s, %s, %s)
      ON CONFLICT (auth0_sub) DO NOTHING
      """,
            (temp_display_name, login_sub, email, "", picture, False),
        )
        return conn.execute(
            "SELECT * FROM users WHERE auth0_sub = %s", (login_sub,)
        ).fetchone()


def get_public_user(username):
    with pool.connection() as conn:
        return conn.execute(
            """
      SELECT id, display_name, username, email, bio, profile_pic, setup_complete
      FROM users WHERE username = %s
      """,
            (username,),
        ).fetchone()


# TO-DO: MASSIVE WIP ON THIS
def update_auth0_img(img_url, auth0_id):
    cnxn = http.client.HTTPSConnection("")

    payload = {"user_metadata": {"picture": img_url}}

    headers = {
        "authorization": "Bearer MGMT_API_ACCESS_TOKEN",
        "content-type": "application/json",
    }

    cnxn.request(
        "PATCH",
        f"/{os.environ['AUTH0_DOMAIN']}/api/v2/users/{auth0_id}",
        payload,
        headers,
    )

    res = cnxn.getresponse()
    data = res.read()


def update_profile(id, display_name, bio, profile_pic):
    with pool.connection() as conn:
        return conn.execute(
            """
      UPDATE users
      SET display_name = %s, bio = %s, profile_pic = %s,
        updated_at = CURRENT_TIMESTAMP
      WHERE id = %s
      RETURNING id, auth0_sub, display_name, bio, profile_pic
      """,
            (display_name, bio, profile_pic, id),
        ).fetchone()


def update_username(id, username):
    with pool.connection() as conn:
        return conn.execute(
            """
      UPDATE users
      SET username = %s, display_name = %s, setup_complete = %s, updated_at = CURRENT_TIMESTAMP
      WHERE id = %s
      RETURNING id, auth0_sub, display_name, bio, profile_pic, setup_complete, username
      """,
            (username, username, True, id),
        ).fetchone()


# ---------- Event ----------
def get_all_events():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from events")
            return cur.fetchall()


def get_all_event_info():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""select e.*, (select count(*) from event_participation p where p.id = e.id), 
            (select g.name as game_name from games g where g.id = e.gameid), 
            (select g.image_url from games g where g.id = e.gameid)
            from events e""")
            return cur.fetchall()


def get_event_info(id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """select e.*, (select count(*) from event_participation p where p.id = e.id), 
            (select g.name as game_name from games g where g.id = e.gameid), 
            (select g.image_url from games g where g.id = e.gameid),
            (select u.display_name from users u where u.id = e.hostid)
            from events e 
            where e.id = %s""",
                (id,),
            )
            return cur.fetchone()


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


def create_event(
    name,
    gameID,
    hostID,
    address,
    time,
    expected_duration,
    max_attendees,
    description,
    status,
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (name, gameID, hostID, address, time, expected_duration, max_attendees, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    name,
                    gameID,
                    hostID,
                    address,
                    time,
                    expected_duration,
                    max_attendees,
                    description,
                    status,
                ),
            )
            return cur.fetchone()


def update_event(
    id,
    name,
    gameID,
    address,
    time,
    expected_duration,
    max_attendees,
    description,
    status,
):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events SET name = %s, gameID = %s, address = %s,
                time = %s, expected_duration = %s, max_attendees = %s, description = %s,
                status = %s
                WHERE id = %s
                """,
                (
                    name,
                    gameID,
                    address,
                    time,
                    expected_duration,
                    max_attendees,
                    description,
                    status,
                    id,
                ),
            )
        return conn.commit()


def attend_event(event_id, user_id, is_host):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_participation (id, user_interested, is_host)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (event_id, user_id, is_host),
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


def follow_user(following_id, followed_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
        INSERT INTO friends (follower, followed)
        VALUES(%s, %s)
        ON CONFLICT (follower, followed) DO NOTHING
        """,
                (following_id, followed_id),
            )
            followed = cur.rowcount > 0  # Returns True if a row was inserted
            conn.commit()
    return followed


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


def get_friend_events(user):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            user_id = cur.execute(
                "SELECT id FROM users WHERE display_name = %s", (user,)
            ).fetchone()["id"]
            cur.execute(
                """
        SELECT name, gameID, address, time, expected_duration, max_attendees,
          description, status, created_at, updated_at
        FROM events INNER JOIN friends
        ON events.hostID = friends.followed
        WHERE friends.follower = %s
        """,
                (user_id,),
            )
            return cur.fetchall()


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
                (f"%{name_query}%",),
            )
            return cur.fetchall()
