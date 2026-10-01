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
 */

import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiUrl } from "../lib/api";

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

export function EntrarNaClinicaPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  // Inicia com o codigo do link (?token=) ja no campo — correto no primeiro
  // render, sem efeito. O convidado ainda pode editar ou limpar antes de aceitar.
  const [codigo, setCodigo] = useState(() => (params.get("token") ?? "").trim());
  const [estado, setEstado] = useState<Estado>({ fase: "formulario" });

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
      </section>
    </Moldura>
  );
}
