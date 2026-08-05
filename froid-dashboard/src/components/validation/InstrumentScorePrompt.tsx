import React, { useCallback, useEffect, useState } from "react";
import {
  INSTRUMENT,
  INSTRUMENT_MAX,
  collectionAllowed,
  fetchConsent,
  recordAdministration,
} from "../../lib/validation";

/**
 * Fim de sessão: registrar a pontuação do instrumento aplicado.
 *
 * Três recusas deliberadas neste componente.
 *
 * Ele não renderiza os itens do questionário. O profissional aplica o PHQ-9
 * pelo meio que já usa e digita o total — um sistema que apresentasse e
 * pontuasse o instrumento seria um instrumento de avaliação psicológica.
 *
 * Ele nunca bloqueia o encerramento da sessão. Se travasse, o profissional
 * aprenderia a digitar qualquer coisa para sair, e a base ficaria contaminada
 * sem que ninguém percebesse — uma amostra suja é pior que uma amostra menor.
 *
 * E ele não aparece para quem não consentiu. Reapresentar a pergunta a quem
 * disse não trata a recusa como erro a corrigir.
 */
type Props = {
  organizationId: string;
  patientId: string;
  sessionId?: string | null;
  /** Padrões medidos na janela desta sessão, já com cobertura e confiança. */
  observations?: Array<Record<string, unknown>>;
  onDone?: () => void;
};

export const InstrumentScorePrompt: React.FC<Props> = ({
  organizationId,
  patientId,
  sessionId,
  observations,
  onDone,
}) => {
  const [visivel, setVisivel] = useState(false);
  const [score, setScore] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [salvo, setSalvo] = useState(false);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      if (!organizationId || !patientId) return;
      try {
        // Duas condicoes, nesta ordem: o comite liberou a coleta, e este
        // paciente aceitou participar. Faltando qualquer uma, nao pergunta.
        const liberado = await collectionAllowed(organizationId);
        if (!liberado) {
          if (!cancelado) setVisivel(false);
          return;
        }
        const consent = await fetchConsent(organizationId, patientId);
        if (!cancelado) setVisivel(consent.state === "granted");
      } catch {
        // Falha ao consultar consentimento não pode virar prompt exibido: na
        // dúvida, não pergunta.
        if (!cancelado) setVisivel(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [organizationId, patientId]);

  const salvar = useCallback(async () => {
    const valor = Number(score);
    if (!Number.isFinite(valor) || valor < 0 || valor > INSTRUMENT_MAX) {
      setError(`Pontuação do ${INSTRUMENT} vai de 0 a ${INSTRUMENT_MAX}.`);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await recordAdministration(organizationId, {
        patient_id: patientId,
        total_score: valor,
        session_id: sessionId || null,
        observations: observations || [],
      });
      setSalvo(true);
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao registrar.");
    } finally {
      setBusy(false);
    }
  }, [score, organizationId, patientId, sessionId, observations, onDone]);

  if (!visivel || salvo) return null;

  return (
    <section className="rounded-lg border border-cyan-800 bg-cyan-950/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black uppercase tracking-wide text-cyan-100">
            Pontuação do {INSTRUMENT}
          </h3>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-300">
            Se você aplicou o {INSTRUMENT} nesta sessão, registre o total. É
            opcional — pular não afeta a sessão nem o prontuário.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setVisivel(false)}
          className="shrink-0 text-[11px] font-bold text-slate-400 underline"
        >
          Pular
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          type="number"
          min={0}
          max={INSTRUMENT_MAX}
          value={score}
          onChange={(event) => setScore(event.target.value)}
          placeholder={`0 a ${INSTRUMENT_MAX}`}
          className="w-28 rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm tabular-nums text-slate-100"
        />
        <button
          type="button"
          disabled={busy || !score}
          onClick={salvar}
          className="rounded bg-cyan-700 px-3 py-1.5 text-[11px] font-bold text-white disabled:opacity-50"
        >
          Registrar
        </button>
      </div>

      {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}

      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        O FROID guarda apenas o total, nunca as respostas item a item. A
        aplicação e a interpretação do instrumento são suas.
      </p>
    </section>
  );
};
