# src/actions/deep_research.py
"""
Investigación profunda con múltiples pasos y citas.
Realiza búsquedas iterativas para profundizar en un tema.
"""

import re
from typing import Dict, Any, Optional

from src.actions.web_search import web_search
from src.actions.file_processor import file_processor


def deep_research(parameters: Dict[str, Any], player=None, speak=None) -> str:
    """
    Realiza una investigación profunda sobre un tema.
    Parámetros:
        topic (str): Tema a investigar.
        depth (int): Número de niveles de profundidad (1-3). Default 2.
        save (bool): Guardar el informe en un archivo. Default True.
    """
    topic = parameters.get("topic", "").strip()
    depth = min(3, max(1, int(parameters.get("depth", 2))))
    save = parameters.get("save", True)
    
    if not topic:
        return "Necesito un tema para investigar, señor."
        
    if speak:
        speak(f"Iniciando investigación profunda sobre {topic}. Esto puede tomar un momento, señor.")
        
    if player:
        player.write_log(f"[DeepResearch] Iniciando investigación sobre: {topic} (profundidad {depth})")
    
    # ===== PASO 1: Búsqueda inicial =====
    if player:
        player.write_log("[DeepResearch] Realizando búsqueda inicial...")
    
    initial_results = web_search({
        "query": topic,
        "mode": "research",
        "max_results": 8
    }, player)
    
    # ===== PASO 2: Profundizar (si depth >= 2) =====
    all_content = [initial_results]
    
    if depth >= 2:
        if player:
            player.write_log("[DeepResearch] Profundizando en el tema...")
        
        # Extraer posibles subtemas de los resultados iniciales
        # (simplificado: hacemos una búsqueda más específica)
        follow_up_queries = [
            f"{topic} detailed analysis",
            f"{topic} latest developments",
            f"{topic} expert opinions"
        ]
        
        for query in follow_up_queries[:depth]:
            if player:
                player.write_log(f"[DeepResearch] Búsqueda adicional: {query}")
            result = web_search({
                "query": query,
                "mode": "research",
                "max_results": 5
            }, player)
            all_content.append(f"\n\n--- {query} ---\n\n{result}")
    
    # ===== PASO 3: Combinar resultados =====
    combined_content = "\n".join(all_content)
    
    # ===== PASO 4: Guardar en archivo (si se solicita) =====
    if save:
        # Limpiar el nombre del archivo
        safe_topic = re.sub(r'[^\w\s]', '', topic)[:40].replace(' ', '_')
        filename = f"research_{safe_topic}.txt"
        
        # Crear informe con encabezado
        header = f"""
╔═══════════════════════════════════════════════════════════════╗
║           INFORME DE INVESTIGACIÓN - AP0L0                  ║
╠═══════════════════════════════════════════════════════════════╣
║  Tema: {topic}
║  Profundidad: {depth}
║  Fecha: {__import__('time').strftime('%Y-%m-%d %H:%M')}
╚═══════════════════════════════════════════════════════════════╝

"""
        full_content = header + combined_content
        
        result = file_processor({
            "file_path": "",  # Generar nuevo archivo
            "action": "write",
            "content": full_content,
            "name": filename
        }, player)
        
        if speak:
            speak(f"Investigación completada. Guardada en {filename}")
        
        return f"Investigación completada. {result}\n\n--- Resumen del contenido ---\n\n{combined_content[:800]}..."
    else:
        return combined_content