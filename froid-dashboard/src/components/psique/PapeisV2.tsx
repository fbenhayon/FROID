import { useCallback, useEffect, useState } from "react";
import {
  ativarRbacV2,
  concederPapelV2,
  listarPapeisV2,
  obterCapacidadesPsiqueV2,
  revogarPapelV2,
  type CapacidadesPsiqueV2,
  type EstadoV2,
  type MembroComPapeisV2,
} from "../../lib/psique-v2-api";

/** Os papéis V2 que a agenda e a clínica usam, com a frase que o gestor lê. */
export const PAPEIS_V2: Array<{ papel: string; rotulo: string; explica: string }> = [
  { papel: "CLINICIAN", rotulo: "Clínico", explica: "tem agenda própria e atende" },
  { papel: "SECRETARY", rotulo: "Secretaria", explica: "marca, reagenda e cancela para todos; vê nomes" },
  { papel: "CLINICAL_SUPERVISOR", rotulo: "Supervisor clínico", explica: "vê e opera a agenda geral, sem nomes de pacientes" },
  { papel: "ORG_ADMIN", rotulo: "Administração", explica: "tudo da agenda e dos papéis; vê nomes" },
];

/**
 * Ativação dos papéis V2 e concessão por membro (Gestão da clínica).
 *
 * A ativação é do owner V1 da organização (o servidor exige). Ao ativar, o
 * servidor já concede Clínico a quem é profissional e Administração a owner e
 * administrador. O resto é concedido aqui, membro a membro.
 */
export function PapeisV2({ isManager }: { isManager: boolean }) {
  const [capacidades, setCapacidades] = useState<EstadoV2<CapacidadesPsiqueV2>>({ estado: "indisponivel", motivo: "CARREGANDO" });
  const [membros, setMembros] = useState<MembroComPapeisV2[]>([]);
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    const caps = await obterCapacidadesPsiqueV2();
    setCapacidades(caps);
    if (caps.estado === "ok" && caps.dados.rbac_version === 2 && caps.dados.capabilities.manage_roles) {
      const lista = await listarPapeisV2();
      if (lista.estado === "ok") setMembros(lista.dados.members);
      else setErro(`Não foi possível listar os papéis: ${lista.motivo}.`);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (capacidades.estado === "indisponivel" && capacidades.motivo !== "CARREGANDO") {
    // Flag desligado no servidor: a seção não existe.
    return null;
  }

  const ativar = async () => {
    if (!window.confirm("Ativar os papéis V2 nesta clínica? A ativação não se desfaz.")) return;
    setOcupado(true);
    setErro("");
    const r = await ativarRbacV2();
    if (r.estado === "ok") setAviso("Papéis V2 ativados. Clínicos e administração já receberam os papéis iniciais.");
    else setErro(`Ativação recusada: ${r.motivo}.`);
    setOcupado(false);
    await carregar();
  };

  const alternar = async (membro: MembroComPapeisV2, papel: string) => {
    setOcupado(true);
    setErro("");
    const tem = membro.v2_roles.includes(papel);
    const r = tem ? await revogarPapelV2(membro.membership_id, papel) : await concederPapelV2(membro.membership_id, papel);
    if (r.estado !== "ok") setErro(`${tem ? "Revogação" : "Concessão"} recusada: ${r.motivo}.`);
    else setAviso(`${tem ? "Revogado" : "Concedido"} ${papel} para ${membro.email}.`);
    setOcupado(false);
    await carregar();
  };

  const v2 = capacidades.estado === "ok" && capacidades.dados.rbac_version === 2;
  const podeGerir = capacidades.estado === "ok" && capacidades.dados.capabilities.manage_roles;

  return (
    <section data-secao="papeis-v2" className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-black text-slate-100">Papéis e agenda (V2)</h2>
        <span className="text-[10px] text-slate-500">
          {capacidades.estado === "ok" ? `papéis versão ${capacidades.dados.rbac_version}` : "confirmando..."}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-slate-400">
        A agenda interna da clínica funciona sobre os papéis V2: quem é clínico tem agenda própria;
        secretaria, administração e supervisão operam a agenda de todos. O servidor decide; esta tela apresenta.
      </p>
      {aviso ? <p data-campo="aviso" className="mt-2 text-xs text-cyan-200">{aviso}</p> : null}
      {erro ? <p data-campo="erro" className="mt-2 text-xs text-red-300">{erro}</p> : null}

      {!v2 ? (
        <div className="mt-3">
          <button
            type="button"
            disabled={!isManager || ocupado || capacidades.estado !== "ok"}
            onClick={() => void ativar()}
            className="rounded bg-cyan-700 px-3 py-1 text-xs font-bold text-white hover:bg-cyan-800 disabled:opacity-60"
          >
            Ativar papéis V2 nesta clínica
          </button>
          <p className="mt-1 text-[10px] text-slate-500">
            Só o owner da organização ativa. Depois da ativação os papéis não voltam à versão anterior.
          </p>
        </div>
      ) : null}

      {v2 && podeGerir ? (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-max table-auto text-left text-[11px]">
            <thead className="text-[9px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-2 py-1">Membro</th>
                {PAPEIS_V2.map((p) => (
                  <th key={p.papel} className="px-2 py-1" title={p.explica}>{p.rotulo}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {membros.map((membro) => (
                <tr key={membro.membership_id}>
                  <td className="px-2 py-1 font-bold text-slate-100">{membro.email}</td>
                  {PAPEIS_V2.map((p) => {
                    const tem = membro.v2_roles.includes(p.papel);
                    return (
                      <td key={p.papel} className="px-2 py-1">
                        <button
                          type="button"
                          disabled={ocupado}
                          onClick={() => void alternar(membro, p.papel)}
                          className={`rounded border px-2 py-0.5 text-[10px] ${
                            tem ? "border-cyan-600 bg-cyan-950/60 text-cyan-100" : "border-slate-700 text-slate-400 hover:border-cyan-800"
                          }`}
                        >
                          {tem ? "sim" : "não"}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {v2 && !podeGerir ? (
        <p className="mt-2 text-[10px] text-slate-500">Somente a administração da clínica concede papéis.</p>
      ) : null}
    </section>
  );
}
