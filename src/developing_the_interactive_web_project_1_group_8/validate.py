from developing_the_interactive_web_project_1_group_8.event_times import (
    CENTRAL,
    parse_utc_time,
    is_event_completed,
    is_event_time_completed,
)

from developing_the_interactive_web_project_1_group_8.db import (
    game_exists,
)

import re

def validate_form(form):
    errors = {}
    name = form.get("name")

    pattern = r'^[a-zA-Z 0-9,.!\']+$'
    pattern_match = re.fullmatch(pattern, name)

    if not name:
        errors["name"] = "Event Name is required"
    elif len(name) > 254:
        errors["name"] = "Title must be 254 characters or fewer"
    elif pattern_match is None:
        errors["name"] = "Title can only consist of alphanumeric characters and symbols ,.!'"

    gameid = form.get("search-value") or form.get("gameid")

    if not gameid:
        errors["bgg-game-search"] = "Must enter a game"
    elif not game_exists(gameid) or gameid < 0:
        errors["bgg-game-search"] = "Must enter a valid game"

    address = form.get("address")
    pattern_match = re.fullmatch(pattern, address)

    if not address:
        errors["address"] = "Event Address is required"
    elif len(address) > 254:
        errors["address"] = "Address must be 254 characters or fewer"
    elif pattern_match is None:
        errors["address"] = "Address can only consist of alphanumeric characters and symbols ,.!'"

    try:
        expected

    try:
        event_time = parse_utc_time(form.get("time"))
    except ValueError:
        errors["time"] = "Choose a valid event time in Central Time (CT)."
    else:
        if not event_time:
            errors["time"] = "You must enter a time"
        elif is_event_time_completed(event_time):
            errors["time"] = "The event time must be held in the future"
    
            


    

    # print(request.form)
    #     print(session["profile"]["id"])
    #     try:
    #         event_time = parse_utc_time(request.form.get("time"))
    #     except ValueError:
    #         return render_template(
    #             "error.html", message="Choose a valid event time in Central Time (CT)."
    #         ), 400
    #     result = db.create_event(
    #         request.form.get("name"),
    #         request.form.get("search-value") or request.form.get("gameid"),
    #         session["profile"]["id"],
    #         request.form.get("address"),
    #         event_time,
    #         request.form.get("expected_duration"),
    #         request.form.get("min_attendees"),
    #         request.form.get("max_attendees"),
    #         request.form.get("description"),
    #         "scheduled",
    #     )
