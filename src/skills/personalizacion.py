import json
import datetime
import os
class PreferencesManager:
    def __init__(self):
        self.preferences = {
            'voice': 'neutral',
            'theme': 'light',
            'responses': 'concise',
            'active_skills': []
        }

    def load_preferences(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                self.preferences = json.load(f)

    def save_preferences(self, filepath):
        with open(filepath, 'w') as f:
            json.dump(self.preferences, f)

    def adjust_preferences(self, params):
        for key, value in params.items():
            if key in self.preferences:
                self.preferences[key] = value

    def get_current_preferences(self):
        return self.preferences
def check_time_for_theme():
    current_hour = datetime.datetime.now().hour
    return 'dark' if 18 <= current_hour < 6 else 'light'
def run(params):
    manager = PreferencesManager()
    manager.load_preferences('preferences.json')
    
    manager.adjust_preferences(params)
    
    if 'theme' not in params:
        manager.preferences['theme'] = check_time_for_theme()
    
    manager.save_preferences('preferences.json')
    return manager.get_current_preferences()