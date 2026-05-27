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
        try:
            body = await request.json()
        except Exception:
            logger.warning("Payload inválido (no es JSON)")
            return []
        logger.info(f"Payload recibido de n8n: conv_id='{body.get('conversation_id', '')}', sender='{body.get('sender', '')}', message='{str(body.get('message', ''))[:50]}'")

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
            conversation_id = (
                body.get("conversation_id")
                or body.get("conversationId")
                or body.get("conversation")
                or ""
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
                    conversation_id=str(conversation_id),
                    es_propio=False,
                    tags=tags,
                ))

        return mensajes

    async def enviar_mensaje(self, telefono: str, mensaje: str, conversation_id: str = "", private: bool = False) -> bool:
        if not self.webhook_url:
            logger.warning("N8N_WEBHOOK_URL no configurado, no se puede enviar respuesta")
            return False

        payload = {
            "respuesta": mensaje,
            "telefono": telefono,
            "conversation_id": conversation_id,
            "private": private,
        }
        logger.info(f"Enviando callback a n8n: conversation_id='{conversation_id}', telefono='{telefono}', private={private}, url={self.webhook_url}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(self.webhook_url, json=payload)
                if r.status_code not in (200, 201, 202):
                    logger.error(f"Error al enviar a n8n: {r.status_code} — {r.text}")
                    return False
                logger.info(f"Callback exitoso a n8n para {telefono} (conv: {conversation_id}, privado: {private})")
                return True
        except Exception as e:
            logger.error(f"Error de conexión con n8n: {e}")
            return False
