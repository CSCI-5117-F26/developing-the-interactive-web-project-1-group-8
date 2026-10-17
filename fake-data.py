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
        users.append(user)


    return users


generate_fake_users(10)