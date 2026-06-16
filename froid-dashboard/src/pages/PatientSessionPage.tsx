import React, { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { apiUrl } from "../lib/api";

type JoinState = "checking" | "joined" | "blocked";
type MediaState = "idle" | "requesting" | "active" | "failed";

export const PatientSessionPage: React.FC = () => {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") || "";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [joinState, setJoinState] = useState<JoinState>("checking");
  const [mediaState, setMediaState] = useState<MediaState>("idle");
  const [patientName, setPatientName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    if (!sessionId || !inviteToken) {
      setJoinState("blocked");
      setError("Link de sessao incompleto.");
      return;
    }

    fetch(apiUrl(`/api/patient-sessions/${sessionId}/join`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invite_token: inviteToken }),
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.detail || "Sessao indisponivel.");
        return data;
      })
      .then((data) => {
        if (!active) return;
        setPatientName(String(data?.patient_name || ""));
        setJoinState("joined");
      })
      .catch((err) => {
        if (!active) return;
        setJoinState("blocked");
        setError(err instanceof Error ? err.message : "Nao foi possivel entrar.");
      });

    return () => {
      active = false;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [inviteToken, sessionId]);

  const activateMedia = async () => {
    setMediaState("requesting");
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setMediaState("active");
    } catch {
      setMediaState("failed");
      setError("Nao foi possivel ativar camera e microfone neste navegador.");
    }
  };

  const statusText =
    joinState === "checking"
      ? "Validando convite..."
      : joinState === "joined"
        ? "Paciente conectado"
        : "Entrada bloqueada";

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <main className="mx-auto max-w-4xl">
        <div className="mb-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
            FROID
          </p>
          <h1 className="mt-2 text-2xl font-bold">Sala do paciente</h1>
          <p className="mt-1 text-sm text-slate-400">
            {statusText}
            {patientName ? ` - ${patientName}` : ""}
          </p>
        </div>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-sm">
          <div className="relative aspect-video overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 h-full w-full object-cover"
            />
            {mediaState !== "active" && (
              <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-slate-400">
                Camera e microfone aguardando permissao.
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-bold text-slate-100">
                Sessao {sessionId}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                O profissional conduz a sessao pelo painel clinico FROID.
              </p>
            </div>
            <button
              type="button"
              onClick={activateMedia}
              disabled={joinState !== "joined" || mediaState === "requesting"}
              className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mediaState === "requesting"
                ? "Ativando..."
                : mediaState === "active"
                  ? "Audio e video ativos"
                  : "Ativar audio e video"}
            </button>
          </div>

          {error && (
            <p className="mt-4 rounded-md border border-red-900/50 bg-red-950/50 px-3 py-2 text-xs font-semibold text-red-200">
              {error}
            </p>
          )}
        </section>
      </main>
    </div>
  );
};
