from flask import Flask, render_template
from developing_the_interactive_web_project_1_group_8.api import api

app = Flask(__name__)
app.register_blueprint(api)

# Pages

@app.route("/")
def index():
    """ Dashboard page, where users can explore for new events """
    return render_template("index.html")

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