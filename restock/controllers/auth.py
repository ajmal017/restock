import json
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from restock import db, bcrypt, socketio
from restock.models.user import User
from restock.utils.errors import ErrorResponse

auth = Blueprint('authentication', __name__)


@auth.route('/register', methods=['POST'])
def register_new_user():
    body = request.json
    user = User(username=body['username'], email=body['email'], password=body['password'])

    db.session.add(user)
    db.session.commit()

    users = User.query.order_by(User.value.desc()).limit(100).all()
    user_ids = [u.id for u in users]
    socketio.emit('leaderboard', json.dumps(user_ids))

    return jsonify(user.to_dict()), 200


@auth.route('/login', methods=['POST'])
def login_user():
    body = request.json
    user = User.query.filter_by(username=body['username']).first()

    if user:
        if bcrypt.check_password_hash(user.password, body['password']):
            return jsonify({ 'auth_token': user.encode_auth_token().decode(), 'id': user.id }), 200
        return ErrorResponse('Authentication', 'Password does not match.').to_json(), 400
    return ErrorResponse('Not Found',
                         'No user with username {} exists.'.format(body['username'])).to_json(), 404
