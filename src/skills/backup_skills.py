import json
import datetime
import os
class ProductivityDashboard:
    def __init__(self):
        self.data_file = 'productivity_data.json'
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as file:
                self.data = json.load(file)
        else:
            self.data = {}

    def save_data(self):
        with open(self.data_file, 'w') as file:
            json.dump(self.data, file)

    def add_entry(self, habit, duration):
        date = str(datetime.date.today())
        if date not in self.data:
            self.data[date] = {}
        if habit not in self.data[date]:
            self.data[date][habit] = 0
        self.data[date][habit] += duration
        self.save_data()

    def analyze_patterns(self):
        total_habits = {}
        for date, habits in self.data.items():
            for habit, duration in habits.items():
                if habit not in total_habits:
                    total_habits[habit] = 0
                total_habits[habit] += duration
        return total_habits

    def generate_report(self):
        report = {}
        for date, habits in self.data.items():
            report[date] = habits
        return report
def run(params):
    dashboard = ProductivityDashboard()
    
    if 'action' in params:
        if params['action'] == 'add':
            dashboard.add_entry(params['habit'], params['duration'])
            return {"status": "success", "message": "Habit added."}
        elif params['action'] == 'analyze':
            patterns = dashboard.analyze_patterns()
            return {"status": "success", "patterns": patterns}
        elif params['action'] == 'report':
            report = dashboard.generate_report()
            return {"status": "success", "report": report}
    
    return {"status": "error", "message": "Invalid action."}