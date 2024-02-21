from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from pymongo.mongo_client import MongoClient
from telegram import Bot
import asyncio
from Client_API import get_total_spent, write_to_mongodb, get_average_spending_by_age

app = Flask(__name__)

# Konfiguracija za SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Konfiguracija za MongoDB
mongo_client = MongoClient("mongodb+srv://janevskim21:qqIJiKq0R0Jo2qGd@cluster0.ffwvt0z.mongodb.net/?retryWrites=true&w=majority")
mongo_db = mongo_client["users_vouchers"]
mongo_collection = mongo_db["vouchers"]


# Vnesuvanje na telegram bot token
TELEGRAM_BOT_TOKEN = '6423310833:AAGdEpfOHeeLXcMx3ZIzFRCBdipNBtC8YoI'
bot = Bot(token=TELEGRAM_BOT_TOKEN)


# Kreiranje na klasi i modeli
class UserInfo(db.Model):
    __tablename__ = 'user_info'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    spendings = db.relationship('UserSpending', backref='user')

    def __repr__(self):
        return f"<UserInfo(user_id={self.user_id}, name={self.name}, email={self.email}, age={self.age})>"


class UserSpending(db.Model):
    __tablename__ = 'user_spending'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_info.user_id'), nullable=False)
    money_spent = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<UserSpending(user_id={self.user_id}, money_spent={self.money_spent}, year={self.year})>"


# Ruta za vkupna potroshuvachka na user
@app.route('/total_spent/<int:user_id>', methods=['GET'])
def total_spent(user_id):
    total_spent = (UserSpending.query.filter_by(user_id=user_id)
                   .with_entities(db.func.avg(UserSpending.money_spent)).scalar())

    if total_spent is not None:
        response = {'user_id': user_id, 'total_spent': float(total_spent)}
        return jsonify(response), 200
    else:
        return jsonify({'error': 'User not found'}), 404


# Ruta za dobivanje na sredna potroshuvachka spored godini
@app.route('/average_spending_by_age', methods=['GET'])
def average_spending_by_age():
    age_ranges = {
        '18-24': (18, 24),
        '25-30': (25, 30),
        '31-36': (31, 36),
        '37-47': (37, 47),
        '>47': (48, 150)
    }

    total_spending_by_age_range = {
        '18-24': 0,
        '25-30': 0,
        '31-36': 0,
        '37-47': 0,
        '>47': 0
    }

    for range_name, age_range in age_ranges.items():
        users_in_range = UserInfo.query.filter(UserInfo.age >= age_range[0], UserInfo.age <= age_range[1]).all()
        total_spending = sum(user.spendings[0].money_spent for user in users_in_range)
        total_spending_by_age_range[range_name] = total_spending

    asyncio.run(send_telegram_message(total_spending_by_age_range))

    return jsonify(total_spending_by_age_range), 200


# Ruta za pishuvanje na mongodb i vnesuvanje funkcii vo telegram
@app.route('/write_to_mongodb', methods=['POST'])
def write_to_mongodb():
    try:
        data = request.get_json()

        if 'user_id' not in data or 'total_spent' not in data:
            return jsonify({'error': 'Incomplete data'}), 400

        mongo_collection.insert_one(data)

        return jsonify({'message': 'Successfully added to MongoDB'}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Funkcija i Inicijaliziranje na telegram za da mozhe da se povrzuva i prakja poraki
async def send_telegram_message(total_spending_by_age_range):
    chat_id = '6786231466'
    message = "Total Spending by Age Ranges:\n"
    for range_name, total_spending in total_spending_by_age_range.items():
        message += f"{range_name}: ${total_spending}\n"

    await bot.send_message(chat_id=chat_id, text=message)

    return None


# Inicijaliziranje na SQL tabeli
with app.app_context():
    db.create_all()

    users_info = [
        {'name': 'Marko', 'email': 'marko@gmail.com', 'age': 22},
        {'name': 'Nikola', 'email': 'nikola@icloud.com', 'age': 44},
        {'name': 'Jovan', 'email': 'jovan@yahoo.com', 'age': 18}
    ]

    for user_info in users_info:
        user = UserInfo.query.filter_by(name=user_info['name']).first()
        if not user:
            new_user = UserInfo(name=user_info['name'], email=user_info['email'], age=user_info['age'])
            db.session.add(new_user)
        else:
            user.email = user_info['email']
            user.age = user_info['age']

    db.session.commit()

    user_spending_info = {
        'Marko': {'money_spent': 1000, 'year': 2023},
        'Nikola': {'money_spent': 3000, 'year': 2024},
        'Jovan': {'money_spent': 2000, 'year': 2025}
    }

    for user_info in users_info:
        user_name = user_info['name']
        user = UserInfo.query.filter_by(name=user_name).first()
        if user:
            user_id = user.user_id
            if UserSpending.query.filter_by(user_id=user_id).count() == 0:
                spending_info = user_spending_info[user_name]
                sample_spending = UserSpending(user_id=user_id,
                                               money_spent=spending_info['money_spent'],
                                               year=spending_info['year'])
                db.session.add(sample_spending)

    db.session.commit()


if __name__ == '__main__':
    app.run(debug=True)
