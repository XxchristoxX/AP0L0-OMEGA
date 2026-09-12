import os
import requests
import json
from datetime import datetime, timedelta
def authenticate_google_calendar(token):
    url = 'https://www.googleapis.com/oauth2/v1/userinfo'
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    return response.json()
def get_events(token):
    now = datetime.utcnow().isoformat() + 'Z'
    end_of_day = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
    url = f'https://www.googleapis.com/calendar/v3/calendars/primary/events?timeMin={now}&timeMax={end_of_day}&singleEvents=true&orderBy=startTime'
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    return response.json()
def run(params):
    token = params.get('token')
    if not token:
        return {'error': 'No token provided'}
    
    user_info = authenticate_google_calendar(token)
    events = get_events(token)
    
    return {
        'user_info': user_info,
        'events': events.get('items', [])
    }