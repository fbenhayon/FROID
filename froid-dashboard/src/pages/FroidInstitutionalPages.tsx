import React from "react";
import { Link } from "react-router-dom";

const facsImage = "/froid-home/facs-mapa-completo.png";
const auImage = "/froid-home/facs-unidades-acao.png";
const matrixImage = "/froid-home/facs-matrizes-emocionais.png";

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3">
        <Link to="/" className="text-sm font-black tracking-[0.38em] text-slate-950">
          FROID
        </Link>
        <nav className="hidden items-center gap-1 text-xs font-black text-slate-600 md:flex">
          <Link to="/froid/ciencia" className="rounded px-3 py-2 hover:bg-slate-100">Ciencia</Link>
          <Link to="/froid/tecnologia" className="rounded px-3 py-2 hover:bg-slate-100">Tecnologia</Link>
          <Link to="/froid/profissionais" className="rounded px-3 py-2 hover:bg-slate-100">Profissionais</Link>
        </nav>
        <Link to="/access/register" className="rounded bg-slate-950 px-3 py-2 text-xs font-black text-white hover:bg-cyan-700">
          Cadastro
        </Link>
      </div>
    </header>
  );
}

function PageShell({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <Header />
      <main>
        <section className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-700">{eyebrow}</p>
            <h1 className="mt-4 max-w-5xl text-4xl font-black leading-tight text-slate-950 md:text-6xl">{title}</h1>
            <p className="mt-5 max-w-4xl text-base leading-8 text-slate-600">{intro}</p>
          </div>
        </section>
        {children}
      </main>
    </div>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-black text-slate-950">{title}</h2>
      <p className="mt-3 text-sm leading-7 text-slate-600">{text}</p>
    </article>
  );
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 border-b border-slate-200 py-4 md:grid-cols-[220px_1fr]">
      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="text-sm leading-7 text-slate-700">{value}</p>
    </div>
  );
}

export const FroidSciencePage: React.FC = () => {
  return (
    <PageShell
      eyebrow="Ciencia FROID"
      title="Da expressao humana ao indice clinico multimodal."
      intro="O FROID organiza a sessao como um sistema de sinais correlacionados. Nenhum marcador isolado deve ser tratado como verdade absoluta; a relevancia surge da composicao entre voz, face, semantica, zonas emocionais e evolucao temporal."
    >
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="grid gap-4">
          <TextBlock
            title="IPM: o velocimetro emocional"
            text="O IPM indica intensidade ou energia global da sessao. Ele mede quanto combustivel emocional esta sendo mobilizado, independentemente de a narrativa estar coerente ou defensiva."
          />
          <TextBlock
            title="IDM: a direcao do desequilibrio"
            text="O IDM aponta para onde a dinamica interna parece se deslocar no mapa de zonas. O valor ganha significado quando comparado ao baseline inicial e aos cortes seguintes."
          />
          <TextBlock
            title="Dissonancias e consonancias"
            text="A dissonancia e registrada quando o FROID detecta divergencia acima da metrica definida entre fala, voz, face e zona dominante. A consonancia reforca coerencia expressiva e pode sustentar o curso clinico adotado."
          />
        </div>
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <img src={matrixImage} alt="Mapa FROID de matrizes emocionais e dissonancias" className="h-full w-full object-cover" />
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <h2 className="text-2xl font-black text-slate-950">Parametros avaliados por camada</h2>
          <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 px-5">
            <DataRow label="Voz" value="MFCC7, MFCC9, F0, ZCR, Jitter, Shimmer, energia, pausas, velocidade da fala, sub-harmonicos e tensao vocal." />
            <DataRow label="Face" value="AUs, intensidade, simetria, onset, apex, offset, duracao, combinacoes expressivas e microexpressoes." />
            <DataRow label="Semantica" value="Transcricao, tema predominante, valencia semantica, mudancas de narrativa e resumo por cortes temporais." />
            <DataRow label="Temporalidade" value="Baseline inicial de 60 segundos, cortes obrigatorios a cada 10 minutos, cortes profissionais e media da sessao." />
            <DataRow label="Integracao" value="IPM, IDM, risco clinico, dissonancias, consonancias, zonas dominantes e FROID Explica no contexto da consulta." />
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export const FroidTechnologyPage: React.FC = () => {
  return (
    <PageShell
      eyebrow="Tecnologia"
      title="Uma arquitetura de IA clinica, auditavel e evolutiva."
      intro="O FROID foi pensado para unir modelos avancados de linguagem, bioacustica, visao computacional, bases vetoriais, Data Mart anonimo e governanca LGPD em um fluxo clinico compreensivel para o profissional."
    >
      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-12 md:grid-cols-2">
        <TextBlock
          title="Duas trilhas de audio"
          text="A transcricao preserva a conversa entre profissional e paciente. A avaliacao FROID, entretanto, deve usar exclusivamente a trilha bioacustica do paciente para os graficos e indices."
        />
        <TextBlock
          title="FROID Explica"
          text="O modulo responde perguntas do profissional com base no contexto da sessao, nas metricas, nas fontes tecnicas e no repositorio clinico configurado, sempre com controle de seguranca."
        />
        <TextBlock
          title="Data Mart anonimo"
          text="Ao final da sessao, metricas e cortes podem ser anonimizados para alimentar comparacoes populacionais, benchmarks e pesquisas sem expor a identidade do paciente."
        />
        <TextBlock
          title="Aprendizado responsavel"
          text="A evolucao do FROID deve combinar dados anonimos, revisao humana, validacao cientifica, trilha de auditoria e melhoria continua dos modelos."
        />
      </section>

      <section className="border-y border-slate-200 bg-slate-950 text-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="overflow-hidden rounded-lg border border-white/15 bg-white">
            <img src={facsImage} alt="FACS completo integrado ao FROID" className="h-full w-full object-cover" />
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.26em] text-cyan-200">Camadas tecnicas</p>
            <h2 className="mt-3 text-3xl font-black leading-tight">Bilhoes de combinacoes possiveis, apresentadas em linguagem clinica.</h2>
            <p className="mt-5 text-sm leading-7 text-slate-200">
              A forca do FROID esta em reduzir a complexidade sem destruir o detalhe:
              transformar sinais de alta dimensao em alertas, metricas, resumos,
              relatorios e perguntas inteligentes que o profissional consegue usar na pratica.
            </p>
            <div className="mt-6 grid gap-3">
              {[
                "Modelos de transcricao para linguagem natural da sessao.",
                "Algoritmos bioacusticos para sinais vocais brutos.",
                "Visao computacional para unidades de acao facial.",
                "RAG e base de conhecimento para explicacoes tecnicas.",
                "DuckDB anonimo para benchmarks populacionais com k-anonimato.",
              ].map((item) => (
                <p key={item} className="rounded border border-white/15 bg-white/5 p-4 text-sm leading-6 text-slate-100">
                  {item}
                </p>
              ))}
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export const FroidProfessionalsPage: React.FC = () => {
  return (
    <PageShell
      eyebrow="Profissionais"
      title="Convite para construir a proxima camada da saude mental."
      intro="O FROID nasce para complementar a escuta clinica, fortalecer a revisao de sessoes, apoiar supervisoes, revelar padroes ocultos e oferecer ao profissional uma inteligencia de observacao que trabalha junto com sua experiencia."
    >
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <img src={auImage} alt="Unidades de acao facial para profissionais FROID" className="h-full w-full object-cover" />
        </div>
        <div className="grid gap-4">
          <TextBlock
            title="Para a pratica diaria"
            text="Durante a sessao, o profissional acompanha transcricao, tom, palavras por minuto, biomarcadores, IPM, IDM, riscos, dissonancias e cortes temporais."
          />
          <TextBlock
            title="Para supervisao e pares"
            text="Ao encerrar a consulta, o relatorio permite selecionar metricas, resumos, anotacoes clinicas e pontos de dissonancia para revisao posterior."
          />
          <TextBlock
            title="Para pesquisa e evolucao"
            text="Com anonimato e governanca, a experiencia de muitos profissionais pode revelar padroes que nenhum observador humano conseguiria mapear sozinho."
          />
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <h2 className="text-2xl font-black text-slate-950">Programa inicial de acesso</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <article className="rounded-lg border border-cyan-200 bg-cyan-50 p-6">
              <p className="text-sm font-black uppercase tracking-[0.18em] text-cyan-800">Primeiros 100 profissionais</p>
              <h3 className="mt-3 text-3xl font-black text-slate-950">20 sessoes gratuitas</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">Para experimentar o FROID em rotina real e contribuir com a primeira etapa de validacao clinica.</p>
            </article>
            <article className="rounded-lg border border-emerald-200 bg-emerald-50 p-6">
              <p className="text-sm font-black uppercase tracking-[0.18em] text-emerald-800">Proximos 100 profissionais</p>
              <h3 className="mt-3 text-3xl font-black text-slate-950">10 sessoes gratuitas</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">Para ampliar a base de uso e acelerar o amadurecimento da plataforma com dados anonimos agregados.</p>
            </article>
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/access/register" className="rounded bg-slate-950 px-5 py-3 text-sm font-black text-white hover:bg-cyan-700">
              Cadastrar agora
            </Link>
            <Link to="/login" className="rounded border border-slate-300 px-5 py-3 text-sm font-black text-slate-900 hover:bg-slate-100">
              Entrar no sistema
            </Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
};
