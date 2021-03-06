import datetime
import jwt
from sqlalchemy.ext.declarative import declared_attr

from restock import db, bcrypt
from restock.config import Config


class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, nullable=False)
    date_registered = db.Column(db.DateTime, nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.generate_password_hash(password).decode()
        self.balance = 100000
        self.value = 100000
        self.date_registered = datetime.datetime.utcnow()

        LatestRecord(self.balance, self.value, self)
        HourlyRecord(self.balance, self.value, self)
        DailyRecord(self.balance, self.value, self)
        WeeklyRecord(self.balance, self.value, self)
        MonthlyRecord(self.balance, self.value, self)

    def __repr__(self):
        return "User(username='{username}')".format(**self.to_dict())

    def to_dict(self):
        return {
            'username': self.username,
            'date_registered': '{:%Y-%m-%d}'.format(self.date_registered),
            'balance': self.balance,
            'value': self.value,
            'portfolio': self.serialize_relationship('portfolio'),
            'transactions': self.serialize_relationship('transactions'),
            'tracking': self.serialize_relationship('tracking'),
            'records': {
                'latest_records': self.serialize_relationship('latest_records'),
                'hourly_records': self.serialize_relationship('hourly_records'),
                'daily_records': self.serialize_relationship('daily_records'),
                'weekly_records': self.serialize_relationship('weekly_records'),
                'monthly_records': self.serialize_relationship('monthly_records')
            },
            'id': self.id
        }

    def serialize_relationship(self, name):
        rel = getattr(self, name, None)
        if rel:
            return [ r.to_dict() for r in rel ]
        return []

    def encode_auth_token(self):
        payload = {
            # 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
            'iat': datetime.datetime.utcnow(),
            'id': self.id
        }
        return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def decode_auth_token(token):
        payload = jwt.decode(token, Config.SECRET_KEY)
        return payload['id']


class RecordMixin():

    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

    @declared_attr
    def user_id(cls):
        return db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)

    def __init__(self, balance, value, user):
        self.balance = balance
        self.value = value
        self.user = user
        self.timestamp = datetime.datetime.utcnow()

    def __repr__(self):
        return "Record(balance={balance}, value={value}, user='{user}')".format(**self.to_dict())

    def to_dict(self):
        return {
            'balance': self.balance,
            'value': self.value,
            'timestamp': '{:%Y-%m-%d %H:%M:%S}'.format(self.timestamp),
            'user': self.user.username,
            'id': self.id
        }


class LatestRecord(RecordMixin, db.Model):

    user = db.relationship(User, backref=db.backref('latest_records'))


class HourlyRecord(RecordMixin, db.Model):

    user = db.relationship(User, backref=db.backref('hourly_records'))


class DailyRecord(RecordMixin, db.Model):

    user = db.relationship(User, backref=db.backref('daily_records'))


class WeeklyRecord(RecordMixin, db.Model):

    user = db.relationship(User, backref=db.backref('weekly_records'))


class MonthlyRecord(RecordMixin, db.Model):

    user = db.relationship(User, backref=db.backref('monthly_records'))


def update_and_limit_record(Record, new_balance, new_value, user):
    new_record = Record(new_balance, new_value, user)
    count = Record.query.filter_by(user=user).count()

    # time_ordered = Record.query.order_by(Record.timestamp.desc()).all()
    # print(time_ordered)

    while count > Config.MAX_RECORDS:
        to_delete = Record.query.filter_by(user=user).order_by(Record.timestamp).first()
        db.session.delete(to_delete)
        count = Record.query.filter_by(user=user).count()

    return new_record


def update_balance_records(new_balance, user):
    user.balance = new_balance
    new_value = new_balance + sum([ asset.aggregate.current_price * asset.shares if not asset.is_short else
                                    2*asset.init_value - asset.shares*asset.aggregate.current_price
                                    # asset.shares * (2*asset.init_price - asset.aggregate.current_price)
                                    for asset in user.portfolio ])
    user.value = new_value

    new_record = update_and_limit_record(LatestRecord, new_balance, new_value, user)

    last_record = HourlyRecord.query.filter_by(user=user).order_by(HourlyRecord.timestamp.desc()).first()
    time_diff = new_record.timestamp - last_record.timestamp
    if time_diff.days >= 1 or time_diff.seconds >= 3600:
        update_and_limit_record(HourlyRecord, new_balance, new_value, user)

    last_record = DailyRecord.query.filter_by(user=user).order_by(DailyRecord.timestamp.desc()).first()
    time_diff = new_record.timestamp - last_record.timestamp
    if time_diff.days >= 1:
        update_and_limit_record(DailyRecord, new_balance, new_value, user)

    last_record = WeeklyRecord.query.filter_by(user=user).order_by(WeeklyRecord.timestamp.desc()).first()
    time_diff = new_record.timestamp - last_record.timestamp
    if time_diff.days >= 7:
        update_and_limit_record(WeeklyRecord, new_balance, new_value, user)

    last_record = MonthlyRecord.query.filter_by(user=user).order_by(MonthlyRecord.timestamp.desc()).first()
    time_diff = new_record.timestamp - last_record.timestamp
    if time_diff.days >= 28:
        update_and_limit_record(MonthlyRecord, new_balance, new_value, user)
