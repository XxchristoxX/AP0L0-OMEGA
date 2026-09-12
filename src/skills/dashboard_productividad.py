import json
import datetime
class ProductivityDashboard:
    def __init__(self):
        self.habits = {}
    def add_habit(self, habit_name, frequency):
        self.habits[habit_name] = {'frequency': frequency, 'records': []}
    def record_habit(self, habit_name):
        if habit_name in self.habits:
            today = datetime.date.today().isoformat()
            self.habits[habit_name]['records'].append(today)
    def get_progress(self, habit_name):
        if habit_name in self.habits:
            total_days = self.habits[habit_name]['frequency']
            completed_days = len(self.habits[habit_name]['records'])
            return f'Hábito: {habit_name}, Completados: {completed_days}/{total_days}'
        return 'Hábito no encontrado'
    def run(self, params):
        action = params.get('action')
        habit_name = params.get('habit_name')
        if action == 'add':
            frequency = params.get('frequency')
            self.add_habit(habit_name, frequency)
            return f'Hábito {habit_name} añadido con frecuencia {frequency}.'
        elif action == 'record':
            self.record_habit(habit_name)
            return f'Hábito {habit_name} registrado en el día de hoy.'
        elif action == 'progress':
            return self.get_progress(habit_name)
        return 'Acción no válida.'
if __name__ == "__main__":
    # Ejemplo de uso
    dashboard = ProductivityDashboard()
    params = {'action': 'add', 'habit_name': 'Ejercicio', 'frequency': 5}
    print(dashboard.run(params))
    params = {'action': 'record', 'habit_name': 'Ejercicio'}
    print(dashboard.run(params))
    params = {'action': 'progress', 'habit_name': 'Ejercicio'}
    print(dashboard.run(params))