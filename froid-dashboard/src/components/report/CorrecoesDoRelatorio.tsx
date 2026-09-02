// As correções do que o FROID escreveu, na palavra de quem estava lá.
//
// Nasceu de um caso real. Em 02/09/2026 um paciente leu o relatório da própria
// sessão e apontou quatro erros:
//
//   - uma cidade trocada (o relatório dizia Boston; era Glen Cove, NY);
//   - uma inferência afetiva que ninguém disse — "saudade da esposa e crianças",
//     quando a família está junta;
//   - um trecho que ficou sem sentido;
//   - uma palavra que caiu do resumo.
//
// Nenhum deles era de índice acústico. Todos vieram da transcrição ou do resumo
// gerado — a camada semântica, não a de sinal.
//
// Não havia onde registrar isso. `clinicalNotes` é texto livre sem alvo, sem
// autor e sem precedência: a correção ficaria num campo de observação geral, e
// quem abrisse o relatório depois leria o erro primeiro e a correção nunca.
//
// Por isso este bloco fica no ALTO do documento. Uma correção que aparece
// depois do texto corrigido chega tarde: a leitura clínica já aconteceu.

import React, { useState } from "react";

import { apiUrl } from "../../lib/api";
import type {
  CorrecaoDeRelatorio,
  OrigemDaCorrecao,
  TipoDeErroNoRelatorio,
} from "../../lib/session-report";

const TIPO_LABEL: Record<TipoDeErroNoRelatorio, string> = {
  transcricao_incorreta: "Transcrição incorreta",
  inferencia_indevida: "Inferência indevida",
  fato_incorreto: "Fato incorreto",
  trecho_incoerente: "Trecho incoerente",
};

// A inferência indevida é destacada em vermelho porque é a única em que o
// sistema AFIRMOU algo que ninguém disse. As outras três são erro de captação;
// esta é conteúdo inventado, e num relatório clínico isso pesa diferente.
const TIPO_COR: Record<TipoDeErroNoRelatorio, string> = {
  inferencia_indevida: "border-red-700 bg-red-950/40 text-red-200",
  transcricao_incorreta: "border-slate-700 bg-slate-900 text-slate-300",
  fato_incorreto: "border-amber-700 bg-amber-950/30 text-amber-200",
  trecho_incoerente: "border-slate-700 bg-slate-900 text-slate-300",
};

type Props = {
  sessionId: string;
  correcoes?: CorrecaoDeRelatorio[];
  /** Só o profissional registra; o paciente hoje aponta por fora e o
   *  profissional transcreve, declarando a origem. */
  podeRegistrar?: boolean;
  onRegistrada?: (correcao: CorrecaoDeRelatorio) => void;
};

export const CorrecoesDoRelatorio: React.FC<Props> = ({
  sessionId,
  correcoes,
  podeRegistrar = false,
  onRegistrada,
}) => {
  const [aberto, setAberto] = useState(false);
  const [origem, setOrigem] = useState<OrigemDaCorrecao>("paciente");
  const [tipo, setTipo] = useState<TipoDeErroNoRelatorio>("fato_incorreto");
  const [trecho, setTrecho] = useState("");
  const [correcao, setCorrecao] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const lista = correcoes || [];

  const registrar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!trecho.trim() || !correcao.trim()) return;
    setSalvando(true);
    setErro("");
    try {
      const token = localStorage.getItem("froid_token") || "";
      const resposta = await fetch(
        apiUrl(`/api/session-reports/${encodeURIComponent(sessionId)}/correcoes`),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            origem,
            tipo,
            trecho_original: trecho.trim(),
            correcao: correcao.trim(),
          }),
        },
      );
      // Ler texto antes de JSON: uma resposta de erro do servidor não é JSON, e
      // `.json()` nela produz "Unexpected token 'I'" em vez do motivo real.
      const bruto = await resposta.text();
      let corpo: Record<string, unknown> | null = null;
      try {
        corpo = bruto ? JSON.parse(bruto) : null;
      } catch {
        corpo = null;
      }
      if (!resposta.ok) {
        throw new Error(
          String(corpo?.detail || bruto || `Erro ${resposta.status}`),
        );
      }
      const nova = corpo?.correcao as CorrecaoDeRelatorio | undefined;
      if (nova) onRegistrada?.(nova);
      setTrecho("");
      setCorrecao("");
      setAberto(false);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível registrar.");
    } finally {
      setSalvando(false);
    }
  };

  if (!lista.length && !podeRegistrar) return null;

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">
            Correções ao relatório
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500">
            O texto original é preservado; a correção tem precedência de leitura.
          </p>
        </div>
        {podeRegistrar && (
          <button
            type="button"
            onClick={() => setAberto((v) => !v)}
            className="rounded border border-slate-600 px-2.5 py-1 text-[11px] font-bold text-slate-200 hover:bg-slate-800"
          >
            {aberto ? "Cancelar" : "Registrar correção"}
          </button>
        )}
      </div>

      {!lista.length && (
        <p className="mt-3 text-xs italic text-slate-500">
          Nenhuma correção registrada para esta sessão.
        </p>
      )}

      {lista.length > 0 && (
        <ul className="mt-3 space-y-2">
          {lista.map((item) => (
            <li
              key={item.id}
              className={`rounded border p-3 ${TIPO_COR[item.tipo] || TIPO_COR.fato_incorreto}`}
            >
              <div className="flex flex-wrap items-center gap-2 text-[9px] font-black uppercase tracking-wide">
                <span>{TIPO_LABEL[item.tipo] || item.tipo}</span>
                <span className="opacity-60">·</span>
                <span className="opacity-80">
                  apontado {item.origem === "paciente" ? "pelo paciente" : "pelo profissional"}
                </span>
              </div>

              <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                O FROID escreveu
              </p>
              <p className="text-xs leading-5 text-slate-400 line-through decoration-slate-600">
                {item.trechoOriginal}
              </p>

              <p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-emerald-400">
                Correto
              </p>
              <p className="text-sm font-bold leading-5 text-slate-100">
                {item.correcao}
              </p>

              {item.observacao && (
                <p className="mt-2 border-t border-white/10 pt-2 text-[11px] leading-4 text-slate-400">
                  {item.observacao}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {aberto && podeRegistrar && (
        <form onSubmit={registrar} className="mt-4 space-y-2 border-t border-slate-800 pt-3">
          <div className="flex flex-wrap gap-2">
            <label className="text-[11px] text-slate-400">
              Quem apontou
              <select
                value={origem}
                onChange={(e) => setOrigem(e.target.value as OrigemDaCorrecao)}
                className="ml-2 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-100"
              >
                <option value="paciente">Paciente</option>
                <option value="profissional">Profissional</option>
              </select>
            </label>
            <label className="text-[11px] text-slate-400">
              Tipo
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoDeErroNoRelatorio)}
                className="ml-2 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-100"
              >
                <option value="fato_incorreto">Fato incorreto</option>
                <option value="inferencia_indevida">Inferência indevida</option>
                <option value="transcricao_incorreta">Transcrição incorreta</option>
                <option value="trecho_incoerente">Trecho incoerente</option>
              </select>
            </label>
          </div>

          <textarea
            value={trecho}
            onChange={(e) => setTrecho(e.target.value)}
            placeholder="Cole aqui o trecho exatamente como o FROID escreveu"
            rows={2}
            className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100"
          />
          <textarea
            value={correcao}
            onChange={(e) => setCorrecao(e.target.value)}
            placeholder="O que é correto"
            rows={2}
            className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100"
          />

          {erro && <p className="text-[11px] text-red-300">{erro}</p>}

          <button
            type="submit"
            disabled={salvando || !trecho.trim() || !correcao.trim()}
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-black text-white disabled:opacity-40"
          >
            {salvando ? "Registrando..." : "Registrar"}
          </button>
        </form>
      )}
    </section>
  );
};
