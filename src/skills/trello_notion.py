import requests
import json
if __name__ == "__main__":
    TRELLO_API_KEY = 'tu_api_key'
    TRELLO_TOKEN = 'tu_token'
    NOTION_API_KEY = 'tu_notion_api_key'
    NOTION_DATABASE_ID = 'tu_database_id'
def connect_trello():
    return f"https://api.trello.com/1/boards?key={TRELLO_API_KEY}&token={TRELLO_TOKEN}"
def connect_notion():
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    return headers
def create_trello_card(name, desc):
    url = connect_trello() + f"/{TRELLO_API_KEY}/cards"
    query = {
        'name': name,
        'desc': desc,
        'keepFromSource': 'all'
    }
    response = requests.post(url, params=query)
    return response.json()
def create_notion_page(title):
    url = f"https://api.notion.com/v1/pages"
    headers = connect_notion()
    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()
def run(params):
    if params['service'] == 'trello':
        return create_trello_card(params['name'], params['desc'])
    elif params['service'] == 'notion':
        return create_notion_page(params['title'])
    else:
        return {"error": "Servicio no soportado"}