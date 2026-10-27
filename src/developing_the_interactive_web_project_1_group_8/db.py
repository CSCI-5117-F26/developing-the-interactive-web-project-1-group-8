from datetime import timedelta, datetime
from developing_the_interactive_web_project_1_group_8.CacheBackendPostgres import (
    CacheBackendPostgres,
)
from boardgamegeek import BGGClient, BGGError
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit
from dotenv import load_dotenv
import http.client
import random
import secrets
from datetime import datetime, timedelta

from developing_the_interactive_web_project_1_group_8.event_times import (
    CENTRAL,
    is_event_completed,
)


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


# warm up the cache so that the first request doesn't take forever
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
            SELECT id, display_name, username, email, bio, profile_pic, setup_complete,
                hosted_events_visibility, attending_events_visibility,
                friends_visibility, followers_visibility
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


def update_profile_privacy(
    user_id,
    hosted_events_visibility,
    attending_events_visibility,
    friends_visibility,
    followers_visibility,
):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE users
            SET hosted_events_visibility = %s, attending_events_visibility = %s,
                friends_visibility = %s, followers_visibility = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id
            """,
            (
                hosted_events_visibility,
                attending_events_visibility,
                friends_visibility,
                followers_visibility,
                user_id,
            ),
        ).fetchone()


def update_username(id, username, display_name):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE users
            SET username = %s, display_name = %s, setup_complete = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, auth0_sub, display_name, bio, profile_pic, setup_complete, username
            """,
            (username, display_name, True, id),
        ).fetchone()


# ---------- Event ----------
def get_all_events():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from events")
            return cur.fetchall()


def get_all_event_info(user_id=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
                FROM events e
                """,
                (user_id,),
            )
            events = cur.fetchall()
    return add_game_info(get_visible_events(events, user_id))


def get_all_user_event_info(id):
    return get_all_event_info(id)


def get_event_info(id, user_id=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count,
                    (SELECT u.display_name FROM users u WHERE u.id = e.hostid) AS display_name,
                    (SELECT u.username FROM users u WHERE u.id = e.hostid) AS host_username
                FROM events e
                WHERE e.id = %s
                """,
                (user_id, id),
            )
            event = cur.fetchone()
    if event is None:
        return None
    add_game_info([event])
    return event


def get_event(id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from events where id = %s", (id,))
            return cur.fetchone()


def get_user_events(user_id, viewer_id=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
                FROM events e
                WHERE e.hostID = %s
                """,
                (viewer_id, user_id),
            )
            events = cur.fetchall()
    return add_game_info(get_visible_events(events, viewer_id, user_id))


def get_user_events_attending(user_id, viewer_id=None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
                FROM events e
                JOIN event_participation ea ON e.id = ea.id
                WHERE ea.user_interested = %s AND NOT ea.is_host AND e.time > now()
                """,
                (viewer_id, user_id),
            )
            events = cur.fetchall()
    return add_game_info(get_visible_events(events, viewer_id, user_id))


def get_all_friend_events(id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending
                FROM events e JOIN friends f ON f.followed = e.hostid
                WHERE f.follower = %s
                ORDER BY e.time DESC
                """,
                (id, id),
            )
            events = cur.fetchall()
    return add_game_info(get_visible_events(events, id))


def get_events_in_week(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                    (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count,
                    EXISTS (SELECT 1 FROM event_participation p
                        WHERE p.id = e.id AND p.user_interested = %s) AS is_attending
                FROM events e
                WHERE e.time >= NOW() AND e.time < NOW() + INTERVAL '7 days' AND e.status <> 'Canceled'
                ORDER BY e.time
                """,
                (user_id,),
            )
            events = cur.fetchall()
    return add_game_info(get_visible_events(events, user_id))


def create_event(
    name,
    gameID,
    hostID,
    address,
    time,
    expected_duration,
    min_attendees,
    max_attendees,
    description,
    status,
    visibility="public",
    public_id=None,
):
    # https://docs.python.org/3/library/secrets.html#secrets.token_urlsafe
    public_id = secrets.token_urlsafe(32) if public_id is None else public_id
    with pool.connection() as conn:
        with conn.cursor() as cur:
            categories = bgg.game(game_id=gameID).categories
            print(categories)
            cur.execute(
                """
                INSERT INTO events (name, gameID, hostID, address, time, expected_duration,
                min_attendees, max_attendees, description, status, game_categories, public_id, visibility)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    name,
                    gameID,
                    hostID,
                    address,
                    time,
                    expected_duration,
                    min_attendees,
                    max_attendees,
                    description,
                    status,
                    categories,
                    public_id,
                    visibility,
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
    min_attendees,
    max_attendees,
    description,
    status,
    visibility,
):
    values = (
        name,
        gameID,
        address,
        time,
        expected_duration,
        min_attendees,
        max_attendees,
        description,
        status,
        visibility,
    )
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events SET name = %s, gameID = %s, address = %s, time = %s,
                expected_duration = %s, min_attendees = %s, max_attendees = %s, description = %s,
                status = %s, visibility = %s
                WHERE id = %s AND
                    (name, gameID, address, time, expected_duration,
                     min_attendees, max_attendees, description, status, visibility)
                    IS DISTINCT FROM (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING name
                """,
                values + (id,) + values,
            )
            event = cur.fetchone()
            if event:
                message = (
                    f"The details of the event '{event['name']}' have been updated."
                )
                notify_event_attendees(conn, id, "event_update", message)
            return event is not None


def get_all_event_attendees(event_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
            SELECT u.id, u.username, u.display_name, u.profile_pic FROM users u, event_participation p
            WHERE u.id = p.user_interested AND p.id = %s AND NOT p.is_host
            """,
                (event_id,),
            )
            return cur.fetchall()


def cancel_event(id):
    with pool.connection() as conn:
        event = conn.execute(
            """
            UPDATE events SET status = 'Canceled'
            WHERE id = %s AND status <> 'Canceled'
            RETURNING name
            """,
            (id,),
        ).fetchone()
        if event:
            message = f"The event '{event['name']}' has been canceled"
            notify_event_attendees(conn, id, "event_cancelation", message)
        return event is not None


def restore_event(id):
    with pool.connection() as conn:
        event = conn.execute(
            """
            UPDATE events SET status = 'scheduled'
            WHERE id = %s AND status = 'Canceled'
            RETURNING name
            """,
            (id,),
        ).fetchone()
        if event:
            message = f"The event '{event['name']}' has been restored and its info can be viewed below"
            notify_event_attendees(conn, id, "event_cancelation", message)
        return event is not None


def delete_event(id):
    with pool.connection() as conn:
        event = conn.execute(
            "SELECT name FROM events WHERE id = %s FOR UPDATE", (id,)
        ).fetchone()
        if event is None:
            return False
        message = f"The event '{event['name']}' has been permanently canceled"
        notify_event_attendees_of_delete(conn, id, "event_cancelation", message)
        remove_event_followers(conn, id)
        conn.execute("DELETE FROM events WHERE id = %s", (id,))
        return True


def attend_event(event_id, user_id, is_host=False):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM events WHERE id = %s FOR UPDATE", (event_id,))
            event = cur.fetchone()
            if event is None:
                return None
            if not is_host and (
                event["status"] == "Canceled"
                or is_event_completed(event)
                or event["hostid"] == user_id
            ):
                return None
            if not is_host:
                cur.execute(
                    "SELECT COUNT(*) AS count FROM event_participation WHERE id = %s",
                    (event_id,),
                )
                attendee_count = cur.fetchone()["count"]
                if attendee_count >= event["max_attendees"]:
                    return None
            cur.execute(
                """
                INSERT INTO event_participation (id, user_interested, is_host)
                VALUES (%s, %s, %s)
                ON CONFLICT (id, user_interested) DO NOTHING
                RETURNING *
                """,
                (event_id, user_id, is_host),
            )
            participation = cur.fetchone()
            if participation and not is_host:
                user = conn.execute(
                    "SELECT username FROM users WHERE id = %s", (user_id,)
                ).fetchone()
                message = f"{user['username']} has committed to attend your event."
                notify_event_host(conn, event_id, "host_update", message, user_id)
            return participation


def decommit_event(event_id, user_id):
    with pool.connection() as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id = %s FOR UPDATE", (event_id,)
        ).fetchone()
        if event is None or is_event_completed(event):
            return False
        result = conn.execute(
            """
            DELETE FROM event_participation
            WHERE id = %s AND user_interested = %s AND NOT is_host
            """,
            (event_id, user_id),
        )
        removed = result.rowcount > 0
        if removed:
            user = conn.execute(
                "SELECT username FROM users WHERE id = %s", (user_id,)
            ).fetchone()
            message = f"{user['username']} has decommitted from attending your event."
            notify_event_host(conn, event_id, "host_update", message, user_id)
        return removed


def remove_event_followers(conn, event_id):
    return conn.execute(
        """
        DELETE FROM event_participation
        WHERE id = %s
        """,
        (event_id,),
    ).rowcount


def create_notification(conn, recipient_id, kind, message, user_id=None, event_id=None):
    return conn.execute(
        """
        INSERT INTO notifications (recipient_id, kind, message, user_id, event_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (recipient_id, kind, message, user_id, event_id),
    ).fetchone()


def notify_event_attendees(conn, event_id, kind, message):
    return conn.execute(
        """
        INSERT INTO notifications (recipient_id, kind, message, user_id, event_id)
        SELECT p.user_interested, %s, %s, e.hostid, e.id
        FROM event_participation p JOIN events e ON e.id = p.id
        WHERE p.id = %s AND NOT p.is_host
        """,
        (kind, message, event_id),
    ).rowcount


def notify_event_attendees_of_delete(conn, event_id, kind, message):
    return conn.execute(
        """
        INSERT INTO notifications (recipient_id, kind, message, user_id)
        SELECT p.user_interested, %s, %s, e.hostid
        FROM event_participation p JOIN events e ON e.id = p.id
        WHERE p.id = %s AND NOT p.is_host
        """,
        (kind, message, event_id),
    ).rowcount


def notify_event_host(conn, event_id, kind, message, user_id):
    return conn.execute(
        """
        INSERT INTO notifications (recipient_id, kind, message, user_id, event_id)
        SELECT hostid, %s, %s, %s, id
        FROM events
        WHERE id = %s
        """,
        (kind, message, user_id, event_id),
    ).rowcount


def get_notifications(recipient_id, limit=21, offset=0):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT n.id, n.kind, n.message, n.event_id, n.is_read, n.created_at,
                users.display_name AS user_name, users.username AS user_username,
                e.public_id AS event_public_id
            FROM notifications n
            LEFT JOIN users ON users.id = n.user_id
            LEFT JOIN events e ON e.id = n.event_id
            WHERE n.recipient_id = %s
            ORDER BY n.created_at DESC, n.id DESC
            LIMIT %s OFFSET %s
            """,
            (recipient_id, limit, offset),
        ).fetchall()


def get_unread_notification_count(recipient_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) AS unread_count FROM notifications
            WHERE recipient_id = %s AND NOT is_read
            """,
            (recipient_id,),
        ).fetchone()["unread_count"]


def mark_notification_read(notification_id, recipient_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            UPDATE notifications SET is_read = TRUE
            WHERE id = %s AND recipient_id = %s AND NOT is_read
            """,
            (notification_id, recipient_id),
        )
        return result.rowcount > 0


def mark_all_notifications_read(recipient_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            UPDATE notifications SET is_read = TRUE
            WHERE recipient_id = %s AND NOT is_read
            """,
            (recipient_id,),
        ).rowcount


def clear_friend_request_notifications(conn, first_user_id, second_user_id):
    conn.execute(
        """
        DELETE FROM notifications WHERE kind = 'friend_request' AND (
            (recipient_id = %s AND user_id = %s)
            OR (recipient_id = %s AND user_id = %s)
        )
        """,
        (first_user_id, second_user_id, second_user_id, first_user_id),
    )


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
                ORDER BY u.username
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
                SELECT u.id, u.username, u.display_name, u.profile_pic
                FROM users u
                JOIN friends f ON u.id = f.follower
                WHERE f.followed = %s
                ORDER BY u.username
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


def get_received_friend_requests(user_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.profile_pic
            FROM friend_requests r
            JOIN users u ON u.id = r.requester_id
            WHERE r.recipient_id = %s AND NOT r.accepted
            ORDER BY u.username
            """,
            (user_id,),
        ).fetchall()


def get_sent_friend_requests(user_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.profile_pic
            FROM friend_requests r
            JOIN users u ON u.id = r.recipient_id
            WHERE r.requester_id = %s AND NOT r.accepted
            ORDER BY u.username
            """,
            (user_id,),
        ).fetchall()


def send_friend_request(requester_id, recipient_id):
    with pool.connection() as conn:
        sent_request = conn.execute(
            """
            INSERT INTO friend_requests (requester_id, recipient_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            RETURNING requester_id, recipient_id
            """,
            (requester_id, recipient_id),
        ).fetchone()
        if sent_request:
            conn.execute(
                """
                INSERT INTO friends (follower, followed)
                VALUES (%s, %s)
                ON CONFLICT (follower, followed) DO NOTHING
                """,
                (requester_id, recipient_id),
            )
            create_notification(
                conn,
                recipient_id,
                "friend_request",
                "You received a friend request.",
                user_id=requester_id,
            )
        return sent_request


def cancel_friend_request(requester_id, recipient_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            DELETE FROM friend_requests
            WHERE requester_id = %s AND recipient_id = %s AND NOT accepted
            """,
            (requester_id, recipient_id),
        )
        removed = result.rowcount > 0
        if removed:
            clear_friend_request_notifications(conn, requester_id, recipient_id)
        return removed


def accept_friend_request(requester_id, recipient_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            UPDATE friend_requests r
            SET accepted = TRUE
            WHERE r.requester_id = %s AND r.recipient_id = %s
                AND NOT r.accepted
                AND NOT EXISTS (
                    SELECT 1 FROM blocked b
                    WHERE (b.blocking = r.requester_id AND b.blocked = r.recipient_id)
                       OR (b.blocking = r.recipient_id AND b.blocked = r.requester_id)
                )
            """,
            (requester_id, recipient_id),
        )
        accepted = result.rowcount > 0
        if accepted:
            conn.execute(
                """
                INSERT INTO friends (follower, followed)
                VALUES (%s, %s), (%s, %s)
                ON CONFLICT (follower, followed) DO NOTHING
                """,
                (requester_id, recipient_id, recipient_id, requester_id),
            )
            clear_friend_request_notifications(conn, requester_id, recipient_id)
            create_notification(
                conn,
                requester_id,
                "friend_accepted",
                "Your friend request was accepted.",
                user_id=recipient_id,
            )
        return accepted


def create_friend_invitation(owner_id, token, max_uses, duration_hours):
    with pool.connection() as conn:
        return conn.execute(
            """
            INSERT INTO friend_invitations (owner_id, token, max_uses, expires_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP + %s * INTERVAL '1 hour')
            RETURNING id
            """,
            (owner_id, token, max_uses, duration_hours),
        ).fetchone()


def get_active_friend_invitations(owner_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT id, token, max_uses, use_count, created_at, expires_at
            FROM friend_invitations
            WHERE owner_id = %s AND NOT revoked
                AND expires_at > clock_timestamp() AND use_count < max_uses
            ORDER BY created_at DESC, id DESC
            """,
            (owner_id,),
        ).fetchall()


def get_friend_invitation(token):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT id, owner_id,
                CASE
                    WHEN revoked THEN 'revoked'
                    WHEN expires_at <= clock_timestamp() THEN 'expired'
                    WHEN use_count >= max_uses THEN 'exhausted'
                    ELSE 'active'
                END AS status
            FROM friend_invitations WHERE token = %s
            """,
            (token,),
        ).fetchone()


def revoke_friend_invitation(invitation_id, owner_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            UPDATE friend_invitations SET revoked = TRUE
            WHERE id = %s AND owner_id = %s AND NOT revoked
                AND expires_at > clock_timestamp() AND use_count < max_uses
            """,
            (invitation_id, owner_id),
        )
        return result.rowcount > 0


def accept_friend_invite(token, recipient_id):
    with pool.connection() as conn:
        invitation = conn.execute(
            """
            SELECT id, owner_id FROM friend_invitations
            WHERE token = %s FOR UPDATE
            """,
            (token,),
        ).fetchone()
        if invitation is None or invitation["owner_id"] == recipient_id:
            return False

        available = conn.execute(
            """
            SELECT 1 FROM friend_invitations
            WHERE id = %s AND NOT revoked
                AND expires_at > clock_timestamp() AND use_count < max_uses
            """,
            (invitation["id"],),
        ).fetchone()
        if available is None:
            return False

        owner_id = invitation["owner_id"]
        blocked = conn.execute(
            """
            SELECT 1 FROM blocked
            WHERE (blocking = %s AND blocked = %s)
               OR (blocking = %s AND blocked = %s)
            """,
            (owner_id, recipient_id, recipient_id, owner_id),
        ).fetchone()
        if blocked:
            return False

        updated = conn.execute(
            """
            UPDATE friend_requests SET accepted = TRUE
            WHERE NOT accepted AND (
                (requester_id = %s AND recipient_id = %s)
                OR (requester_id = %s AND recipient_id = %s)
            )
            """,
            (owner_id, recipient_id, recipient_id, owner_id),
        )
        if updated.rowcount == 0:
            inserted = conn.execute(
                """
                INSERT INTO friend_requests (requester_id, recipient_id, accepted)
                VALUES (%s, %s, TRUE)
                ON CONFLICT DO NOTHING
                RETURNING requester_id
                """,
                (owner_id, recipient_id),
            ).fetchone()
            if inserted is None:
                return False

        conn.execute(
            """
            INSERT INTO friends (follower, followed)
            VALUES (%s, %s), (%s, %s)
            ON CONFLICT (follower, followed) DO NOTHING
            """,
            (owner_id, recipient_id, recipient_id, owner_id),
        )
        conn.execute(
            """
            UPDATE friend_invitations SET use_count = use_count + 1
            WHERE id = %s
            """,
            (invitation["id"],),
        )
        clear_friend_request_notifications(conn, owner_id, recipient_id)
        return True


def remove_friend(first_user_id, second_user_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            DELETE FROM friend_requests
            WHERE accepted AND (
                (requester_id = %s AND recipient_id = %s)
                OR (requester_id = %s AND recipient_id = %s)
            )
            """,
            (first_user_id, second_user_id, second_user_id, first_user_id),
        )
        return result.rowcount > 0


def are_friends(first_user_id, second_user_id):
    with pool.connection() as conn:
        result = conn.execute(
            """
            SELECT 1 FROM friend_requests
            WHERE accepted AND (
                (requester_id = %s AND recipient_id = %s)
                OR (requester_id = %s AND recipient_id = %s)
            )
            """,
            (first_user_id, second_user_id, second_user_id, first_user_id),
        ).fetchone()
        return result is not None


def get_friends(user_id):
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT u.id, u.username, u.display_name, u.profile_pic
            FROM users u
            JOIN friend_requests r
                ON (r.requester_id = %s AND r.recipient_id = u.id)
                OR (r.recipient_id = %s AND r.requester_id = u.id)
            WHERE r.accepted
            ORDER BY u.username
            """,
            (user_id, user_id),
        ).fetchall()


# ---------- Block ----------


def get_blocked_users(user_id):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.display_name, u.profile_pic
                FROM users u
                JOIN blocked b ON u.id = b.blocked
                WHERE b.blocking = %s
                ORDER BY u.username
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
            blocked = cur.rowcount > 0
            cur.execute(
                """
                DELETE FROM friend_requests
                WHERE (requester_id = %s AND recipient_id = %s)
                   OR (requester_id = %s AND recipient_id = %s)
                """,
                (blocking_id, blocked_id, blocked_id, blocking_id),
            )
            cur.execute(
                """
                DELETE FROM friends
                WHERE (follower = %s AND followed = %s)
                   OR (follower = %s AND followed = %s)
                """,
                (blocking_id, blocked_id, blocked_id, blocking_id),
            )
            clear_friend_request_notifications(conn, blocking_id, blocked_id)
            return blocked


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


def search_events(
    q,
    user_id,
    game,
    category,
    category_name,
    min_players,
    max_players,
    duration,
    recency,
    full,
    pending,
    played,
):
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
            query, params = build_query(
                q,
                user_id,
                game,
                category,
                category_name,
                min_players,
                max_players,
                duration,
                recency,
                full,
                pending,
                played,
            )
            events = cur.execute(query, params).fetchall()
    return add_game_info(get_visible_events(events, user_id))


def build_query(
    q,
    user_id,
    game,
    category,
    category_name,
    min_players,
    max_players,
    duration,
    recency,
    full,
    pending,
    played,
):
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
    if category:
        conditions.append("%s = ANY(e.game_categories)")
        params.append(category_name)
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
        start = datetime.now(CENTRAL).replace(hour=0, minute=0, second=0, microsecond=0)
        if recency == "today":
            end = start + timedelta(days=1)
        else:
            end = start + timedelta(weeks=1)
        params.extend([start, end])
    if full:
        conditions.append(
            "(SELECT COUNT(*) FROM event_participation ep2 WHERE ep2.id = e.id) < e.max_attendees"
        )
    if pending:
        conditions.append("e.status = 'pending'")

    print(params)
    cond_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""SELECT e.*, (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count,
        EXISTS (SELECT 1 FROM event_participation p
            WHERE p.id = e.id AND p.user_interested = %s) AS is_attending
        FROM events e LEFT JOIN event_participation ep ON ep.id = e.id
        {cond_clause}
        GROUP BY e.id"""
    return query, [user_id] + params


# https://bgg-api.readthedocs.io/en/stable/modules.html#boardgamegeek.api.BGGClient.game
def add_game_info(events):
    games = {}
    for event in events:
        event["is_completed"] = is_event_completed(event)
        game_id = event["gameid"]
        if game_id is None or game_id <= 0:
            event["game_name"] = None
            event["image_url"] = None
            event["game_categories"] = []
            continue
        if game_id not in games:
            try:
                games[game_id] = bgg.game(game_id=game_id)
            except BGGError:
                games[game_id] = None
        game = games[game_id]
        event["game_name"] = game.name if game else None
        event["image_url"] = (game.image or game.thumbnail) if game else None
        if game:
            event["game_categories"] = game.categories
    return events


def get_event_by_public_id(public_id):
    with pool.connection() as conn:
        event = conn.execute(
            """SELECT e.*,
            (SELECT COUNT(*) FROM event_participation p WHERE p.id = e.id) AS count
            FROM events e WHERE public_id = %s""",
            (public_id,),
        ).fetchone()
    if event is not None:
        event["is_completed"] = is_event_completed(event)
    return event


def get_visible_events(events, viewer_id, profile_owner_id=None):
    if viewer_id is not None and viewer_id == profile_owner_id:
        return events
    friend_ids = set()
    if viewer_id is not None:
        friend_ids = {friend["id"] for friend in get_friends(viewer_id)}
    visible = []
    for event in events:
        if event["visibility"] == "public":
            visible.append(event)
        elif event["visibility"] == "friends" and (
            event["hostid"] == viewer_id or event["hostid"] in friend_ids
        ):
            visible.append(event)
    return visible

def game_exists(game_id):
    try:
        bgg.game(game_id=game_id)
        return True
    except BGGError:
        return False