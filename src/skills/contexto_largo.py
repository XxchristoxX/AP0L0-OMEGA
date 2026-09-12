import json
import os
from datetime import datetime, timedelta
class ConversationContext:
    def __init__(self, filename='conversations.json'):
        self.filename = filename
        self.load_conversations()
    def load_conversations(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                self.conversations = json.load(f)
        else:
            self.conversations = {}
    def save_conversations(self):
        with open(self.filename, 'w') as f:
            json.dump(self.conversations, f)
    def add_conversation(self, date, text):
        self.conversations[date] = text
        self.save_conversations()
    def get_recent_conversation(self, days=7):
        cutoff_date = datetime.now() - timedelta(days=days)
        recent = {date: text for date, text in self.conversations.items() if datetime.strptime(date, '%Y-%m-%d') > cutoff_date}
        return recent
def run(params):
    context = ConversationContext()
    if 'add' in params:
        date = datetime.now().strftime('%Y-%m-%d')
        context.add_conversation(date, params['add'])
        return "Conversación añadida."
    if 'get_recent' in params:
        return context.get_recent_conversation(params.get('days', 7))
    return "Parámetro no reconocido."