import React from "react";
import { Link } from "react-router-dom";

const facsImage = "/froid-home/facs-mapa-completo.png";
const auImage = "/froid-home/facs-unidades-acao.png";
const matrixImage = "/froid-home/facs-matrizes-emocionais.png";

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4">
        <Link to="/" className="text-sm font-black tracking-[0.42em] text-cyan-300">
          FROID
        </Link>
        <nav className="hidden items-center gap-1 text-xs font-black text-slate-300 md:flex">
          <Link to="/froid/ciencia" className="rounded px-3 py-2 hover:bg-white/10">Ciencia</Link>
          <Link to="/froid/tecnologia" className="rounded px-3 py-2 hover:bg-white/10">Tecnologia</Link>
          <Link to="/froid/profissionais" className="rounded px-3 py-2 hover:bg-white/10">Profissionais</Link>
        </nav>
        <Link to="/access/register" className="rounded bg-cyan-400 px-3 py-2 text-xs font-black text-slate-950 hover:bg-cyan-300">
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
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Header />
      <main>
        <section className="border-b border-white/10 bg-slate-900/70">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">{eyebrow}</p>
            <h1 className="mt-4 max-w-5xl text-4xl font-black leading-tight text-white md:text-6xl">{title}</h1>
            <p className="mt-5 max-w-4xl text-base leading-8 text-slate-300">{intro}</p>
          </div>
        </section>
        {children}
      </main>
    </div>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <article className="rounded-lg border border-white/10 bg-slate-900 p-5 shadow-lg shadow-slate-950/20">
      <h2 className="text-lg font-black text-white">{title}</h2>
      <p className="mt-3 text-sm leading-7 text-slate-300">{text}</p>
    </article>
  );
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 border-b border-white/10 py-4 md:grid-cols-[230px_1fr]">
      <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-200">{label}</p>
      <p className="text-sm leading-7 text-slate-300">{value}</p>
    </div>
  );
}

function ImagePanel({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white p-3 shadow-2xl shadow-cyan-950/30">
      <img src={src} alt={alt} className="h-auto max-h-[680px] w-full object-contain" />
    </div>
  );
}

export const FroidSciencePage: React.FC = () => {
  return (
    <PageShell
      eyebrow="Ciencia FROID"
      title="A composicao entre voz, face, tempo e sentido."
      intro="A ciencia operacional do FROID nao depende de um marcador isolado. Ela nasce do cruzamento entre sinais bioacusticos, unidades de acao facial, semantica, baseline individual, cortes temporais, IPM, IDM e dissonancias efetivamente apuradas."
    >
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="grid gap-4">
          <TextBlock
            title="Baseline de 60 segundos"
            text="A sessao precisa iniciar a avaliacao apos o audio estar ativo. Os primeiros 60 segundos estabelecem a referencia individual para voz, face, tema inicial, IPM, IDM, riscos, zonas e demais indices comparativos."
          />
          <TextBlock
            title="IPM e IDM"
            text="O IPM mede intensidade global; o IDM indica direcao do desequilibrio. Delta inicial pode ser zero, mas a referencia inicial deve registrar todos os indices para comparacao com os cortes posteriores."
          />
          <TextBlock
            title="Dissonancia clinica"
            text="Dissonancia e um aviso ao profissional quando fala, voz, face, tema, zona, risco ou comportamento temporal divergem acima da metrica definida. O FROID deve listar apenas o que foi efetivamente apurado."
          />
          <TextBlock
            title="Psicossomatologia investigavel"
            text="O FROID pode apoiar a investigacao de relacoes entre tensoes psiquicas, defesas, padroes expressivos e manifestacoes corporais, sem transformar correlacao em causalidade automatica."
          />
        </div>
        <ImagePanel src={matrixImage} alt="Mapa FROID de expressoes faciais, matrizes emocionais e dissonancias" />
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <h2 className="text-2xl font-black text-white">Parametros por camada</h2>
          <div className="mt-6 rounded-lg border border-white/10 bg-slate-950 px-5">
            <DataRow label="Voz" value="MFCC7, MFCC9, F0, ZCR, Jitter, Shimmer, energia, pausas, velocidade, cadencia, tensao e sub-harmonicos." />
            <DataRow label="Face" value="AUs, intensidade, simetria, combinacoes, regioes anatomicas, microexpressoes, onset, apex e offset." />
            <DataRow label="Semantica" value="Transcricao, sentido, tema em ate cinco palavras, valencia, contradicoes narrativas e resumo de 100 a 200 palavras por corte." />
            <DataRow label="Temporalidade" value="Baseline inicial, cortes obrigatorios de 10 minutos, cortes feitos pelo profissional, medias de sessao e comparacao final." />
            <DataRow label="Sintese FROID" value="IPM, IDM, riscos, zonas, dissonancias, consonancias, FROID Explica e Relatorio da Consulta." />
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
      title="IA de ponta, dados anonimos e engenharia clinica auditavel."
      intro="O FROID combina modelos modernos de linguagem, transcricao, analise bioacustica, visao computacional, base vetorial, Data Mart anonimo e governanca LGPD para transformar sessoes em conhecimento clinico estruturado."
    >
      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-12 md:grid-cols-2">
        <TextBlock
          title="Trilha semantica"
          text="A transcricao preserva a conversa entre profissional e paciente, mantendo a distincao DR e PAC para leitura clinica, resumos, temas e relatorio."
        />
        <TextBlock
          title="Trilha bioacustica"
          text="A avaliacao dos graficos e indices deve usar exclusivamente a voz do paciente, mantendo a trilha do profissional apenas para contexto semantico."
        />
        <TextBlock
          title="FROID Explica"
          text="A camada explicativa responde perguntas do profissional a partir das metricas, do relatorio, das fontes tecnicas e da base de conhecimento configurada."
        />
        <TextBlock
          title="Data Mart anonimo"
          text="Ao final da sessao, cortes e metricas anonimizadas podem alimentar benchmarks e pesquisa populacional com k-anonimato, auditoria e governanca."
        />
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[1.1fr_0.9fr]">
          <ImagePanel src={facsImage} alt="Mapa completo FACS, AUs e descritores de acao no FROID" />
          <div>
            <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Aprendizado responsavel</p>
            <h2 className="mt-3 text-3xl font-black leading-tight text-white">Evoluir com padroes anonimos, sem perder governanca clinica.</h2>
            <p className="mt-5 text-sm leading-7 text-slate-300">
              A capacidade de desenvolvimento do FROID deve vir da combinacao entre
              dados anonimos, fontes tecnicas, revisao humana e validacao cientifica.
              A plataforma pode sugerir caminhos ocultos, associacoes e padroes, mas
              sua forca esta em servir ao profissional, nao em substituir a clinica.
            </p>
            <div className="mt-6 grid gap-3">
              {[
                "Base vetorial para manuais, FACS, zonas, regras e fontes tecnicas.",
                "Data Mart anonimo para benchmarks populacionais e comparacao longitudinal.",
                "Guardrails para evitar reidentificacao e proteger dados sensiveis.",
                "Relatorios auditaveis com metricas, cortes e anotacoes clinicas.",
                "IA explicativa para transformar dados complexos em linguagem clinica utilizavel.",
              ].map((item) => (
                <p key={item} className="rounded-lg border border-white/10 bg-slate-950 p-4 text-sm leading-7 text-slate-300">
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
      title="Uma ferramenta para ampliar a escuta, a revisao e a decisao clinica."
      intro="O FROID foi criado para profissionais que desejam observar a sessao com mais profundidade: nao apenas o que foi dito, mas como foi dito, quando mudou, como o corpo respondeu e onde a coerencia se rompeu ou se confirmou."
    >
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.95fr_1.05fr]">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Na rotina clinica</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">Do convite ao relatorio final.</h2>
          <div className="mt-6 grid gap-4">
            <TextBlock
              title="Antes da sessao"
              text="O profissional gera convite, define pagamento ou pacote, envia link ao paciente e registra consentimentos e dados necessarios conforme a LGPD."
            />
            <TextBlock
              title="Durante a sessao"
              text="Acompanha video, audio, transcricao, biomarcadores, IPM, IDM, riscos, zonas, dissonancias, cortes e FROID Explica."
            />
            <TextBlock
              title="Depois da sessao"
              text="Recebe o Relatorio da Consulta com parametros iniciais, medias, cortes, resumos, anotacoes clinicas e dados anonimizaveis para pesquisa."
            />
          </div>
        </div>
        <ImagePanel src={auImage} alt="Unidades de acao facial aplicadas ao FROID" />
      </section>

      <section className="border-y border-cyan-300/20 bg-cyan-300/5">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <h2 className="text-2xl font-black text-white">Programa inicial de acesso</h2>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-300">
            O objetivo e formar uma primeira comunidade de validacao real, com profissionais
            capazes de testar, criticar, aprimorar e ajudar a consolidar a plataforma.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <article className="rounded-lg border border-cyan-300/30 bg-slate-950 p-6">
              <p className="text-sm font-black uppercase tracking-[0.18em] text-cyan-200">Primeiros 100 profissionais</p>
              <h3 className="mt-3 text-3xl font-black text-white">20 sessoes gratuitas</h3>
              <p className="mt-3 text-sm leading-7 text-slate-300">Entrada para experimentar o FROID em rotina clinica real com relatorio, cortes e FROID Explica.</p>
            </article>
            <article className="rounded-lg border border-emerald-300/30 bg-slate-950 p-6">
              <p className="text-sm font-black uppercase tracking-[0.18em] text-emerald-200">Proximos 100 profissionais</p>
              <h3 className="mt-3 text-3xl font-black text-white">10 sessoes gratuitas</h3>
              <p className="mt-3 text-sm leading-7 text-slate-300">Acesso para ampliar a base de uso e acelerar a evolucao do sistema com experiencia anonima agregada.</p>
            </article>
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/access/register" className="rounded-lg bg-cyan-400 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-300">
              Cadastrar profissional
            </Link>
            <Link to="/login" className="rounded-lg border border-white/20 px-5 py-3 text-sm font-black text-white hover:bg-white/10">
              Entrar no FROID
            </Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

