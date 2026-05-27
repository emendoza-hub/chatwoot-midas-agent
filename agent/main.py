import os
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
REQUIRED_TAG = os.getenv("REQUIRED_TAG", "")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    if REQUIRED_TAG:
        logger.info(f"Filtro de tag activado: solo responde a conversaciones con tag '{REQUIRED_TAG}'")
    else:
        logger.info("Sin filtro de tag — responde a todos los mensajes")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "agentkit"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return {"challenge": resultado}
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        mensajes = await proveedor.parsear_webhook(request)

        respuestas = []

        for msg in mensajes:
            if msg.es_propio or not msg.texto:
                continue

            if REQUIRED_TAG and (not msg.tags or REQUIRED_TAG not in msg.tags):
                logger.info(f"Mensaje de {msg.telefono} ignorado — falta tag '{REQUIRED_TAG}' (tags: {msg.tags})")
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            historial = await obtener_historial(msg.telefono)

            respuesta = await generar_respuesta(msg.texto, historial)

            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            menciona_agente = bool(re.search(r'(claudia|@claudia)', msg.texto, re.IGNORECASE))
            enviado = await proveedor.enviar_mensaje(
                msg.telefono, respuesta,
                conversation_id=msg.conversation_id,
                private=menciona_agente
            )
            logger.info(f"Respuesta a {msg.telefono}: {respuesta[:100]}... (enviado: {enviado}, privado: {menciona_agente})")

            respuestas.append({
                "telefono": msg.telefono,
                "respuesta": respuesta,
                "conversation_id": msg.conversation_id,
                "private": menciona_agente,
                "enviado": enviado,
            })

        return {"status": "ok", "respuestas": respuestas}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
