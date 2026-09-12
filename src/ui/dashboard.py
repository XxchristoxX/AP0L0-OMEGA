import time
import psutil
import matplotlib.pyplot as plt
import matplotlib.animation as animation

class SystemStatus:
    def __init__(self):
        self.cpu_usage = []
        self.memory_usage = []
        self.temperatures = []

    def update_metrics(self):
        self.cpu_usage.append(psutil.cpu_percent(interval=1))
        self.memory_usage.append(psutil.virtual_memory().percent)
        # Temperatura no está soportada en todos los sistemas
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                self.temperatures.append(temps['coretemp'][0].current)
            else:
                self.temperatures.append(None)
        except Exception:
            self.temperatures.append(None)

    def get_metrics(self):
        return self.cpu_usage, self.memory_usage, self.temperatures

class Dashboard:
    def __init__(self, system_status):
        self.system_status = system_status
        self.fig, self.axs = plt.subplots(3, 1, figsize=(10, 8))

        self.cpu_line, = self.axs[0].plot([], [], label='CPU Usage (%)', color='r')
        self.memory_line, = self.axs[1].plot([], [], label='Memory Usage (%)', color='g')
        self.temp_line, = self.axs[2].plot([], [], label='Temperature (°C)', color='b')

        for ax in self.axs:
            ax.legend(loc='upper right')
            ax.grid()

        self.axs[0].set_ylim(0, 100)
        self.axs[1].set_ylim(0, 100)
        self.axs[2].set_ylim(0, 100)

        self.axs[0].set_title('CPU Usage')
        self.axs[1].set_title('Memory Usage')
        self.axs[2].set_title('Temperature')

    def animate(self, i):
        self.system_status.update_metrics()
        cpu, memory, temp = self.system_status.get_metrics()

        self.cpu_line.set_data(range(len(cpu)), cpu)
        self.memory_line.set_data(range(len(memory)), memory)
        self.temp_line.set_data(range(len(temp)), temp)

        self.cpu_line.axes.relim()
        self.cpu_line.axes.autoscale_view()
        self.memory_line.axes.relim()
        self.memory_line.axes.autoscale_view()
        self.temp_line.axes.relim()
        self.temp_line.axes.autoscale_view()

    def run(self):
        ani = animation.FuncAnimation(self.fig, self.animate, interval=1000)
        plt.show()

if __name__ == "__main__":
    system_status = SystemStatus()
    dashboard = Dashboard(system_status)
    dashboard.run()