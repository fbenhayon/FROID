/** Resgate de convite de equipe (profissional entrando numa clínica).
 *
 *  O dono da clínica gera um código em /clinica; este é o único lugar onde o
 *  convidado o informa. O backend (POST /api/organization-invitations/accept)
 *  valida token, e-mail do destinatário, validade e limite do plano — aqui só
 *  coletamos o código e traduzimos a resposta. O link do WhatsApp pode trazer
 *  o código em ?token=, então o campo já vem preenchido; mesmo assim nada é
 *  enviado sem o clique, para o convidado conferir antes de aceitar.
 *
 *  Esta rota exige login (protectedElement), mas NÃO exige onboarding próprio:
 *  o convidado costuma ser um autônomo sem plano, e ele passa a consumir do
 *  pool da clínica, não de um plano seu.
 *
 *  Para evitar o beco do "logado com o e-mail errado": um GET público
 *  (/api/organization-invitations/{token}) revela a clínica e o e-mail
 *  convidado, então a tela mostra para quem o convite foi emitido e, se a conta
 *  logada não for essa, oferece trocar de conta — sem nunca afrouxar a trava de
 *  e-mail do backend (que é a guarda do acesso clínico).
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";

type DetalhesConvite = {
  clinic_name: string;
  invited_email: string;
  roles: string[];
  status: string;
  expired: boolean;
};

type Estado =
  | { fase: "formulario" }
  | { fase: "enviando" }
  | { fase: "aceito" }
  | { fase: "erro"; mensagem: string };

function cabecalhoAutorizacao(): Record<string, string> {
  const token =
    (typeof localStorage !== "undefined" &&
      localStorage.getItem("froid_token")) ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function normalizarEmail(email: string): string {
  return (email || "").trim().toLowerCase();
}

/** Estado do convite diante da conta logada — puro, para ser testável sem efeito. */
export function situacaoDoConvite(
  emailLogado: string,
  detalhes: DetalhesConvite | null,
): "sem_detalhes" | "indisponivel" | "email_divergente" | "pronto" {
  if (!detalhes) return "sem_detalhes";
  if (detalhes.status !== "pending" || detalhes.expired) return "indisponivel";
  if (
    emailLogado &&
    normalizarEmail(emailLogado) !== normalizarEmail(detalhes.invited_email)
  ) {
    return "email_divergente";
  }
  return "pronto";
}

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

const SHELL = "min-h-screen bg-slate-900 text-slate-100";

function Moldura({ children }: { children: React.ReactNode }) {
  return (
    <div className={SHELL}>
      <header className="border-b border-slate-700 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link className="text-sm font-black tracking-[0.35em] text-cyan-700" to="/">
            FROID
          </Link>
          <Link
            to="/settings"
            className="rounded-md border border-slate-700 px-3 py-2 text-xs font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
          >
            Configurações
          </Link>
        </div>
      </header>
      <main className="mx-auto flex max-w-7xl justify-center px-5 py-16">
        <div className="w-full max-w-xl">{children}</div>
      </main>
    </div>
  );
}

const PAPEL_PT: Record<string, string> = {
  professional: "profissional",
  supervisor: "supervisor",
  administrator: "administrador",
  owner: "proprietário",
};

function papeisEmTexto(roles: string[]): string {
  const nomes = (roles || []).map((r) => PAPEL_PT[r] || r);
  return nomes.length ? nomes.join(", ") : "profissional";
}

export function EntrarNaClinicaPage({ user }: { user?: FroidUser | null }) {
  const [params] = useSearchParams();
  const nav = useNavigate();
  // Inicia com o codigo do link (?token=) ja no campo — correto no primeiro
  // render, sem efeito. O convidado ainda pode editar ou limpar antes de aceitar.
  const [codigo, setCodigo] = useState(() => (params.get("token") ?? "").trim());
  const [estado, setEstado] = useState<Estado>({ fase: "formulario" });
  const [detalhes, setDetalhes] = useState<DetalhesConvite | null>(null);

  const emailLogado = user?.email ?? "";

  // Busca os dados do convite (clinica + e-mail convidado) para a tela informar
  // com qual conta entrar. Leitura publica; nao resgata nada.
  useEffect(() => {
    const t = (params.get("token") ?? "").trim();
    if (!t) {
      setDetalhes(null);
      return;
    }
    let vivo = true;
    fetch(apiUrl("/api/organization-invitations/" + encodeURIComponent(t)))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (vivo) setDetalhes(d as DetalhesConvite | null);
      })
      .catch(() => {
        if (vivo) setDetalhes(null);
      });
    return () => {
      vivo = false;
    };
  }, [params]);

  const situacao = situacaoDoConvite(emailLogado, detalhes);

  const sairEEntrar = () => {
    try {
      localStorage.removeItem("froid_token");
    } catch {
      /* localStorage pode estar indisponivel; o reload abaixo ainda leva ao login */
    }
    const t = codigo.trim();
    if (typeof window !== "undefined") {
      window.location.hash = t
        ? `#/entrar-clinica?token=${encodeURIComponent(t)}`
        : "#/entrar-clinica";
      window.location.reload();
    }
  };

  const resgatar = async () => {
    const token = codigo.trim();
    if (!token) {
      setEstado({ fase: "erro", mensagem: "Informe o código de convite que a clínica enviou." });
      return;
    }
    setEstado({ fase: "enviando" });
    try {
      const resposta = await fetch(apiUrl("/api/organization-invitations/accept"), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...cabecalhoAutorizacao() },
        body: JSON.stringify({ invitation_token: token }),
      });
      if (resposta.ok) {
        setEstado({ fase: "aceito" });
        return;
      }
      const corpo = await resposta.json().catch(() => null);
      setEstado({
        fase: "erro",
        mensagem: mensagemDoErro(resposta.status, corpo?.detail || ""),
      });
    } catch {
      setEstado({
        fase: "erro",
        mensagem: "Falha de conexão ao resgatar o convite. Verifique a internet e tente de novo.",
      });
    }
  };

  if (estado.fase === "aceito") {
    return (
      <Moldura>
        <section className="rounded-lg border border-slate-700 bg-slate-950 p-8 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-emerald-800/70 bg-emerald-950/30 text-2xl text-emerald-300">
            ✓
          </div>
          <p className="mt-5 text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
            Equipe FROID
          </p>
          <h1 className="mt-2 text-3xl font-black">Você entrou na clínica</h1>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            Seu acesso já inclui a equipe da clínica. Ao atender no contexto
            dela, os créditos consomem do saldo da clínica, não do seu. Sua
            conta e seus pacientes de sempre continuam como estão.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button
              type="button"
              onClick={() => nav("/dashboard")}
              className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
            >
              Ir para o painel
            </button>
            <Link
              to="/clinica"
              className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
            >
              Ver a clínica
            </Link>
          </div>
        </section>
      </Moldura>
    );
  }

  const enviando = estado.fase === "enviando";
  return (
    <Moldura>
      <section className="rounded-lg border border-slate-700 bg-slate-950 p-8 shadow-sm">
        <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
          Equipe FROID
        </p>
        <h1 className="mt-2 text-3xl font-black">Entrar numa clínica</h1>

        {detalhes && situacao !== "indisponivel" && (
          <div
            data-campo="convite"
            className="mt-5 rounded-lg border border-slate-700 bg-slate-900/60 p-4 text-sm leading-6 text-slate-200"
          >
            Convite para <span className="font-black">{detalhes.clinic_name || "a clínica"}</span>{" "}
            como <span className="font-black">{papeisEmTexto(detalhes.roles)}</span>.
            <br />
            Emitido para{" "}
            <span className="font-black text-cyan-300">{detalhes.invited_email}</span>. Entre
            com a conta desse e-mail para aceitar.
          </div>
        )}

        {situacao === "email_divergente" ? (
          <>
            <p
              data-campo="divergencia"
              className="mt-5 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
            >
              Você está conectada(o) como <span className="font-black">{emailLogado}</span>, mas
              este convite é para <span className="font-black">{detalhes?.invited_email}</span>. Saia
              e entre com o e-mail que recebeu o convite para aceitar.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={sairEEntrar}
                className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600"
              >
                Sair e entrar com o e-mail certo
              </button>
              <Link
                to="/settings"
                className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
              >
                Cancelar
              </Link>
            </div>
          </>
        ) : situacao === "indisponivel" ? (
          <>
            <p
              data-campo="erro"
              className="mt-5 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
            >
              {mensagemDoErro(404, "")}
            </p>
            <div className="mt-6">
              <Link
                to="/settings"
                className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
              >
                Voltar
              </Link>
            </div>
          </>
        ) : (
          <>
            <p className="mt-4 text-sm leading-6 text-slate-300">
              Recebeu um convite para integrar a equipe de uma clínica no FROID?
              Informe abaixo o código que ela enviou. Entre com a conta do e-mail
              para o qual o convite foi emitido.
            </p>
            <label className="mt-6 block">
              <span className="text-[11px] font-black uppercase tracking-wide text-slate-400">
                Código de convite
              </span>
              <input
                type="text"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                placeholder="Cole aqui o código que a clínica enviou"
                autoFocus
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              />
            </label>
            {estado.fase === "erro" && (
              <p
                data-campo="erro"
                className="mt-4 rounded-lg border border-amber-700 bg-amber-950/60 p-3 text-xs font-bold leading-5 text-amber-100"
              >
                {estado.mensagem}
              </p>
            )}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={resgatar}
                disabled={enviando}
                className="rounded-lg bg-cyan-700 px-4 py-3 text-sm font-black text-white hover:bg-cyan-600 disabled:cursor-wait disabled:opacity-60"
              >
                {enviando ? "Resgatando..." : "Entrar na clínica"}
              </button>
              <Link
                to="/settings"
                className="rounded-lg border border-slate-700 px-4 py-3 text-sm font-black text-slate-200 hover:border-cyan-500 hover:text-cyan-300"
              >
                Cancelar
              </Link>
            </div>
          </>
        )}
      </section>
    </Moldura>
  );
}
