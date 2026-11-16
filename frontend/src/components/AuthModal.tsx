import React, { useState } from "react";
import { X, Lock, Mail, User as UserIcon, AlertCircle, Loader2 } from "lucide-react";
import { loginUser, recoverPassword, registerUser } from "../api";
import type { User } from "../types";

interface AuthModalProps {
  isOpen: boolean;
  resetToken: string | null;
  onClose: () => void;
  onDismissResetLink: () => void;
  onPasswordReset: () => void;
  onSuccess: (user: User) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen, resetToken, onClose, onDismissResetLink, onPasswordReset, onSuccess,
}) => {
  const [mode, setMode] = useState<"login" | "register" | "forgot">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const isReset = resetToken !== null;
  const isRegister = mode === "register" && !isReset;
  const isForgot = mode === "forgot" && !isReset;

  const changeMode = (nextMode: typeof mode) => {
    setMode(nextMode);
    setError(null);
    setMessage(null);
    setPassword("");
    setConfirmation("");
  };

  const close = () => {
    if (loading) return;
    changeMode("login");
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      if (isReset) {
        if (password !== confirmation) throw new Error("As senhas devem ser iguais");
        if (new TextEncoder().encode(password).length > 72) {
          throw new Error("A senha deve ter no máximo 72 bytes");
        }
        const result = await recoverPassword({ token: resetToken, password });
        changeMode("login");
        onPasswordReset();
        setMessage(result);
        return;
      }
      if (isForgot) {
        setMessage(await recoverPassword({ email }));
        return;
      }
      if (isRegister) {
        if (!name.trim()) throw new Error("Informe seu nome");
        if (password.length < 6) throw new Error("A senha deve ter no mínimo 6 caracteres");
        const res = await registerUser(name, email, password);
        onSuccess(res.user);
      } else {
        const res = await loginUser(email, password);
        onSuccess(res.user);
      }
      changeMode("login");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha na autenticação");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-modal-header">
          {isReset || isForgot ? (
            <h2 className="auth-recovery-title">{isReset ? "Redefinir senha" : "Recuperar senha"}</h2>
          ) : <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${!isRegister ? "active" : ""}`}
              onClick={() => changeMode("login")}
              disabled={loading}
            >
              Entrar
            </button>
            <button
              type="button"
              className={`auth-tab ${isRegister ? "active" : ""}`}
              onClick={() => changeMode("register")}
              disabled={loading}
            >
              Criar Conta
            </button>
          </div>}
          <button className="auth-close-btn" onClick={close} disabled={loading} aria-label="Fechar">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && (
            <div className="auth-error" role="alert">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
          {message && <p className="auth-message" role="status">{message}</p>}

          {isRegister && (
            <div className="form-group">
              <label>Nome Completo</label>
              <div className="input-wrap">
                <UserIcon size={16} className="input-icon" />
                <input
                  type="text"
                  placeholder="Seu nome"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          {!isReset && <div className="form-group">
            <label htmlFor="auth-email">E-mail</label>
            <div className="input-wrap">
              <Mail size={16} className="input-icon" />
              <input
                type="email"
                id="auth-email"
                autoComplete="email"
                placeholder="seu.email@exemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>}

          {!isForgot && <div className="form-group">
            <label htmlFor="auth-password">{isReset ? "Nova senha" : "Senha"}</label>
            <div className="input-wrap">
              <Lock size={16} className="input-icon" />
              <input
                type="password"
                id="auth-password"
                autoComplete={isRegister || isReset ? "new-password" : "current-password"}
                minLength={isRegister || isReset ? 6 : undefined}
                placeholder="Mínimo de 6 caracteres"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>}

          {!isRegister && !isForgot && !isReset && (
            <button
              type="button"
              className="auth-switch-link auth-recovery-link"
              disabled={loading}
              onClick={() => changeMode("forgot")}
            >
              Esqueci minha senha
            </button>
          )}

          {isReset && (
            <div className="form-group">
              <label htmlFor="auth-confirmation">Confirme a nova senha</label>
              <div className="input-wrap">
                <Lock size={16} className="input-icon" />
                <input
                  type="password"
                  id="auth-confirmation"
                  autoComplete="new-password"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? (
              <>
                <Loader2 size={16} className="spin" /> Processando...
              </>
            ) : isReset ? (
              "Salvar nova senha"
            ) : isForgot ? (
              "Enviar link por e-mail"
            ) : isRegister ? (
              "Cadastrar e Iniciar"
            ) : (
              "Entrar no Sistema"
            )}
          </button>
        </form>

        <div className="auth-footer">
          {isReset || isForgot ? (
            <button
              type="button"
              className="auth-switch-link"
              disabled={loading}
              onClick={() => {
                if (isReset) onDismissResetLink();
                changeMode(isReset ? "forgot" : "login");
              }}
            >
              {isReset ? "Solicitar outro link" : "Voltar para entrar"}
            </button>
          ) : (
          <>
          <p>
            {isRegister ? "Já possui uma conta?" : "Ainda não tem conta?"}{" "}
            <button
              type="button"
              className="auth-switch-link"
              disabled={loading}
              onClick={() => changeMode(isRegister ? "login" : "register")}
            >
              {isRegister ? "Faça login" : "Cadastre-se gratuitamente"}
            </button>
          </p>
          </>
          )}
        </div>
      </div>
    </div>
  );
};
