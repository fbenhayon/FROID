import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FroidUser } from "../App";
import { apiUrl } from "../lib/api";
import {
  TEMAS,
  VERBETES,
  type TemaExplica,
  type VerbeteExplica,
} from "../lib/nr1-explica-conteudo";
import { GlossarioDeSiglas } from "../lib/siglas";

/**
 * FROID Explica NR-1 — a tela que responde a pergunta do cliente.
 *
 * Nasce de uma observacao do proprio operador durante o teste ponta a ponta:
 * se quem construiu o produto tropeça na diferenca entre os dois portoes,
 * entre suprimir e declarar, entre censo e amostra, o cliente vai tropecar
 * mais — e vai tropecar na frente da diretoria dele.
 *
 * Duas decisoes de desenho que nao sao estilo:
 *
 * 1. **A resposta e dado, nao geracao.** Esta tela e aberta no meio de uma
 *    reuniao em que se decide um contrato, as vezes na frente de um auditor.
 *    Ali "quase sempre responde certo" nao e propriedade aceitavel. Resposta
 *    gerada depende de indexacao, chave de API, latencia e de o modelo nao
 *    inventar um subitem da norma. Cada uma dessas coisas e um jeito de a tela
 *    falhar no pior momento. Aqui a resposta e a mesma sempre, foi revisada, e
 *    funciona sem rede.
 *
 * 2. **A pergunta aberta usa rota propria, nunca a clinica.**
 *    `/api/froid-explica/query` exige aprovacao profissional e injeta resumo
 *    da carteira de pacientes em pergunta comparativa. Reaproveita-la aqui
 *    levaria dado clinico para o lado errado da fronteira por um caminho que
 *    ninguem estaria olhando. A rota do NR-1 consulta uma collection separada,
 *    sem material clinico dentro.
 *
 * As duas camadas convivem: a busca curada responde sempre, inclusive sem
 * rede; a pergunta aberta cobre o que ninguem previu, e quando ela nao esta
 * disponivel a tela diz isso e continua util.
 */

type Props = { user: FroidUser | null };

/** Quebra de paragrafo na resposta gerada, construida por escape: classe
 *  literal com quebra de linha dentro nao sobrevive a edicao. */
const PARAGRAFOS = new RegExp("\n{2,}");

const COMBINANTES = new RegExp("[\u0300-\u036f]", "g");

export function normalizar(texto: string): string {
  // A classe de sinais combinantes e construida a partir de string com
  // escape, e nao escrita como classe literal: literal, ela fica invisivel
  // no editor e nao sobrevive a uma conversao de codificacao — que e risco
  // real neste repositorio.
  return texto.normalize("NFD").replace(COMBINANTES, "").toLowerCase();
}

export function combina(verbete: VerbeteExplica, termo: string): boolean {
  if (!termo) return true;
  const alvo = normalizar(
    [
      verbete.pergunta,
      verbete.resposta.join(" "),
      verbete.referencia || "",
      (verbete.chaves || []).join(" "),
    ].join(" "),
  );
  // Todas as palavras precisam aparecer, em qualquer ordem: "filial relatorio"
  // acha a pergunta sobre recorte por endereco sem que ninguem tenha escrito
  // essa frase.
  return normalizar(termo)
    .split(/\s+/)
    .filter(Boolean)
    .every((palavra) => alvo.includes(palavra));
}

const Cartao: React.FC<{
  verbete: VerbeteExplica;
  aberto: boolean;
  onToggle: () => void;
}> = ({ verbete, aberto, onToggle }) => (
  <article className="rounded-lg border border-slate-800 bg-slate-900">
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
    >
      <span className="text-sm font-black text-slate-100">{verbete.pergunta}</span>
      <span className="mt-0.5 text-xs font-black text-cyan-300">
        {aberto ? "−" : "+"}
      </span>
    </button>
    {aberto && (
      <div className="border-t border-slate-800 px-4 py-3">
        {verbete.resposta.map((paragrafo, indice) => (
          <p
            key={indice}
            className="mt-2 text-xs leading-6 text-slate-300 first:mt-0"
          >
            {paragrafo}
          </p>
        ))}
        {verbete.referencia && (
          <p className="mt-3 border-t border-slate-800 pt-2 text-[11px] leading-4 text-slate-500">
            <span className="font-black text-slate-400">Fonte:</span>{" "}
            {verbete.referencia}
          </p>
        )}
        <button
          type="button"
          onClick={() => {
            const texto = [
              verbete.pergunta,
              "",
              ...verbete.resposta,
              verbete.referencia ? `\nFonte: ${verbete.referencia}` : "",
            ]
              .join("\n")
              .trim();
            void navigator.clipboard?.writeText(texto);
          }}
          className="mt-3 rounded border border-slate-700 px-3 py-1 text-[11px] font-black text-slate-300 hover:bg-slate-800"
        >
          Copiar resposta
        </button>
      </div>
    )}
  </article>
);

type RespostaAberta = {
  disponivel: boolean;
  motivo?: string;
  resposta: string;
  citacoes: string[];
  motor?: string;
};

export const Nr1Explica: React.FC<Props> = ({ user }) => {
  const [busca, setBusca] = useState("");
  const [tema, setTema] = useState<TemaExplica | "todos">("todos");
  const [abertos, setAbertos] = useState<Record<string, boolean>>({});
  const [pergunta, setPergunta] = useState("");
  const [pensando, setPensando] = useState(false);
  const [aberta, setAberta] = useState<RespostaAberta | null>(null);
  const [erroAberta, setErroAberta] = useState("");

  const organizationId = String(user?.active_organization_id || "");

  /** A pergunta que a busca curada nao cobriu.
   *
   *  Falha aqui nunca derruba a tela: o conteudo curado abaixo continua
   *  respondendo, e a mensagem diz isso em vez de mostrar um erro tecnico a
   *  quem esta no meio de uma reuniao. */
  const perguntar = async () => {
    const texto = pergunta.trim();
    if (!texto || !organizationId) return;
    setPensando(true);
    setErroAberta("");
    setAberta(null);
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
      setAberta(corpo as RespostaAberta);
    } catch (e) {
      setErroAberta(String((e as Error).message));
    } finally {
      setPensando(false);
    }
  };

  const encontrados = useMemo(
    () =>
      VERBETES.filter(
        (verbete) =>
          (tema === "todos" || verbete.tema === tema) && combina(verbete, busca),
      ),
    [busca, tema],
  );

  const porTema = useMemo(() => {
    const mapa = new Map<TemaExplica, VerbeteExplica[]>();
    for (const verbete of encontrados) {
      const lista = mapa.get(verbete.tema) || [];
      lista.push(verbete);
      mapa.set(verbete.tema, lista);
    }
    return mapa;
  }, [encontrados]);

  const alternar = (id: string) =>
    setAbertos((atual) => ({ ...atual, [id]: !atual[id] }));

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100">
      <main className="mx-auto max-w-4xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
              FROID Explica · NR-1
            </p>
            <h1 className="mt-2 text-2xl font-black text-white">
              Perguntas sobre a norma e sobre a avaliação
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              {VERBETES.length} respostas, com a fonte normativa quando existe.
              Escritas para serem lidas em voz alta na frente de quem perguntou:
              cada uma pode ser copiada inteira.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/nr1"
              className="rounded border border-cyan-700 bg-cyan-950 px-4 py-2 text-xs font-black text-cyan-100 hover:bg-cyan-900"
            >
              Painel de conformidade
            </Link>
            <Link
              to="/nr1/campanha"
              className="rounded border border-slate-700 px-4 py-2 text-xs font-black text-slate-200 hover:bg-slate-900"
            >
              Campanha e convites
            </Link>
          </div>
        </header>

        <div className="mt-6">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar — por exemplo: filial, multa, anonimato, quantas respostas"
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100 outline-none placeholder:italic placeholder:text-slate-600 focus:border-cyan-500"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setTema("todos")}
              className={`rounded-full px-3 py-1 text-[11px] font-black ${
                tema === "todos"
                  ? "bg-cyan-500 text-cyan-950"
                  : "border border-slate-700 text-slate-300 hover:bg-slate-900"
              }`}
            >
              Tudo
            </button>
            {TEMAS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTema(item.id)}
                title={item.resumo}
                className={`rounded-full px-3 py-1 text-[11px] font-black ${
                  tema === item.id
                    ? "bg-cyan-500 text-cyan-950"
                    : "border border-slate-700 text-slate-300 hover:bg-slate-900"
                }`}
              >
                {item.titulo}
              </button>
            ))}
          </div>
        </div>

        {/* Pergunta aberta. Fica DEPOIS da busca curada de proposito: o
            caminho mais confiavel e o primeiro que se oferece, e este e o
            recurso para quando aquele nao cobriu. */}
        <section className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-4">
          <p className="text-xs font-black text-slate-200">
            Não achou? Pergunte com suas palavras.
          </p>
          <p className="mt-1 text-[11px] leading-4 text-slate-500">
            A resposta é montada a partir do texto da norma, das publicações
            oficiais do Ministério do Trabalho e Emprego e da documentação do
            FROID — e cita quais delas usou. Nenhum dado de pessoa alguma entra
            nesta consulta.
          </p>
          <textarea
            value={pergunta}
            onChange={(e) => setPergunta(e.target.value)}
            rows={2}
            placeholder="Exemplo: a empresa precisa reavaliar depois de implementar uma medida?"
            className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none placeholder:italic placeholder:text-slate-600 focus:border-cyan-500"
          />
          <button
            type="button"
            disabled={pensando || !pergunta.trim()}
            onClick={perguntar}
            className="mt-2 rounded-lg bg-cyan-500 px-4 py-2 text-xs font-black text-cyan-950 hover:bg-cyan-400 disabled:opacity-50"
          >
            {pensando ? "Consultando o acervo..." : "Perguntar"}
          </button>

          {erroAberta && (
            <p className="mt-3 rounded border border-amber-900 bg-amber-950/50 p-3 text-[11px] leading-4 text-amber-100">
              Não foi possível consultar agora ({erroAberta}). As respostas
              revisadas abaixo continuam valendo e não dependem desta consulta.
            </p>
          )}

          {aberta && !aberta.disponivel && (
            <p className="mt-3 rounded border border-amber-900 bg-amber-950/50 p-3 text-[11px] leading-4 text-amber-100">
              {aberta.motivo === "acervo_nao_indexado"
                ? "O acervo ainda não foi indexado neste servidor. As respostas revisadas abaixo continuam valendo."
                : "A consulta aberta está indisponível no momento. As respostas revisadas abaixo continuam valendo."}
            </p>
          )}

          {aberta && aberta.disponivel && (
            <div className="mt-3 rounded-lg border border-cyan-900 bg-cyan-950/30 p-4">
              {aberta.resposta.split(PARAGRAFOS).map((paragrafo, indice) => (
                <p
                  key={indice}
                  className="mt-2 whitespace-pre-line text-xs leading-6 text-slate-200 first:mt-0"
                >
                  {paragrafo}
                </p>
              ))}
              {aberta.citacoes.length > 0 && (
                <p className="mt-3 border-t border-cyan-900 pt-2 text-[11px] leading-4 text-slate-400">
                  <span className="font-black text-slate-300">Consultado:</span>{" "}
                  {aberta.citacoes.join(" · ")}
                </p>
              )}
              {/* O limite dito junto da resposta, e nao so no rodape: quem le
                  uma resposta gerada precisa saber que ela e gerada. */}
              <p className="mt-2 text-[11px] leading-4 text-slate-500">
                Resposta montada a partir das fontes acima. Confira o trecho
                citado antes de usá-la em documento oficial.
              </p>
            </div>
          )}
        </section>

        {!encontrados.length && (
          <div className="mt-6 rounded-lg border border-amber-900 bg-amber-950/40 p-4 text-xs leading-5 text-amber-100">
            <p className="font-black text-amber-200">
              Nada encontrado para “{busca}”.
            </p>
            <p className="mt-2">
              Esta tela responde o que já foi perguntado antes, e não toda
              pergunta possível — é assim de propósito, para que a resposta seja
              sempre a mesma e sempre conferida. Se a sua pergunta não está
              aqui, ela é útil: escreva para{" "}
              <a className="font-black underline" href="mailto:froid@froid.com.br">
                froid@froid.com.br
              </a>{" "}
              e ela entra na próxima revisão.
            </p>
          </div>
        )}

        <div className="mt-6 space-y-6">
          {TEMAS.filter((item) => (porTema.get(item.id) || []).length).map(
            (item) => (
              <section key={item.id}>
                <h2 className="text-xs font-black uppercase tracking-wide text-cyan-300">
                  {item.titulo}
                </h2>
                <p className="mt-1 text-[11px] leading-4 text-slate-500">
                  {item.resumo}
                </p>
                <div className="mt-3 space-y-2">
                  {(porTema.get(item.id) || []).map((verbete) => (
                    <Cartao
                      key={verbete.id}
                      verbete={verbete}
                      aberto={Boolean(abertos[verbete.id])}
                      onToggle={() => alternar(verbete.id)}
                    />
                  ))}
                </div>
              </section>
            ),
          )}
        </div>

        {/* O limite dito na propria tela. Um material de conformidade que se
            apresenta como parecer juridico e um passivo, nao um diferencial. */}
        <p className="mt-8 rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-[11px] leading-5 text-slate-400">
          Este material é apresentado para contextualização, com base no texto da
          norma e nas publicações oficiais do Ministério do Trabalho e Emprego.
          <strong className="text-slate-300">
            {" "}
            Não constitui parecer jurídico
          </strong>
          : a análise do caso concreto cabe à assessoria jurídica da sua
          organização. Em caso de divergência prevalece o texto publicado no
          Diário Oficial da União.
          {user?.email ? "" : ""}
        </p>

        <GlossarioDeSiglas
          termos={[
            "NR-1",
            "NR-17",
            "NR-28",
            "PGR",
            "GRO",
            "AEP",
            "AET",
            "PCMSO",
            "CIPA",
            "SESMT",
            "SST",
            "MTE",
            "MPT",
            "LGPD",
            "eSocial",
            "TAC",
            "CLT",
          ]}
        />
      </main>
    </div>
  );
};

export default Nr1Explica;
