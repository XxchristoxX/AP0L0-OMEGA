import random
import time
def simulate_lights_on(num_lights):
    lights = [f'Light {i+1}' for i in range(num_lights)]
    on_lights = random.sample(lights, random.randint(1, num_lights))
    return on_lights
def run(params):
    num_lights = params.get('num_lights', 5)
    duration = params.get('duration', 60)
    interval = params.get('interval', 10)
    end_time = time.time() + duration
    result = []
    while time.time() < end_time:
        on_lights = simulate_lights_on(num_lights)
        result.append(on_lights)
        time.sleep(interval)
    return result