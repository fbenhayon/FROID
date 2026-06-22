import React, { useCallback, useState } from "react";
import { ClinicalNote } from "../../lib/session-report";
import { FroidTooltip } from "../ui/FroidTooltip";

interface Props {
  notes: ClinicalNote[];
  onAddNote: (text: string) => void;
}

export const ClinicalNotes: React.FC<Props> = ({ notes, onAddNote }) => {
  const [text, setText] = useState("");

  const addNote = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onAddNote(trimmed);
    setText("");
  }, [onAddNote, text]);

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-slate-200 pt-3">
      <div className="flex items-center gap-2">
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">
          NOTA
        </span>
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Anotacoes Clinicas
        </h3>
      </div>
      <FroidTooltip
        content={
          <div>
            <p className="font-bold">Registro Clinico</p>
            <p className="text-[11px]">
              Estas observacoes entram no Relatorio da Consulta.
            </p>
          </div>
        }
      >
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && event.ctrlKey) addNote();
          }}
          placeholder="Registre observacoes do profissional..."
          className="h-20 w-full resize-none rounded-lg border border-slate-300 bg-white p-2 text-xs text-slate-700 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </FroidTooltip>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-400">Ctrl+Enter</span>
        <button
          onClick={addNote}
          disabled={!text.trim()}
          className="rounded bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-200 disabled:opacity-40"
        >
          Adicionar
        </button>
      </div>
      <div className="max-h-[160px] min-h-[60px] flex-1 space-y-2 overflow-y-auto pr-1">
        {notes.length === 0 && (
          <p className="py-2 text-center text-[10px] italic text-slate-400">
            Sem anotacoes
          </p>
        )}
        {notes.map((note) => (
          <div
            key={note.id}
            className="rounded-md border border-slate-100 bg-slate-50 p-2"
          >
            <p className="whitespace-pre-wrap text-[11px] leading-snug text-slate-700">
              {note.text}
            </p>
            <p className="mt-1 text-[9px] text-slate-400">
              {new Date(note.timestamp).toLocaleTimeString("pt-BR")}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
