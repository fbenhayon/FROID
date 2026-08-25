import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { rememberProfessionalEmail } from "../lib/professional-prompts";
import {
  defaultAuthenticatedPath,
  readProductChoice,
} from "../lib/product-choice";
import {
  AccessCard,
  LinkDeDesenvolvimento,
  botaoClasse,
  campoClasse,
  postAuthJson,
} from "../components/access/AccessShell";

/**
 * As duas telas que chegam por link de e-mail: verificação e recuperação.
 *
 * Entrar e criar acesso ficam juntos em LoginPage, que é a porta. Estas aqui
 * não são porta: só existem quando alguém abre uma mensagem, e por isso ficam
 * fora do bundle inicial.
 */

const SENHA_MINIMA_PADRAO = 6;

type LoginProp = { onLogin: (user: FroidUser) => void };

/** Guarda a sessão devolvida por verificação ou recuperação e entra no painel. */
function useEntrarComSessao(onLogin: (user: FroidUser) => void) {
  const navigate = useNavigate();
  return (data: any) => {
    localStorage.setItem("froid_token", data.token);
    rememberProfessionalEmail(data.user?.email);
    onLogin(data.user);
    navigate(
      defaultAuthenticatedPath(data.user, readProductChoice()),
      { replace: true },
    );
  };
}

function useSenhaMinima() {
  const [senhaMinima, setSenhaMinima] = useState(SENHA_MINIMA_PADRAO);
  useEffect(() => {
    fetch(apiUrl("/api/auth/config"))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.password_min_length) setSenhaMinima(Number(data.password_min_length));
      })
      .catch(() => undefined);
  }, []);
  return senhaMinima;
}

export const VerifyEmailPage: React.FC<LoginProp> = ({ onLogin }) => {
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [reenviado, setReenviado] = useState(false);
  const [devLink, setDevLink] = useState("");
  const entrarComSessao = useEntrarComSessao(onLogin);

  useEffect(() => {
    if (!token) {
      setError("Link de verificação sem token.");
      return;
    }
    let ativo = true;
    postAuthJson("/api/auth/verify-email", { token })
      .then((data) => {
        if (ativo) entrarComSessao(data);
      })
      .catch((err: any) => {
        if (ativo) setError(err.message || "Link inválido ou expirado");
      });
    return () => {
      ativo = false;
    };
    // Roda uma vez por token: repetir a chamada gastaria um token de uso único.
  }, [token]);

  const reenviar = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = await postAuthJson("/api/auth/resend-verification", { email });
      setDevLink(String(data.dev_link || ""));
      setReenviado(true);
    } catch (err: any) {
      setError(err.message || "Não foi possível reenviar");
    }
  };

  if (!error) {
    return (
      <AccessCard titulo="Confirmando seu e-mail" subtitulo="Um instante...">
        <p className="text-sm text-slate-400">Validando o link de acesso.</p>
      </AccessCard>
    );
  }

  return (
    <AccessCard titulo="Link não pôde ser usado" subtitulo={error}>
      {reenviado ? (
        <p className="text-sm text-slate-300">
          Se este e-mail tiver um cadastro pendente, um novo link acabou de ser
          enviado.
        </p>
      ) : (
        <form onSubmit={reenviar} className="space-y-3">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
            autoComplete="email"
            placeholder="seu@email.com"
            className={campoClasse}
          />
          <button className={botaoClasse}>Receber novo link</button>
        </form>
      )}
      <LinkDeDesenvolvimento link={devLink} />
      <Link to="/login" className="mt-4 block text-center text-sm text-cyan-400">
        Voltar para o acesso
      </Link>
    </AccessCard>
  );
};

export const PasswordResetPage: React.FC<LoginProp> = ({ onLogin }) => {
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pedido, setPedido] = useState(false);
  const [devLink, setDevLink] = useState("");
  const senhaMinima = useSenhaMinima();
  const entrarComSessao = useEntrarComSessao(onLogin);

  const pedirLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await postAuthJson("/api/auth/password-reset", { email });
      setDevLink(String(data.dev_link || ""));
      setPedido(true);
    } catch (err: any) {
      setError(err.message || "Não foi possível enviar o link");
    } finally {
      setLoading(false);
    }
  };

  const definirSenha = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== passwordConfirm) {
      setError("A confirmação da senha não confere");
      return;
    }
    setLoading(true);
    try {
      const data = await postAuthJson("/api/auth/password-reset/confirm", {
        token,
        password,
        password_confirm: passwordConfirm,
      });
      entrarComSessao(data);
    } catch (err: any) {
      setError(err.message || "Não foi possível definir a nova senha");
    } finally {
      setLoading(false);
    }
  };

  if (token) {
    return (
      <AccessCard
        titulo="Definir nova senha"
        subtitulo="Ao concluir, todas as sessões abertas nesta conta serão encerradas."
      >
        <form onSubmit={definirSenha} className="space-y-3">
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            minLength={senhaMinima}
            autoComplete="new-password"
            placeholder={"nova senha (mínimo " + senhaMinima + " caracteres)"}
            className={campoClasse}
          />
          <input
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            type="password"
            required
            minLength={senhaMinima}
            autoComplete="new-password"
            placeholder="repita a nova senha"
            className={campoClasse}
          />
          <button disabled={loading} className={botaoClasse}>
            {loading ? "Salvando..." : "Salvar e entrar"}
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        <Link to="/login" className="mt-4 block text-center text-sm text-cyan-400">
          Voltar para o acesso
        </Link>
      </AccessCard>
    );
  }

  return (
    <AccessCard
      titulo="Recuperar senha"
      subtitulo="Informe o e-mail do acesso e enviaremos um link para definir uma nova senha."
    >
      {pedido ? (
        <p className="text-sm text-slate-300">
          Se este e-mail tiver um acesso no FROID, o link acabou de ser enviado.
          Ele vale por uma hora e só pode ser usado uma vez.
        </p>
      ) : (
        <form onSubmit={pedirLink} className="space-y-3">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
            autoComplete="email"
            placeholder="seu@email.com"
            className={campoClasse}
          />
          <button disabled={loading} className={botaoClasse}>
            {loading ? "Enviando..." : "Enviar link de recuperação"}
          </button>
        </form>
      )}
      <LinkDeDesenvolvimento link={devLink} />
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <Link to="/login" className="mt-4 block text-center text-sm text-cyan-400">
        Voltar para o acesso
      </Link>
    </AccessCard>
  );
};
