import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { FroidUser } from "../App";
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
 * 2. **Nenhuma chamada ao servidor.** Consequencia da primeira, e tambem
 *    garantia de fronteira: uma tela do lado do empregador que consultasse o
 *    acervo do FROID Explica clinico atravessaria exatamente a separacao que o
 *    produto existe para sustentar. O acervo clinico e do profissional de
 *    saude; este conteudo e do empregador. Eles nao se encontram.
 *
 * A camada generativa continua fazendo sentido para a pergunta que ninguem
 * previu. Quando existir, sera endpoint proprio, isolado, e esta tela sera o
 * conteudo canonico dela.
 */

type Props = { user: FroidUser | null };

/** Normaliza para busca: sem acento, sem maiuscula.
 *
 *  Quem digita com pressa nao acentua. Sem isto, procurar "inventario" nao
 *  acha "inventário" — e a tela parece nao saber o que ela sabe. */
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

export const Nr1Explica: React.FC<Props> = ({ user }) => {
  const [busca, setBusca] = useState("");
  const [tema, setTema] = useState<TemaExplica | "todos">("todos");
  const [abertos, setAbertos] = useState<Record<string, boolean>>({});

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
