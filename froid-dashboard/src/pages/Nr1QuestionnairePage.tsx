import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiUrl } from "../lib/api";

type ScaleLabel = { value: number; label: string };

type Questionnaire = {
  campaign_title: string;
  closes_at: string;
  purpose_notice: string;
  support_channel: { label: string; detail: string };
  scale: { min: number; max: number; labels: unknown };
  items: Array<{ item_id: string; statement: string; dimension: string }>;
};

/**
 * Anonymous questionnaire. No login, no organization header: the single-use
 * token in the link is the whole authorization.
 *
 * Two deliberate properties, both required rather than cosmetic:
 *
 * - The purpose notice is shown before the first question, never after. The
 *   Guia MTE asks the organization to explain the assessment in advance so
 *   people take part knowing what it is for.
 * - The support channel appears at the end for everybody, identical regardless
 *   of what was answered, with no automatic trigger. Anonymity means nobody can
 *   reach a person who signals distress — so the channel is offered to all
 *   rather than fired at some.
 */
function normalizeScaleLabels(raw: unknown, min: number, max: number): ScaleLabel[] {
  const fallback: ScaleLabel[] = [];
  for (let value = min; value <= max; value += 1) {
    fallback.push({ value, label: String(value) });
  }
  if (!Array.isArray(raw) || !raw.length) return fallback;
  return raw.slice(0, max - min + 1).map((label, index) => ({
    value: min + index,
    label: typeof label === "string" && label.trim() ? label : String(min + index),
  }));
}

export const Nr1QuestionnairePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [form, setForm] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!token) {
      setError("Link inválido: token ausente.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        apiUrl(`/api/nr1/questionnaire?token=${encodeURIComponent(token)}`),
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Convite indisponível.");
      }
      setForm(data as Questionnaire);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível abrir o questionário.",
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const scale = useMemo(() => {
    if (!form) return [] as ScaleLabel[];
    return normalizeScaleLabels(form.scale.labels, form.scale.min, form.scale.max);
  }, [form]);

  const answered = Object.keys(answers).length;
  const total = form?.items.length || 0;
  const complete = total > 0 && answered === total;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!complete || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(apiUrl("/api/nr1/responses"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, answers }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível registrar as respostas.");
      }
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Falha ao enviar as respostas.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const supportBox = form ? (
    <section className="mt-6 rounded-lg border border-cyan-900 bg-cyan-950/40 p-5">
      <h2 className="text-sm font-black text-cyan-100">{form.support_channel.label}</h2>
      <p className="mt-2 whitespace-pre-line text-sm leading-6 text-cyan-50/90">
        {form.support_channel.detail}
      </p>
      <p className="mt-3 text-[11px] text-cyan-200/70">
        Este canal está disponível para todas as pessoas, independentemente do
        que foi respondido aqui. Suas respostas não acionam nenhum contato.
      </p>
    </section>
  ) : null;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm font-semibold text-slate-300">
        Carregando questionário...
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
        <main className="mx-auto max-w-2xl">
          <div className="rounded-lg border border-emerald-900 bg-emerald-950/50 p-6">
            <h1 className="text-xl font-black text-white">Respostas registradas</h1>
            <p className="mt-2 text-sm text-emerald-100/90">
              Obrigado por participar. Suas respostas entram apenas em resultados
              agregados: ninguém na empresa vê o que você respondeu
              individualmente.
            </p>
          </div>
          {supportBox}
        </main>
      </div>
    );
  }

  if (!form) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
        <main className="mx-auto max-w-2xl">
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <h1 className="text-xl font-black text-white">Convite indisponível</h1>
            <p className="mt-2 text-sm text-slate-400">
              {error ||
                "Este link não está mais válido. Ele pode já ter sido usado ou a coleta pode ter sido encerrada."}
            </p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-2xl pb-24">
        <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
          Avaliação de condições de trabalho
        </p>
        <h1 className="mt-2 text-2xl font-black text-white">{form.campaign_title}</h1>

        <section className="mt-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-sm font-black text-white">Antes de começar</h2>
          <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-300">
            {form.purpose_notice}
          </p>
          <ul className="mt-4 space-y-2 text-xs leading-5 text-slate-400">
            <li>
              As perguntas são sobre <strong className="text-slate-200">como o trabalho é
              organizado</strong>, não sobre você. Não é uma avaliação de saúde
              mental nem de desempenho.
            </li>
            <li>
              As respostas são anônimas e só aparecem somadas a de outras
              pessoas. Recortes muito pequenos são bloqueados pelo sistema.
            </li>
            <li>
              O link é de uso único e expira em{" "}
              {new Date(form.closes_at).toLocaleDateString("pt-BR")}.
            </li>
          </ul>
        </section>

        {error && (
          <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
            {error}
          </p>
        )}

        <form onSubmit={submit} className="mt-6 space-y-4">
          {form.items.map((item, index) => (
            <fieldset
              key={item.item_id}
              className="rounded-lg border border-slate-800 bg-slate-900 p-4"
            >
              <legend className="px-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                {index + 1} de {total} · {item.dimension}
              </legend>
              <p className="mt-1 text-sm font-semibold leading-6 text-slate-100">
                {item.statement}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {scale.map((option) => {
                  const active = answers[item.item_id] === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={active}
                      onClick={() =>
                        setAnswers((current) => ({
                          ...current,
                          [item.item_id]: option.value,
                        }))
                      }
                      className={`rounded border px-3 py-2 text-xs font-bold transition ${
                        active
                          ? "border-cyan-500 bg-cyan-600 text-white"
                          : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ))}

          <div className="sticky bottom-0 -mx-4 border-t border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs font-bold text-slate-400">
                {answered} de {total} respondidas
              </p>
              <button
                type="submit"
                disabled={!complete || submitting}
                className="rounded bg-cyan-600 px-5 py-2 text-xs font-black text-white disabled:opacity-40"
              >
                {submitting ? "Enviando..." : "Enviar respostas"}
              </button>
            </div>
            {!complete && (
              <p className="mt-2 text-[11px] text-slate-500">
                Responda todas as perguntas para enviar.
              </p>
            )}
          </div>
        </form>

        {supportBox}
      </main>
    </div>
  );
};
