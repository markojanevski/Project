from flask import Flask, jsonify, request, render_template, redirect, url_for, after_this_request
from flask_sqlalchemy import SQLAlchemy
from pymongo.mongo_client import MongoClient
from telegram import Bot
import asyncio

app = Flask(__name__)

# Konfiguracija za SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Konfiguracija za MongoDB
mongo_client = MongoClient("mongodb+srv://janevskim21:qqIJiKq0R0Jo2qGd@cluster0.ffwvt0z.mongodb.net/"
                           "?retryWrites=true&w=majority&appName=Cluster0")
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


# Ruta za da mozhe html file da se napravi za pochetnata strana
@app.route('/')
def index():
    return render_template('index.html')


# Ruta za dodavanje i chuvanje na nov user
@app.route('/add_new_user', methods=['GET'])
def add_new_user():
    return render_template('add_new_user.html')


@app.route('/save_new_user', methods=['POST'])
def save_new_user():
    name = request.form['name']
    email = request.form['email']
    age = request.form['age']
    money_spent = request.form['money_spent']
    year = request.form['year']

    new_user = UserInfo(name=name, email=email, age=age)

    try:
        db.session.add(new_user)
        db.session.commit()

        new_spending = UserSpending(user_id=new_user.user_id, money_spent=money_spent, year=year)
        db.session.add(new_spending)
        db.session.commit()

        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# Ruta za brishenje na korisnik i potrebnite funkcii
@app.route('/delete_user', methods=['GET'])
def delete_user():
    all_users = UserInfo.query.all()
    return render_template('delete_user.html', users=all_users)


@app.route('/delete_user/<int:user_id>', methods=['POST', 'DELETE'])
def delete_single_user(user_id):
    if request.method == 'POST' or request.method == 'DELETE':
        user = UserInfo.query.get(user_id)
        if user:
            try:
                UserSpending.query.filter_by(user_id=user_id).delete()

                db.session.delete(user)
                db.session.commit()

                return redirect(url_for('delete_user'))
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': str(e)}), 500
        else:
            return jsonify({'error': 'User not found'}), 404


# Ruta za vkupna potroshuvachka na user
@app.route('/total_spent/<int:user_id>', methods=['GET'])
def total_spent(user_id):
    user = UserInfo.query.get(user_id)
    if user:
        total_spent_amount = (UserSpending.query.filter_by(user_id=user_id)
                              .with_entities(db.func.sum(UserSpending.money_spent)).scalar())
        if total_spent_amount is not None:
            if request.accept_mimetypes.accept_html:
                return render_template('total_spent.html', user_id=user_id, total_spent=total_spent_amount), 200
            else:
                return jsonify({'user_id': user_id, 'total_spent': total_spent_amount}), 200
        else:
            return jsonify({'error': 'No spending record found for the user'}), 404
    else:
        if request.accept_mimetypes.accept_html:
            return render_template('user_not_found.html', user_id=user_id), 404
        else:
            return jsonify({'error': 'User not found'}), 404


# Ruta za dobivanje na sredna potroshuvachka spored godini
@app.route('/average_spending_by_age', methods=['GET'])
def average_spending_by_age_route():
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

    @after_this_request
    def send_telegram(response):
        asyncio.run(send_telegram_message(total_spending_by_age_range))
        return response

    if request.accept_mimetypes.accept_html:
        return render_template('average_spending_by_age.html', total_spending_by_age_range=total_spending_by_age_range)
    else:
        return jsonify(total_spending_by_age_range)


# Ruta za pishuvanje na mongodb i vnesuvanje funkcii vo telegram
@app.route('/write_to_mongodb', methods=['POST'])
def write_to_mongodb():
    try:
        all_users = UserInfo.query.all()
        users_eligible_for_voucher = []
        for user in all_users:
            total_spent = (db.session.query(db.func.sum(UserSpending.money_spent))
                           .filter_by(user_id=user.user_id).scalar())
            if total_spent is not None and total_spent >= 500:
                user_data = {
                    'user_id': user.user_id,
                    'name': user.name,
                    'email': user.email,
                    'age': user.age
                }
                mongo_collection.insert_one(user_data)
                users_eligible_for_voucher.append(user_data)

        return jsonify({'message': 'Site uspeshno se dodadeni vo MongoDB'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/all_user_ids', methods=['GET'])
def get_all_user_ids():
    user_ids = [user.user_id for user in UserInfo.query.all()]
    return jsonify(user_ids), 200


# Funkcija i Inicijaliziranje na telegram za da mozhe da se povrzuva i prakja poraki
@app.route('/send_telegram_message', methods=['POST'])
def send_telegram_message_route():
    try:
        total_spending_by_age_range = request.get_json()
        asyncio.run(send_telegram_message(total_spending_by_age_range))
        return jsonify({'message': 'Telegram porakata e uspeshno pratena'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


async def send_telegram_message(total_spending_by_age_range):
    chat_id = '6786231466'
    message = "Total Spending by Age Ranges:\n"
    for range_name, total_spending in total_spending_by_age_range.items():
        message += f"{range_name}: ${total_spending}\n"

    await bot.send_message(chat_id=chat_id, text=message)


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
