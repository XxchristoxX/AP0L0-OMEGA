class BitacoraConocimiento:
    def __init__(self):
        self.conocimientos = []
    def agregar_conocimiento(self, conocimiento):
        self.conocimientos.append(conocimiento)
    def mostrar_conocimientos(self):
        return self.conocimientos
    def run(self, params):
        if 'conocimiento' in params:
            self.agregar_conocimiento(params['conocimiento'])
        return self.mostrar_conocimientos()