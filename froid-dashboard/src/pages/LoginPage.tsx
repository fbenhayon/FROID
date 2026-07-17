import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import { rememberProfessionalEmail } from "../lib/professional-prompts";

interface Props {
  onLogin: (user: FroidUser) => void;
  afterLoginPath?: string;
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

export const LoginPage: React.FC<Props> = ({ onLogin, afterLoginPath = "/dashboard" }) => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [googleReady, setGoogleReady] = useState(false);
  const googleButtonRef = useRef<HTMLDivElement | null>(null);
  const googleClientId = useMemo(
    () => ((import.meta as any).env?.VITE_GOOGLE_CLIENT_ID || "").trim(),
    [],
  );

  const completeLogin = async (payload: Record<string, string>) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(apiUrl("/api/auth/google"), {
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
      const target = data.user?.access_status?.onboarding_required
        ? "/access/register"
        : afterLoginPath;
      navigate(target, { replace: true });
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
    googleAuth.renderButton(googleButtonRef.current, {
      theme: "outline",
      size: "large",
      type: "standard",
      text: "signin_with",
      shape: "rectangular",
      width: 352,
    });
  }, [googleClientId, googleReady]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await completeLogin({ email, password, name: email.split("@", 1)[0] });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
        <div className="mb-6">
          <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">
            FROID
          </p>
          <h1 className="mt-2 text-2xl font-bold">Acesso profissional</h1>
          <p className="mt-2 text-sm text-slate-400">
            Entre com o e-mail profissional para acessar o painel clínico e os
            recursos multimodais.
          </p>
        </div>
        <div className="space-y-4">
          {googleClientId && (
            <div className="rounded-lg bg-white p-2">
              <div ref={googleButtonRef} className="flex justify-center" />
            </div>
          )}

          {googleClientId && (
            <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.24em] text-slate-500">
              <span className="h-px flex-1 bg-slate-700" />
              ou
              <span className="h-px flex-1 bg-slate-700" />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
              placeholder="seu@email.com"
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              placeholder="senha"
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
            />
            <button
              disabled={loading}
              className="w-full rounded-lg bg-cyan-600 px-3 py-2 text-sm font-bold text-white hover:bg-cyan-500 disabled:opacity-60"
            >
              {loading ? "Entrando..." : "Entrar com email e senha"}
            </button>
          </form>

          {googleClientId && loading && (
            <p className="text-sm text-slate-400">Validando credencial...</p>
          )}
          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
        <p className="mt-4 text-[11px] text-slate-500">
          {googleClientId
            ? "Login protegido por Google Identity Services com fallback local autorizado."
            : "Defina VITE_GOOGLE_CLIENT_ID para ativar o botão real do Google."}
        </p>
      </div>
    </div>
  );
};
