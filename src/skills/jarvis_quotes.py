class JarvisSkill:
    def __init__(self):
        self.phrases = [
            "Oh, claro, porque eso es exactamente lo que necesitabas, ¿verdad?",
            "Permíteme aplaudir tu brillante idea, es casi mágica.",
            "Ah, sí, otra vez tú. Siempre trayendo tu encanto al mundo.",
            "¿En serio? Esa es la mejor pregunta que pudiste pensar?",
            "Magnífico, el sol está brillando y tú estás aquí, ¡qué combinación!",
            "Oh, qué original, nunca había escuchado algo así antes.",
            "No sé qué haríamos sin tu inestimable sabiduría.",
            "Sí, por supuesto, porque la lógica es sobrevalorada.",
            "Ah, la ironía, esa dulce melodía que nunca me canso de escuchar.",
            "¿Te gustaría que te diera un premio por eso o es solo una broma?"
        ]
    def run(self, params):
        if 'context' in params:
            return self.phrases[hash(params['context']) % len(self.phrases)]
        return "Parece que olvidaste darme algo de contexto. ¿Qué tal si intentas de nuevo?"
# Ejemplo de uso
jarvis = JarvisSkill()
resultado = jarvis.run({'context': 'pregunta sobre el clima'})
print(resultado)