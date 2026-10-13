from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit
from dotenv import load_dotenv
import http.client


load_dotenv()

pool = None

def setup():
  global pool
  # note use of `[]` over `.get()` is intentional here. I want a hard-and-fast crash if environment is not setup right.
  pool = ConnectionPool(
      os.environ["DATABASE_URL"], open=True, kwargs={"row_factory": dict_row}
  )
  # I'm not _actually_ convinced this is required, but the docs said to do it!
  atexit.register(pool.close)

# User DB Functions

def get_user(user_id):
  with pool.connection() as conn:
    return conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()


def get_or_create_user(user_info):
  display_name = user_info.get("name")
  picture = user_info.get("picture")
  email = user_info.get("email")

  with pool.connection() as conn:
    conn.execute(
      """
      INSERT INTO users (auth0_sub, display_name, email, bio, auth0_avatar_url)
      VALUES (%s, %s, %s, %s, %s)
      ON CONFLICT (auth0_sub) DO NOTHING
      """,
      (user_info["sub"], display_name[:80], email, "", picture),
    )
    return conn.execute(
        "SELECT * FROM users WHERE auth0_sub = %s", (user_info["sub"],)
    ).fetchone()


def get_public_user(username):
  with pool.connection() as conn:
    return conn.execute(
      """
      SELECT display_name, email, bio, profile_pic
      FROM users WHERE display_name = %s
      """,
    (username,),
    ).fetchone()

# TO-DO: MASSIVE WIP ON THIS
def update_auth0_img(img_url, auth0_id):
  cnxn = http.client.HTTPSConnection("")

  payload = {"user_metadata": {"picture": img_url}}

  headers = {
    'authorization': "Bearer MGMT_API_ACCESS_TOKEN",
    'content-type': "application/json"
  }

  cnxn.request("PATCH", f"/{os.environ["AUTH0_DOMAIN"]}/api/v2/users/{auth0_id}", payload, headers)

  res = cnxn.getresponse()
  data = res.read()

def update_profile(display_name, bio, profile_pic):
  with pool.connection() as conn:
    return conn.execute(
      """
      UPDATE users
      SET display_name = %s, bio = %s, profile_pic = %s,
        updated_at = CURRENT_TIMESTAMP
      WHERE display_name = %s
      RETURNING id, auth0_sub, display_name
      """,
    (display_name, bio, profile_pic, display_name),
    ).fetchone()


# Event DB functions

def get_event(id):
  with pool.connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM events WHERE id = %s", (id,))
      return cur.fetchone()

def get_all_events():
  with pool.connection() as conn:
    with conn.cursor() as cur:
      cur.execute("SELECT * FROM events")
      return cur.fetchall()

def get_or_create_event(event_info):
  name = event_info.get("name")
  game_id = event_info.get("game")
  host_id = event_info.get("username")
  address = event_info.get("address")
  expected_duration = event_info.get("duration")
  num_attendees = event_info.get("attendees")
  desc = event_info.get("desc")
  status = event_info.get("status")

  with pool.connection() as conn:
      conn.execute(
        """
        INSERT INTO events (name, gameID, hostID, address, expected_duration, max_attendees, description, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (name, game_id, host_id, address, expected_duration, num_attendees, desc, status),
      )
      return conn.execute(
          "SELECT * FROM events WHERE name = %s ORDER BY created_at DESC", (name)
      ).fetchone()

def delete_event(event_id):
  with pool.connection() as conn, conn.cursor() as cur:
    cur.execute(
      """
      DELETE FROM events
      WHERE id = %s
      """,
      (event_id,)
    )
    conn.commit()

def add_availability(time_info):
  user = time_info.get("username")
  event = time_info.get("event_id")
  availability = time_info.get("availability")

  with pool.connection() as conn:
    with conn.cursor() as cur:
      user_id = cur.execute("SELECT * FROM users WHERE display_name = %s", (user,))
      cur.execute(
        """
        INSERT INTO event_calendars (event_id, user_available, time_available)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (event, user_id, availability)
      )
      conn.commit()

def remove_availability(time_info):
  user = time_info.get("username")
  event = time_info.get("event_id")
  with pool.connection() as conn:
      with conn.cursor() as cur:
        user_id = cur.execute("SELECT * FROM users WHERE display_name = %s", (user,))
        cur.execute(
          """
          DELETE FROM event_calendars
          WHERE event_id = %s AND user_available = %s
          """,
          (event, user_id)
        )
        conn.commit()

def add_user_to_event(participation_info):
  user = participation_info.get("username")
  event = participation_info.get("event_id")
  is_host = participation_info.get("hosting")

  with pool.connection() as conn:
    with conn.cursor() as cur:
      user_id = cur.execute("SELECT id FROM users WHERE display_name = %s", (user,))
      cur.execute(
        """
        INSERT INTO event_participation (event_id, user_interested, is_host)
        VALUES (%s, %s, %s)
        """,
        (event, user_id, is_host)
      )
      conn.commit()

def remove_interest(participation_info):
  user = participation_info.get("username")
  event = participation_info.get("event_id")
  with pool.connection() as conn:
    with conn.cursor() as cur:
      user_id = cur.execute("SELECT * FROM users WHERE display_name = %s", (user,))
      cur.execute(
        """
        DELETE FROM event_participation
        WHERE event_id = %s AND user_interested = %s
        """,
        (event, user_id)
      )
      conn.commit()

# Friend functionalities

def follow_user(follow_info):
  following_user = follow_info.get("current_user")
  followed_user = follow_info.get("followed_user")

  with pool.connection() as conn:
    with conn.cursor() as cur:
      following_id = cur.execute("SELECT id FROM users WHERE display_name = %s", (following_user,))
      followed_id = cur.execute("SELECT id FROM users WHERE display_name = %s", (followed_user,))

      cur.execute(
        """
        INSERT INTO friends (follower, followed)
        VALUES(%s, %s)
        """,
        (following_id, followed_id)
      )
      conn.commit()

def get_friend_events(user):
  with pool.connection() as conn:
    with conn.cursor() as cur:
      user_id = cur.execute("SELECT id FROM users WHERE display_name = %s", (user,))
      cur.execute(
        """
        SELECT name, gameID, address, time, expected_duration, max_attendees,
          description, status, created_at, updated_at
        FROM events INNER JOIN friends
        ON events.hostID = friends.followed
        WHERE friends.follower = %s
        """,
        (user_id,)
      )
      return cur.fetchall()