import React from "react";
interface Props { cameraOn: boolean; micOn: boolean; simulated?: boolean; }
export const MediaStatus: React.FC<Props> = ({ cameraOn, micOn, simulated }) => (
  <div className="absolute top-3 right-3 flex gap-2 z-20">
    <div title={cameraOn ? (simulated ? "Câmera Simulada" : "Câmera ativa") : "Câmera bloqueada"} className={`rounded-full p-1.5 backdrop-blur-sm border border-white/20 shadow-sm ${cameraOn ? (simulated ? "bg-amber-500/40 text-amber-300" : "bg-green-500/40 text-green-300") : "bg-red-500/40 text-red-300"}`}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
    </div>
    <div title={micOn ? "Microfone ativo" : "Microfone bloqueado"} className={`rounded-full p-1.5 backdrop-blur-sm border border-white/20 shadow-sm ${micOn ? "bg-green-500/40 text-green-300" : "bg-red-500/40 text-red-300"}`}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
    </div>
  </div>
);
