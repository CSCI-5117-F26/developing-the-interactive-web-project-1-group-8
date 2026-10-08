from flask import Flask, render_template
from developing_the_interactive_web_project_1_group_8.api import api

app = Flask(__name__)
app.register_blueprint(api)

@app.route("/")
def index():
    return render_template("index.html")

