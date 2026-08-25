import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
 * Tela única de acesso: entrar e criar acesso no mesmo lugar, com o Google
 * servindo aos dois.
 *
 * Separar "login" de "cadastro" em telas distintas obriga quem chega a saber,
 * antes de qualquer coisa, se já tem conta — e é justamente o que a pessoa não
 * lembra. Pior no caso do Google: o mesmo botão resolve os dois casos, então
 * escondê-lo atrás da aba errada faz a pessoa procurar cadastro para uma conta
 * que ela já tem.
 */

type AccessMode = "entrar" | "criar";

interface Props {
  onLogin: (user: FroidUser) => void;
  afterLoginPath?: string;
  initialMode?: AccessMode;
}

type GoogleCredentialResponse = {
  credential?: string;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, string | number>,
          ) => void;
        };
      };
    };
  }
}

const SENHA_MINIMA_PADRAO = 6;

export const LoginPage: React.FC<Props> = ({
  onLogin,
  afterLoginPath = "/dashboard",
  initialMode = "entrar",
}) => {
  const navigate = useNavigate();
  const [mode, setMode] = useState<AccessMode>(initialMode);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [googleReady, setGoogleReady] = useState(false);
  // O servidor decide se o cadastro próprio existe. Sem entrega de e-mail
  // configurada ele não se completa, e oferecer a aba prometeria um caminho
  // que termina numa caixa de entrada que nunca recebe nada.
  const [registrationEnabled, setRegistrationEnabled] = useState(false);
  const [senhaMinima, setSenhaMinima] = useState(SENHA_MINIMA_PADRAO);
  const [cadastroEnviado, setCadastroEnviado] = useState(false);
  const [devLink, setDevLink] = useState("");
  const googleButtonRef = useRef<HTMLDivElement | null>(null);
  const googleClientId = useMemo(
    () => ((import.meta as any).env?.VITE_GOOGLE_CLIENT_ID || "").trim(),
    [],
  );

  const criando = mode === "criar";

  const completeLogin = async (
    payload: Record<string, string>,
    path = "/api/auth/google",
  ) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(apiUrl(path), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data.detail || "Falha no login");
      localStorage.setItem("froid_token", data.token);
      rememberProfessionalEmail(data.user?.email);
      onLogin(data.user);
      // A regra de destino mora em product-choice, e nao aqui. Esta copia
      // decidia sozinha que `onboarding_required` significa "va escolher um
      // produto", e por isso o administrador da plataforma continuava caindo na
      // tela de escolha mesmo depois de a excecao dele existir no App.
      const destino = defaultAuthenticatedPath(data.user, readProductChoice());
      navigate(
        destino === "/dashboard" ? afterLoginPath : destino,
        { replace: true },
      );
    } catch (err: any) {
      setError(err.message || "Falha no login");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!googleClientId || googleReady) return;

    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );

    const activateGoogle = () => setGoogleReady(true);

    if (existing) {
      if (window.google?.accounts?.id) activateGoogle();
      else existing.addEventListener("load", activateGoogle, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = activateGoogle;
    script.onerror = () =>
      setError("Não foi possível carregar o login do Google.");
    document.head.appendChild(script);
  }, [googleClientId, googleReady]);

  useEffect(() => {
    if (!googleReady || !googleClientId || !googleButtonRef.current) return;
    const googleAuth = window.google?.accounts?.id;
    if (!googleAuth) return;

    googleAuth.initialize({
      client_id: googleClientId,
      callback: (response) => {
        if (!response.credential) {
          setError("O Google não retornou uma credencial válida.");
          return;
        }
        void completeLogin({ credential: response.credential });
      },
    });
    // "continue_with" em vez de "signin_with": o mesmo botão entra e cadastra,
    // e prometer só "entrar" faria quem ainda não tem conta desviar para o
    // formulário achando que o Google não serve para ela.
    googleAuth.renderButton(googleButtonRef.current, {
      theme: "outline",
      size: "large",
      type: "standard",
      text: "continue_with",
      shape: "rectangular",
      width: 352,
    });
  }, [googleClientId, googleReady]);

  useEffect(() => {
    fetch(apiUrl("/api/auth/config"))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setRegistrationEnabled(Boolean(data?.registration_enabled));
        if (data?.password_min_length) setSenhaMinima(Number(data.password_min_length));
      })
      .catch(() => undefined);
  }, []);

  const trocarModo = (proximo: AccessMode) => {
    setMode(proximo);
    setError("");
    setPassword("");
    setPasswordConfirm("");
  };

  const entrar = async (e: React.FormEvent) => {
    e.preventDefault();
    await completeLogin({ email, password }, "/api/auth/login");
  };

  const cadastrar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== passwordConfirm) {
      setError("A confirmação da senha não confere");
      return;
    }
    setLoading(true);
    try {
      const data = await postAuthJson("/api/auth/register", {
        name,
        email,
        password,
        password_confirm: passwordConfirm,
      });
      setDevLink(String(data.dev_link || ""));
      setCadastroEnviado(true);
    } catch (err: any) {
      setError(err.message || "Não foi possível concluir o cadastro");
    } finally {
      setLoading(false);
    }
  };

  const reenviar = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await postAuthJson("/api/auth/resend-verification", { email });
      setDevLink(String(data.dev_link || ""));
    } catch (err: any) {
      setError(err.message || "Não foi possível reenviar");
    } finally {
      setLoading(false);
    }
  };

  if (cadastroEnviado) {
    return (
      <AccessCard
        titulo="Confirme seu e-mail"
        subtitulo={
          "Enviamos um link de confirmação para " +
          email +
          ". Abra a mensagem para ativar o acesso e escolher o produto."
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            Não chegou? Confira a caixa de spam antes de pedir outro — cada novo
            pedido invalida o link anterior.
          </p>
          <button onClick={reenviar} disabled={loading} className={botaoClasse}>
            {loading ? "Reenviando..." : "Reenviar e-mail de confirmação"}
          </button>
          <LinkDeDesenvolvimento link={devLink} />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button
            type="button"
            onClick={() => {
              setCadastroEnviado(false);
              trocarModo("entrar");
            }}
            className="w-full text-center text-sm text-cyan-400"
          >
            Voltar para o acesso
          </button>
        </div>
      </AccessCard>
    );
  }

  return (
    <AccessCard
      titulo="Acesso FROID"
      subtitulo={
        criando
          ? "Crie o acesso de profissional, clínica ou empresa. O cadastro do produto vem logo depois."
          : "Entre para acessar o painel clínico e os recursos multimodais."
      }
      rodape={
        <p className="mt-4 text-[11px] text-slate-500">
          {googleClientId
            ? "Acesso protegido por Google Identity Services. O mesmo botão entra e cria conta."
            : "Defina VITE_GOOGLE_CLIENT_ID para ativar o botão real do Google."}
        </p>
      }
    >
      <div className="space-y-4">
        {googleClientId && (
          <div className="rounded-lg bg-white p-2">
            <div ref={googleButtonRef} className="flex justify-center" />
          </div>
        )}

        {googleClientId && (
          <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.24em] text-slate-500">
            <span className="h-px flex-1 bg-slate-700" />
            ou com e-mail
            <span className="h-px flex-1 bg-slate-700" />
          </div>
        )}

        {registrationEnabled && (
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-950/60 p-1">
            {(["entrar", "criar"] as AccessMode[]).map((opcao) => (
              <button
                key={opcao}
                type="button"
                onClick={() => trocarModo(opcao)}
                className={
                  "rounded-md px-3 py-2 text-sm font-bold transition " +
                  (mode === opcao
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:text-white")
                }
              >
                {opcao === "entrar" ? "Entrar" : "Criar acesso"}
              </button>
            ))}
          </div>
        )}

        {criando ? (
          <form onSubmit={cadastrar} className="space-y-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoComplete="name"
              placeholder="nome completo ou razão social"
              className={campoClasse}
            />
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
              autoComplete="email"
              placeholder="seu@email.com"
              className={campoClasse}
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              minLength={senhaMinima}
              autoComplete="new-password"
              placeholder={"senha (mínimo " + senhaMinima + " caracteres)"}
              className={campoClasse}
            />
            <input
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              type="password"
              required
              minLength={senhaMinima}
              autoComplete="new-password"
              placeholder="repita a senha"
              className={campoClasse}
            />
            <p className="text-[11px] leading-5 text-slate-500">
              A senha precisa combinar letras e números. Ao continuar você
              concorda com os{" "}
              <Link to="/termos" className="text-cyan-400">
                termos de uso
              </Link>{" "}
              e a{" "}
              <Link to="/privacidade" className="text-cyan-400">
                política de privacidade
              </Link>
              .
            </p>
            <button disabled={loading} className={botaoClasse}>
              {loading ? "Enviando confirmação..." : "Criar acesso"}
            </button>
          </form>
        ) : (
          <form onSubmit={entrar} className="space-y-3">
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
              autoComplete="email"
              placeholder="seu@email.com"
              className={campoClasse}
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              autoComplete="current-password"
              placeholder="senha"
              className={campoClasse}
            />
            <button disabled={loading} className={botaoClasse}>
              {loading ? "Entrando..." : "Entrar"}
            </button>
          </form>
        )}

        {googleClientId && loading && (
          <p className="text-sm text-slate-400">Validando credencial...</p>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}

        {!criando && (
          <Link
            to="/recuperar-senha"
            className="block text-sm text-slate-400 hover:text-cyan-400"
          >
            Esqueci minha senha
          </Link>
        )}
      </div>
    </AccessCard>
  );
};
