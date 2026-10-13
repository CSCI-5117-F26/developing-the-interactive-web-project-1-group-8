from flask import Flask, render_template
from developing_the_interactive_web_project_1_group_8.api import api

app = Flask(__name__)
app.register_blueprint(api)

# Pages

@app.route("/")
def index():
    """ Dashboard page, where users can explore for new events """
    data = [
        {"name": "Event 1", "host_name": "host1", "game_name": "Game 1", "date": "Oct 14", "location": "Place 1"},
        {"name": "Event 2", "host_name": "host2", "game_name": "Game 2", "date": "Oct 15", "location": "Place 2"},
        {"name": "Event 3", "host_name": "host3", "game_name": "Game 3", "date": "Oct 16", "location": "Place 3"},
        {"name": "Event 4", "host_name": "host4", "game_name": "Game 4", "date": "Oct 17", "location": "Place 4"},
        {"name": "Event 5", "host_name": "host5", "game_name": "Game 5", "date": "Oct 18", "location": "Place 5"},
        {"name": "Event 6", "host_name": "host6", "game_name": "Game 6", "date": "Oct 19", "location": "Place 6"},
        {"name": "Event 7", "host_name": "host7", "game_name": "Game 7", "date": "Oct 20", "location": "Place 7"},
    ]

    sections = [
        ("Events from Popular Games", data),
        ("Events from Games You've Played", data),
        ("Events in the Next Week", data),
        ("Friend Events!", data),
    ]
    return render_template("index.html", sections=sections)

@app.route("/login")
def login():
    """ Login page, where users can log in to their account """
    return render_template("login.html")

@app.route("/register")
def register():
    """ Register page, where users can create a new account """
    return render_template("register.html")

@app.route("/search/")
def search():
    """ Search page, where users can search for events """
    return render_template("search.html")

@app.route("/event/<int:event_id>")
def event(event_id):
    """ Event page, where users can view details about a specific event """
    return render_template("event.html", event_id=event_id)

@app.route("/user/<string:username>")
def user(username):
    """ User page, where users can view details about a specific user """
    return render_template("user.html", username=username)