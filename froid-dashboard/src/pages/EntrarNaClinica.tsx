/** Convite de equipe (profissional entrando numa clínica) — igual ao do paciente.
 *
 *  Espelho de PatientInvitePage (/convite/:token): página PÚBLICA, com a cara
 *  da clínica, onde o convidado cria a senha (ou informa a que já tem) e entra
 *  na clínica num passo só. O servidor cria a conta NO E-MAIL DO CONVITE e o
 *  vínculo com a clínica na mesma chamada (POST /api/organization-invitations/
 *  {token}/accept) e já devolve a sessão.
 *
 *  Decisão do dono em 05/10/2026, depois de cinco tentativas falhadas do modelo
 *  "entre logado com o e-mail convidado": esta tela NÃO consulta a sessão do
 *  navegador. Quem abre o link estando logado como outra conta (a dona da
 *  clínica, no caso real) não é derrubado por isso — como no paciente.
 *
 *  O e-mail não é editável: vem do convite, que a clínica emitiu. Senha já
 *  existente nunca é redefinida por aqui (anti-sequestro): o servidor exige a
 *  senha atual. "Entrar com Google" segue como alternativa de 1 clique.
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
  /** O e-mail convidado já tem acesso FROID por senha: só pede a senha. */
  has_password?: boolean;
  /** Identidade existe sem senha (conta Google): o link não cria senha nela. */
  google_only?: boolean;
  /** Convite de gestão: aceite só com a conta, pelo painel. */
  requires_session?: boolean;
  /** Pessoa desativada pela plataforma. */
  blocked?: boolean;
};

type GoogleCredentialResponse = { credential?: string };

/** Traduz o erro do backend para uma frase que diz o que fazer a seguir. */
export function mensagemDoErro(status: number, detalhe: string): string {
  switch (status) {
    case 401:
      return "Senha incorreta para este e-mail. Se esqueceu a senha, use \"Esqueci minha senha\" na tela de acesso e volte a este link.";
    case 403:
      // O servidor tem tres recusas 403 distintas; so a de e-mail divergente
      // usa a frase generica, as outras ja vem explicadas.
      if (detalhe && !detalhe.includes("outro email")) return detalhe;
      return "Este convite foi emitido para outro e-mail. Entre com a conta do e-mail que recebeu o convite, ou peça à clínica um novo código para o seu endereço.";
    case 409:
      if (detalhe.includes("Google")) return detalhe;
      return "A clínica já atingiu o limite de profissionais do plano dela. Fale com quem administra a clínica para ampliar o plano antes de entrar.";
    case 402:
      return "O plano da clínica está inativo no momento. A clínica precisa regularizar a assinatura antes de admitir novos profissionais.";
    case 404:
      return "Código inválido ou expirado. Os códigos valem por tempo limitado e são de uso único — peça um novo à clínica.";
    default:
      return detalhe || "Não foi possível entrar na clínica agora. Tente novamente em instantes.";
  }
}

const PAPEL_PT: Record<string, string> = {
  professional: "profissional",
  supervisor: "supervisor",
  administrator: "administrador",
  owner: "proprietário",
};

/** Como o convite nomeia os papéis, em português; puro, testável sem efeito. */
export function papeisEmTexto(roles: string[]): string {
  const nomes = (roles || []).map((r) => PAPEL_PT[r] || r);
  return nomes.length ? nomes.join(", ") : "profissional";
}

function guardarSessao(data: any) {
  if (!data?.token) return;
  try {
    localStorage.setItem("froid_token", data.token);
  } catch {
    /* sem localStorage a sessão vale só nesta tela; o painel pedirá login */
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

const CAMPO =
  "w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500";

export function EntrarNaClinicaPage() {
  const [params, setParams] = useSearchParams();
  const [codigo, setCodigo] = useState("");
  const usarCodigo = (e: React.FormEvent) => {
    e.preventDefault();
    const limpo = codigo.trim();
    if (limpo) setParams({ token: limpo });
  };
  // Recarga inteira: o App le a sessao so na montagem. Sem ela, quem ja estava
  // logado (a dona da clinica) seguiria vendo a propria conta com o token do
  // convidado por baixo -- uma identidade na tela, outra nas chamadas.
  const irParaOPainel = () => {
    try {
      localStorage.removeItem("froid_user");
    } catch {
      /* sem storage, a recarga basta */
    }
    window.location.replace("/app/#/dashboard");
    window.location.reload();
  };
  const token = (params.get("token") ?? "").trim();

  const [detalhes, setDetalhes] = useState<DetalhesConvite | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erroConvite, setErroConvite] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [senha2, setSenha2] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [aceito, setAceito] = useState(false);
  const [senhaMinima, setSenhaMinima] = useState(6);
  const [googlePronto, setGooglePronto] = useState(false);
  const googleRef = useRef<HTMLDivElement | null>(null);
  const googleClientId = useMemo(
    () => (((import.meta as any).env?.VITE_GOOGLE_CLIENT_ID as string) || "").trim(),
    [],
  );

  // Dados do convite (clínica + e-mail + se já tem senha), leitura pública.
  useEffect(() => {
    if (!token) {
      setCarregando(false);
      setErroConvite("Este link de convite veio sem código. Peça à clínica um novo link.");
      return;
    }
    let vivo = true;
    setCarregando(true);
    setErroConvite("");
    setDetalhes(null);
    fetch(apiUrl("/api/organization-invitations/" + encodeURIComponent(token)))
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(mensagemDoErro(r.status, d?.detail || ""));
        return d as DetalhesConvite;
      })
      .then((d) => {
        if (!vivo) return;
        if (d.status !== "pending" || d.expired) {
          // Link velho: o servidor nao devolve mais e-mail nem clinica.
          setErroConvite(mensagemDoErro(404, ""));
          return;
        }
        setDetalhes(d);
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

  useEffect(() => {
    fetch(apiUrl("/api/auth/config"))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.password_min_length) setSenhaMinima(Number(d.password_min_length));
      })
      .catch(() => undefined);
  }, []);

  // O aceite pelo link: cria a conta no e-mail do convite (ou confere a senha
  // existente) e entra na clínica num passo só — como o paciente.
  const entrar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro("");
    const novo = !detalhes?.has_password;
    if (senha.length < senhaMinima) {
      setErro(`A senha precisa ter ao menos ${senhaMinima} caracteres.`);
      return;
    }
    if (novo && senha !== senha2) {
      setErro("A confirmação da senha não confere.");
      return;
    }
    if (novo && !nome.trim()) {
      setErro("Informe seu nome.");
      return;
    }
    setOcupado(true);
    try {
      const r = await fetch(
        apiUrl("/api/organization-invitations/" + encodeURIComponent(token) + "/accept"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            novo
              ? { name: nome.trim(), password: senha, password_confirm: senha2 }
              : { password: senha },
          ),
        },
      );
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setErro(mensagemDoErro(r.status, d?.detail || ""));
        return;
      }
      if (d?.token) guardarSessao(d);
      setAceito(true);
    } catch {
      setErro("Falha de conexão ao entrar na clínica. Verifique a internet e tente de novo.");
    } finally {
      setOcupado(false);
    }
  };

  // Alternativa de 1 clique: o Google prova o e-mail; a sessão dele aceita o
  // convite pelo caminho autenticado.
  const aceitarComSessao = async (sessao: any) => {
    // A sessao do Google so e guardada se o aceite der certo: um 403 (e-mail
    // de outra conta) nao pode derrubar a sessao que ja estava no navegador.
    const r = await fetch(apiUrl("/api/organization-invitations/accept"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sessao?.token ? { Authorization: `Bearer ${sessao.token}` } : {}),
      },
      body: JSON.stringify({ invitation_token: token }),
    });
    if (r.ok) {
      guardarSessao(sessao);
      setAceito(true);
      return;
    }
    const c = await r.json().catch(() => null);
    setErro(mensagemDoErro(r.status, c?.detail || ""));
  };

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
    const mostrando = !aceito && Boolean(detalhes) && !erroConvite;
    if (!googlePronto || !googleClientId || !mostrando || !googleRef.current) return;
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
          .then((d) => aceitarComSessao(d))
          .catch((e) => setErro(e instanceof Error ? e.message : "Falha no login do Google."))
          .finally(() => setOcupado(false));
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
  }, [googlePronto, googleClientId, aceito, detalhes, erroConvite]);

  if (carregando) {
    return (
      <Moldura>
        <p className="mt-6 text-sm text-slate-400">Carregando o convite...</p>
      </Moldura>
    );
  }

  if (!token) {
    // A mensagem do WhatsApp oferece "informe este codigo" para quando o link
    // nao abre; sem este campo, o caminho terminava em "veio sem codigo".
    return (
      <Moldura>
        <h1 className="mt-2 text-2xl font-black">Entrar numa clínica</h1>
        <form onSubmit={usarCodigo} className="mt-4 space-y-3">
          <p className="text-sm leading-6 text-slate-300">
            Cole o código do convite que a clínica enviou.
          </p>
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            required
            autoComplete="off"
            aria-label="código do convite"
            placeholder="código do convite"
            className={CAMPO}
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
          >
            Abrir o convite
          </button>
        </form>
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

  const convite = detalhes as DetalhesConvite;

  if (aceito) {
    return (
      <Moldura>
        <div className="mt-4 rounded-lg border border-emerald-800/70 bg-emerald-950/30 p-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-emerald-700 text-2xl text-emerald-300">
            ✓
          </div>
          <h1 className="mt-3 text-2xl font-black">Você entrou na clínica</h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Seu acesso já inclui a equipe de{" "}
            <span className="font-black">{convite.clinic_name || "a clínica"}</span>. Ao atender
            no contexto dela, os créditos consomem do saldo da clínica, não do seu.
          </p>
          <button
            type="button"
            onClick={irParaOPainel}
            className="mt-6 inline-flex rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
          >
            Ir para o painel
          </button>
        </div>
      </Moldura>
    );
  }

  // Recusas que o servidor ja anuncia no GET: a tela nem oferece o formulario.
  const recusa = convite.blocked
    ? "Seu acesso ao FROID está desativado pela plataforma. Fale com froid@froid.com.br."
    : convite.requires_session
      ? "Convite de gestão da clínica: entre com a sua conta (Google ou e-mail e senha) e aceite pelo painel."
      : "";
  const indisponivel = Boolean(erroConvite || recusa);
  const jaTemSenha = Boolean(convite.has_password);
  const soGoogle = Boolean(convite.google_only);

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
        E-mail do convite:{" "}
        <span className="font-black text-cyan-300">{convite.invited_email}</span>.
      </div>

      {indisponivel ? (
        <p
          data-campo="erro"
          className="mt-5 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
        >
          {erroConvite || recusa}
        </p>
      ) : (
        <div className="mt-6 space-y-4">
          {soGoogle && (
            <p className="rounded-lg border border-cyan-800 bg-cyan-950/40 p-3 text-sm leading-6 text-cyan-100">
              Este e-mail já tem acesso FROID pelo Google. Use “Continuar com o Google” abaixo
              para entrar na clínica.
            </p>
          )}
          {!soGoogle && (
          <form onSubmit={entrar} className="space-y-3">
            <p className="text-sm leading-6 text-slate-300">
              {jaTemSenha
                ? "Este e-mail já tem acesso FROID. Informe sua senha para entrar na clínica."
                : "Crie sua senha de acesso e você entra na clínica na hora."}
            </p>
            {!jaTemSenha && (
              <input
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
                autoComplete="name"
                placeholder="seu nome completo"
                className={CAMPO}
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
              autoComplete={jaTemSenha ? "current-password" : "new-password"}
              placeholder={jaTemSenha ? "sua senha" : `senha (mínimo ${senhaMinima} caracteres, letras e números)`}
              className={CAMPO}
            />
            {!jaTemSenha && (
              <input
                type="password"
                value={senha2}
                onChange={(e) => setSenha2(e.target.value)}
                required
                minLength={senhaMinima}
                autoComplete="new-password"
                placeholder="repita a senha"
                className={CAMPO}
              />
            )}
            {erro && (
              <p
                data-campo="erro"
                className="rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
              >
                {erro}
              </p>
            )}
            <button
              type="submit"
              disabled={ocupado}
              className="w-full rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-60"
            >
              {ocupado ? "Entrando..." : "Entrar na clínica"}
            </button>
          </form>
          )}

          {googleClientId && (
            <>
              <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.24em] text-slate-500">
                <span className="h-px flex-1 bg-slate-700" />
                ou com Google
                <span className="h-px flex-1 bg-slate-700" />
              </div>
              <div className="rounded-lg bg-white p-2">
                <div ref={googleRef} className="flex justify-center" />
              </div>
            </>
          )}

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
