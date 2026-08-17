import { useEffect, useState } from "react";
import { apiUrl } from "../../lib/api";

/**
 * A chave que decide se ESTE paciente vê os resultados na área dele.
 *
 * Não confundir com o botão "Baixar relatório", que vive no portal do paciente:
 * aquele é a ação DELE sobre um relatório já liberado; esta é a decisão DO
 * PROFISSIONAL sobre se ele vê alguma coisa. São dois papéis, e cada um mora do
 * seu lado.
 *
 * A chave já existia no formulário de convite, mas ali ela é escolhida uma vez.
 * A decisão muda com o caso clínico, e sem este cartão mudar de ideia sobre um
 * paciente já cadastrado exigia chamar a API na mão.
 *
 * DESLIGAR NÃO FECHA O PORTAL, e o texto diz isso: o paciente continua entrando,
 * vendo os próprios dados e exercendo os direitos de titular. O que ele deixa de
 * ver são sessões e relatórios.
 */
export function PatientResultsAccessCard({
  patientId,
  patientName,
}: {
  patientId: string;
  patientName?: string;
}) {
  const [habilitado, setHabilitado] = useState<boolean | null>(null);
  const [explicito, setExplicito] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [aviso, setAviso] = useState("");

  const cabecalhos = () => {
    const token = localStorage.getItem("froid_token") || "";
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  useEffect(() => {
    if (!patientId) return;
    let ativo = true;
    fetch(apiUrl(`/api/patients/${patientId}/results-access`), { headers: cabecalhos() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!ativo || !d) return;
        setHabilitado(d.portal_results_enabled !== false);
        setExplicito(Boolean(d.explicit));
      })
      .catch(() => {});
    return () => {
      ativo = false;
    };
  }, [patientId]);

  const alternar = async (valor: boolean) => {
    setSalvando(true);
    setAviso("");
    try {
      const r = await fetch(apiUrl(`/api/patients/${patientId}/results-access`), {
        method: "PUT",
        headers: cabecalhos(),
        body: JSON.stringify({ enabled: valor }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "Não foi possível salvar.");
      setHabilitado(d.portal_results_enabled !== false);
      setExplicito(true);
      setAviso(valor ? "Acesso habilitado." : "Acesso desabilitado.");
    } catch (err) {
      setAviso(err instanceof Error ? err.message : "Falha ao salvar.");
    } finally {
      setSalvando(false);
    }
  };

  // Enquanto não se sabe o estado, não se desenha a chave: uma chave que nasce
  // sempre desligada mente sobre o que está valendo.
  if (habilitado === null) return null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          checked={habilitado}
          disabled={salvando}
          onChange={(e) => alternar(e.target.checked)}
          className="mt-1 h-4 w-4 shrink-0 accent-cyan-500"
        />
        <span>
          <span className="text-xs font-black text-white">
            {patientName ? `${patientName} pode ver os resultados` : "Pode ver os resultados"}
          </span>
          <span className="mt-1 block text-[11px] font-normal leading-4 text-slate-400">
            {habilitado
              ? "O paciente abre e baixa na área dele os relatórios que você liberar. Habilitar aqui não libera nada sozinho: cada sessão passa pela composição e pelo botão de liberar, no Relatório da Sessão."
              : "O paciente entra na área dele, vê os próprios dados e exerce os direitos de titular, mas não vê sessões nem relatórios. Isso não afeta a exportação LGPD, que é direito dele e não passa por esta chave."}
          </span>
          {!explicito && (
            // Cadastro anterior a este controle conta como habilitado por
            // compatibilidade. Dizer isso evita que pareça uma escolha que
            // alguém fez.
            <span className="mt-1 block text-[10px] font-bold text-slate-500">
              Cadastro anterior a este controle: habilitado por padrão, ainda sem decisão registrada.
            </span>
          )}
          {aviso && (
            <span className="mt-1 block text-[10px] font-bold text-cyan-300">{aviso}</span>
          )}
        </span>
      </label>
    </div>
  );
}
