# src/auth/face_auth.py
"""
Autenticación facial usando MediaPipe Face Landmarker.
"""
import cv2
import numpy as np
from pathlib import Path
import json

# ===== IMPORTACIÓN ROBUSTA DE MEDIAPIPE =====
MEDIAPIPE_AVAILABLE = False
mp_face = None

try:
    import mediapipe as mp
    # Verificar que la versión tenga el módulo solutions
    if hasattr(mp, 'solutions'):
        mp_face = mp.solutions.face_mesh
        MEDIAPIPE_AVAILABLE = True
    else:
        # Fallback: intentar importar desde mediapipe.solutions directamente
        try:
            from mediapipe import solutions
            mp_face = solutions.face_mesh
            MEDIAPIPE_AVAILABLE = True
        except ImportError:
            MEDIAPIPE_AVAILABLE = False
            print("[FaceAuth] ⚠️ MediaPipe no disponible. La autenticación facial estará desactivada.")
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[FaceAuth] ⚠️ MediaPipe no instalado. La autenticación facial estará desactivada.")


class FaceAuthenticator:
    def __init__(self, model_path="models/face_embedding.npy"):
        if not MEDIAPIPE_AVAILABLE:
            print("[FaceAuth] ⚠️ MediaPipe no disponible. Usando modo simulación.")
            self.face_mesh = None
        else:
            self.face_mesh = mp_face.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                min_detection_confidence=0.5
            )
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.embeddings = self._load_embeddings()

    def _load_embeddings(self):
        if self.model_path.exists():
            try:
                return np.load(self.model_path, allow_pickle=True).item()
            except Exception:
                return {}
        return {}

    def _save_embeddings(self):
        try:
            np.save(self.model_path, self.embeddings)
        except Exception as e:
            print(f"[FaceAuth] ⚠️ No se pudo guardar embeddings: {e}")

    def extract_embedding(self, image_path):
        """Extrae el embedding facial de una imagen."""
        if not MEDIAPIPE_AVAILABLE or self.face_mesh is None:
            return None
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(img_rgb)
        if not results.multi_face_landmarks:
            return None
        landmarks = results.multi_face_landmarks[0].landmark
        embedding = np.array([[lm.x, lm.y, lm.z] for lm in landmarks]).flatten()
        return embedding

    def register_user(self, user_id, image_path):
        """Registra un nuevo usuario."""
        embedding = self.extract_embedding(image_path)
        if embedding is not None:
            self.embeddings[user_id] = embedding
            self._save_embeddings()
            return True
        return False

    def verify_user(self, image_path, threshold=0.6):
        """Verifica la identidad del usuario."""
        embedding = self.extract_embedding(image_path)
        if embedding is None:
            return None, 0.0
        best_match = None
        best_score = float('inf')
        for user_id, stored_embedding in self.embeddings.items():
            if len(stored_embedding) != len(embedding):
                continue
            dist = np.linalg.norm(stored_embedding - embedding)
            if dist < best_score:
                best_score = dist
                best_match = user_id
        if best_score < threshold:
            return best_match, best_score
        return None, best_score