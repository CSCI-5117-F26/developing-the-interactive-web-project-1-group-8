from asyncio import events
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

fake = Faker()
Faker.seed(0)  # Seed for reproducibility
db.setup()


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
            id=e["id"],
            display_name=user["name"],
            bio=user["bio"],
            profile_pic=user["profile_pic"],
        )
        user["user_id"] = e["id"]

        db.update_username(
            id=e["id"], username=user["username"], display_name=user["name"]
        )
        users.append(user)

    # have the shitgoblins follow eachother
    for user in users:
        i = fake.random_int(min=0, max=10)
        for _ in range(i):
            other_user = random.choice(users)
            if other_user != user:
                if fake.boolean(chance_of_getting_true=50):
                    db.follow_user(
                        user.get("user_id"),
                        other_user.get("user_id"),
                    )
                else:
                    db.send_friend_request(
                        user.get("user_id"),
                        other_user.get("user_id"),
                    )
                    db.accept_friend_request(
                        user.get("user_id"),
                        other_user.get("user_id"),
                    )

        stati = ["cancelled", "scheduled", "pending"]

    # make them create events, goddamn it
    events = []
    for user in users:
        i = fake.random_choices(
            elements=OrderedDict([(0, 0.4), (1, 0.3), (2, 0.2), (3, 0.1)]), length=1
        )[0]
        for _ in range(i):
            # make sure the game we grab exists
            while True:
                gameid = fake.random_int(min=1, max=10000)
                try:
                    game = db.bgg.game(game_id=gameid)
                    break
                except:
                    pass

            game_words = game.name.split()

            # I ASKED AI TO GENERATE A BUNCH OF STUFF
            game_words.extend(
                [
                    "Game",
                    "Stuff",
                    "Event",
                    "Fun",
                    "Party",
                    "Activity",
                    "Night",
                    "Day",
                    "Play",
                    "Enjoy",
                    "Friend",
                    "Social",
                    "Gaming",
                    "Board",
                    "Tabletop",
                    "Hangout",
                    "UMN",
                    "Time",
                    "Yippee",
                    "Exciting",
                    "Thrilling",
                    "Enthusiastic",
                    "Boring",
                ]
            )
            game_words.extend(game.categories)
            game_words.extend(game.mechanics)

            ev = {
                "name": fake.sentence(nb_words=3, ext_word_list=game_words),
                "gameID": gameid,
                "description": fake.text(max_nb_chars=200),
                "date": fake.date_this_year(),
                # time should be formatted 2026-10-14 10:31:00, from now
                "time": fake.date_time_between_dates(
                    datetime.datetime.now(),
                    datetime.datetime.now() + datetime.timedelta(days=30),
                ).strftime("%Y-%m-%dT%H:%M"),
                "location": fake.address(),
                "duration": fake.time_delta().days,
                "max_attendees": fake.random_int(min=1, max=15),
                "status": random.choice(stati),
                "duration": random.randint(1, 5) * 60,  # duration in minutes
            }

            newEv = db.create_event(
                name=ev["name"],
                gameID=ev["gameID"],
                hostID=user.get("user_id"),
                address=ev["location"],
                time=ev["time"],
                expected_duration=ev["duration"],
                min_attendees=ev["max_attendees"] // 2,
                max_attendees=ev["max_attendees"],
                description=ev["description"],
                status=ev["status"],
            )
            # Create a fake event for each user
            ev["id"] = newEv["id"]
            events.append(ev)
            pass

    # make them go to events, goddamn it
    for user in users:
        i = fake.random_int(min=0, max=10)
        for _ in range(i):
            event = random.choice(events)
            if event and event:
                db.attend_event(event_id=event.get("id"), user_id=user.get("user_id"))

    return users


generate_fake_users(100)
