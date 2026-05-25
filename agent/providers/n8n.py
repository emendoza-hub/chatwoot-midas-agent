import os
import logging
import httpx
from fastapi import Request
from agent.providers.base import ProveedorWhatsApp, MensajeEntrante

logger = logging.getLogger("agentkit")


class ProveedorN8N(ProveedorWhatsApp):
    def __init__(self):
        self.webhook_url = os.getenv("N8N_WEBHOOK_URL", "")
        if not self.webhook_url:
            logger.warning("N8N_WEBHOOK_URL no configurado en .env")

    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        body = await request.json()
        logger.info(f"Payload recibido de n8n: {body}")

        mensajes = []

        if isinstance(body, dict):
            texto = (
                body.get("mensaje")
                or body.get("message")
                or body.get("text")
                or body.get("content")
                or body.get("texto")
                or ""
            )
            telefono = (
                body.get("telefono")
                or body.get("from")
                or body.get("sender")
                or body.get("phone_number")
                or body.get("phone")
                or "desconocido"
            )
            mensaje_id = (
                body.get("mensaje_id")
                or body.get("message_id")
                or body.get("id")
                or str(hash(str(body)))
            )

            if isinstance(telefono, dict):
                telefono = telefono.get("phone_number", telefono.get("id", "desconocido"))
            if isinstance(telefono, (int, float)):
                telefono = str(telefono)

            tags_raw = body.get("tags") or body.get("etiquetas") or []
            if isinstance(tags_raw, str):
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            elif isinstance(tags_raw, list):
                tags = [str(t) for t in tags_raw]
            else:
                tags = []

            if texto:
                mensajes.append(MensajeEntrante(
                    telefono=str(telefono),
                    texto=str(texto),
                    mensaje_id=str(mensaje_id),
                    es_propio=False,
                    tags=tags,
                ))

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        if not self.webhook_url:
            logger.warning("N8N_WEBHOOK_URL no configurado, no se puede enviar respuesta")
            return False

        payload = {
            "respuesta": mensaje,
            "telefono": telefono,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.webhook_url, json=payload)
                if r.status_code not in (200, 201, 202):
                    logger.error(f"Error al enviar a n8n: {r.status_code} — {r.text}")
                    return False
                logger.info(f"Respuesta enviada a n8n para {telefono}")
                return True
        except Exception as e:
            logger.error(f"Error de conexión con n8n: {e}")
            return False
