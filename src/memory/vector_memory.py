# src/memory/vector_memory.py
"""
Memoria vectorial para recordar conversaciones, resultados y experiencias.
Usa ChromaDB si está disponible; si no, cae en un almacén simple TF‑IDF.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Intentar importar ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# Intentar importar sentence-transformers para embeddings
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


class VectorMemory:
    """
    Memoria a largo plazo basada en vectores.
    Guarda recuerdos con metadatos y permite búsqueda por similitud.
    """

    def __init__(self, persist_dir: str = "data/vector_memory"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.collection = None
        self.model = None
        self._fallback_memories = []
        self._fallback_vectors = []  # representación TF‑IDF simplificada

        if CHROMA_AVAILABLE:
            try:
                self.client = chromadb.Client(Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(self.persist_dir)
                ))
                self.collection = self.client.get_or_create_collection(
                    name="assistant_memory",
                    metadata={"hnsw:space": "cosine"}
                )
                print("[VectorMemory] ✅ ChromaDB inicializada.")
            except Exception as e:
                print(f"[VectorMemory] ⚠️ Error al iniciar ChromaDB: {e}. Usando fallback.")
                self.collection = None
        else:
            print("[VectorMemory] ⚠️ ChromaDB no instalada. Usando fallback TF‑IDF.")

        if ST_AVAILABLE and self.collection is not None:
            try:
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                print("[VectorMemory] ✅ Modelo de embeddings cargado.")
            except Exception as e:
                print(f"[VectorMemory] ⚠️ No se pudo cargar el modelo de embeddings: {e}")
                self.model = None

        # Cargar fallback si existe
        self._load_fallback()

    def _embed(self, text: str) -> List[float]:
        """Genera un vector para el texto usando el modelo disponible."""
        if self.model:
            return self.model.encode(text).tolist()
        else:
            # Fallback: vector de frecuencias de palabras (hash)
            words = text.lower().split()
            vector = [0.0] * 256
            for w in words:
                h = int(hashlib.md5(w.encode()).hexdigest(), 16) % 256
                vector[h] += 1.0
            norm = sum(v * v for v in vector) ** 0.5 or 1.0
            return [v / norm for v in vector]

    def _load_fallback(self):
        path = self.persist_dir / "fallback_memories.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._fallback_memories = json.load(f)
                self._fallback_vectors = [self._embed(m["text"]) for m in self._fallback_memories]
            except Exception:
                pass

    def _save_fallback(self):
        path = self.persist_dir / "fallback_memories.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._fallback_memories, f, ensure_ascii=False, indent=2)

    def add(self, text: str, metadata: Optional[Dict[str, Any]] = None, kind: str = "general") -> str:
        """
        Agrega un recuerdo. Devuelve un ID único.
        """
        mem_id = hashlib.md5(f"{text}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        meta = metadata or {}
        meta["kind"] = kind
        meta["timestamp"] = datetime.now().isoformat()

        if self.collection is not None:
            try:
                self.collection.add(
                    ids=[mem_id],
                    documents=[text],
                    metadatas=[meta],
                    embeddings=[self._embed(text)] if self.model else None
                )
            except Exception as e:
                print(f"[VectorMemory] Error al agregar: {e}")

        # Siempre guardar en fallback
        self._fallback_memories.append({"id": mem_id, "text": text, "metadata": meta})
        self._fallback_vectors.append(self._embed(text))
        self._save_fallback()
        return mem_id

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Busca recuerdos similares a la consulta.
        """
        results = []
        if self.collection is not None:
            try:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"]
                )
                for i, doc in enumerate(res["documents"][0]):
                    results.append({
                        "text": doc,
                        "metadata": res["metadatas"][0][i] if res["metadatas"] else {},
                        "distance": res["distances"][0][i] if res["distances"] else None
                    })
            except Exception as e:
                print(f"[VectorMemory] Error en búsqueda ChromaDB: {e}")

        # Si no hay resultados o no hay Chroma, usar fallback
        if not results and self._fallback_vectors:
            q_vec = self._embed(query)
            # Calcular similitud coseno
            similarities = []
            for i, vec in enumerate(self._fallback_vectors):
                dot = sum(a * b for a, b in zip(q_vec, vec))
                similarities.append((dot, i))
            similarities.sort(reverse=True)
            for _, idx in similarities[:top_k]:
                mem = self._fallback_memories[idx]
                results.append({
                    "text": mem["text"],
                    "metadata": mem.get("metadata", {}),
                    "distance": 1 - similarities[idx][0] if similarities else None
                })
        return results

    def get_context(self, query: str, max_chars: int = 2000) -> str:
        """
        Devuelve un texto con los recuerdos más relevantes para usar como contexto.
        """
        memories = self.search(query, top_k=5)
        if not memories:
            return ""
        lines = []
        total = 0
        for m in memories:
            snippet = m["text"][:300]
            if total + len(snippet) > max_chars:
                break
            lines.append(f"- {snippet}")
            total += len(snippet)
        return "\n".join(lines)