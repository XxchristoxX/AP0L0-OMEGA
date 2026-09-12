import os
import requests
import json
from datetime import datetime, timedelta
def get_unread_emails(token):
    url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages'
    params = {
        'q': 'is:unread',
        'access_token': token
    }
    response = requests.get(url, params=params)
    return response.json()
def summarize_emails(messages, token):
    summaries = []
    for message in messages.get('messages', []):
        msg_id = message['id']
        msg_url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?access_token={token}'
        msg_response = requests.get(msg_url)
        msg_data = msg_response.json()
        subject = next(header['value'] for header in msg_data['payload']['headers'] if header['name'] == 'Subject')
        summaries.append(subject)
    return summaries
def run(params):
    token = params.get('token')
    unread_emails = get_unread_emails(token)
    summaries = summarize_emails(unread_emails, token)
    return summaries