import psycopg
import faker
from flask import Flask, jsonify, Blueprint, request, render_template

# this module holds all of the api endpoints



api = Blueprint('api', __name__, template_folder='templates')


# ---------- Events ----------

@api.route('/event/create', methods=['POST'])
def disp():
    """
    Create a new event.
    
    Parameters:
      name (str): The name of the new event.
      description (str): The description of the new event.
      date (str): The date of the new event.

    Returns:
      A JSON response indicating success or failure of event creation.
    """
    name = request.args.get('name', type=str)
    description = request.args.get('description', type=str)
    date = request.args.get('date', type=str)


    return jsonify({'data': name})


# ---------- Accounts ----------

@api.route('/account/create', methods=['GET','POST'])
def accountCreate():
    """
    Create an account.
    
    Parameters:
      username (str): The username for the new account.
      password (str): The password for the new account.

    Returns:
      A JSON response indicating success or failure of account creation.
    """
    username = request.args.get('username', type=str)
    password = request.args.get('password', type=str)

    # sanity checks for username and password
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    if not password:
        return jsonify({'error': 'Password is required'}), 400
    if len(username) < 5:
        return jsonify({'error': 'Username must be at least 5 characters long'}), 400
    if len(username) > 32:
        return jsonify({'error': 'Username must be at most 32 characters long'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long'}), 400

    # TODO: Add logic to create the account in the database

    return jsonify({'message': 'Account created successfully'}), 201


# ---------- Search ----------
