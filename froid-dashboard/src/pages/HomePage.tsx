import React from "react";
import { Link } from "react-router-dom";
import { LgpdNotice } from "../components/legal/LgpdNotice";

const matrixImage = "/froid-home/facs-matrizes-emocionais.png";
const auImage = "/froid-home/facs-unidades-acao.png";
const facsMapImage = "/froid-home/facs-mapa-completo.png";

const navItems = [
  { label: "Inicio", to: "/" },
  { label: "Ciencia", to: "/froid/ciencia" },
  { label: "Tecnologia", to: "/froid/tecnologia" },
  { label: "Profissionais", to: "/froid/profissionais" },
];

const statStrip = [
  ["500ms", "janela de fusao multimodal"],
  ["60s", "calibracao de linha de base"],
  ["12 zonas", "espectro emocional mapeado"],
  ["468 pts", "landmarks faciais rastreados"],
];

const principles = [
  "FROID existe para ampliar, nunca substituir, o raciocinio clinico do profissional habilitado. Cada score e hipotese investigavel, nao sentenca diagnostica.",
  "Sua funcao e estabelecer pontes matematicamente rastreaveis entre psique, linguagem, corpo, voz, expressao facial involuntaria e dinamica temporal da sessao.",
  "A plataforma processa multiplos vetores de sinal, muitos deles imperceptiveis a audicao e a observacao subjetiva, para revelar coerencias, contradicoes e caminhos de investigacao.",
  "A base anonima e agregada permite que o sistema amadureca por padroes populacionais, sempre sob governanca, LGPD e supervisao profissional.",
];

const abilities = [
  {
    title: "A voz, a maior expressao da psique humana",
    subtitle:
      "Bioacustica vocal dedicada ao paciente para detectar tensao, energia, cadencia, pausas e biomarcadores acusticos.",
    how:
      "O FROID processa MFCC7, MFCC9, F0, ZCR, Jitter, Shimmer, energia, velocidade, pausas e bandas sub-harmonicas. A trilha bioacustica prioriza exclusivamente a voz do paciente.",
    value:
      "Permite perceber vazamentos autonomicos e emocionais que podem estar ausentes ou mascarados na narrativa consciente.",
    tags: ["MFCC7", "MFCC9", "F0", "5-20Hz"],
  },
  {
    title: "FACS, AUs e matriz facial dinamica",
    subtitle:
      "Unidades de acao facial, intensidade, simetria, onset, apex e offset transformados em sinais clinicos auditaveis.",
    how:
      "A leitura facial combina AUs isoladas e compostas, regioes anatomicas, microexpressoes, assimetria e duracao para compor vetores expressivos temporais.",
    value:
      "Amplia a capacidade de observar dor, medo, tristeza mascarada, raiva contida, nojo, surpresa e defesas expressivas.",
    tags: ["AU1", "AU4", "AU15", "AU20"],
  },
  {
    title: "Transcricao semantica em tempo clinico",
    subtitle:
      "A fala real do paciente e do profissional preservada como memoria narrativa da sessao.",
    how:
      "A transcricao separa DR/PAC, alimenta tema, resumo, cortes temporais, relatorio pos-sessao e FROID Explica sem quebrar artificialmente a fala.",
    value:
      "Permite revisar a sequencia clinica, acompanhar mudancas de tema e reconstruir o percurso emocional com precisao.",
    tags: ["DR/PAC", "Tema", "Resumo", "Cortes"],
  },
  {
    title: "IPM e IDM como instrumentos de navegacao",
    subtitle:
      "O IPM mede intensidade global; o IDM indica direcao dominante do desequilibrio no mapa zonal.",
    how:
      "A linha de base de 60 segundos registra os indices iniciais e permite comparar deltas a cada corte obrigatorio ou profissional.",
    value:
      "O profissional ganha uma leitura rapida da intensidade e da direcao do processo para ajustar ritmo e intervencao.",
    tags: ["IPM", "IDM", "Delta", "Zonas"],
  },
  {
    title: "Dissonancias e consonancias",
    subtitle:
      "O nucleo de inteligencia que distingue coerencia expressiva de contradicao multimodal.",
    how:
      "O FROID cruza fala, voz, face, tema, zona, baseline e riscos. Apenas divergencias acima da metrica definida sao listadas.",
    value:
      "Avisa o profissional quando ha um ponto tecnico que merece investigacao, acolhimento ou mudanca de curso na sessao.",
    tags: ["Voz", "Face", "Semantica", "Tempo"],
  },
  {
    title: "Riscos clinicos em leitura contextual",
    subtitle:
      "Depressao, ansiedade somatica, mania, estresse cognitivo, dissociacao e trauma como scores de apoio.",
    how:
      "Os riscos combinam marcadores acusticos, expressivos e semanticos, calibrados por baseline e por familias clinimetricas de referencia.",
    value:
      "Ajuda a priorizar hipoteses e acompanhar tendencias sem transformar correlacao em diagnostico automatico.",
    tags: ["PHQ-9", "HAMD", "YMRS", "Trauma"],
  },
  {
    title: "Cortes, temas e resumos por janela",
    subtitle:
      "A sessao convertida em blocos comparaveis, com tema, resumo e metricas do periodo.",
    how:
      "Cortes obrigatorios de 10 minutos e cortes profissionais registram IPM, IDM, biomarcadores, tom, palavras/minuto, sub-harmonicos e dissonancias.",
    value:
      "Permite acompanhar progressao, estabilizacao, deslocamento ou intensificacao dos temas ao longo da consulta.",
    tags: ["0-10", "10-20", "Metricas", "Resumo"],
  },
  {
    title: "FROID Explica",
    subtitle:
      "Inteligencia interrogavel para explicar metricas, fontes, correlacoes e achados durante ou apos a sessao.",
    how:
      "A camada explicativa consulta contexto da sessao, RAG clinico, fontes tecnicas e Data Mart anonimo quando autorizado.",
    value:
      "Transforma matematica multimodal em raciocinio clinico compreensivel para profissionais altamente especializados.",
    tags: ["RAG", "Fontes", "Coortes", "Perguntas"],
  },
  {
    title: "Data-FROID: Data Mart Anonimo",
    subtitle:
      "A maior base multimodal anonimizada de evidencias em saude mental para pesquisa, benchmark e descoberta.",
    how:
      "Metricas anonimizadas passam por governanca, k-anonimato e segregacao entre dados identificados e dados populacionais.",
    value:
      "Permite comparar trajetorias, testar hipoteses e encontrar padroes impossiveis de mapear manualmente em escala humana.",
    tags: ["k-anon", "Bench", "LGPD", "Padroes"],
  },
];

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-black/95">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-center gap-3 px-5">
        <nav className="flex flex-wrap items-center justify-center gap-2 text-[15px] font-bold">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="rounded-md px-4 py-2 text-slate-300 hover:bg-cyan-300/10 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
          <Link to="/login" className="rounded-md border border-white/15 px-4 py-2 text-cyan-100 hover:bg-white/10">
            Login
          </Link>
          <Link to="/access/register" className="rounded-md bg-cyan-300 px-4 py-2 text-slate-950 hover:bg-cyan-200">
            Cadastro
          </Link>
        </nav>
      </div>
    </header>
  );
}

function StatStrip() {
  return (
    <section className="border-y border-white/10 bg-slate-900/70">
      <div className="mx-auto grid max-w-7xl gap-4 px-5 py-8 md:grid-cols-4">
        {statStrip.map(([value, label]) => (
          <div key={value} className="rounded-[10px] border border-white/10 bg-slate-950 p-5">
            <p className="font-mono text-3xl font-semibold text-cyan-100">{value}</p>
            <p className="mt-2 text-xs font-black uppercase tracking-[0.2em] text-slate-400">{label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function SectionKicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-black uppercase tracking-[0.3em] text-cyan-300">{children}</p>
  );
}

function TechnicalImage({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-[10px] border border-cyan-300/20 bg-slate-950 p-4 shadow-2xl shadow-cyan-950/30">
      <div className="overflow-hidden rounded-lg border border-white/10 bg-white">
        <img src={src} alt={alt} className="h-auto w-full object-contain" />
      </div>
    </div>
  );
}

function AbilityBlock({
  ability,
  index,
}: {
  ability: (typeof abilities)[number];
  index: number;
}) {
  const reversed = index % 2 === 1;
  const image = index % 3 === 0 ? auImage : index % 3 === 1 ? facsMapImage : matrixImage;
  return (
    <section className="border-t border-white/10 bg-[#020617]">
      <div
        className={`mx-auto flex max-w-7xl flex-wrap gap-10 px-5 py-12 ${
          reversed ? "lg:flex-row-reverse" : ""
        }`}
      >
        <div className="min-w-[280px] flex-1">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-300/15 font-mono text-sm font-semibold text-cyan-100">
              {String(index + 1).padStart(2, "0")}
            </span>
            <SectionKicker>Dominio FROID</SectionKicker>
          </div>
          <h3 className="mt-4 text-center font-serif text-2xl font-normal leading-tight text-white md:text-3xl">
            {ability.title}
          </h3>
          <p className="mt-4 text-base font-semibold leading-8 text-cyan-100">{ability.subtitle}</p>
          <div className="mt-6 grid gap-3">
            <div className="rounded-[10px] border border-white/10 bg-slate-900 p-5">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Como funciona</p>
              <p className="mt-3 text-sm leading-7 text-slate-300">{ability.how}</p>
            </div>
            <div className="rounded-[10px] border border-emerald-300/20 bg-emerald-300/5 p-5">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-200">Valor para o profissional</p>
              <p className="mt-3 text-sm leading-7 text-slate-300">{ability.value}</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {ability.tags.map((tag) => (
              <span key={tag} className="rounded border border-cyan-300/20 bg-cyan-300/5 px-3 py-1 font-mono text-xs text-cyan-100">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="min-w-[280px] flex-1">
          <TechnicalImage src={image} alt={ability.title} />
        </div>
      </div>
    </section>
  );
}

export const HomePage: React.FC = () => {
  return (
    <div
      className="min-h-screen bg-[#020617] text-slate-100"
      style={{
        backgroundImage:
          "radial-gradient(circle at 1px 1px, rgba(255,255,255,.05) 1px, transparent 0)",
        backgroundSize: "28px 28px",
      }}
    >
      <Header />

      <main>
        <section className="relative flex min-h-[92vh] flex-col items-center justify-between overflow-hidden bg-black">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,.08) 18%, rgba(0,0,0,.08) 76%, rgba(0,0,0,.9) 100%), url(${matrixImage})`,
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
              backgroundSize: "cover",
            }}
          />
          <p className="relative px-5 pt-10 text-center text-xs font-black uppercase tracking-[0.4em] text-cyan-100 drop-shadow">
            A dissonancia, decifrada
          </p>
          <div className="relative flex flex-col items-center gap-3 pb-9">
            <span className="h-9 w-px bg-gradient-to-b from-transparent to-cyan-300" />
            <span className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
              Role para explorar
            </span>
          </div>
        </section>

        <section className="relative overflow-hidden border-b border-white/10 bg-black">
          <div
            className="relative mx-auto min-h-[596px] max-w-7xl px-5 py-16"
            style={{
              backgroundImage: `linear-gradient(90deg, rgba(0,0,0,.82), rgba(0,0,0,.36)), url(${facsMapImage})`,
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
              backgroundSize: "cover",
            }}
          >
            <div className="max-w-[640px]">
              <SectionKicker>Frequency Recognition of Internal Dynamics</SectionKicker>
              <h1 className="mt-5 text-center font-serif text-3xl font-medium leading-tight text-white md:text-[42px]">
                O FROID e uma inteligencia disruptiva que aprende e cresce exponencialmente identificando coerencias e dissonancias entre o espirito humano e suas expressoes.
              </h1>
              <p className="mt-8 rounded-[10px] border border-cyan-300/20 bg-slate-950/85 p-6 text-justify text-[17px] leading-8 text-slate-300 shadow-2xl shadow-cyan-950/30">
                Devido a riqueza das expressoes humanas, o FROID e a plataforma de reconhecimento das dinamicas internas aumentada que proporcionara habilidades e percepcoes extras para diagnostico, monitoramento e apoio sem precedentes para a psiquiatria e psicologia moderna. O objetivo e localizar padroes ocultos, insights auditaveis, novos procedimentos e caminhos para incorporar em sessoes e praticas diarias.
                <br />
                <br />
                Hoje, parte relevante desse conhecimento cientifico esta a disposicao e foi minuciosamente codificado em um complexo algoritmo processado pelas mais sofisticadas ferramentas de inteligencia online disponiveis no planeta, que permitiram dar vida ao FROID.
              </p>
            </div>
          </div>
        </section>

        <StatStrip />

        <section className="mx-auto max-w-7xl px-5 py-14">
          <SectionKicker>DNA FROID</SectionKicker>
          <h2 className="mt-4 max-w-5xl font-serif text-3xl font-normal leading-tight text-white md:text-5xl">
            Uma segunda camada de percepcao para uma clinica mais precisa.
          </h2>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {principles.map((point) => (
              <p key={point} className="rounded-[10px] border border-cyan-300/15 bg-cyan-300/5 p-5 text-sm leading-7 text-slate-300">
                {point}
              </p>
            ))}
          </div>
        </section>

        <section className="border-y border-white/10 bg-slate-900/70">
          <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="relative min-h-[380px] rounded-[10px] border border-cyan-300/20 bg-black p-6">
              <SectionKicker>Arquitetura multimodal</SectionKicker>
              <h2 className="mt-4 text-center font-serif text-3xl font-normal leading-tight text-white">
                Arquitetura e Algoritmos para a avaliacao das Dissonancias
              </h2>
              <p className="mt-6 text-justify text-[15px] leading-8 text-slate-300">
                Este e o nucleo de inteligencia que distingue o FROID como unico e superior a sistemas de prontuario eletronico ou similares. Ele opera como sensor radiografico do subconsciente humano, comparando a intencao consciente com vazamentos biologicos involuntarios a cada 500 milissegundos.
              </p>
              <div className="mt-8 grid grid-cols-2 gap-3">
                {["Consciencia", "Subconsciente", "Voz", "Face"].map((item) => (
                  <div key={item} className="rounded border border-white/10 bg-white/[0.03] p-4 text-center">
                    <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">{item}</p>
                  </div>
                ))}
              </div>
            </div>
            <TechnicalImage src={matrixImage} alt="Matriz visual tecnica FROID" />
          </div>
        </section>

        <section>
          {abilities.map((ability, index) => (
            <AbilityBlock key={ability.title} ability={ability} index={index} />
          ))}
        </section>

        <section className="border-y border-cyan-300/20 bg-cyan-300/5">
          <div className="mx-auto grid max-w-7xl gap-8 px-5 py-14 lg:grid-cols-[1fr_0.8fr]">
            <div>
              <SectionKicker>Convite aos profissionais</SectionKicker>
              <h2 className="mt-4 font-serif text-3xl font-normal leading-tight text-white md:text-5xl">
                Participe da primeira fase do FROID.
              </h2>
              <p className="mt-5 max-w-3xl text-sm leading-8 text-slate-300">
                Procuramos profissionais dispostos a testar uma ferramenta sem paralelo direto em sua proposta: unir psique, fala, corpo, face, voz, tempo, relatorio e inteligencia explicativa em uma mesma pratica clinica.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/access/register" className="rounded-md bg-cyan-300 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-200">
                  Solicitar cadastro
                </Link>
                <Link to="/login" className="rounded-md border border-white/20 px-5 py-3 text-sm font-black text-white hover:bg-white/10">
                  Entrar no FROID
                </Link>
              </div>
            </div>
            <div className="grid gap-4">
              <div className="rounded-[10px] border border-cyan-300/30 bg-slate-950 p-6">
                <p className="text-sm font-black uppercase tracking-[0.18em] text-cyan-200">Primeiros 100 profissionais</p>
                <p className="mt-3 text-3xl font-black text-white">20 sessoes gratuitas</p>
              </div>
              <div className="rounded-[10px] border border-emerald-300/30 bg-slate-950 p-6">
                <p className="text-sm font-black uppercase tracking-[0.18em] text-emerald-200">Proximos 100 profissionais</p>
                <p className="mt-3 text-3xl font-black text-white">10 sessoes gratuitas</p>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-[#020617]">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <h2 className="font-serif text-3xl font-normal text-white">LGPD, consentimento e limites clinicos</h2>
            <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-300">
              O FROID opera com consentimento destacado, minimizacao de dados, segregacao entre dados identificados e anonimizados, auditoria e exclusao formal quando solicitada. Indicadores sao apoio tecnico ao profissional habilitado, nao diagnostico automatico.
            </p>
            <div className="mt-6">
              <LgpdNotice audience="home" />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};
