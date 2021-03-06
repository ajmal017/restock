from flask import Blueprint, jsonify

from restock.models.user import User
from restock.utils.errors import ErrorResponse

users = Blueprint('users', __name__)


@users.route('/', methods=['GET'])
def get_all_users():
    users = User.query.order_by(User.value.desc()).all()
    serialized_users = [u.to_dict() for u in users]
    return jsonify(serialized_users), 200


@users.route('/leaderboard', methods=['GET'])
def get_top_users():
    users = User.query.order_by(User.value.desc()).limit(30).all()
    serialized_users = [u.to_dict() for u in users]
    return jsonify(serialized_users), 200


@users.route('/<int:id>', methods=['GET'])
def get_user_by_id(id):
    user = User.query.get(id)
    if user:
        return jsonify(user.to_dict()), 200
    return ErrorResponse('Not Found',
                         'No user with ID {} exists.'.format(id)).to_json(), 404

@users.route('/search/<string:search>', methods=['GET'])
def get_users_by_search(search):
    serialized = []
    users = User.query.all()
    for user in users:
        if search in user.username:
            serialized.append({ 'username': user.username, 'id': user.id, 'value': user.value, 'balance': user.balance })
    return jsonify(serialized), 200
