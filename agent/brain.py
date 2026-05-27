import os
import yaml
import logging
from pathlib import Path
from openai import AsyncOpenAI
from dotenv import load_dotenv

from agent.tools import cargar_info_negocio, buscar_en_knowledge

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))


BASE_DIR = Path(__file__).resolve().parent.parent


def cargar_config_prompts() -> dict:
    try:
        with open(BASE_DIR / "config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente útil. Responde en español.")


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?")


def _build_enriched_system_prompt(consulta_usuario: str) -> str:
    base = cargar_system_prompt()

    info_negocio = cargar_info_negocio()
    negocio = info_negocio.get("negocio", {})
    contexto_negocio = f"Nombre del negocio: {negocio.get('nombre', 'No disponible')}\n"
    contexto_negocio += f"Descripción: {negocio.get('descripcion', 'No disponible')}\n"
    contexto_negocio += f"Horario: {negocio.get('horario', 'No disponible')}"

    conocimiento = buscar_en_knowledge(consulta_usuario)
    if conocimiento and "No encontré" not in conocimiento:
        contexto_negocio += f"\n\nInformación relevante de la base de conocimiento:\n{conocimiento}"

    return f"{base}\n\n## Contexto del negocio\n{contexto_negocio}"


async def generar_respuesta(mensaje: str, historial: list[dict]) -> str:
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = _build_enriched_system_prompt(mensaje)

    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    mensajes.append({
        "role": "user",
        "content": mensaje
    })

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt}
            ] + mensajes,
            extra_headers={
                "HTTP-Referer": "https://midas-red.agentkit.app",
                "X-Title": "Midas Red - AgentKit"
            }
        )

        respuesta = response.choices[0].message.content
        logger.info(f"Respuesta generada ({response.usage.prompt_tokens} in / {response.usage.completion_tokens} out)")
        return respuesta

    except Exception as e:
        logger.error(f"Error OpenRouter API: {e}")
        return obtener_mensaje_error()
