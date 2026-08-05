import React, { useCallback, useEffect, useState } from "react";
import {
  Administration,
  ConsentInfo,
  INSTRUMENT,
  collectionAllowed,
  fetchPatientValidation,
  setConsent,
} from "../../lib/validation";

/**
 * Participação do paciente no estudo, na ficha dele.
 *
 * Três estados e não dois: concedido, revogado e nunca perguntado. O terceiro
 * existe para que a ausência de resposta não seja lida como recusa nem como
 * aceite — e para que o prompt de fim de sessão saiba quando não aparecer.
 *
 * Revogar aqui apaga os pares do paciente da base do estudo. O botão diz
 * quantos, porque uma ação irreversível tem de mostrar seu tamanho antes de
 * ser confirmada.
 */
type Props = {
  organizationId: string;
  patientId: string;
  patientName?: string;
};

export const ResearchConsentCard: React.FC<Props> = ({
  organizationId,
  patientId,
  patientName,
}) => {
  const [consent, setConsentInfo] = useState<ConsentInfo | null>(null);
  const [history, setHistory] = useState<Administration[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [liberado, setLiberado] = useState(false);

  const load = useCallback(async () => {
    if (!organizationId || !patientId) return;
    try {
      const data = await fetchPatientValidation(organizationId, patientId);
      setConsentInfo(data.consent);
      setHistory(Array.isArray(data.administrations) ? data.administrations : []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar.");
    }
  }, [organizationId, patientId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let cancelado = false;
    collectionAllowed(organizationId).then((ok) => {
      if (!cancelado) setLiberado(ok);
    });
    return () => {
      cancelado = true;
    };
  }, [organizationId]);

  const decide = useCallback(
    async (granted: boolean) => {
      setBusy(true);
      try {
        await setConsent(organizationId, patientId, granted);
        setConfirming(false);
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao registrar.");
      } finally {
        setBusy(false);
      }
    },
    [organizationId, patientId, load],
  );

  if (!consent) return null;

  const ativo = consent.state === "granted";

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black uppercase tracking-wide text-slate-200">
            Estudo de validade
          </h3>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
            Participação é opcional e não altera o atendimento. Ao aceitar, o{" "}
            {INSTRUMENT} aplicado por você é pareado com os padrões medidos na
            mesma sessão.
          </p>
        </div>
        <span
          className={`shrink-0 rounded px-2 py-1 text-[10px] font-black uppercase ${
            ativo
              ? "bg-emerald-900/60 text-emerald-200"
              : consent.state === "revoked"
                ? "bg-slate-800 text-slate-400"
                : "bg-amber-900/50 text-amber-200"
          }`}
        >
          {ativo ? "Participando" : consent.state === "revoked" ? "Retirado" : "Não perguntado"}
        </span>
      </div>

      {history.length > 0 && (
        <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 p-2">
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
            Aplicações registradas
          </p>
          <ul className="mt-1 space-y-1">
            {history.slice(0, 5).map((item) => (
              <li
                key={item.administered_at}
                className="flex justify-between text-[11px] text-slate-300"
              >
                <span>{new Date(item.administered_at).toLocaleDateString("pt-BR")}</span>
                <span className="tabular-nums">
                  {item.instrument} {item.total_score}/{item.score_max}
                  <span className="ml-2 text-slate-500">{item.patterns} padrões</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="mt-2 text-[11px] text-rose-300">{error}</p>}

      <div className="mt-3 flex flex-wrap gap-2">
        {!ativo && !liberado && (
          <p className="text-[11px] leading-relaxed text-amber-200">
            A coleta ainda nao foi liberada: o parecer do Comite de Etica em
            Pesquisa nao esta registrado. Aceite colhido antes da aprovacao
            seria aceite para um estudo que ainda nao existe no formato
            aprovado.
          </p>
        )}
        {!ativo && liberado && (
          <button
            type="button"
            disabled={busy}
            onClick={() => decide(true)}
            className="rounded bg-emerald-700 px-3 py-1.5 text-[11px] font-bold text-white disabled:opacity-50"
          >
            Registrar aceite{patientName ? ` de ${patientName}` : ""}
          </button>
        )}
        {ativo && !confirming && (
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming(true)}
            className="rounded border border-slate-600 px-3 py-1.5 text-[11px] font-bold text-slate-300 disabled:opacity-50"
          >
            Retirar participação
          </button>
        )}
        {ativo && confirming && (
          <div className="w-full rounded border border-rose-800 bg-rose-950/40 p-3">
            <p className="text-[11px] leading-relaxed text-rose-100">
              Retirar apaga {history.length} aplicaç{history.length === 1 ? "ão" : "ões"}{" "}
              e os padrões pareados da base do estudo. Análises já publicadas a
              partir de amostras anteriores não podem ser desfeitas.
            </p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => decide(false)}
                className="rounded bg-rose-700 px-3 py-1.5 text-[11px] font-bold text-white disabled:opacity-50"
              >
                Confirmar retirada
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded border border-slate-600 px-3 py-1.5 text-[11px] font-bold text-slate-300"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
