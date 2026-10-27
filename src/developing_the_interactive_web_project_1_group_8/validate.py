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
    error_event = form.copy()
    print("------ copy: ------")
    print(error_event)
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
        errors["bgg-game-search"] = "Must enter a valid game"
    elif not game_exists(gameid):
        errors["bgg-game-search"] = "Must enter a valid game"
    else:
        error_event["game_name"] = form.get("search-key")
        error_event["gameid"] = form.get("search-value")

    address = form.get("address")
    pattern_match = re.fullmatch(pattern, address)

    if not address:
        errors["address"] = "Event Address is required"
    elif len(address) > 254:
        errors["address"] = "Address must be 254 characters or fewer"
    elif pattern_match is None:
        errors["address"] = "Address can only consist of alphanumeric characters and symbols ,.!'"

    try:
        expected_duration = int(form.get("expected_duration"))
    except ValueError:
        errors["expected_duration"] = "Expected duration (minutes) must be a whole number"
        error_event["expected_duration"] = None
    else:
        if not 1 <= expected_duration <= 1440:
            errors["expected_duration"] = "Expected duration must be between 1 and 1440 (24h)"

    try:
        min_attendees = int(form.get("min_attendees"))
    except ValueError:
        errors["min_attendees"] = "Minimum number of attendees must be a whole number"
        error_event["min_attendees"] = None
    else:
        if not 2 <= min_attendees <= 10000:
            errors["min_attendees"] = "Minimum number of attendees must be between 2 and 10,000"

        try:
            max_attendees = int(form.get("max_attendees"))
        except ValueError:
            errors["max_attendees"] = "Maximum number of attendees must be a whole number"
            error_event["max_attendees"] = None
        else:
            if not 2 <= max_attendees <= 10000:
                errors["max_attendees"] = "Maximum number of attendees must be between 2 and 10,000"
            elif min_attendees > max_attendees:
                errors["max_attendees"] = "Maximum number of attendees must be greater than or equal to the attendee minimum"

    description = form.get("description")
    if len(description) > 4094:
        errors["description"] = "Description must be 4096 characters or fewer"
            

    try:
        event_time = parse_utc_time(form.get("time"))
    except ValueError:
        errors["time"] = "Choose a valid event time in Central Time (CT)."
        error_event["time"] = None
    else:
        error_event["time"] = parse_utc_time(form.get("time"))
        if not event_time:
            errors["time"] = "You must enter a time"
        elif is_event_time_completed(event_time):
            errors["time"] = "The event time must be held in the future"

    visibility = form.get("visibility")
    if visibility not in ("public", "friends", "private"):
        errors["visibilty"] = "Event visibility must bePublic, Friends only, or Private for event visibility."
        error_event["visibility"] = None

    return errors, error_event


    

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
