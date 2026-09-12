import json
import datetime
class LearningAgent:
    def __init__(self):
        self.interactions = []
        self.errors = {}
    def analyze_interactions(self):
        for interaction in self.interactions:
            if interaction['error']:
                self.errors[interaction['task']] = self.errors.get(interaction['task'], 0) + 1
    def adjust_behavior(self):
        adjustments = {}
        for task, count in self.errors.items():
            if count > 1:
                adjustments[task] = "Review instructions for better clarity."
        return adjustments
    def run(self, params):
        task = params.get('task')
        error_occurred = params.get('error', False)
        self.interactions.append({
            'task': task,
            'error': error_occurred,
            'timestamp': datetime.datetime.now().isoformat()
        })
        self.analyze_interactions()
        adjustments = self.adjust_behavior()
        return {
            'task': task,
            'error_occurred': error_occurred,
            'adjustments': adjustments
        }
if __name__ == "__main__":
    # Ejemplo de uso
    agent = LearningAgent()
    result = agent.run({'task': 'process_data', 'error': True})
    print(result)