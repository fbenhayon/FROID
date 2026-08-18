"""Envio de e-mail transacional por SMTP.

O FROID nasceu sem nenhum canal de e-mail: toda identidade profissional vinha
do Google, que já provava o endereço antes de o backend ver o usuário. Com o
cadastro por senha o e-mail deixa de ser dado de contato e passa a ser a prova
de que a pessoa controla aquele endereço — por isso este módulo é pré-requisito
do cadastro, e não um enfeite de notificação.

Fica deliberadamente na biblioteca padrão (`smtplib`). O volume aqui é de
verificação e recuperação de senha, não de campanha: um provedor SMTP qualquer
resolve, e evitar mais uma dependência mantém o backend auditável.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formataddr, make_msgid
import logging
import os
import smtplib
import ssl

LOGGER = logging.getLogger("froid.mailer")


class MailerError(RuntimeError):
    """Falha no envio. Nunca carrega o corpo da mensagem nem o destinatário."""


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _env_flag(name: str, default: str) -> bool:
    return _env(name, default).lower() in {"1", "true", "yes", "on"}


SMTP_HOST = _env("FROID_SMTP_HOST")
SMTP_PORT = int(_env("FROID_SMTP_PORT", "587") or "587")
SMTP_USER = _env("FROID_SMTP_USER")
SMTP_PASSWORD = _env("FROID_SMTP_PASSWORD")
SMTP_FROM = _env("FROID_SMTP_FROM") or SMTP_USER
SMTP_FROM_NAME = _env("FROID_SMTP_FROM_NAME", "FROID")
SMTP_STARTTLS = _env_flag("FROID_SMTP_STARTTLS", "true")
SMTP_SSL = _env_flag("FROID_SMTP_SSL", "false")
SMTP_TIMEOUT = float(_env("FROID_SMTP_TIMEOUT", "15") or "15")

# Escotilha explícita de desenvolvimento: sem SMTP configurado, o link de
# verificação volta na resposta da API em vez de ser enviado. Nunca deve ficar
# ligada em produção — é ela que transformaria "verificar e-mail" em teatro.
SMTP_DEV_ECHO = _env_flag("FROID_SMTP_DEV_ECHO", "false")


def mailer_enabled() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def dev_echo_enabled() -> bool:
    return SMTP_DEV_ECHO and not mailer_enabled()


def send_email(to_address: str, subject: str, text_body: str, html_body: str = "") -> None:
    """Envia uma mensagem. Bloqueante — chame por `asyncio.to_thread`.

    O laço de eventos do FastAPI atende as sessões ao vivo (o tick de 1s do
    stream multimodal); um SMTP lento no laço congelaria o atendimento de todo
    mundo enquanto espera o handshake.
    """
    destino = str(to_address or "").strip()
    if not destino:
        raise MailerError("destinatário ausente")
    if not mailer_enabled():
        raise MailerError("SMTP não configurado")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    message["To"] = destino
    message["Message-ID"] = make_msgid()
    # Correio transacional: nenhum cliente deve tratar isto como marketing nem
    # gerar resposta automática de férias para um link de uso único.
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    try:
        if SMTP_SSL:
            with smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context
            ) as client:
                if SMTP_USER:
                    client.login(SMTP_USER, SMTP_PASSWORD)
                client.send_message(message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as client:
                client.ehlo()
                if SMTP_STARTTLS:
                    client.starttls(context=context)
                    client.ehlo()
                if SMTP_USER:
                    client.login(SMTP_USER, SMTP_PASSWORD)
                client.send_message(message)
    except Exception as exc:
        # A exceção do smtplib pode conter o endereço de destino na mensagem.
        # O log fica com o tipo e o host; o e-mail de quem se cadastrou não vai
        # parar no arquivo de log por causa de uma falha de entrega.
        LOGGER.warning(
            "Falha no envio SMTP (host=%s, erro=%s)", SMTP_HOST, type(exc).__name__
        )
        raise MailerError("falha ao enviar e-mail") from exc
