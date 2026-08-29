// O FROID Explica NR-1 como coluna fixa, e não como tela para onde se vai.
//
// O painel clínico do profissional já resolveu isto: a inteligência mora numa
// segunda coluna, ao lado do trabalho, e não atrás de um botão. A diferença
// importa porque a dúvida sobre a norma aparece com a tela aberta — no meio do
// cadastro de um setor, olhando uma linha que não publicou — e obrigar a pessoa
// a sair da tela para perguntar é o mesmo que pedir que ela desista.
//
// Duas camadas, como no resto do módulo:
//
//   1. As 57 respostas revisadas. Selecionar uma devolve o texto conferido na
//      hora, SEM REDE. É a camada que funciona na frente de um auditor.
//   2. A consulta aberta ao acervo, para o que ninguém previu. Pode falhar, e
//      quando falha a camada 1 continua inteira.
//
// Sobre cláusula contratual o painel aponta para o documento e não o
// parafraseia: o contrato é versionado e tem impressão digital, e uma paráfrase
// criaria uma segunda narrativa da mesma obrigação, sem versão e sem digital.

import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiUrl } from "../../lib/api";
import {
  TEMAS,
  VERBETES,
  type VerbeteExplica,
} from "../../lib/nr1-explica-conteudo";
import {
  acrescentaAoHistorico,
  chaveHistorico,
  chavePrompts,
  grava,
  jaSalvo,
  ler,
  novoId,
  removePrompt,
  salvaPrompt,
  tituloDoPrompt,
  type ItemHistorico,
  type PromptSalvo,
  type RespostaAberta,
} from "../../lib/nr1-explica-sessao";

const PARAGRAFOS = /\n{2,}/;

/** Os documentos desta contratação, citados por nome e alcançáveis daqui.
 *
 *  Ficam no rodapé do painel de propósito: a pergunta contratual é comum, e a
 *  resposta honesta a quase toda ela é "está escrito aqui, veja o texto". */
const DOCUMENTOS = [
  { rotulo: "Termos de Uso — FROID NR-1", para: "/termos-nr1" },
  {
    rotulo: "Contrato de Prestação de Serviço — FROID NR-1, Riscos Psicossociais",
    para: "/contrato-nr1",
  },
  { rotulo: "Política de Privacidade", para: "/privacidade" },
  { rotulo: "Comprovante de aceite desta contratação", para: "/nr1/comprovante" },
];

type Props = {
  organizationId: string;
  /** O verbete que a tela hospedeira torna mais provável. O painel abre com ele
   *  selecionado — quem está no inventário tem uma dúvida diferente de quem
   *  está cadastrando setor. */
  verbeteSugerido?: string;
  /** Rótulo da tela, só para o cabeçalho do painel. */
  contexto?: string;
};

export const Nr1ExplicaPainel: React.FC<Props> = ({
  organizationId,
  verbeteSugerido = "",
  contexto,
}) => {
  const [selecionado, setSelecionado] = useState(verbeteSugerido);
  const [pergunta, setPergunta] = useState("");
  const [pensando, setPensando] = useState(false);
  const [erro, setErro] = useState("");
  const [verMeusPrompts, setVerMeusPrompts] = useState(false);

  const [historico, setHistorico] = useState<ItemHistorico[]>(() =>
    ler<ItemHistorico[]>(
      globalThis.sessionStorage,
      chaveHistorico(organizationId),
      [],
    ),
  );
  const [prompts, setPrompts] = useState<PromptSalvo[]>(() =>
    ler<PromptSalvo[]>(globalThis.localStorage, chavePrompts(organizationId), []),
  );

  useEffect(() => {
    grava(globalThis.sessionStorage, chaveHistorico(organizationId), historico);
  }, [historico, organizationId]);

  useEffect(() => {
    grava(globalThis.localStorage, chavePrompts(organizationId), prompts);
  }, [prompts, organizationId]);

  /** Os verbetes agrupados por tema, para o seletor. */
  const porTema = useMemo(
    () =>
      TEMAS.map((tema) => ({
        tema,
        verbetes: VERBETES.filter((v) => v.tema === tema.id),
      })).filter((grupo) => grupo.verbetes.length > 0),
    [],
  );

  const verbete: VerbeteExplica | undefined = useMemo(
    () => VERBETES.find((v) => v.id === selecionado),
    [selecionado],
  );

  const registrar = (item: ItemHistorico) =>
    setHistorico((atual) => acrescentaAoHistorico(atual, item));

  /** A camada revisada. Não vai à rede, e por isso não falha. */
  const responderComVerbete = (id: string) => {
    setSelecionado(id);
    const achado = VERBETES.find((v) => v.id === id);
    if (!achado) return;
    registrar({
      id: novoId(),
      pergunta: achado.pergunta,
      quando: new Date().toISOString(),
      resposta: {
        disponivel: true,
        resposta: achado.resposta.join("\n\n"),
        citacoes: achado.referencia ? [achado.referencia] : [],
        motor: "revisada",
      },
    });
  };

  const perguntar = async () => {
    const texto = pergunta.trim();
    if (!texto || !organizationId) return;
    setPensando(true);
    setErro("");
    try {
      const resposta = await fetch(
        apiUrl(`/api/organizations/${organizationId}/nr1/explica`),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${window.localStorage.getItem("froid_token") || ""}`,
            "X-FROID-Organization-ID": organizationId,
          },
          body: JSON.stringify({ pergunta: texto }),
        },
      );
      const corpo = await resposta.json();
      if (!resposta.ok) {
        throw new Error(corpo?.detail || "não foi possível consultar agora");
      }
      registrar({
        id: novoId(),
        pergunta: texto,
        quando: new Date().toISOString(),
        resposta: corpo as RespostaAberta,
      });
      setPergunta("");
    } catch (e) {
      const motivo = String((e as Error).message);
      setErro(motivo);
      // A pergunta que falhou entra assim mesmo. Perdê-la é o defeito.
      registrar({
        id: novoId(),
        pergunta: texto,
        quando: new Date().toISOString(),
        resposta: null,
        erro: motivo,
      });
    } finally {
      setPensando(false);
    }
  };

  const salvarPromptAtual = () => {
    const texto = pergunta.trim();
    if (!texto) return;
    setPrompts((atual) =>
      salvaPrompt(atual, { id: novoId(), titulo: tituloDoPrompt(texto), texto }),
    );
  };

  return (
    <aside className="froid-nao-imprime rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:sticky xl:top-4 xl:self-start">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-black text-slate-100">FROID Explica NR-1</p>
          <p className="mt-0.5 text-[11px] leading-4 text-slate-500">
            {contexto
              ? `A norma, o contrato e a operação — a partir de ${contexto}.`
              : "A norma, o contrato e a operação, com a fonte citada."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setVerMeusPrompts((v) => !v)}
          className={`shrink-0 rounded-lg px-3 py-1.5 text-[11px] font-black ${
            verMeusPrompts
              ? "bg-cyan-500 text-cyan-950"
              : "border border-slate-700 text-slate-300 hover:bg-slate-800"
          }`}
        >
          Meus prompts
        </button>
      </div>

      {verMeusPrompts && (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
          {prompts.length === 0 ? (
            <p className="text-[11px] leading-4 text-slate-500">
              Nenhum prompt salvo ainda. Escreva uma pergunta abaixo e use
              “Salvar” — ela fica guardada para o próximo ciclo.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {prompts.map((salvo) => (
                <span
                  key={salvo.id}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900 py-1 pl-3 pr-1 text-[11px] text-slate-300"
                >
                  <button
                    type="button"
                    onClick={() => setPergunta(salvo.texto)}
                    title={salvo.texto}
                    className="font-black hover:text-cyan-300"
                  >
                    {salvo.titulo}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPrompts((atual) => removePrompt(atual, salvo.id))
                    }
                    aria-label={`Remover ${salvo.titulo}`}
                    title="Remover de meus prompts"
                    className="rounded-full px-2 text-slate-500 hover:bg-slate-800 hover:text-slate-200"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* A área de resposta. Começa com o histórico da sessão, mais recente em
          cima — o painel clínico faz igual, e é o que permite comparar duas
          respostas sem perder a primeira. */}
      <div className="mt-3 max-h-[26rem] min-h-[9rem] overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-3">
        {historico.length === 0 ? (
          <p className="py-6 text-center text-[11px] leading-5 text-slate-600">
            FROID Explica NR-1 pronto.
            <br />
            Escolha uma pergunta revisada ou escreva a sua.
          </p>
        ) : (
          <div className="space-y-3">
            {historico.map((item) => (
              <article
                key={item.id}
                className="rounded border border-slate-800 bg-slate-900/60 p-2.5"
              >
                <p className="text-[11px] font-black leading-4 text-slate-200">
                  {item.pergunta}
                </p>

                {item.erro && (
                  <p className="mt-2 rounded border border-amber-900 bg-amber-950/50 p-2 text-[11px] leading-4 text-amber-100">
                    Não foi possível consultar ({item.erro}). As respostas
                    revisadas continuam valendo.
                  </p>
                )}

                {item.resposta && !item.resposta.disponivel && (
                  <p className="mt-2 rounded border border-amber-900 bg-amber-950/50 p-2 text-[11px] leading-4 text-amber-100">
                    {item.resposta.motivo === "acervo_nao_indexado"
                      ? "O acervo ainda não foi indexado neste servidor. As respostas revisadas continuam valendo."
                      : "A consulta aberta está indisponível. As respostas revisadas continuam valendo."}
                  </p>
                )}

                {item.resposta?.disponivel && (
                  <>
                    {item.resposta.resposta
                      .split(PARAGRAFOS)
                      .map((paragrafo, indice) => (
                        <p
                          key={indice}
                          className="mt-2 whitespace-pre-line text-[11px] leading-5 text-slate-300"
                        >
                          {paragrafo}
                        </p>
                      ))}
                    {item.resposta.citacoes.length > 0 && (
                      <p className="mt-2 border-t border-slate-800 pt-1.5 text-[10px] leading-4 text-slate-500">
                        <span className="font-black text-slate-400">Fonte:</span>{" "}
                        {item.resposta.citacoes.join(" · ")}
                      </p>
                    )}
                    {/* Só a resposta gerada leva a ressalva. A revisada foi
                        conferida uma vez e não se remonta a cada consulta. */}
                    {item.resposta.motor !== "revisada" && (
                      <p className="mt-1 text-[10px] leading-4 text-slate-600">
                        Resposta montada a partir das fontes acima. Confira o
                        trecho citado antes de usá-la em documento oficial.
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        const texto = [
                          item.pergunta,
                          "",
                          item.resposta?.resposta || "",
                          item.resposta?.citacoes.length
                            ? `\nFonte: ${item.resposta.citacoes.join(" · ")}`
                            : "",
                        ]
                          .join("\n")
                          .trim();
                        void navigator.clipboard?.writeText(texto);
                      }}
                      className="mt-2 rounded border border-slate-700 px-2 py-0.5 text-[10px] font-black text-slate-400 hover:bg-slate-800"
                    >
                      Copiar
                    </button>
                  </>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      {historico.length > 0 && (
        <div className="mt-2 text-right">
          <button
            type="button"
            onClick={() => setHistorico([])}
            title="Apaga o histórico desta sessão. Os prompts salvos permanecem."
            className="text-[10px] font-black text-slate-500 hover:text-slate-300"
          >
            Limpar histórico
          </button>
        </div>
      )}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wide text-slate-500">
            Prompts FROID Explica
          </span>
          <select
            value={selecionado}
            onChange={(e) => responderComVerbete(e.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-[11px] text-slate-200"
          >
            <option value="">Selecione um prompt…</option>
            {porTema.map((grupo) => (
              <optgroup key={grupo.tema.id} label={grupo.tema.titulo}>
                {grupo.verbetes.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.pergunta}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-[10px] font-black uppercase tracking-wide text-slate-500">
            Meus prompts
          </span>
          <select
            value=""
            onChange={(e) => e.target.value && setPergunta(e.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-[11px] text-slate-200"
          >
            <option value="">
              {prompts.length
                ? "Selecione um prompt salvo…"
                : "Nenhum prompt pessoal ainda"}
            </option>
            {prompts.map((salvo) => (
              <option key={salvo.id} value={salvo.texto}>
                {salvo.titulo}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* O verbete contratual aponta para o documento em vez de reescrevê-lo. */}
      {verbete?.destino && (
        <Link
          to={verbete.destino.para}
          className="mt-2 inline-block rounded border border-cyan-700 bg-cyan-950 px-3 py-1 text-[11px] font-black text-cyan-100 hover:bg-cyan-900"
        >
          {verbete.destino.rotulo} →
        </Link>
      )}

      <textarea
        value={pergunta}
        onChange={(e) => setPergunta(e.target.value)}
        rows={3}
        placeholder="Pergunta livre ao FROID Explica NR-1…"
        className="mt-2 max-h-40 w-full resize-y overflow-y-auto rounded border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] leading-5 text-slate-100 outline-none placeholder:italic placeholder:text-slate-600 focus:border-cyan-500"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={pensando || !pergunta.trim()}
          onClick={perguntar}
          className="rounded-lg bg-cyan-500 px-4 py-1.5 text-[11px] font-black text-cyan-950 hover:bg-cyan-400 disabled:opacity-50"
        >
          {pensando ? "Consultando…" : "Enviar"}
        </button>
        <button
          type="button"
          disabled={!pergunta.trim() || jaSalvo(prompts, pergunta)}
          onClick={salvarPromptAtual}
          title="Guarda esta formulação para reutilizar no próximo ciclo."
          className="rounded-lg border border-slate-700 px-3 py-1.5 text-[11px] font-black text-slate-300 hover:bg-slate-800 disabled:opacity-40"
        >
          {jaSalvo(prompts, pergunta) ? "Salvo" : "Salvar"}
        </button>
      </div>

      {erro && (
        <p className="mt-2 rounded border border-amber-900 bg-amber-950/50 p-2 text-[10px] leading-4 text-amber-100">
          Consulta aberta indisponível. Os prompts revisados acima continuam
          funcionando sem rede.
        </p>
      )}

      <div className="mt-3 border-t border-slate-800 pt-2">
        <p className="text-[10px] font-black uppercase tracking-wide text-slate-500">
          Documentos desta contratação
        </p>
        <ul className="mt-1.5 space-y-1">
          {DOCUMENTOS.map((documento) => (
            <li key={documento.para}>
              <Link
                to={documento.para}
                className="text-[11px] leading-4 text-cyan-300 hover:underline"
              >
                {documento.rotulo}
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[10px] leading-4 text-slate-600">
          Sobre cláusula, o texto que vale é o do documento versionado. O painel
          diz de que trata a seção e leva até ela — nunca a parafraseia.
        </p>
      </div>
    </aside>
  );
};
