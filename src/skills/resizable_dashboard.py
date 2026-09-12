import json
class PerformanceDashboard:
    def __init__(self):
        self.panels = {}
    def add_panel(self, panel_id, size):
        self.panels[panel_id] = size
    def resize_panel(self, panel_id, new_size):
        if panel_id in self.panels:
            self.panels[panel_id] = new_size
    def get_panels(self):
        return self.panels
def run(params):
    dashboard = PerformanceDashboard()
    # Agregar paneles desde los parámetros
    for panel_id, size in params.get('panels', {}).items():
        dashboard.add_panel(panel_id, size)
    # Redimensionar paneles si se indica
    for panel_id, new_size in params.get('resize_panels', {}).items():
        dashboard.resize_panel(panel_id, new_size)
    return dashboard.get_panels()