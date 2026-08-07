import React from "react";
import { Link, useNavigate } from "react-router-dom";

import type { FroidUser } from "../App";
import type { FroidProduct } from "../lib/product-choice";

/**
 * Escolha do produto, logo depois da autenticação.
 *
 * Antes desta tela o Google devolvia a pessoa direto para a ficha cadastral
 * clínica, qualquer que fosse a intenção dela. Um empregador que veio contratar
 * a avaliação NR-1 caía num formulário que pede conselho profissional e plano
 * de sessões — e concluía, com razão, que o produto não era para ele.
 *
 * Os dois produtos não são variações de um mesmo cadastro: um trata dado
 * clínico de paciente, o outro avalia condições de trabalho de forma anônima e
 * jamais entrega dado individual ao empregador. Misturar os dois num único
 * fluxo é o que produz a confusão que a fronteira do produto existe para
 * impedir.
 */

type Props = {
  user: FroidUser | null;
  /** A escolha vigente. Vive no App, não aqui: é ela que decide qual rota vale,
   *  e estado local desta tela não faria as rotas recalcularem. */
  choice: FroidProduct | null;
  onChoose: (product: FroidProduct) => void;
  onReset: () => void;
  onLogout?: () => void;
};

const CONTATO_EMPRESAS = "froid@froid.com.br";

export const ProductChoice: React.FC<Props> = ({
  user,
  choice,
  onChoose,
  onReset,
  onLogout,
}) => {
  const navigate = useNavigate();

  const escolher = (produto: FroidProduct) => {
    onChoose(produto);
    navigate(produto === "clinical" ? "/access/register" : "/access/empresa", {
      replace: true,
    });
  };

  const primeiroNome = (user?.name || user?.email || "").split(/[\s@]/)[0];

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-700 bg-slate-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
          <Link to="/" className="text-sm font-black tracking-[0.35em] text-cyan-700">
            FROID
          </Link>
          {onLogout && (
            <button
              type="button"
              onClick={onLogout}
              className="rounded-md bg-slate-950 px-3 py-2 text-xs font-black text-white"
            >
              Sair
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-10">
        <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-700">
          Passo 1 de 2
        </p>
        <h1 className="mt-2 text-3xl font-black">
          {primeiroNome ? `Bem-vindo, ${primeiroNome}. ` : ""}O que você veio contratar?
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
          O FROID tem dois produtos distintos, com cadastros diferentes porque as
          necessidades são diferentes. Escolha abaixo e o cadastro seguinte já vem
          com os campos certos.
        </p>

        {choice !== "nr1" && (
          <div className="mt-8 grid gap-5 md:grid-cols-2">
            <section className="flex flex-col rounded-xl border border-slate-700 bg-slate-950 p-6">
              <span className="text-[11px] font-black uppercase tracking-widest text-cyan-300">
                Para quem atende pacientes
              </span>
              <h2 className="mt-2 text-xl font-black">Sessões clínicas</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Análise multimodal durante a sessão, métricas de fala e face,
                relatórios e FROID Explica. Você compra créditos por sessão.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                <li>• Profissional autônomo ou clínica com equipe</li>
                <li>• Exige registro em conselho (CRP, CRM)</li>
                <li>• Trata dado clínico de paciente, com consentimento</li>
              </ul>
              <button
                type="button"
                onClick={() => escolher("clinical")}
                className="mt-6 rounded-lg bg-cyan-600 px-4 py-3 text-sm font-black text-white hover:bg-cyan-500"
              >
                Quero contratar sessões
              </button>
            </section>

            <section className="flex flex-col rounded-xl border border-amber-800 bg-amber-950/30 p-6">
              <span className="text-[11px] font-black uppercase tracking-widest text-amber-300">
                Para empregadores
              </span>
              <h2 className="mt-2 text-xl font-black">Plano NR-1 empresarial</h2>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Avaliação de riscos psicossociais conforme a Portaria MTE nº
                1.419/2024. Campanha anônima, resultado agregado por setor e os
                documentos que a norma exige.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-slate-300">
                <li>• Cadastro da empresa: unidades, setores e efetivo</li>
                <li>• Não avalia indivíduos e não produz diagnóstico</li>
                <li>• O empregador nunca recebe resposta individual</li>
              </ul>
              <button
                type="button"
                onClick={() => escolher("nr1")}
                className="mt-6 rounded-lg bg-amber-500 px-4 py-3 text-sm font-black text-amber-950 hover:bg-amber-400"
              >
                Quero o plano NR-1
              </button>
            </section>
          </div>
        )}

        {choice === "nr1" && (
          <section className="mt-8 rounded-xl border border-amber-800 bg-amber-950/30 p-6">
            <span className="text-[11px] font-black uppercase tracking-widest text-amber-300">
              Plano NR-1 empresarial
            </span>
            <h2 className="mt-2 text-xl font-black">
              O cadastro da empresa é conduzido pela nossa equipe
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              O cadastro NR-1 não é um formulário que se preenche sozinho: antes
              de abrir qualquer campanha é preciso definir as unidades e setores,
              o <strong>canal de apoio ao trabalhador</strong> e os critérios de
              gradação alinhados ao PGR que a sua empresa já usa. Sem canal de
              apoio informado o sistema recusa abrir a campanha — perguntar a
              alguém como ele está sem ter para onde encaminhá-lo é pior do que
              não perguntar.
            </p>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Registramos a sua escolha. Escreva para{" "}
              <a className="font-black text-amber-300 underline" href={`mailto:${CONTATO_EMPRESAS}`}>
                {CONTATO_EMPRESAS}
              </a>{" "}
              e conduzimos a configuração com você.
            </p>

            <div className="mt-5 rounded-lg border border-amber-900 bg-amber-950/50 p-4">
              <p className="text-sm font-black text-amber-200">
                Antes da reunião, vale checar uma coisa
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Abaixo de cerca de 75 trabalhadores por unidade a campanha não
                atinge o piso de anonimato e não produz resultado liberável. O
                diagnóstico responde isso em dois minutos — e diz não quando é
                não.
              </p>
              <a
                className="mt-3 inline-block rounded-lg bg-amber-500 px-4 py-2 text-sm font-black text-amber-950 hover:bg-amber-400"
                href="https://www.froid.com.br/diagnostico-nr1.html"
                target="_blank"
                rel="noreferrer"
              >
                Checar o enquadramento da minha empresa
              </a>
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onReset}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-black text-slate-200"
              >
                Escolher outro produto
              </button>
              <a
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-black text-slate-200"
                href="https://www.froid.com.br/como-funciona-nr1.html"
                target="_blank"
                rel="noreferrer"
              >
                Ver como funciona, etapa por etapa
              </a>
            </div>
          </section>
        )}

        <p className="mt-8 max-w-3xl text-xs leading-5 text-slate-400">
          Escolheu errado? Dá para voltar: a escolha define apenas quais campos o
          cadastro pede, e pode ser refeita antes de concluir. Configurações fora
          do padrão são tratadas por{" "}
          <a className="underline" href={`mailto:${CONTATO_EMPRESAS}`}>
            {CONTATO_EMPRESAS}
          </a>
          .
        </p>
      </main>
    </div>
  );
};

export default ProductChoice;
