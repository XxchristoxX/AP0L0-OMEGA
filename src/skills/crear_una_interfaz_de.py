class Interfaz:
    def __init__(self):
        self.elementos = []
    def agregar_elemento(self, elemento):
        self.elementos.append(elemento)
    def mostrar_elementos(self):
        for elemento in self.elementos:
            print(elemento)
def crear_una_interfaz_de():
    interfaz = Interfaz()
    interfaz.agregar_elemento("Botón")
    interfaz.agregar_elemento("Etiqueta")
    interfaz.agregar_elemento("Campo de texto")
    return interfaz
def run():
    interfaz = crear_una_interfaz_de()
    interfaz.mostrar_elementos()
if __name__ == "__main__":
    run()