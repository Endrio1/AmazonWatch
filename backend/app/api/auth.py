"""Endpoints de autenticação e registro de usuários."""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.password_recovery import issue_password_reset, reset_digest, send_recovery_email
from app.schemas import PasswordReset, PasswordResetRequest, Token, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Cadastra um novo usuário no sistema."""
    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="E-mail inválido")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter no mínimo 6 caracteres")

    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um usuário cadastrado com este e-mail",
        )

    user = User(
        email=email_clean,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "ver": user.password_version})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Autentica o usuário e retorna o token de acesso."""
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta de usuário inativa",
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "ver": user.password_version})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: PasswordResetRequest, tasks: BackgroundTasks) -> dict[str, str]:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(status_code=503, detail="Recuperação por e-mail indisponível")

    email = payload.email.strip().lower()
    tasks.add_task(issue_password_reset, email)
    return {"message": "Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha."}


@router.post("/reset-password")
def reset_password(payload: PasswordReset, tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, str]:
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="A senha deve ter no máximo 72 bytes")

    user = db.scalar(
        select(User)
        .where(User.password_reset_digest == reset_digest(payload.token), User.is_active.is_(True))
        .with_for_update()
    )
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite um novo link.")

    user.password_hash = hash_password(payload.password)
    user.password_reset_digest = None
    user.password_reset_expires_at = None
    user.password_version += 1
    db.commit()

    tasks.add_task(
        send_recovery_email, user.email, "Senha do AmazonWatch alterada",
        "A senha da sua conta AmazonWatch foi alterada. Se você não fez essa alteração, redefina sua senha.",
    )
    return {"message": "Senha redefinida. Entre com a nova senha."}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do usuário autenticado."""
    return UserOut.model_validate(current_user)
