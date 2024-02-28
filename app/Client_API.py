import requests
from requests.exceptions import JSONDecodeError


def get_total_spending():
    base_url = 'http://127.0.0.1:5000/total_spent'
    user_ids = [1, 2, 3]
    total_spending_data = {}

    for user_id in user_ids:
        url = f'{base_url}/{user_id}'
        response = requests.get(url)
        try:
            response.raise_for_status()
            data = response.json()
            total_spending_data[user_id] = data.get('total_spent')
        except JSONDecodeError:
            print(f'Failed to parse JSON response for user {user_id}')
        except requests.exceptions.HTTPError as err:
            print(f'HTTP error occurred: {err}')
        except Exception as e:
            print(f'An unexpected error occurred: {e}')

    return total_spending_data


def write_to_mongodb(eligible_users_data):
    url = 'http://127.0.0.1:5000/write_to_mongodb'
    try:
        response = requests.post(url, json=eligible_users_data)
        response.raise_for_status()
        print('Data successfully written to MongoDB')
    except requests.exceptions.HTTPError as err:
        print(f'Error writing data to MongoDB: {err}')


def get_average_spending_by_age():
    url = 'http://127.0.0.1:5000/average_spending_by_age'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError):
            print(f'HTTP error occurred: {e}')
        else:
            print(f'Error fetching average spending by age: {e}')
        return None


def main():
    total_spending_data = get_total_spending()
    write_to_mongodb(total_spending_data)
    average_spending_by_age = get_average_spending_by_age()
    if average_spending_by_age:
        print('Average Spending by Age Ranges:', average_spending_by_age)


if __name__ == '__main__':
    main()
