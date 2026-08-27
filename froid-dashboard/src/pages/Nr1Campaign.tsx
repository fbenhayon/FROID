import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import {
  caminhoDoPorte,
  exigeCenso,
  exigidoNaCampanha,
  exigidoNoRecorte,
  PISO_CAMPANHA,
  PISO_RECORTE,
} from "../lib/nr1-representatividade";
import { GlossarioDeSiglas, Sigla } from "../lib/siglas";

/**
 * Campanha e convites: a camada que faltava entre a estrutura da empresa e o
 * painel de conformidade.
 *
 * Os tres endpoints usados aqui existem no servidor desde a migration 010 —
 * criar campanha, abrir a coleta e gerar convites — e nenhuma tela os chamava.
 * Na pratica a coleta so comecava com alguem operando o banco a mao, e era por
 * isso que a configuracao precisava ser "conduzida pela equipe FROID".
 *
 * Duas propriedades desta tela nao sao estilo, sao consequencia da norma:
 *
 * - O efetivo do periodo de referencia aparece com o numero de respostas que
 *   ele exige, na hora em que e digitado. Descobrir no fim da coleta que
 *   faltavam 40 respostas e a conversa que o portao de representatividade
 *   existe para evitar, nao para produzir.
 * - Os tokens dos convites sao mostrados UMA vez. O servidor guarda o digest,
 *   nunca o token, e nao guarda o par matricula-token em lugar nenhum — e essa
 *   ausencia que sustenta o anonimato. Perder esta tela sem baixar o arquivo
 *   significa reemitir os convites, nao recupera-los.
 */

const CONTATO = "froid@froid.com.br";

/** O estado da campanha em portugues.
 *
 *  O enum do banco vazava cru para a tela — DRAFT, OPEN, CLOSED — numa pagina
 *  que a empresa contratante abre na frente da diretoria dela. "OPEN" ainda se
 *  adivinha; "DRAFT" ao lado de uma campanha que ja custou dinheiro, nao. */
const ESTADO_DA_CAMPANHA: Record<string, string> = {
  draft: "Rascunho",
  open: "Em coleta",
  closed: "Encerrada",
  cancelled: "Cancelada",
};

type Unidade = {
  unit_id: string;
  parent_unit_id: string | null;
  unit_type: "site" | "sector" | "exposure_group";
  name: string;
  external_code: string;
  headcount: number;
  status: string;
  child_count: number;
};

type Instrumento = {
  instrument_id: string;
  code: string;
  version: string;
  title: string;
  language: string;
  scale_min: number;
  scale_max: number;
  source_reference: string;
};

type Campanha = {
  campaign_id: string;
  title: string;
  status: string;
  opens_at?: string;
  closes_at?: string;
  unit_id?: string | null;
  target_headcount?: number;
};

type Convite = { payroll_number: string; token: string };

type Props = { user: FroidUser | null };

function token() {
  return localStorage.getItem("froid_token") || "";
}

/** A base publica do link que o trabalhador abre.
 *
 *  `/avaliacao` e rota direta: `normalizarEntradaDireta` (lib/entrada-direta)
 *  a reescreve para `/app/#/avaliacao` preservando a query, justamente para
 *  que o token sobreviva — e roda ANTES de o React montar, senao o roteador
 *  chega primeiro e manda o trabalhador para o login. Distribuir o link com hash funcionaria, mas passa por filtro de
 *  e-mail corporativo bem pior — e sao centenas de caixas de entrada. */
export function linkDoConvite(t: string): string {
  const origem =
    typeof window !== "undefined" && window.location.origin
      ? window.location.origin
      : "https://www.froid.com.br";
  return `${origem}/avaliacao?token=${encodeURIComponent(t)}`;
}

async function chamar(caminho: string, organizationId: string, init?: RequestInit) {
  const resposta = await fetch(apiUrl(caminho), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
      "X-FROID-Organization-ID": organizationId,
      ...(init?.headers || {}),
    },
  });
  const texto = await resposta.text();
  const corpo = texto ? JSON.parse(texto) : {};
  if (!resposta.ok) throw new Error(corpo?.detail || `falha ${resposta.status}`);
  return corpo;
}

const Campo: React.FC<{
  rotulo: string;
  valor: string;
  onChange: (v: string) => void;
  obrigatorio?: boolean;
  placeholder?: string;
  tipo?: string;
  dica?: string;
}> = ({ rotulo, valor, onChange, obrigatorio, placeholder, tipo = "text", dica }) => (
  <label className="block">
    <span className="text-xs font-black text-slate-300">
      {rotulo}
      {obrigatorio && <span className="ml-1 text-red-300">*</span>}
    </span>
    <input
      type={tipo}
      value={valor}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-500"
    />
    {dica && <span className="mt-1 block text-[11px] leading-4 text-slate-500">{dica}</span>}
  </label>
);

/**
 * Uma linha da lista colada pelo RH.
 *
 * Aceita `matricula`, `matricula;setor` e `matricula,setor` porque a lista vem
 * de uma planilha e ninguem vai reformatar centenas de linhas a mao. O setor e
 * casado pelo NOME ou pelo CODIGO INTERNO da unidade, sem diferenciar
 * maiuscula — o RH conhece a unidade pelo nome que usa, nao pelo UUID.
 */
export function interpretarLinha(
  linha: string,
  unidades: Unidade[],
): { payroll_number: string; unit_id: string | null; setorNaoEncontrado: string } | null {
  const limpa = linha.trim();
  if (!limpa) return null;
  const partes = limpa.split(/[;,\t]/).map((parte) => parte.trim());
  const matricula = partes[0] || "";
  if (!matricula) return null;
  const setor = partes[1] || "";
  if (!setor) return { payroll_number: matricula, unit_id: null, setorNaoEncontrado: "" };
  const alvo = setor.toLowerCase();
  const achada = unidades.find(
    (unidade) =>
      unidade.name.trim().toLowerCase() === alvo ||
      (unidade.external_code || "").trim().toLowerCase() === alvo,
  );
  return {
    payroll_number: matricula,
    unit_id: achada ? achada.unit_id : null,
    setorNaoEncontrado: achada ? "" : setor,
  };
}

/** O CSV que o RH abre no Excel para disparar os convites.
 *
 *  Ponto e virgula como separador, e BOM na frente: o Excel em portugues do
 *  Brasil abre CSV virgulado numa coluna so e come o acento sem o BOM. A
 *  planilha chegaria ilegivel justamente a quem precisa usa-la sob pressa. */
export function montarCsv(convites: Convite[]): string {
  const linhas = ["matricula;link"];
  for (const convite of convites) {
    linhas.push(`${convite.payroll_number};${linkDoConvite(convite.token)}`);
  }
  return `﻿${linhas.join("\r\n")}\r\n`;
}

/**
 * `datetime-local` exige 'AAAA-MM-DDTHH:mm' em hora LOCAL.
 *
 * `toISOString()` devolveria UTC e adiantaria a janela em três horas no
 * Brasil — a coleta abriria antes do horário que a tela mostra.
 */
function paraCampoLocal(data: Date): string {
  const doisDigitos = (n: number) => String(n).padStart(2, "0");
  return (
    `${data.getFullYear()}-${doisDigitos(data.getMonth() + 1)}-` +
    `${doisDigitos(data.getDate())}T${doisDigitos(data.getHours())}:` +
    `${doisDigitos(data.getMinutes())}`
  );
}

/**
 * Janela sugerida: começa hoje às 8h, fecha em duas semanas às 18h.
 *
 * Não é conveniência. O seletor de data do navegador deixa a HORA em branco
 * quando a pessoa escolhe só o dia, e um `datetime-local` sem hora vale string
 * VAZIA — a tela mostra "29/08/2026 --:--" e o campo, para o código, está em
 * branco. Quem preencheu tudo o que via recebia "a janela de coleta é
 * obrigatória" sem nada para corrigir. Nascer preenchido elimina o estado em
 * que o campo parece cheio e está vazio.
 */
function janelaPadrao(): { abre: string; fecha: string } {
  const abre = new Date();
  abre.setHours(8, 0, 0, 0);
  const fecha = new Date(abre);
  fecha.setDate(fecha.getDate() + 14);
  fecha.setHours(18, 0, 0, 0);
  return { abre: paraCampoLocal(abre), fecha: paraCampoLocal(fecha) };
}

export const Nr1Campaign: React.FC<Props> = ({ user }) => {
  const organizationId = String(user?.active_organization_id || "");

  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [salvando, setSalvando] = useState(false);

  const [unidades, setUnidades] = useState<Unidade[]>([]);
  const [instrumentos, setInstrumentos] = useState<Instrumento[]>([]);
  const [campanhas, setCampanhas] = useState<Campanha[]>([]);
  const [selecionada, setSelecionada] = useState<Campanha | null>(null);

  const [instrumentoId, setInstrumentoId] = useState("");
  const [titulo, setTitulo] = useState("");
  const [unidadeId, setUnidadeId] = useState("");
  const [periodo, setPeriodo] = useState("");
  const [efetivo, setEfetivo] = useState("");
  const [janela] = useState(janelaPadrao);
  const [abreEm, setAbreEm] = useState(janela.abre);
  const [fechaEm, setFechaEm] = useState(janela.fecha);
  const [finalidade, setFinalidade] = useState("");
  const [canalRotulo, setCanalRotulo] = useState("");
  const [canalDetalhe, setCanalDetalhe] = useState("");

  const [lista, setLista] = useState("");
  const [convites, setConvites] = useState<Convite[]>([]);
  // Matriculas que o servidor ignorou por ja terem convite nesta campanha.
  const [jaConvidados, setJaConvidados] = useState<string[]>([]);
  // Encerrar nao tem volta, entao pede um segundo clique deliberado.
  const [confirmandoFecho, setConfirmandoFecho] = useState<string | null>(null);
  const [listaReemissao, setListaReemissao] = useState("");
  const [semConvitePendente, setSemConvitePendente] = useState<string[]>([]);

  const carregar = useCallback(async () => {
    if (!organizationId) return;
    setErro("");
    try {
      const [u, i, c] = await Promise.all([
        chamar(`/api/organizations/${organizationId}/nr1/units`, organizationId),
        chamar(`/api/organizations/${organizationId}/nr1/instruments`, organizationId),
        chamar(`/api/organizations/${organizationId}/nr1/campaigns`, organizationId),
      ]);
      setUnidades(u.units || []);
      setInstrumentos(i.instruments || []);
      setCampanhas(c.campaigns || []);
      const publicados: Instrumento[] = i.instruments || [];
      setInstrumentoId((atual) => atual || publicados[0]?.instrument_id || "");
    } catch (e) {
      setErro(String((e as Error).message));
    }
  }, [organizationId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const estabelecimentos = useMemo(
    () => unidades.filter((u) => u.unit_type === "site"),
    [unidades],
  );
  const setores = useMemo(
    () => unidades.filter((u) => u.unit_type === "sector"),
    [unidades],
  );
  const efetivoTotal = useMemo(
    () => estabelecimentos.reduce((soma, site) => soma + site.headcount, 0),
    [estabelecimentos],
  );

  // O efetivo digitado manda, porque e ele que vai para o banco e decide o
  // portao. O somado da estrutura entra so como sugestao — divergir dele e
  // legitimo (rotatividade, periodo de referencia diferente do cadastro).
  const efetivoNumero = Number(efetivo) || 0;
  const exigidoAgora = exigidoNaCampanha(efetivoNumero);
  const caminho = caminhoDoPorte(efetivoNumero || efetivoTotal);

  const criar = async () => {
    setErro("");
    setAviso("");
    // Um erro por campo, nomeando o campo. A mensagem única ("instrumento,
    // título e janela são obrigatórios") era verdadeira e inútil: ela não diz
    // QUAL dos três, e no caso mais comum — hora em branco num campo que
    // mostra a data — o operador olha para um formulário que lhe parece
    // completo e não tem o que corrigir.
    if (!instrumentoId) {
      setErro(
        "Escolha o instrumento. Se a lista estiver vazia, nenhum questionário " +
          "está publicado no catálogo e a campanha não tem o que aplicar.",
      );
      return;
    }
    if (!titulo.trim()) {
      setErro("Dê um título à campanha: é por ele que ela aparece no painel.");
      return;
    }
    if (!abreEm || !fechaEm) {
      const faltando = !abreEm ? "Abertura da coleta" : "Fechamento da coleta";
      setErro(
        `O campo “${faltando}” precisa de data E hora. O seletor do navegador ` +
          "deixa a hora em branco (--:--) quando só o dia é escolhido, e sem a " +
          "hora o campo inteiro conta como vazio — clique sobre --:-- e informe " +
          "a hora.",
      );
      return;
    }
    if (new Date(fechaEm).getTime() <= new Date(abreEm).getTime()) {
      setErro("O fechamento precisa ser depois da abertura.");
      return;
    }
    if (efetivoNumero <= 0) {
      setErro(
        "Informe o efetivo do período de referência: sem denominador não há " +
          "amostra suficiente, e o servidor recusa abrir a coleta sem ele.",
      );
      return;
    }
    if (!canalRotulo.trim() || !canalDetalhe.trim()) {
      setErro(
        "O canal de apoio ao trabalhador é obrigatório. Perguntar a alguém " +
          "como ele está sem ter para onde encaminhá-lo é pior do que não perguntar.",
      );
      return;
    }
    setSalvando(true);
    try {
      const criada = await chamar(
        `/api/organizations/${organizationId}/nr1/campaigns`,
        organizationId,
        {
          method: "POST",
          body: JSON.stringify({
            instrument_id: instrumentoId,
            title: titulo.trim(),
            unit_id: unidadeId || null,
            reference_period: periodo.trim(),
            target_headcount: efetivoNumero,
            opens_at: new Date(abreEm).toISOString(),
            closes_at: new Date(fechaEm).toISOString(),
            purpose_notice: finalidade.trim(),
            support_channel_label: canalRotulo.trim(),
            support_channel_detail: canalDetalhe.trim(),
          }),
        },
      );
      setAviso(
        "Campanha criada em rascunho. Ela ainda não coleta nada: abrir a " +
          "coleta é um segundo ato, e é ele que começa a contar a janela.",
      );
      await carregar();
      setSelecionada({
        campaign_id: String(criada.campaign_id),
        title: titulo.trim(),
        status: "draft",
        target_headcount: efetivoNumero,
      });
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setSalvando(false);
    }
  };

  const abrir = async (campanha: Campanha) => {
    setErro("");
    setAviso("");
    setSalvando(true);
    try {
      await chamar(
        `/api/organizations/${organizationId}/nr1/campaigns/${campanha.campaign_id}/open`,
        organizationId,
        { method: "POST" },
      );
      setAviso("Coleta aberta. Os convites já podem ser distribuídos.");
      await carregar();
      setSelecionada({ ...campanha, status: "open" });
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setSalvando(false);
    }
  };

  /** Encerra a coleta — e é o encerramento que torna o resultado legível.
   *
   *  A rota existe no servidor desde a migration 010 e nenhuma tela a chamava.
   *  O efeito era pior do que um botão faltando: o painel só serve agregado de
   *  campanha encerrada, então o resultado inteiro do módulo ficava
   *  inalcançável pela interface. Quem operasse o produto teria de fechar a
   *  campanha por chamada direta à API.
   *
   *  Encerrar é definitivo — não há rota que devolva uma campanha encerrada ao
   *  estado aberto —, e por isso a confirmação em dois passos. */
  const fechar = async (campanha: Campanha) => {
    setErro("");
    setAviso("");
    setSalvando(true);
    try {
      await chamar(
        `/api/organizations/${organizationId}/nr1/campaigns/${campanha.campaign_id}/close`,
        organizationId,
        { method: "POST" },
      );
      setConfirmandoFecho(null);
      setAviso(
        "Coleta encerrada. O resultado agregado passa a ser legível no painel " +
          "de conformidade, e o inventário já pode ser gerado.",
      );
      await carregar();
      setSelecionada({ ...campanha, status: "closed" });
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setSalvando(false);
    }
  };

  const linhasInterpretadas = useMemo(
    () =>
      lista
        .split(/\r?\n/)
        .map((linha) => interpretarLinha(linha, unidades))
        .filter(Boolean) as Array<{
        payroll_number: string;
        unit_id: string | null;
        setorNaoEncontrado: string;
      }>,
    [lista, unidades],
  );

  const setoresNaoEncontrados = useMemo(
    () =>
      Array.from(
        new Set(
          linhasInterpretadas.map((linha) => linha.setorNaoEncontrado).filter(Boolean),
        ),
      ),
    [linhasInterpretadas],
  );

  const duplicadas = useMemo(() => {
    const vistas = new Set<string>();
    const repetidas = new Set<string>();
    for (const linha of linhasInterpretadas) {
      const chave = linha.payroll_number.toLowerCase();
      if (vistas.has(chave)) repetidas.add(linha.payroll_number);
      vistas.add(chave);
    }
    return Array.from(repetidas);
  }, [linhasInterpretadas]);

  const gerarConvites = async () => {
    setErro("");
    setAviso("");
    if (!selecionada) return;
    if (!linhasInterpretadas.length) {
      setErro("Cole a lista de matrículas primeiro.");
      return;
    }
    if (duplicadas.length) {
      setErro(
        `Matrícula repetida na lista: ${duplicadas.slice(0, 5).join(", ")}. ` +
          "Cada pessoa recebe um convite; repetir gera dois links para a mesma " +
          "pessoa e infla o denominador da adesão.",
      );
      return;
    }
    setSalvando(true);
    try {
      const resposta = await chamar(
        `/api/organizations/${organizationId}/nr1/campaigns/${selecionada.campaign_id}/invitations`,
        organizationId,
        {
          method: "POST",
          body: JSON.stringify({
            subjects: linhasInterpretadas.map((linha) => ({
              payroll_number: linha.payroll_number,
              unit_id: linha.unit_id,
            })),
          }),
        },
      );
      setConvites(resposta.links || []);
      setJaConvidados(resposta.already_invited || []);
      setAviso(
        `${resposta.created} convite(s) emitido(s). Baixe o arquivo agora: ` +
          "os links não são recuperáveis depois que esta tela sair.",
      );
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setSalvando(false);
    }
  };

  /** Troca o link de quem perdeu o dele. Destrutivo por natureza: o link
   *  anterior morre. Por isso e acao separada, com lista propria — nao um
   *  segundo clique no mesmo botao de emitir. */
  const reemitir = async () => {
    setErro("");
    setAviso("");
    if (!selecionada) return;
    const matriculas = listaReemissao
      .split(/\r?\n/)
      // Aceita a linha inteira colada da planilha: só a matrícula importa aqui,
      // porque a reemissão preserva o setor gravado na emissão original.
      .map((linha) => linha.split(/[;,\t]/)[0].trim())
      .filter(Boolean);
    if (!matriculas.length) {
      setErro("Cole as matrículas que precisam de link novo.");
      return;
    }
    setSalvando(true);
    try {
      const resposta = await chamar(
        `/api/organizations/${organizationId}/nr1/campaigns/${selecionada.campaign_id}/invitations/reissue`,
        organizationId,
        { method: "POST", body: JSON.stringify({ payroll_numbers: matriculas }) },
      );
      setConvites(resposta.links || []);
      setJaConvidados([]);
      setSemConvitePendente(resposta.sem_convite_pendente || []);
      setAviso(
        `${resposta.reissued} convite(s) reemitido(s). O link anterior dessas ` +
          "pessoas parou de funcionar agora — baixe o arquivo e distribua.",
      );
    } catch (e) {
      setErro(String((e as Error).message));
    } finally {
      setSalvando(false);
    }
  };

  const baixarCsv = () => {
    const blob = new Blob([montarCsv(convites)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const ancora = document.createElement("a");
    ancora.href = url;
    // O aviso vai no NOME do arquivo, nao dentro dele: dentro quebraria a
    // planilha, e no nome ele sobrevive ao download, ao anexo de e-mail e a
    // pasta compartilhada onde o arquivo costuma ficar esquecido.
    ancora.download = `convites-${(selecionada?.title || "campanha")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")}-APAGAR-APOS-DISTRIBUIR.csv`;
    document.body.appendChild(ancora);
    ancora.click();
    document.body.removeChild(ancora);
    URL.revokeObjectURL(url);
  };

  // Sair da tela com convites na mao e perde-los de vez. O aviso do navegador e
  // grosseiro, e e proporcional: reemitir invalida os ja distribuidos e
  // recomeca a distribuicao do zero.
  useEffect(() => {
    if (!convites.length) return undefined;
    const avisar = (evento: BeforeUnloadEvent) => {
      evento.preventDefault();
      evento.returnValue = "";
    };
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [convites.length]);

  if (!organizationId) {
    return (
      <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
        <p className="text-sm text-slate-300">
          Nenhuma organização ativa nesta sessão. Recarregue a página; se
          persistir, escreva para{" "}
          <a className="underline" href={`mailto:${CONTATO}`}>
            {CONTATO}
          </a>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              NR-1 · Coleta
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">Campanha e convites</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              A campanha define a janela e o denominador; o convite é o link
              único que cada pessoa recebe. O FROID guarda o resumo
              criptográfico do link e um pseudônimo da matrícula — nunca o par
              entre os dois, que é o que impede reconstruir quem respondeu o quê.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/access/empresa"
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Estrutura da empresa
            </Link>
            <Link
              to="/nr1"
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              Painel de conformidade
            </Link>
          </div>
        </header>

        {erro && (
          <p className="mt-4 rounded border border-red-900 bg-red-950 p-3 text-xs font-bold text-red-200">
            {erro}
          </p>
        )}
        {aviso && (
          <p className="mt-4 rounded border border-emerald-900 bg-emerald-950 p-3 text-xs font-bold text-emerald-200">
            {aviso}
          </p>
        )}

        {!estabelecimentos.length && (
          <p className="mt-4 rounded border border-amber-800 bg-amber-950/60 p-3 text-xs leading-5 text-amber-100">
            Nenhum estabelecimento cadastrado. A campanha pode ser criada assim
            mesmo, mas sem unidades os convites não têm setor e nenhum recorte
            existe para publicar.{" "}
            <Link className="font-black underline" to="/access/empresa">
              Cadastrar a estrutura primeiro
            </Link>
            .
          </p>
        )}

        <section className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-sm font-black text-white">1. Criar a campanha</h2>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-xs font-black text-slate-300">
                Instrumento<span className="ml-1 text-red-300">*</span>
              </span>
              <select
                value={instrumentoId}
                onChange={(e) => setInstrumentoId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              >
                {!instrumentos.length && <option value="">Nenhum publicado</option>}
                {instrumentos.map((item) => (
                  <option key={item.instrument_id} value={item.instrument_id}>
                    {item.title} — v{item.version}
                  </option>
                ))}
              </select>
            </label>

            <Campo
              rotulo="Título da campanha"
              valor={titulo}
              onChange={setTitulo}
              obrigatorio
              placeholder="Avaliação de riscos psicossociais 2026"
            />

            <label className="block">
              <span className="text-xs font-black text-slate-300">Abrangência</span>
              <select
                value={unidadeId}
                onChange={(e) => setUnidadeId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              >
                <option value="">Organização inteira</option>
                {estabelecimentos.map((site) => (
                  <option key={site.unit_id} value={site.unit_id}>
                    {site.name} ({site.headcount})
                  </option>
                ))}
              </select>
              <span className="mt-1 block text-[11px] leading-4 text-slate-500">
                Uma campanha por organização soma o efetivo de todos os
                estabelecimentos e é o caminho normal. Campanha por
                estabelecimento só publica se aquele endereço sozinho vencer os
                dois portões.
              </span>
            </label>

            <Campo
              rotulo="Período de referência"
              valor={periodo}
              onChange={setPeriodo}
              placeholder="2026"
              dica="O período do PGR (Programa de Gerenciamento de Riscos) a que esta avaliação se refere."
            />

            <Campo
              rotulo="Efetivo do período de referência"
              valor={efetivo}
              onChange={setEfetivo}
              obrigatorio
              tipo="number"
              dica={
                efetivoTotal
                  ? `A estrutura cadastrada soma ${efetivoTotal} trabalhadores.`
                  : undefined
              }
            />

            <div />

            <Campo
              rotulo="Abertura da coleta"
              valor={abreEm}
              onChange={setAbreEm}
              obrigatorio
              tipo="datetime-local"
            />
            <Campo
              rotulo="Fechamento da coleta"
              valor={fechaEm}
              onChange={setFechaEm}
              obrigatorio
              tipo="datetime-local"
            />
          </div>

          {efetivoNumero > 0 && (
            <div className="mt-4 rounded-lg border border-cyan-900 bg-cyan-950/40 p-4 text-xs leading-5 text-cyan-100">
              {caminho === "aep" ? (
                <>
                  Com {efetivoNumero} trabalhadores nenhuma campanha publica
                  resultado — o piso de anonimato de {PISO_CAMPANHA} respostas é
                  absoluto. O caminho é a{" "}
                  <Link className="font-black underline" to="/nr1/aep">
                    <Sigla nome="AEP" />
                  </Link>
                  , obrigatória de todo modo e sem piso.
                </>
              ) : exigeCenso(efetivoNumero) ? (
                <>
                  Com {efetivoNumero} trabalhadores esta campanha só publica em{" "}
                  <strong>censo</strong>: {exigidoAgora} de {efetivoNumero}{" "}
                  respostas substantivas. Como responder é voluntário, uma única
                  recusa suspende o inventário — a <Sigla nome="AEP" /> deve
                  correr em paralelo.
                </>
              ) : (
                <>
                  Com {efetivoNumero} trabalhadores esta campanha precisa de{" "}
                  <strong>{exigidoAgora} respostas substantivas</strong> para
                  publicar (95% de confiança, margem de 5 pontos). Abaixo disso o
                  resultado descreve quem respondeu, não o trabalho da
                  organização.
                </>
              )}
            </div>
          )}

          {/* Os recortes que NAO vao publicar, ditos antes da coleta.
              Numa empresa com muitos enderecos pequenos quase nenhum recorte
              vence o portao de representatividade, e descobrir isso com o
              painel aberto na frente do cliente e a pior hora possivel. */}
          {efetivoNumero > 0 && estabelecimentos.length > 1 && (
            <div className="mt-3 rounded-lg border border-amber-900 bg-amber-950/40 p-4 text-xs leading-5 text-amber-100">
              <p className="font-black text-amber-200">
                O que cada estabelecimento publica sozinho
              </p>
              <ul className="mt-2 space-y-1">
                {estabelecimentos.map((site) => {
                  const exigido = exigidoNoRecorte(site.headcount);
                  // Exigir mais respostas do que existem pessoas não é "censo",
                  // é impossibilidade — e a tela dizia "só em censo (10 de 9)",
                  // que soa como meta apertada quando na verdade nenhuma adesão
                  // resolve. Acontece sempre que o efetivo é menor que o piso
                  // de anonimato: ali o portão que barra é o do anonimato, e o
                  // remédio não é insistir na coleta, é a AEP.
                  const impossivel = exigido === null || exigido > site.headcount;
                  return (
                    <li key={site.unit_id}>
                      <strong>{site.name}</strong> ({site.headcount}):{" "}
                      {impossivel
                        ? `abaixo do piso de anonimato (${PISO_RECORTE} respostas) — não publica recorte próprio em nenhuma hipótese, por mais adesão que haja.`
                        : exigeCenso(site.headcount)
                          ? `só em censo (${exigido} de ${site.headcount}).`
                          : `${exigido} respostas.`}
                    </li>
                  );
                })}
              </ul>
              <p className="mt-2 text-amber-100/80">
                Recorte que não vence o portão não some do relatório: ele entra
                no mesmo inventário como linha declarada insuficiente, com o
                portão que falhou e o caminho de remédio. Painel vazio seria lido
                como “não há risco aqui”, que é a única conclusão que a ausência
                de dado nunca autoriza.
              </p>
            </div>
          )}

          <div className="mt-4 grid gap-4">
            <label className="block">
              <span className="text-xs font-black text-slate-300">
                Aviso de finalidade aos trabalhadores
              </span>
              <textarea
                value={finalidade}
                onChange={(e) => setFinalidade(e.target.value)}
                rows={3}
                placeholder="Por que a empresa está perguntando, o que será feito com o resultado e o que não será."
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-500"
              />
              <span className="mt-1 block text-[11px] leading-4 text-slate-500">
                Aparece antes da primeira pergunta. A base legal (<Sigla
                  nome="LGPD"
                />{" "}
                art. 7º II e art. 11 II “a”) é acrescentada pelo servidor — não
                precisa ser digitada, e digitá-la errado seria pior.
              </span>
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <Campo
                rotulo="Canal de apoio — nome"
                valor={canalRotulo}
                onChange={setCanalRotulo}
                obrigatorio
                placeholder="Programa de Apoio ao Empregado"
              />
              <Campo
                rotulo="Canal de apoio — como acessar"
                valor={canalDetalhe}
                onChange={setCanalDetalhe}
                obrigatorio
                placeholder="0800 000 0000, 24h, sigiloso"
              />
            </div>
            <p className="text-[11px] leading-4 text-slate-500">
              O banco recusa abrir coleta sem canal de apoio, e essa recusa é
              deliberada: a resposta é anônima, então ninguém consegue procurar
              quem sinalizou sofrimento. O canal é oferecido a todos no fim do
              questionário, igual para quem respondeu o quê.
            </p>
          </div>

          <button
            type="button"
            disabled={salvando}
            onClick={criar}
            className="mt-5 rounded-lg bg-cyan-500 px-5 py-2.5 text-sm font-black text-cyan-950 hover:bg-cyan-400 disabled:opacity-60"
          >
            {salvando ? "Salvando..." : "Criar campanha em rascunho"}
          </button>
        </section>

        <section className="mt-5 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-sm font-black text-white">
            2. Abrir e encerrar a coleta
          </h2>
          <p className="mt-1 text-[11px] leading-4 text-slate-500">
            São dois atos, e o segundo é o que libera o resultado. Enquanto a
            coleta está aberta o painel só mostra adesão: uma coorte que ainda
            cresce pode ser deduzida uma resposta por vez, e nenhum piso protege
            disso.
          </p>
          <div className="mt-3 space-y-2">
            {campanhas.map((campanha) => (
              <div
                key={campanha.campaign_id}
                className={`rounded border p-3 ${
                  selecionada?.campaign_id === campanha.campaign_id
                    ? "border-cyan-600 bg-cyan-950/40"
                    : "border-slate-700 bg-slate-950"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setSelecionada(campanha)}
                    className="text-left text-sm font-black text-slate-100"
                  >
                    {campanha.title}
                  </button>
                  {/* O estado saia cru — DRAFT, OPEN, CLOSED — numa tela que a
                      empresa contratante abre na frente da diretoria dela. */}
                  <span className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
                    {ESTADO_DA_CAMPANHA[campanha.status] || campanha.status}
                  </span>
                  {campanha.status === "draft" && (
                    <button
                      type="button"
                      disabled={salvando}
                      onClick={() => abrir(campanha)}
                      className="rounded bg-emerald-500 px-3 py-1.5 text-[11px] font-black text-emerald-950 hover:bg-emerald-400 disabled:opacity-60"
                    >
                      Abrir coleta
                    </button>
                  )}
                  {/* Encerrar nao tinha botao em lugar nenhum. A rota existe no
                      servidor desde a migration 010 e nenhuma tela a chamava —
                      entao o resultado, que so aparece com a campanha
                      encerrada, era inalcancavel pela interface. */}
                  {campanha.status === "open" &&
                    (confirmandoFecho === campanha.campaign_id ? (
                      <span className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          disabled={salvando}
                          onClick={() => fechar(campanha)}
                          className="rounded bg-red-500 px-3 py-1.5 text-[11px] font-black text-red-950 hover:bg-red-400 disabled:opacity-60"
                        >
                          {salvando ? "Encerrando..." : "Confirmar encerramento"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmandoFecho(null)}
                          className="rounded border border-slate-600 px-3 py-1.5 text-[11px] font-black text-slate-300"
                        >
                          Cancelar
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={salvando}
                        onClick={() => setConfirmandoFecho(campanha.campaign_id)}
                        className="rounded border border-amber-700 px-3 py-1.5 text-[11px] font-black text-amber-200 hover:bg-amber-900/40 disabled:opacity-60"
                      >
                        Encerrar coleta
                      </button>
                    ))}
                </div>
                {confirmandoFecho === campanha.campaign_id && (
                  <p className="mt-2 rounded border border-red-900 bg-red-950/50 p-2 text-[11px] leading-4 text-red-100">
                    <strong>Encerrar não tem volta.</strong> A campanha não
                    reabre, e quem ainda não respondeu perde a chance — os links
                    pendentes param de funcionar. Em troca, é o encerramento que
                    torna o resultado legível e permite gerar o inventário.
                  </p>
                )}
              </div>
            ))}
            {!campanhas.length && (
              <p className="text-xs text-slate-500">Nenhuma campanha ainda.</p>
            )}
          </div>
        </section>

        <section className="mt-5 rounded-lg border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-sm font-black text-white">3. Emitir os convites</h2>
          {!selecionada ? (
            <p className="mt-2 text-xs text-slate-500">Selecione uma campanha acima.</p>
          ) : (
            <>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                Campanha selecionada:{" "}
                <strong className="text-slate-200">{selecionada.title}</strong> (
                {selecionada.status}). Uma matrícula por linha. Para atribuir o
                setor, use <code className="text-cyan-300">matrícula;setor</code> —
                o setor é casado pelo nome ou pelo código interno cadastrado.
              </p>

              <textarea
                value={lista}
                onChange={(e) => setLista(e.target.value)}
                rows={10}
                spellCheck={false}
                placeholder={"10432;Operações\n10433;Comercial\n10434"}
                className="mt-3 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-cyan-500"
              />

              <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-400">
                <span>{linhasInterpretadas.length} matrícula(s) na lista</span>
                <span>·</span>
                <span>
                  {linhasInterpretadas.filter((l) => l.unit_id).length} com setor
                  reconhecido
                </span>
                {setores.length > 0 && (
                  <>
                    <span>·</span>
                    <span>{setores.length} setor(es) cadastrado(s)</span>
                  </>
                )}
              </div>

              {setoresNaoEncontrados.length > 0 && (
                <p className="mt-2 rounded border border-amber-900 bg-amber-950/60 p-2 text-[11px] leading-4 text-amber-100">
                  Setor não encontrado na estrutura:{" "}
                  {setoresNaoEncontrados.slice(0, 8).join(", ")}
                  {setoresNaoEncontrados.length > 8 && " …"}. Essas pessoas entram
                  sem setor — respondem e contam para a campanha, mas não formam
                  recorte próprio.
                </p>
              )}

              {jaConvidados.length > 0 && (
                <p className="mt-2 rounded border border-amber-900 bg-amber-950/60 p-2 text-[11px] leading-4 text-amber-100">
                  <strong>
                    {jaConvidados.length} matrícula(s) já tinham convite nesta
                    campanha e não receberam link novo:
                  </strong>{" "}
                  {jaConvidados.slice(0, 12).join(", ")}
                  {jaConvidados.length > 12 && " …"}. O convite original continua
                  valendo, com o setor que foi atribuído na emissão dele — reemitir
                  invalidaria o link que a pessoa já tem. Para trocar o setor de
                  quem já foi convidado, a saída é uma campanha nova.
                </p>
              )}

              {duplicadas.length > 0 && (
                <p className="mt-2 rounded border border-red-900 bg-red-950/60 p-2 text-[11px] leading-4 text-red-100">
                  Matrícula repetida: {duplicadas.slice(0, 8).join(", ")}
                  {duplicadas.length > 8 && " …"}
                </p>
              )}

              <button
                type="button"
                disabled={salvando || !linhasInterpretadas.length}
                onClick={gerarConvites}
                className="mt-4 rounded-lg bg-amber-500 px-5 py-2.5 text-sm font-black text-amber-950 hover:bg-amber-400 disabled:opacity-50"
              >
                {salvando
                  ? "Emitindo..."
                  : `Emitir ${linhasInterpretadas.length} convite(s)`}
              </button>

              {convites.length > 0 && (
                <div className="mt-5 rounded-lg border border-emerald-800 bg-emerald-950/40 p-4">
                  <p className="text-sm font-black text-emerald-200">
                    {convites.length} link(s) emitido(s) — visíveis uma única vez
                  </p>
                  <p className="mt-2 text-xs leading-5 text-emerald-100">
                    O servidor guardou o resumo criptográfico de cada link, não o
                    link. Saindo desta tela sem baixar o arquivo, a única saída é
                    reemitir — o que invalida os já distribuídos.
                  </p>
                  {/* O unico ponto do sistema em que matricula e link convivem.
                      Nao e descuido: sem esse par ninguem consegue entregar o
                      convite a pessoa certa. Mas ele existe so nesta tela e
                      nesse arquivo, e enquanto o arquivo existir alguem pode
                      abrir cada link e ver qual recusa — descobrindo QUEM
                      respondeu. O controle nao e tecnico, e de guarda. */}
                  <p className="mt-2 rounded border border-amber-800 bg-amber-950/50 p-2 text-xs leading-5 text-amber-100">
                    <strong>Apague o arquivo depois de distribuir.</strong> Ele é
                    o único lugar onde matrícula e link aparecem juntos — o FROID
                    nunca guarda esse par. Enquanto ele existir, quem o tiver
                    consegue descobrir <em>quem</em> já respondeu (não o que
                    respondeu, que ninguém consegue). Distribuiu, apagou.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={baixarCsv}
                      className="rounded bg-emerald-500 px-4 py-2 text-xs font-black text-emerald-950 hover:bg-emerald-400"
                    >
                      Baixar CSV (matrícula ; link)
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void navigator.clipboard?.writeText(montarCsv(convites));
                        setAviso("Lista copiada para a área de transferência.");
                      }}
                      className="rounded border border-emerald-700 px-4 py-2 text-xs font-black text-emerald-200 hover:bg-emerald-900"
                    >
                      Copiar
                    </button>
                  </div>
                  <div className="mt-3 max-h-64 overflow-y-auto rounded border border-emerald-900 bg-slate-950 p-2">
                    <table className="w-full text-left text-[11px]">
                      <thead className="text-emerald-300">
                        <tr>
                          <th className="p-1">Matrícula</th>
                          <th className="p-1">Link</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono text-slate-300">
                        {convites.map((convite) => (
                          <tr key={convite.token} className="border-t border-slate-800">
                            <td className="p-1">{convite.payroll_number}</td>
                            <td className="break-all p-1">
                              {linkDoConvite(convite.token)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Reemissao: acao separada, e nao um segundo clique no botao de
                  emitir. O efeito e destrutivo — o link anterior morre — e
                  precisa de um gesto proprio para nao acontecer por engano no
                  meio da distribuicao normal. */}
              <div className="mt-6 rounded-lg border border-slate-700 bg-slate-950 p-4">
                <p className="text-xs font-black text-slate-200">
                  Alguém perdeu o link?
                </p>
                <p className="mt-1 text-[11px] leading-4 text-slate-400">
                  Cole as matrículas, uma por linha. Cada uma recebe um link
                  novo, e <strong>o link anterior dela para de funcionar</strong>.
                  O setor atribuído na emissão original é mantido. Quem já
                  respondeu não recebe link novo — responder duas vezes contaria
                  a mesma pessoa duas vezes na coorte.
                </p>
                <textarea
                  value={listaReemissao}
                  onChange={(e) => setListaReemissao(e.target.value)}
                  rows={3}
                  placeholder={"1042\n1043"}
                  className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-cyan-500"
                />
                {semConvitePendente.length > 0 && (
                  <p className="mt-2 rounded border border-amber-900 bg-amber-950/60 p-2 text-[11px] leading-4 text-amber-100">
                    Sem convite pendente nesta campanha:{" "}
                    {semConvitePendente.slice(0, 12).join(", ")}
                    {semConvitePendente.length > 12 && " …"}. Não recebem link
                    novo. A tela não diz o motivo de propósito — pode ser que a
                    pessoa já tenha respondido, pode ser que nunca tenha sido
                    convidada, e distinguir os dois entregaria a quem tem esta
                    lista a relação de quem respondeu.
                  </p>
                )}
                <button
                  type="button"
                  disabled={salvando || !listaReemissao.trim()}
                  onClick={reemitir}
                  className="mt-3 rounded-lg border border-amber-700 px-4 py-2 text-xs font-black text-amber-200 hover:bg-amber-900/40 disabled:opacity-50"
                >
                  {salvando ? "Reemitindo..." : "Reemitir convite"}
                </button>
              </div>
            </>
          )}
        </section>

        <GlossarioDeSiglas termos={["NR-1", "PGR", "AEP", "LGPD"]} />
      </main>
    </div>
  );
};

export default Nr1Campaign;
