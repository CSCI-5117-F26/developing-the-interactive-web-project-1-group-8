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
from datetime import datetime, timedelta


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
        user = conn.execute(
            "SELECT id FROM users WHERE username = %s", (username,)
        ).fetchone()
        return user["id"] if user else None


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
      RETURNING id, auth0_sub, display_name, bio, profile_pic, username, setup_complete
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
                SELECT e.*, g.name AS game_name, g.image_url,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
                FROM events e LEFT JOIN games g ON g.id = e.gameid
                WHERE e.hostID = %s
                """,
                (user_id,),
            )
            return cur.fetchall()


def get_user_events_attending(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*, g.name AS game_name, g.image_url,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
                FROM events e
                LEFT JOIN games g ON g.id = e.gameid
                JOIN event_participation ea ON e.id = ea.id
                WHERE ea.user_interested = %s
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
                ON CONFLICT (id, user_interested) DO NOTHING
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
                SELECT u.id, u.username, u.display_name, u.profile_pic, u.bio
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
          description, status, created_at
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


def search_events(q, user_id, game, category, min_players, max_players, duration, recency, full, pending, played):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # cur.execute(
            #     """
            #     SELECT e.*, g.name AS game_name, g.image_url,
            #         (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
            #     FROM events e LEFT JOIN games g ON g.id = e.gameid
            #     WHERE LOWER(e.name) LIKE LOWER(%s)
            #     """,
            #     (f"%{name_query}%",),
            # )
            # return cur.fetchall()
            query, params = build_query(q, user_id, game, category, min_players, max_players, duration, recency, full, pending, played)
            return cur.execute(query, params).fetchall()

def build_query(q, user_id, game, category, min_players, max_players, duration, recency, full, pending, played):
    conditions = []
    params = []
    conditions.append("LOWER(e.name) LIKE LOWER(%s)")
    params.append(f"%{q}%")

    # Filter for game id
    if game:
        conditions.append("e.gameid = %s")
        params.append(game)
    elif user_id and played:
        conditions.append(
            """e.gameid IN (
                SELECT DISTINCT e2.gameid
                FROM events e2
                JOIN event_participation ep ON ep.id = e2.id
                WHERE ep.user_interested = %s
            )"""
        )
        params.append(user_id)

    if min_players is not None:
        conditions.append("e.min_attendees >= %s")
        params.append(min_players)
    if max_players is not None:
        conditions.append("e.max_attendees <= %s")
        params.append(max_players)
    if duration is not None:
        min_duration = duration - 1
        max_duration = duration + 1
        conditions.append("e.expected_duration >= %s")
        conditions.append("e.expected_duration <= %s")
        params.append(min_duration)
        params.append(max_duration)
    if recency:
        conditions.append("e.time >= %s AND e.time < %s")
        start = datetime.now().replace(hour=0,minute=0,second=0, microsecond=0)
        if recency == 'today':
            end = start + timedelta(days=1)
        else:
            end = start + timedelta(weeks=1)
        params.extend([start, end])
    if full:
        conditions.append("(SELECT COUNT(*) FROM event_participation ep2 WHERE ep2.id = e.id) < e.max_attendees")
    if pending:
        conditions.append("e.status = 'pending'")

    cond_clause ="WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""SELECT e.*, (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
        FROM events e LEFT JOIN event_participation ep ON ep.id = e.id
        {cond_clause}
        GROUP BY e.id"""
    return query, params
