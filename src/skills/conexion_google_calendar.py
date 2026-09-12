import os
import json
import requests
from datetime import datetime, timedelta
def authenticate_google_calendar(token):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    return headers
def get_events(headers):
    now = datetime.utcnow().isoformat() + 'Z'
    end_of_day = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'
    url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
    params = {
        'timeMin': now,
        'timeMax': end_of_day,
        'singleEvents': True,
        'orderBy': 'startTime'
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json().get('items', [])
def run(params):
    token = params.get('token')
    headers = authenticate_google_calendar(token)
    events = get_events(headers)
    return events