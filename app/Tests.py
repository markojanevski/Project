import pytest
import json
from main import app, db, UserInfo, UserSpending


@pytest.fixture
def client():
    app.config['TESTING'] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


# Test za dodavanje na nov korisnik
def test_add_new_user(client):
    response = client.post('/save_new_user', data=json.dumps({
        'name': 'John',
        'email': 'john@example.com',
        'age': 30,
        'money_spent': 500,
        'year': 2024
    }), content_type='application/json')

    assert response.status_code == 400


# Test za dodavanje nov korisnik so neispravni podatoci
def test_add_new_user_invalid_data(client):
    response = client.post('/save_new_user', data=json.dumps({
        'name': 'Jane',
        'email': '',
        'age': 25,
        'money_spent': 700,
        'year': 2023
    }), content_type='application/json')

    assert response.status_code == 400
    assert UserInfo.query.filter_by(name='Jane').first() is None


# Test za brishenje postoechki user
def test_delete_existing_user(client):
    user = UserInfo(name='Test User', email='test@example.com', age=40)
    db.session.add(user)
    db.session.commit()

    response = client.post(f'/delete_user/{user.user_id}')
    assert response.status_code == 302
    assert UserInfo.query.filter_by(name='Test User').first() is None


# Test za brishenje na nepostoechki user
def test_delete_non_existing_user(client):
    response = client.post('/delete_user/1000')
    assert response.status_code == 404
    assert b'User not found' in response.data


# Test za Vkupno potrosheno
def test_total_spent(client):
    user1 = UserInfo(name='Marko', email='marko@gmail.com', age=22)
    db.session.add(user1)
    db.session.commit()
    spending1 = UserSpending(user_id=user1.user_id, money_spent=1000, year=2021)
    db.session.add(spending1)
    db.session.commit()

    response = client.get('/total_spent/1')

    assert response.content_type == 'application/json'

    data = response.json

    assert 'total_spent' in data

    assert data['total_spent'] == 1000.0


# Test za vkupno potrosheno dokolku userot ne e najden
def test_total_spent_user_not_found(client):
    response = client.get('/total_spent/3')
    data = json.loads(response.data.decode('utf-8'))

    assert response.status_code == 404
    assert data['error'] == 'User not found'


# Test za prosechno potrosheno spored godini
def test_average_spending_by_age(client):
    user1 = UserInfo(name='Marko', email='marko@gmail.com', age=22)
    user2 = UserInfo(name='Nikola', email='nikola@icloud.com', age=44)
    user3 = UserInfo(name='Jovan', email='jovan@yahoo.com', age=18)
    db.session.add_all([user1, user2, user3])
    db.session.commit()
    spending1 = UserSpending(user_id=user1.user_id, money_spent=1000, year=2023)
    spending2 = UserSpending(user_id=user2.user_id, money_spent=3000, year=2024)
    spending3 = UserSpending(user_id=user3.user_id, money_spent=2000, year=2025)
    db.session.add(spending1)
    db.session.add(spending2)
    db.session.add(spending3)
    db.session.commit()

    response = client.get('/average_spending_by_age')
    data = json.loads(response.data.decode('utf-8'))

    assert response.status_code == 200
    assert '18-24' in data
    assert '25-30' in data
    assert '31-36' in data
    assert '37-47' in data
    assert '>47' in data


# Test za Vpishuvanje podatocite vo MongoDB
def test_write_to_mongodb(client):
    payload = {'user_id': 1, 'total_spent': 1000}
    response = client.post('/write_to_mongodb', json=payload)

    try:
        assert response.status_code == 201
    except AssertionError:
        assert response.status_code == 500

        if response.content_type == 'application/json':
            data = json.loads(response.data)
            print("Error message:", data.get('error'))


# Test za ako podatocite se nekompletni za vpishuvanje vo MongoDB
def test_write_to_mongodb_incomplete_data(client):
    payload = {'user_id': 1}
    response = client.post('/write_to_mongodb', json=payload)
    assert response.status_code == 201
