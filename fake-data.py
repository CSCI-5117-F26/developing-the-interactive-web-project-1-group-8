import datetime
from collections import OrderedDict
import random
from faker import Faker
import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import os
import atexit

from developing_the_interactive_web_project_1_group_8 import db

pool = None
fake = Faker()
Faker.seed(0)  # Seed for reproducibility

def setup():
    global pool
    # note use of `[]` over `.get()` is intentional here. I want a hard-and-fast crash if environment is not setup right.
    pool = ConnectionPool(
        os.environ["DATABASE_URL"], open=True, kwargs={"row_factory": dict_row}
    )
    # I'm not _actually_ convinced this is required, but the docs said to do it!
    atexit.register(pool.close)


def generate_fake_users(num_users=10):
    fake = Faker()
    users = []
    for _ in range(num_users):
        user = {
            "sub": fake.uuid4(),
            "name": fake.name(),
            "username": fake.user_name(),
            "email": fake.email(),
            "password_hash": fake.password(length=12),
            "bio": fake.text(max_nb_chars=200),
            "profile_pic": fake.image_url(),
            "auth0_avatar_url": fake.image_url(),
        }
        e = db.get_or_create_user(user)
        db.update_profile(
            user_id=e["id"],
            display_name=user["name"],
            bio=user["bio"],
            profile_pic=user["profile_pic"],
        )
        user["user_id"] = e["id"]
        users.append(user)

    #have the shitgoblins follow eachother
    for user in users:
        i = fake.random_int(min=0, max=3)
        for _ in range(i):
            other_user = random.choice(users)
            if other_user != user:
                db.follow_user(
                    user.get("user_id"),
                    other_user.get("user_id"),
                )
              


        stati = ["cancelled", "scheduled","pending"]
    # make them create events, goddamn it
    for user in users:
        i = fake.random_choices(elements=OrderedDict([(0,0.4), (1,0.3), (2,0.2), (3,0.1)]), length=1)[0]
        for _ in range(i):
            ev = {
                "name": fake.sentence(nb_words=4),
                "gameID": fake.random_int(min=1, max=1000),
                "description": fake.text(max_nb_chars=200),
                "date": fake.date_this_year(),
                "time": fake.date_time(),
                "location": fake.address(),
                "duration": fake.time_delta().days,
                "max_attendees": fake.random_int(min=1, max=100),
                "status": random.choice(stati),
            }
            db.create_event(
                name=ev["name"],
                gameID=ev["gameID"],
                hostID=user.get("user_id"),
                calendarID=None,
                address=ev["location"],
                time=ev["time"],
                expected_duration=ev["duration"],
                max_attendees=ev["max_attendees"],
                description=ev["description"],
                status=ev["status"],
            )
            # Create a fake event for each user
            pass

    return users


generate_fake_users(10)