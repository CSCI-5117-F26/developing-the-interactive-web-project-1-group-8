from dotenv import load_dotenv
import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit

pool = None
load_dotenv()


def setup():
    global pool
    # note use of `[]` over `.get()` is intentional here. I want a hard-and-fast crash if environment is not setup right.
    pool = ConnectionPool(
        os.environ["DATABASE_URL"], open=True, kwargs={"row_factory": dict_row}
    )
    # I'm not _actually_ convinced this is required, but the docs said to do it!
    atexit.register(pool.close)


def setup_db():
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    auth0_sub TEXT UNIQUE NOT NULL,
                    display_name VARCHAR(80) NOT NULL,
                    username VARCHAR(30) UNIQUE,
                    email TEXT,
                    password_hash VARCHAR(255),
                    bio TEXT DEFAULT '',
                    profile_pic TEXT,
                    auth0_avatar_url TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    gameID INTEGER NOT NULL,
                    hostID INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
                    calendarID INTEGER,
                    address VARCHAR(255) NOT NULL,
                    time TIMESTAMP,
                    expected_duration FLOAT NOT NULL,
                    max_attendees INTEGER NOT NULL,
                    description VARCHAR(4095) NOT NULL,
                    status VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    bgg_id INTEGER UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description VARCHAR(4095) NOT NULL,
                    rank INTEGER NOT NULL,
                    average_rating FLOAT NOT NULL,
                    num_ratings INTEGER NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    category VARCHAR(255) NOT NULL,
                    num_players INTEGER NOT NULL,
                    play_time INTEGER NOT NULL,
                    publisher VARCHAR(255) NOT NULL,
                    release_date DATE NOT NULL,
                    average_age INTEGER NOT NULL,
                    theme VARCHAR(255) NOT NULL,
                    tags TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS event_calendars (
                    id SERIAL,
                    user_available INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (id, user_available),
                    time_available tsrange NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS event_participation (
                    id SERIAL,
                    user_interested INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (id, user_interested),
                    is_host BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS friends (
                    follower INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    followed INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (follower, followed),
                    date_followed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blocked (
                    blocking INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (blocking, blocked),
                    date_blocked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()
setup()