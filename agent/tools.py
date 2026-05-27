import os
import re
import yaml
import logging
from pathlib import Path

logger = logging.getLogger("agentkit")

BASE_DIR = Path(__file__).resolve().parent.parent


def cargar_info_negocio() -> dict:
    try:
        with open(BASE_DIR / "config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> str:
    info = cargar_info_negocio()
    return info.get("negocio", {}).get("horario", "No disponible")


def buscar_en_knowledge(consulta: str) -> str:
    knowledge_dir = BASE_DIR / "knowledge"

    if not knowledge_dir.exists():
        return "No hay archivos de conocimiento disponibles."

    tokens = set(re.findall(r'\w+', consulta.lower()))
    if not tokens:
        return "No encontré información específica sobre eso en mis archivos."

    resultados = []

    for archivo in knowledge_dir.iterdir():
        if archivo.name.startswith(".") or not archivo.is_file():
            continue
        try:
            contenido = archivo.read_text(encoding="utf-8")
            contenido_lower = contenido.lower()
            matching = sum(1 for t in tokens if t in contenido_lower)
            if matching > 0:
                relevancia = matching / len(tokens)
                resultados.append((relevancia, f"[{archivo.name}]: {contenido[:500]}"))
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        resultados.sort(key=lambda x: -x[0])
        return "\n---\n".join(r[1] for r in resultados[:3])
    return "No encontré información específica sobre eso en mis archivos."
