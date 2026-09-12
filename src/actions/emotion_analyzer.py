from pathlib import Path

class EmotionAnalyzer:
    def __init__(self):
        self.deepface_available = False
        try:
            from deepface import DeepFace
            self.DeepFace = DeepFace
            self.deepface_available = True
            print("[EmotionAnalyzer] DeepFace disponible.")
        except ImportError:
            print("[EmotionAnalyzer] DeepFace no instalado. Instala: pip install deepface")

    def analyze_face(self, image_path: str) -> str:
        if not Path(image_path).exists():
            return f"Imagen no encontrada: {image_path}"
        if not self.deepface_available:
            return "DeepFace no disponible. Instala: pip install deepface"
        try:
            result = self.DeepFace.analyze(img_path=image_path, actions=['emotion', 'age', 'gender'])
            if isinstance(result, list):
                result = result[0]
            return (
                f"Emoción dominante: {result.get('dominant_emotion', 'N/A')}\n"
                f"Edad estimada: {result.get('age', 'N/A')}\n"
                f"Género: {result.get('gender', 'N/A')}"
            )
        except Exception as e:
            return f"Error en análisis facial: {e}"

    def analyze_voice(self, audio_path: str) -> str:
        # Placeholder – se requiere speechbrain
        return "Análisis de voz no implementado. Usa speechbrain."