import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { apiUrl, publicAppUrl } from "../lib/api";
import { rememberSessionPatient } from "../lib/session-report";
import { LgpdNotice } from "../components/legal/LgpdNotice";
import {
  loadSessionLanguagePreferences,
  saveSessionLanguagePreferences,
  sessionLocaleOptions,
  type SessionLanguagePreferences,
  type SessionLocale,
} from "../lib/localization";

type PaymentMode = "package" | "single";

interface InviteResult {
  token: string;
  session_id: string;
  invite_url: string;
  whatsapp_url: string;
  whatsapp_message: string;
  patient_id?: string;
  patient_known: boolean;
  payment: {
    mode: PaymentMode;
    package_sessions: number;
    session_value_brl: string;
    package_total_brl: string;
    pix_code: string;
    payment_status: string;
  };
}

interface SessionEvent {
  id: number;
  type: "invite_created" | "invite_opened" | "invite_accepted" | "patient_joined";
  session_id: string;
  patient_name?: string;
  created_at: string;
}

const initialForm = {
  patient_name: "",
  patient_email: "",
  patient_phone: "",
  payment_mode: "single" as PaymentMode,
  session_value: "",
  package_sessions: "4",
  pix_code: "",
};

function makeId() {
  return `froid-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export const NewPatient: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const captureMode = searchParams.get("capture") === "patient_mobile" ? "patient_mobile" : "";
  const isPatientMobileCapture = captureMode === "patient_mobile";
  const patientNamePrefill = searchParams.get("name") || "";
  const patientEmailPrefill = searchParams.get("email") || "";
  const patientPhonePrefill = searchParams.get("phone") || "";
  const [form, setForm] = useState(() => ({
    ...initialForm,
    patient_name: patientNamePrefill,
    patient_email: patientEmailPrefill,
    patient_phone: patientPhonePrefill,
  }));
  const [languages, setLanguages] = useState<SessionLanguagePreferences>(
    loadSessionLanguagePreferences,
  );
  // Este paciente poderá ver as próprias sessões na área dele? Decisão do
  // profissional. Nasce desligado de propósito: liberar dado clínico ao
  // paciente é ato, e ato não se pratica por omissão. Alterável depois na ficha
  // — ligar aqui não libera nada sozinho, cada relatório ainda passa pela
  // composição e liberação na tela do Relatório da Sessão.
  const [patientResultsEnabled, setPatientResultsEnabled] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [invite, setInvite] = useState<InviteResult | null>(null);
  const [patientActivity, setPatientActivity] = useState("");
  // Confirmação visual de que o clique em "Copiar" realmente copiou o
  // conteúdo — sem isso, não havia certeza de que o botão foi acionado.
  const [copiedKey, setCopiedKey] = useState<"message" | "link" | null>(null);
  const copiedTimerRef = useRef<number | null>(null);
  const eventCursorRef = useRef<number | null>(null);
  const redirectingRef = useRef(false);
  const inviteBaseUrl = useMemo(() => publicAppUrl(), []);

  useEffect(() => {
    setForm({
      ...initialForm,
      patient_name: patientNamePrefill,
      patient_email: patientEmailPrefill,
      patient_phone: patientPhonePrefill,
    });
    setInvite(null);
    setError("");
    setPatientActivity("");
    eventCursorRef.current = null;
    redirectingRef.current = false;
  }, [
    location.key,
    patientEmailPrefill,
    patientNamePrefill,
    patientPhonePrefill,
  ]);

  const updateForm = (key: keyof typeof initialForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateLanguage = (key: keyof SessionLanguagePreferences, value: SessionLocale) => {
    setLanguages((previous) => {
      const next = { ...previous, [key]: value };
      saveSessionLanguagePreferences(next);
      return next;
    });
  };

  const copyText = async (text: string): Promise<boolean> => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard indisponível");
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      window.prompt("Copie o conteúdo abaixo:", text);
      return false;
    }
  };

  const handleCopy = async (key: "message" | "link", text: string) => {
    const success = await copyText(text);
    if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
    if (success) {
      setCopiedKey(key);
      copiedTimerRef.current = window.setTimeout(() => {
        setCopiedKey(null);
        copiedTimerRef.current = null;
      }, 2200);
    }
  };

  useEffect(() => {
    return () => {
      if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
    };
  }, []);

  const createInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    setError("");
    setInvite(null);

    try {
      const token = localStorage.getItem("froid_token") || "";
      const response = await fetch(apiUrl("/api/session-invites"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ...form,
          session_id: makeId(),
          base_url: inviteBaseUrl,
          package_sessions: Number(form.package_sessions || 0),
          session_value: form.session_value,
          session_mode: isPatientMobileCapture ? "presential_mobile" : "remote",
          patient_results_enabled: patientResultsEnabled,
          patient_ui_locale: languages.patientUiLocale,
          spoken_language: languages.spokenLanguage,
          analysis_language: languages.analysisLanguage,
          report_locale: languages.reportLocale,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "Não foi possível criar o convite.");
      }
      setInvite(data);
      rememberSessionPatient(data.session_id, {
        id: data.patient_id,
        name: form.patient_name,
        email: form.patient_email,
        phone: form.patient_phone,
        sessionMode: isPatientMobileCapture ? "presential_mobile" : "remote",
        captureProfile: isPatientMobileCapture ? "patient_mobile" : "local_default",
        patientUiLocale: languages.patientUiLocale,
        spokenLanguage: languages.spokenLanguage,
        analysisLanguage: languages.analysisLanguage,
        reportLocale: languages.reportLocale,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar convite.");
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    if (!invite?.session_id) return;
    let active = true;
    redirectingRef.current = false;

    const pollSessionEvents = async () => {
      try {
        if (eventCursorRef.current === null) {
          const token = localStorage.getItem("froid_token") || "";
          const response = await fetch(apiUrl("/api/session-events/latest"), {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (!response.ok) return;
          const data = await response.json();
          eventCursorRef.current = Number(data?.latest_id || 0);
          return;
        }

        const token = localStorage.getItem("froid_token") || "";
        const response = await fetch(
          apiUrl(`/api/session-events?after=${eventCursorRef.current}`),
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!response.ok) return;
        const data = await response.json();
        const events: SessionEvent[] = Array.isArray(data?.events)
          ? data.events
          : [];
        eventCursorRef.current = Math.max(
          Number(eventCursorRef.current || 0),
          Number(data?.latest_id || 0),
          ...events.map((event) => Number(event.id || 0)),
        );
        const sessionEvents = events.filter(
          (event) => event.session_id === invite.session_id,
        );
        const latest = sessionEvents[sessionEvents.length - 1];
        if (!latest || !active) return;
        const patient = latest.patient_name || form.patient_name || "Paciente";
        if (latest.type === "invite_opened") {
          setPatientActivity(`${patient} abriu o link de cadastro FROID.`);
        }
        if (latest.type === "invite_accepted") {
          setPatientActivity(`${patient} confirmou cadastro e consentimentos LGPD.`);
        }
        if (latest.type === "patient_joined" && !redirectingRef.current) {
          setPatientActivity(`${patient} entrou na sessão. Abrindo sala do profissional...`);
          rememberSessionPatient(invite.session_id, {
            id: invite.patient_id,
            name: patient,
            email: form.patient_email,
            phone: form.patient_phone,
            sessionMode: isPatientMobileCapture ? "presential_mobile" : "remote",
            captureProfile: isPatientMobileCapture ? "patient_mobile" : "local_default",
            patientUiLocale: languages.patientUiLocale,
            spokenLanguage: languages.spokenLanguage,
            analysisLanguage: languages.analysisLanguage,
            reportLocale: languages.reportLocale,
          });
          redirectingRef.current = true;
          window.setTimeout(() => {
            if (active) navigate(`/session/${invite.session_id}`);
          }, 700);
        }
      } catch {
        // Polling best-effort.
      }
    };

    void pollSessionEvents();
    const intervalId = window.setInterval(pollSessionEvents, 2500);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [form.patient_email, form.patient_name, form.patient_phone, invite, isPatientMobileCapture, languages, navigate]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">
              Cadastro de Paciente
            </p>
            <h1 className="text-xl font-bold text-slate-100">
              {isPatientMobileCapture
                ? "Presencial com celular do paciente"
                : "Novo paciente e convite LGPD"}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              {isPatientMobileCapture
                ? "Gere o link para o paciente abrir no próprio celular dentro do consultório."
                : "Gere o link público para cadastro, consentimentos e entrada na sessão."}
            </p>
          </div>
          <button
            onClick={() => navigate("/dashboard")}
            className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-bold text-slate-300 hover:bg-slate-950"
          >
            Dashboard
          </button>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-4 p-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-slate-700 bg-slate-900 p-4 shadow-sm">
          <h2 className="text-sm font-bold text-slate-100">
            Dados iniciais e pagamento
          </h2>
          {isPatientMobileCapture && (
            <div className="mt-3 rounded-lg border border-violet-800 bg-violet-950 p-3 text-xs leading-relaxed text-violet-100">
              <p className="font-black uppercase tracking-wide">Captura dedicada do paciente</p>
              <p className="mt-1">
                O paciente deve abrir o link no próprio celular. O aparelho funcionará
                como câmera e microfone próximos ao paciente. Recomenda-se que o
                profissional use microfone de lapela próprio para reduzir vazamento da
                voz do DR na trilha do paciente.
              </p>

              {/* O enquadramento é pré-condição da medida, e não uma preferência
                  estética.
                  A leitura FACS sai dos blendshapes que o MediaPipe extrai do vídeo
                  DESTE aparelho — o celular do paciente é a única câmera analisada.
                  Sem rosto detectado não há blendshape, o servidor declara
                  `facs_source: "sem_apuracao"` e a sessão inteira sai sem leitura
                  facial e sem nenhuma dissonância facial-vocal possível. Falha
                  honesta, e irrecuperável depois: não há como reprocessar o que não
                  foi capturado.
                  O procedimento estava só na cabeça de quem montou o modo. Agora
                  está na tela em que o convite é gerado, que é onde ele é lido. */}
              <p className="mt-3 font-black uppercase tracking-wide">
                Antes de iniciar — enquadramento e áudio
              </p>
              <ul className="mt-1 list-disc space-y-1 pl-4">
                <li>
                  <strong>Apoie o celular</strong> em suporte, tripé ou base fixa, na
                  altura aproximada dos olhos do paciente. Na mão, a oscilação
                  interrompe a detecção do rosto.
                </li>
                <li>
                  <strong>Rosto inteiro e de frente</strong>, dentro do quadro: testa,
                  sobrancelhas, olhos e boca visíveis ao mesmo tempo. As unidades de
                  ação FACS dependem dessas regiões; rosto cortado ou de perfil não
                  produz leitura.
                </li>
                <li>
                  <strong>Luz na frente, nunca atrás.</strong> Janela ou luminária
                  às costas do paciente deixa o rosto em contraluz e a detecção falha.
                </li>
                <li>
                  <strong>Sem máscara, boné com aba baixa ou óculos escuros</strong>,
                  e cabelo fora dos olhos e das sobrancelhas.
                </li>
                <li>
                  <strong>O celular fica perto do paciente</strong> — é dele que sai a
                  voz analisada. O áudio deste aparelho não é reproduzido na sala, de
                  propósito, para não gerar eco.
                </li>
                <li>
                  <strong>Confirme na tela do paciente</strong> que a câmera e o
                  microfone foram liberados antes de começar. Se o navegador do celular
                  bloquear qualquer um dos dois, a sessão corre sem aquela medida.
                </li>
              </ul>
              {/* Só o que é verificável.
                  A primeira versão desta frase dizia que "o painel informa durante
                  a sessão qual leitura está entrando". É verdade para a acústica —
                  a página do paciente manda o estado da captura pelo canal de
                  sinalização e o painel o exibe —, mas NÃO para a facial: a
                  procedência da face só é contabilizada no fim, ao montar o
                  relatório, e durante a sessão a seção "Leitura FACS/AUs" só
                  aparece quando já há leitura. Ausência não se anuncia. Prometer
                  um aviso que não existe é o mesmo defeito que este trabalho
                  inteiro está corrigindo. */}
              <p className="mt-2 text-[11px] text-violet-200/90">
                Confira o enquadramento na tela do celular antes de iniciar. O que
                não for captado não pode ser recuperado depois: a sessão termina com
                a leitura facial declarada como não apurada, e não há reprocessamento.
              </p>
            </div>
          )}
          <form autoComplete="off" onSubmit={createInvite} className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="grid gap-3 rounded-lg border border-cyan-900/60 bg-cyan-950/30 p-3 md:col-span-2 md:grid-cols-2">
              <div className="md:col-span-2">
                <p className="text-xs font-black uppercase tracking-wide text-cyan-200">
                  Idiomas da sessão
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                  Inglês, francês e espanhol estão disponíveis em validação controlada. A
                  transcrição literal permanece no idioma falado e nunca é substituída pela tradução.
                </p>
              </div>
              {([
                ["spokenLanguage", "Idioma falado"],
                ["patientUiLocale", "Interface do paciente"],
                ["analysisLanguage", "Idioma da análise semântica"],
                ["reportLocale", "Idioma do relatório"],
              ] as Array<[keyof SessionLanguagePreferences, string]>).map(([key, label]) => (
                <label key={key} className="text-xs font-bold text-slate-300">
                  {label}
                  <select
                    value={languages[key]}
                    onChange={(event) => updateLanguage(key, event.target.value as SessionLocale)}
                    className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500"
                  >
                    {sessionLocaleOptions().map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}{option.validationStatus === "pilot" ? " — validação" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <label className="text-xs font-bold text-slate-300">
              Nome do paciente
              <input
                autoComplete="off"
                value={form.patient_name}
                onChange={(event) => updateForm("patient_name", event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
              />
            </label>
            <label className="text-xs font-bold text-slate-300">
              WhatsApp
              <input
                autoComplete="off"
                value={form.patient_phone}
                onChange={(event) => updateForm("patient_phone", event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
              />
            </label>
            <label className="text-xs font-bold text-slate-300">
              E-mail
              <input
                autoComplete="off"
                value={form.patient_email}
                onChange={(event) => updateForm("patient_email", event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
              />
            </label>
            <label className="text-xs font-bold text-slate-300">
              Forma de pagamento
              <select
                value={form.payment_mode}
                onChange={(event) =>
                  updateForm("payment_mode", event.target.value as PaymentMode)
                }
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
              >
                <option value="single">Sessão avulsa com PIX</option>
                <option value="package">Pacote de sessões</option>
              </select>
            </label>
            <label className="text-xs font-bold text-slate-300">
              Valor da sessão (R$)
              <input
                value={form.session_value}
                onChange={(event) => updateForm("session_value", event.target.value)}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
              />
            </label>
            {form.payment_mode === "package" ? (
              <label className="text-xs font-bold text-slate-300">
                Número de sessões
                <input
                  type="number"
                  min={1}
                  value={form.package_sessions}
                  onChange={(event) =>
                    updateForm("package_sessions", event.target.value)
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
                />
              </label>
            ) : (
              <label className="text-xs font-bold text-slate-300">
                Código PIX cópia e cola
                <input
                  value={form.pix_code}
                  onChange={(event) => updateForm("pix_code", event.target.value)}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-normal outline-none focus:border-cyan-500 focus:bg-slate-900"
                />
              </label>
            )}
            {/* Acesso do paciente aos próprios resultados. Fica no convite
                porque é onde o profissional decide o enquadramento do caso, e
                não escondido numa tela de configuração. */}
            <div className="md:col-span-2 rounded-lg border border-slate-700 bg-slate-950 p-3">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={patientResultsEnabled}
                  onChange={(event) => setPatientResultsEnabled(event.target.checked)}
                  className="mt-1 h-4 w-4 shrink-0 accent-cyan-500"
                />
                <span>
                  <span className="text-xs font-black text-white">
                    Habilitar o paciente a ver os resultados na área dele
                  </span>
                  <span className="mt-1 block text-[11px] font-normal leading-4 text-slate-400">
                    {patientResultsEnabled
                      ? "O paciente poderá abrir e baixar os relatórios que você liberar. Ligar aqui não libera nada sozinho: cada sessão ainda passa pela composição e pelo botão de liberar, no Relatório da Sessão."
                      : "O paciente entra na área dele, vê os próprios dados cadastrais e exerce os direitos de titular, mas não vê sessões nem relatórios. Você pode mudar isso depois, na ficha dele."}
                  </span>
                </span>
              </label>
            </div>
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={creating}
                className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-800 disabled:opacity-50"
              >
                {creating
                  ? "Gerando..."
                  : isPatientMobileCapture
                    ? "Gerar link para celular do paciente"
                    : "Gerar link de cadastro"}
              </button>
              {error && (
                <p className="mt-2 rounded bg-red-50 px-3 py-2 text-xs font-bold text-red-700">
                  {error}
                </p>
              )}
            </div>
          </form>
        </section>

        <aside className="rounded-lg border border-blue-800 bg-blue-950 p-4 text-xs text-blue-100">
          <h2 className="text-sm font-bold">Fluxo do paciente</h2>
          <p className="mt-2 leading-relaxed">
            {isPatientMobileCapture
              ? "No consultório, o paciente abre o link no celular, confirma consentimentos e entra na sala. O celular passa a ser a captura dedicada do paciente."
              : "O paciente recebe o link, confirma dados, aceita LGPD e entra na sala. O cadastro definitivo acontece no aceite do convite."}
          </p>
          {patientActivity && (
            <p className="mt-3 rounded border border-emerald-100 bg-emerald-950/40 p-2 font-bold text-emerald-800">
              {patientActivity}
            </p>
          )}
          <p className="mt-2 rounded border border-blue-100 bg-slate-950 p-2 font-mono text-[11px] text-blue-200">
            Base publica: {inviteBaseUrl}
          </p>
          <div className="mt-3">
            <LgpdNotice audience="professional" compact />
          </div>
          {invite ? (
            <div className="mt-4 space-y-3">
              <p className="font-bold">
                Convite criado: {invite.session_id} |{" "}
                {invite.patient_known ? "paciente cadastrado" : "novo cadastro"}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => void handleCopy("message", invite.whatsapp_message)}
                  className={`rounded border px-2 py-1 font-bold transition-colors ${
                    copiedKey === "message"
                      ? "border-emerald-500 bg-emerald-900 text-emerald-100"
                      : "border-blue-800 bg-slate-900 text-blue-200 hover:bg-blue-900"
                  }`}
                >
                  {copiedKey === "message" ? "✓ Copiado!" : "Copiar mensagem"}
                </button>
                <button
                  onClick={() => void handleCopy("link", invite.invite_url)}
                  className={`rounded border px-2 py-1 font-bold transition-colors ${
                    copiedKey === "link"
                      ? "border-emerald-500 bg-emerald-900 text-emerald-100"
                      : "border-blue-800 bg-slate-900 text-blue-200 hover:bg-blue-900"
                  }`}
                >
                  {copiedKey === "link" ? "✓ Copiado!" : "Copiar link"}
                </button>
                <button
                  onClick={() => navigate(`/session/${invite.session_id}`)}
                  className="rounded border border-blue-800 bg-slate-900 px-2 py-1 font-bold text-blue-200 hover:bg-blue-900"
                >
                  Abrir sala DR
                </button>
              </div>
              <textarea
                readOnly
                value={invite.whatsapp_message}
                className="h-44 w-full rounded border border-blue-100 bg-slate-950 p-2 text-slate-300"
              />
            </div>
          ) : (
            <p className="mt-4 rounded border border-blue-100 bg-slate-950 p-3 text-blue-200">
              {isPatientMobileCapture
                ? "Preencha os dados para gerar o link que será aberto no celular do paciente."
                : "Preencha os dados para gerar o link de cadastro do paciente."}
            </p>
          )}
        </aside>
      </main>
    </div>
  );
};


