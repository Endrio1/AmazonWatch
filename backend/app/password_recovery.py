"""Emissão de links de recuperação e entrega por SMTP."""

import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from hashlib import sha256

from sqlalchemy import or_, update

from app.config import get_settings
from app.db import session_scope
from app.models import User

log = logging.getLogger(__name__)
RESET_LIFETIME = timedelta(minutes=30)
REQUEST_INTERVAL = timedelta(minutes=2)


def reset_digest(token: str) -> str:
    return sha256(token.encode("ascii")).hexdigest()


def send_recovery_email(recipient: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    context = ssl.create_default_context()

    try:
        if settings.smtp_port == 465:
            connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
        else:
            connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with connection:
            if settings.smtp_port != 465:
                connection.starttls(context=context)
            if settings.smtp_user:
                connection.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            connection.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("Falha na entrega de e-mail de recuperação (%s)", type(exc).__name__)


def issue_password_reset(email: str) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + RESET_LIFETIME

    with session_scope() as db:
        recipient = db.scalar(
            update(User)
            .where(
                User.email == email,
                User.is_active.is_(True),
                or_(
                    User.password_reset_expires_at.is_(None),
                    User.password_reset_expires_at <= expires_at - REQUEST_INTERVAL,
                ),
            )
            .values(password_reset_digest=reset_digest(token), password_reset_expires_at=expires_at)
            .returning(User.email)
        )

    if recipient:
        url = f"{get_settings().app_public_url}#redefinir-senha={token}"
        send_recovery_email(
            recipient,
            "Redefinição de senha do AmazonWatch",
            f"Use o link abaixo para redefinir sua senha em até 30 minutos.\n\n{url}\n\n"
            "Se você não solicitou a recuperação, ignore este e-mail.",
        )
