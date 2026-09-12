import os
import psutil
import time
class ResourceManager:
    def __init__(self):
        self.cpu_threshold = 80  # CPU usage threshold
        self.ram_threshold = 80   # RAM usage threshold
        self.battery_threshold = 20  # Battery percentage threshold

    def check_resources(self):
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        battery_percentage = battery.percent if battery else 100

        return cpu_usage, ram_usage, battery_percentage

    def adapt_performance(self):
        cpu_usage, ram_usage, battery_percentage = self.check_resources()

        if cpu_usage > self.cpu_threshold or ram_usage > self.ram_threshold or battery_percentage < self.battery_threshold:
            return "Reduce performance"
        return "Normal performance"
def run(params):
    resource_manager = ResourceManager()
    performance = resource_manager.adapt_performance()
    return {
        "status": "success",
        "performance": performance,
        "params": params
    }