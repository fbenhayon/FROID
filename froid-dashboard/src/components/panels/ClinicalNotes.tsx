import React, { useState, useCallback } from "react";
import { FroidTooltip } from "../ui/FroidTooltip";
interface Note { id: string; text: string; timestamp: number; }
function makeId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 9); }
export const ClinicalNotes: React.FC = () => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [text, setText] = useState("");
  const addNote = useCallback(() => {
    const t = text.trim(); if (!t) return;
    setNotes(prev => [{ id: makeId(), text: t, timestamp: Date.now() }, ...prev]);
    setText("");
  }, [text]);
  return (
    <div className="flex flex-col gap-2 mt-3 border-t border-slate-200 pt-3">
      <div className="flex items-center gap-2"><span className="text-lg">📝</span><h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Anotações Clínicas</h3></div>
      <FroidTooltip content={<div><p className="font-bold">Registro Clínico</p><p className="text-[11px]">Privado e opcionalmente criptografado.</p></div>}>
        <textarea value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === "Enter" && e.ctrlKey && addNote()} placeholder="Registre observações..." className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-700 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none h-20" />
      </FroidTooltip>
      <div className="flex items-center justify-between"><span className="text-[10px] text-slate-400">Ctrl+Enter</span><button onClick={addNote} disabled={!text.trim()} className="rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-200 disabled:opacity-40">Adicionar</button></div>
      <div className="flex-1 overflow-y-auto min-h-[60px] max-h-[160px] space-y-2 pr-1">
        {notes.length === 0 && <p className="text-center text-[10px] italic text-slate-400 py-2">Sem anotações</p>}
        {notes.map(n => <div key={n.id} className="rounded-md border border-slate-100 bg-slate-50 p-2"><p className="text-[11px] leading-snug text-slate-700 whitespace-pre-wrap">{n.text}</p><p className="mt-1 text-[9px] text-slate-400">{new Date(n.timestamp).toLocaleTimeString("pt-BR")}</p></div>)}
      </div>
    </div>
  );
};
