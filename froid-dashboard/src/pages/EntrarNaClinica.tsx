/** Resgate de convite de equipe (profissional entrando numa clínica).
 *
 *  Espelha o fluxo do paciente (PatientInvitePage): página PÚBLICA, com a cara
 *  da clínica, onde o profissional se cadastra/entra ali mesmo e passa a integrar
 *  a equipe — sem login-first e sem beco de "e-mail errado". O link do WhatsApp
 *  traz o código em ?token=; um GET público revela a clínica e o e-mail convidado.
 *
 *  Segurança (ordem do dono, "rigor máximo"): o convite é amarrado ao e-mail
 *  (guarda do acesso clínico, validada no backend). O token viaja no WhatsApp e
 *  NÃO prova a caixa, então:
 *   - "Entrar com Google" resolve em 1 clique (o Google prova o e-mail);
 *   - "Criar conta com senha" exige CONFIRMAR o e-mail antes de entrar na clínica
 *     (prova de caixa) — decisão do dono em 02/10/2026.
 *  A conta é sempre criada/usada SOBRE o e-mail convidado, então o 403 do backend
 *  (invited_email × e-mail provado) continua sendo a trava, por construção.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiUrl } from "../lib/api";

type DetalhesConvite = {
  clinic_name: string;
  invited_email: string;
  roles: string[];
  status: string;
  expired: boolean;
};

type GoogleCredentialResponse = { credential?: string };

/** Traduz o erro do backend para uma frase que diz o que fazer a seguir. */
export function mensagemDoErro(status: number, detalhe: string): string {
  switch (status) {
    case 403:
      return "Este convite foi emitido para outro e-mail. Entre com a conta do e-mail que recebeu o convite, ou peça à clínica um novo código para o seu endereço.";
    case 409:
      return "A clínica já atingiu o limite de profissionais do plano dela. Fale com quem administra a clínica para ampliar o plano antes de entrar.";
    case 402:
      return "O plano da clínica está inativo no momento. A clínica precisa regularizar a assinatura antes de admitir novos profissionais.";
    case 404:
      return "Código inválido ou expirado. Os códigos valem por tempo limitado e são de uso único — peça um novo à clínica.";
    default:
      return detalhe || "Não foi possível resgatar o convite agora. Tente novamente em instantes.";
  }
}

const PAPEL_PT: Record<string, string> = {
  professional: "profissional",
  supervisor: "supervisor",
  administrator: "administrador",
  owner: "proprietário",
};

/** Como o convite nomeia os papéis, em português; só nomes testáveis sem efeito. */
export function papeisEmTexto(roles: string[]): string {
  const nomes = (roles || []).map((r) => PAPEL_PT[r] || r);
  return nomes.length ? nomes.join(", ") : "profissional";
}

function lerToken(): string {
  try {
    return (typeof localStorage !== "undefined" && localStorage.getItem("froid_token")) || "";
  } catch {
    return "";
  }
}

const SHELL = "min-h-screen bg-slate-950 text-slate-100 px-4 py-8";

function Moldura({ children }: { children: React.ReactNode }) {
  return (
    <div className={SHELL}>
      <main className="mx-auto max-w-xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-sm">
        <p className="text-[10px] font-black uppercase tracking-[0.24em] text-cyan-300">
          Equipe FROID
        </p>
        {children}
      </main>
    </div>
  );
}

export function EntrarNaClinicaPage() {
  const [params] = useSearchParams();
  const token = (params.get("token") ?? "").trim();

  const [detalhes, setDetalhes] = useState<DetalhesConvite | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erroConvite, setErroConvite] = useState("");
  const [logado, setLogado] = useState<boolean>(() => Boolean(lerToken()));
  const [modo, setModo] = useState<"criar" | "entrar">("criar");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [senha2, setSenha2] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [fase, setFase] = useState<"form" | "aceito" | "confirme_email">("form");
  const [devLink, setDevLink] = useState("");
  const [registroHabilitado, setRegistroHabilitado] = useState(false);
  const [senhaMinima, setSenhaMinima] = useState(6);
  const [googlePronto, setGooglePronto] = useState(false);
  const googleRef = useRef<HTMLDivElement | null>(null);
  const googleClientId = useMemo(
    () => (((import.meta as any).env?.VITE_GOOGLE_CLIENT_ID as string) || "").trim(),
    [],
  );

  // Dados do convite (clínica + e-mail convidado), leitura pública.
  useEffect(() => {
    if (!token) {
      setCarregando(false);
      setErroConvite("Este link de convite veio sem código. Peça à clínica um novo link.");
      return;
    }
    let vivo = true;
    setCarregando(true);
    fetch(apiUrl("/api/organization-invitations/" + encodeURIComponent(token)))
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(mensagemDoErro(r.status, d?.detail || ""));
        return d as DetalhesConvite;
      })
      .then((d) => {
        if (!vivo) return;
        setDetalhes(d);
        setNome("");
        if (d.status !== "pending" || d.expired) setErroConvite(mensagemDoErro(404, ""));
      })
      .catch((e) => {
        if (vivo) setErroConvite(e instanceof Error ? e.message : "Convite não encontrado.");
      })
      .finally(() => {
        if (vivo) setCarregando(false);
      });
    return () => {
      vivo = false;
    };
  }, [token]);

  // Config de cadastro próprio (o servidor decide se existe).
  useEffect(() => {
    fetch(apiUrl("/api/auth/config"))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setRegistroHabilitado(Boolean(d?.registration_enabled));
        if (d?.password_min_length) setSenhaMinima(Number(d.password_min_length));
        if (!d?.registration_enabled) setModo("entrar");
      })
      .catch(() => undefined);
  }, []);

  const aceitar = async () => {
    setOcupado(true);
    setErro("");
    try {
      const auth = lerToken();
      const r = await fetch(apiUrl("/api/organization-invitations/accept"), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}) },
        body: JSON.stringify({ invitation_token: token }),
      });
      if (r.ok) {
        setFase("aceito");
        return;
      }
      const c = await r.json().catch(() => null);
      setErro(mensagemDoErro(r.status, c?.detail || ""));
    } catch {
      setErro("Falha de conexão ao entrar na clínica. Verifique a internet e tente de novo.");
    } finally {
      setOcupado(false);
    }
  };

  const comSessaoEntrar = async (data: any) => {
    if (data?.token) {
      try {
        localStorage.setItem("froid_token", data.token);
      } catch {
        /* sem localStorage o accept abaixo ainda tentara com o header vazio */
      }
      setLogado(true);
    }
    await aceitar();
  };

  // Google Identity Services (mesmo padrão do LoginPage), só quando faz sentido.
  useEffect(() => {
    if (!googleClientId || googlePronto) return;
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    const ativar = () => setGooglePronto(true);
    if (existing) {
      if (window.google?.accounts?.id) ativar();
      else existing.addEventListener("load", ativar, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = ativar;
    script.onerror = () => setErro("Não foi possível carregar o login do Google.");
    document.head.appendChild(script);
  }, [googleClientId, googlePronto]);

  useEffect(() => {
    const mostrandoAuth = !logado && fase === "form" && Boolean(detalhes) && !erroConvite;
    if (!googlePronto || !googleClientId || !mostrandoAuth || !googleRef.current) return;
    const g = window.google?.accounts?.id;
    if (!g) return;
    g.initialize({
      client_id: googleClientId,
      callback: (resp: GoogleCredentialResponse) => {
        if (!resp.credential) {
          setErro("O Google não retornou uma credencial válida.");
          return;
        }
        setOcupado(true);
        setErro("");
        fetch(apiUrl("/api/auth/google"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ credential: resp.credential }),
        })
          .then(async (r) => {
            const d = await r.json().catch(() => null);
            if (!r.ok) throw new Error(d?.detail || "Falha no login do Google.");
            return d;
          })
          .then((d) => comSessaoEntrar(d))
          .catch((e) => {
            setErro(e instanceof Error ? e.message : "Falha no login do Google.");
            setOcupado(false);
          });
      },
    });
    g.renderButton(googleRef.current, {
      theme: "outline",
      size: "large",
      type: "standard",
      text: "continue_with",
      shape: "rectangular",
      width: 320,
    });
  }, [googlePronto, googleClientId, logado, fase, detalhes, erroConvite]);

  const criarConta = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro("");
    if (senha.length < senhaMinima) {
      setErro(`A senha precisa ter ao menos ${senhaMinima} caracteres.`);
      return;
    }
    if (senha !== senha2) {
      setErro("A confirmação da senha não confere.");
      return;
    }
    setOcupado(true);
    try {
      const r = await fetch(apiUrl("/api/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nome,
          email: detalhes?.invited_email || "",
          password: senha,
          password_confirm: senha2,
        }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || "Não foi possível criar a conta.");
      setDevLink(String(d?.dev_link || ""));
      setFase("confirme_email");
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar a conta.");
    } finally {
      setOcupado(false);
    }
  };

  const entrarComSenha = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      const r = await fetch(apiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: detalhes?.invited_email || "", password: senha }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || "E-mail ou senha incorretos.");
      await comSessaoEntrar(d);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "E-mail ou senha incorretos.");
    } finally {
      setOcupado(false);
    }
  };

  const sairParaOutraConta = () => {
    try {
      localStorage.removeItem("froid_token");
    } catch {
      /* ignore */
    }
    setLogado(false);
    setErro("");
  };

  if (carregando) {
    return (
      <Moldura>
        <p className="mt-6 text-sm text-slate-400">Carregando o convite...</p>
      </Moldura>
    );
  }

  if (erroConvite && !detalhes) {
    return (
      <Moldura>
        <h1 className="mt-2 text-2xl font-black">Convite indisponível</h1>
        <p
          data-campo="erro"
          className="mt-4 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
        >
          {erroConvite}
        </p>
      </Moldura>
    );
  }

  if (fase === "aceito") {
    return (
      <Moldura>
        <div className="mt-4 rounded-lg border border-emerald-800/70 bg-emerald-950/30 p-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-emerald-700 text-2xl text-emerald-300">
            ✓
          </div>
          <h1 className="mt-3 text-2xl font-black">Você entrou na clínica</h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Seu acesso já inclui a equipe de{" "}
            <span className="font-black">{detalhes?.clinic_name || "a clínica"}</span>. Ao atender
            no contexto dela, os créditos consomem do saldo da clínica, não do seu.
          </p>
          <a
            href="/app/#/dashboard"
            className="mt-6 inline-flex rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
          >
            Ir para o painel
          </a>
        </div>
      </Moldura>
    );
  }

  if (fase === "confirme_email") {
    return (
      <Moldura>
        <h1 className="mt-2 text-2xl font-black">Confirme seu e-mail</h1>
        <p className="mt-4 text-sm leading-6 text-slate-300">
          Enviamos um link de confirmação para{" "}
          <span className="font-black text-cyan-300">{detalhes?.invited_email}</span>. Abra a
          mensagem e confirme — isso prova que a caixa é sua. Depois, volte a este mesmo link do
          convite para entrar na equipe de{" "}
          <span className="font-black">{detalhes?.clinic_name || "a clínica"}</span>.
        </p>
        {devLink && (
          <p className="mt-4 break-all text-[11px] text-slate-500">
            Link de desenvolvimento: <a className="text-cyan-400 underline" href={devLink}>{devLink}</a>
          </p>
        )}
      </Moldura>
    );
  }

  const convite = detalhes as DetalhesConvite;
  return (
    <Moldura>
      <h1 className="mt-2 text-2xl font-black">Entrar numa clínica</h1>
      <div
        data-campo="convite"
        className="mt-4 rounded-lg border border-blue-800 bg-blue-950 p-4 text-sm leading-6 text-slate-100"
      >
        Convite para a equipe de{" "}
        <span className="font-black">{convite.clinic_name || "a clínica"}</span> como{" "}
        <span className="font-black">{papeisEmTexto(convite.roles)}</span>.
        <br />
        Emitido para{" "}
        <span className="font-black text-cyan-300">{convite.invited_email}</span>. Entre com a
        conta desse e-mail para aceitar.
      </div>

      {logado ? (
        <div className="mt-6">
          <p className="text-sm text-slate-300">
            Você já está conectada(o). Se esta for a conta de{" "}
            <span className="font-black">{convite.invited_email}</span>, é só entrar na clínica.
          </p>
          {erro && (
            <p data-campo="erro" className="mt-4 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100">
              {erro}
            </p>
          )}
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={aceitar}
              disabled={ocupado}
              className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-60"
            >
              {ocupado ? "Entrando..." : "Entrar na clínica"}
            </button>
            <button
              type="button"
              onClick={sairParaOutraConta}
              className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
            >
              Usar outra conta
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-6 space-y-4">
          {googleClientId && (
            <div className="rounded-lg bg-white p-2">
              <div ref={googleRef} className="flex justify-center" />
            </div>
          )}
          {googleClientId && (
            <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.24em] text-slate-500">
              <span className="h-px flex-1 bg-slate-700" />
              ou com e-mail e senha
              <span className="h-px flex-1 bg-slate-700" />
            </div>
          )}

          {registroHabilitado && (
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-slate-950/60 p-1">
              {(["criar", "entrar"] as const).map((opcao) => (
                <button
                  key={opcao}
                  type="button"
                  onClick={() => {
                    setModo(opcao);
                    setErro("");
                    setSenha("");
                    setSenha2("");
                  }}
                  className={
                    "rounded-md px-3 py-2 text-sm font-bold transition " +
                    (modo === opcao ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white")
                  }
                >
                  {opcao === "criar" ? "Criar conta" : "Já tenho conta"}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={modo === "criar" && registroHabilitado ? criarConta : entrarComSenha} className="space-y-3">
            {modo === "criar" && registroHabilitado && (
              <input
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
                autoComplete="name"
                placeholder="seu nome completo"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
              />
            )}
            <input
              value={convite.invited_email}
              readOnly
              aria-label="e-mail do convite"
              className="w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-400"
            />
            <input
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
              minLength={senhaMinima}
              autoComplete={modo === "criar" && registroHabilitado ? "new-password" : "current-password"}
              placeholder={modo === "criar" && registroHabilitado ? `senha (mínimo ${senhaMinima} caracteres)` : "sua senha"}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
            />
            {modo === "criar" && registroHabilitado && (
              <input
                type="password"
                value={senha2}
                onChange={(e) => setSenha2(e.target.value)}
                required
                minLength={senhaMinima}
                autoComplete="new-password"
                placeholder="repita a senha"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
              />
            )}
            {erro && (
              <p data-campo="erro" className="rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100">
                {erro}
              </p>
            )}
            <button
              type="submit"
              disabled={ocupado}
              className="w-full rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-60"
            >
              {ocupado
                ? "Enviando..."
                : modo === "criar" && registroHabilitado
                  ? "Criar conta e entrar na clínica"
                  : "Entrar na clínica"}
            </button>
          </form>
          <p className="text-center text-[11px] leading-5 text-slate-500">
            Ao continuar você concorda com os{" "}
            <Link to="/termos" className="text-cyan-400">termos de uso</Link> e a{" "}
            <Link to="/privacidade" className="text-cyan-400">política de privacidade</Link>.
          </p>
        </div>
      )}
    </Moldura>
  );
}
