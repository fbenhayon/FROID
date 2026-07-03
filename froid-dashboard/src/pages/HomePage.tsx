import React from "react";
import { Link } from "react-router-dom";
import { LgpdNotice } from "../components/legal/LgpdNotice";

const heroImage = "/froid-home/facs-matrizes-emocionais.png";
const auImage = "/froid-home/facs-unidades-acao.png";
const facsImage = "/froid-home/facs-mapa-completo.png";

const navItems = [
  { label: "Ciencia", to: "/froid/ciencia" },
  { label: "Tecnologia", to: "/froid/tecnologia" },
  { label: "Profissionais", to: "/froid/profissionais" },
];

const capabilityBlocks = [
  {
    title: "Sessao multimodal em tempo real",
    text:
      "Voz, face, semantica, IPM, IDM, riscos, dissonancias, cortes temporais e relatorio clinico em um mesmo fluxo de trabalho.",
  },
  {
    title: "Bioacustica vocal",
    text:
      "Analise de MFCC7, MFCC9, F0, ZCR, Jitter, Shimmer, energia, pausas, cadencia verbal e sub-harmonicos vocais.",
  },
  {
    title: "FACS e unidades de acao",
    text:
      "Leitura de AUs, assimetrias, intensidade, duracao e combinacoes faciais que podem revelar consonancias e dissonancias expressivas.",
  },
  {
    title: "IPM e IDM",
    text:
      "O IPM funciona como velocimetro da intensidade emocional; o IDM aponta a direcao dominante do desequilibrio no mapa zonal.",
  },
  {
    title: "FROID Explica",
    text:
      "Uma camada de inteligencia para apoiar perguntas do profissional durante a sessao, no relatorio e na analise longitudinal.",
  },
  {
    title: "Base anonima evolutiva",
    text:
      "Dados anonimizados podem alimentar benchmarks, comparacoes e pesquisas com governanca, k-anonimato e auditoria tecnica.",
  },
];

const clinicalSignals = [
  "Dissonancias entre fala, voz, face e zonas emocionais",
  "Mudancas de intensidade comparadas ao baseline de 60 segundos",
  "Padroes vocais associados a tensao, retardo, aceleracao ou sobrecarga",
  "Consonancias expressivas que reforcam coerencia do relato",
  "Temas e resumos por cortes para revisao clinica posterior",
  "Relatorio da Consulta com metricas, observacoes e historico",
];

const systemLayers = [
  "Captura protegida de audio e video da sessao",
  "Transcricao semantica com separacao entre profissional e paciente",
  "Analise bioacustica exclusiva da trilha vocal do paciente",
  "Mapeamento facial por unidades de acao e microdinamica expressiva",
  "Fusao de sinais em IPM, IDM, riscos, dissonancias e cortes",
  "Anonimizacao para Data Mart populacional e aprendizado agregado",
];

const offers = [
  {
    title: "Primeiros 100 profissionais",
    value: "20 sessoes gratuitas",
    text: "Acesso inicial para experimentar o FROID em rotina clinica real, com relatorios e FROID Explica.",
  },
  {
    title: "Proximos 100 profissionais",
    value: "10 sessoes gratuitas",
    text: "Entrada assistida para ampliar a base de uso, validar fluxos e acelerar a evolucao da plataforma.",
  },
];

function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3">
        <Link to="/" className="text-sm font-black tracking-[0.38em] text-slate-950">
          FROID
        </Link>
        <nav className="hidden items-center gap-1 text-xs font-black text-slate-600 md:flex">
          {navItems.map((item) => (
            <Link key={item.to} to={item.to} className="rounded px-3 py-2 hover:bg-slate-100">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" className="rounded border border-slate-300 px-3 py-2 text-xs font-black text-slate-800 hover:bg-slate-100">
            Login
          </Link>
          <Link to="/access/register" className="rounded bg-slate-950 px-3 py-2 text-xs font-black text-white hover:bg-cyan-700">
            Cadastro
          </Link>
        </div>
      </div>
    </header>
  );
}

function SectionTitle({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return (
    <div className="max-w-3xl">
      <p className="text-xs font-black uppercase tracking-[0.26em] text-cyan-700">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-black leading-tight text-slate-950 md:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-7 text-slate-600 md:text-base">{text}</p>
    </div>
  );
}

function CapabilityGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {capabilityBlocks.map((block) => (
        <article key={block.title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-black text-slate-950">{block.title}</h3>
          <p className="mt-3 text-sm leading-7 text-slate-600">{block.text}</p>
        </article>
      ))}
    </div>
  );
}

function NumberList({ items }: { items: string[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((item, index) => (
        <div key={item} className="flex gap-3 rounded-lg border border-slate-200 bg-white p-4">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-cyan-50 text-xs font-black text-cyan-800">
            {index + 1}
          </span>
          <p className="text-sm font-semibold leading-6 text-slate-700">{item}</p>
        </div>
      ))}
    </div>
  );
}

export const HomePage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <MarketingHeader />

      <main>
        <section
          className="relative min-h-[82vh] overflow-hidden bg-slate-950"
          style={{
            backgroundImage: `linear-gradient(90deg, rgba(3,7,18,0.93) 0%, rgba(3,7,18,0.78) 42%, rgba(3,7,18,0.18) 100%), url(${heroImage})`,
            backgroundPosition: "center",
            backgroundSize: "cover",
          }}
        >
          <div className="mx-auto flex min-h-[82vh] max-w-7xl items-center px-5 py-16">
            <div className="max-w-3xl text-white">
              <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-200">
                Frequency Recognition of Internal Dynamics
              </p>
              <h1 className="mt-5 text-4xl font-black leading-[1.02] md:text-6xl">
                FROID: coerencia entre psique, voz, face e narrativa clinica.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-100 md:text-lg">
                Uma plataforma de percepcao clinica aumentada para apoiar profissionais
                de saude mental na identificacao de consonancias, dissonancias,
                padroes bioacusticos e microexpressivos durante a sessao.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/access/register" className="rounded bg-cyan-300 px-5 py-3 text-sm font-black text-slate-950 hover:bg-cyan-200">
                  Quero testar o FROID
                </Link>
                <Link to="/froid/ciencia" className="rounded border border-white/50 px-5 py-3 text-sm font-black text-white hover:bg-white/10">
                  Entender a ciencia
                </Link>
              </div>
              <p className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">
                20 sessoes gratuitas para os primeiros 100 profissionais cadastrados
              </p>
            </div>
          </div>
        </section>

        <section className="border-b border-slate-200 bg-white">
          <div className="mx-auto grid max-w-7xl gap-6 px-5 py-10 md:grid-cols-3">
            <div>
              <p className="text-3xl font-black text-cyan-700">4</p>
              <p className="mt-1 text-sm font-black text-slate-950">fontes principais</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">voz, face, semantica e historico temporal da sessao.</p>
            </div>
            <div>
              <p className="text-3xl font-black text-emerald-700">500ms</p>
              <p className="mt-1 text-sm font-black text-slate-950">atualizacao de indices</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">indicadores dinamicos para acompanhamento clinico em tempo real.</p>
            </div>
            <div>
              <p className="text-3xl font-black text-rose-700">60s</p>
              <p className="mt-1 text-sm font-black text-slate-950">baseline individual</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">marco inicial para comparacao dos cortes e do relatorio final.</p>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-14">
          <SectionTitle
            eyebrow="Porque existe"
            title="O DNA do FROID e ampliar a leitura clinica sem substituir o profissional."
            text="A saude mental exige escuta, experiencia e sensibilidade. O FROID acrescenta uma camada tecnica capaz de observar sinais que escapam ao olho e ao ouvido humanos: microvariacoes vocais, unidades de acao facial, tensoes, assimetrias, coerencias e contradicoes entre aquilo que e dito e aquilo que o corpo expressa."
          />
          <div className="mt-8 rounded-lg border border-cyan-200 bg-cyan-50 p-6">
            <p className="text-sm leading-7 text-slate-800 md:text-base">
              O objetivo nao e automatizar a clinica. O objetivo e oferecer ao profissional uma
              segunda inteligencia de observacao: rigorosa, auditavel, multimodal e capaz de
              aprender com padroes anonimos agregados para revelar associacoes, caminhos
              terapeuticos possiveis e pontos de atencao que podem orientar a sessao.
            </p>
          </div>
        </section>

        <section className="border-y border-slate-200 bg-white">
          <div className="mx-auto max-w-7xl px-5 py-14">
            <SectionTitle
              eyebrow="Habilidades"
              title="Uma leitura integrada da expressao humana."
              text="Cada modulo do FROID observa uma camada da sessao. A potencia esta na fusao: sinais isolados ajudam, mas as correlacoes entre eles podem revelar dissonancias clinicamente relevantes."
            />
            <div className="mt-8">
              <CapabilityGrid />
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-8 px-5 py-14 lg:grid-cols-[0.95fr_1.05fr]">
          <div>
            <SectionTitle
              eyebrow="FACS / AUs"
              title="A face como matriz de unidades de acao."
              text="O FROID utiliza o mapa de AUs para apoiar a leitura de combinacoes expressivas, assimetrias e microdinamicas. A relevancia clinica surge quando a face, a voz e a narrativa apontam direcoes divergentes."
            />
            <div className="mt-7">
              <NumberList items={clinicalSignals} />
            </div>
          </div>
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <img src={auImage} alt="Mapa de unidades de acao facial FACS do FROID" className="h-full w-full object-cover" />
          </div>
        </section>

        <section className="border-y border-slate-200 bg-slate-950 text-white">
          <div className="mx-auto grid max-w-7xl gap-8 px-5 py-14 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="overflow-hidden rounded-lg border border-white/15 bg-white">
              <img src={facsImage} alt="Mapa completo FACS e AUs FROID" className="h-full w-full object-cover" />
            </div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.26em] text-cyan-200">Dissonancias</p>
              <h2 className="mt-3 text-2xl font-black leading-tight md:text-4xl">
                O aviso que importa antes da ruptura clinica.
              </h2>
              <p className="mt-4 text-sm leading-7 text-slate-200 md:text-base">
                Dissonancia nao e uma frase do paciente. E uma avaliacao tecnica entregue ao
                profissional quando o FROID detecta divergencias acima da metrica definida
                entre semantica, bioacustica, face, zonas emocionais e comportamento temporal.
              </p>
              <div className="mt-7 grid gap-3">
                {[
                  "O paciente afirma estabilidade, mas a voz apresenta tensao, pausas e sub-harmonicos elevados.",
                  "A fala indica calma, mas AUs de dor, medo ou contencao aparecem com intensidade relevante.",
                  "O tema verbal muda, mas o IDM permanece fixado em uma zona de resistencia ou risco.",
                  "O IPM aumenta sem coerencia com a narrativa, sugerindo sobrecarga ou defesa emocional.",
                ].map((item) => (
                  <p key={item} className="rounded border border-white/15 bg-white/5 p-4 text-sm leading-6 text-slate-100">
                    {item}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-14">
          <SectionTitle
            eyebrow="Inteligencia evolutiva"
            title="A base anonima transforma experiencia clinica em conhecimento agregado."
            text="Com consentimento, governanca e anonimato, os cortes e metricas das sessoes podem alimentar uma base populacional para revelar benchmarks, padroes raros, correlacoes de percurso e novas hipoteses de intervencao."
          />
          <div className="mt-8 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {systemLayers.map((layer) => (
              <div key={layer} className="rounded-lg border border-slate-200 bg-white p-4">
                <p className="text-sm font-bold leading-6 text-slate-700">{layer}</p>
              </div>
            ))}
          </div>
          <p className="mt-6 max-w-4xl text-sm leading-7 text-slate-600">
            Essa capacidade nao elimina a necessidade de validacao cientifica e supervisao
            profissional. Ela cria uma infraestrutura para que o FROID evolua com dados
            anonimos, auditoria, revisao humana e aperfeicoamento continuo dos seus modelos.
          </p>
        </section>

        <section className="border-y border-slate-200 bg-white">
          <div className="mx-auto max-w-7xl px-5 py-14">
            <SectionTitle
              eyebrow="Convite"
              title="Acesso inicial para profissionais de saude mental."
              text="Estamos abrindo o FROID para profissionais que desejam testar uma nova camada de percepcao clinica, contribuir com validacao real e participar da formacao de uma base anonima de conhecimento em saude mental."
            />
            <div className="mt-8 grid gap-4 md:grid-cols-2">
              {offers.map((offer) => (
                <article key={offer.title} className="rounded-lg border border-cyan-200 bg-cyan-50 p-6">
                  <p className="text-sm font-black uppercase tracking-[0.18em] text-cyan-800">{offer.title}</p>
                  <h3 className="mt-3 text-3xl font-black text-slate-950">{offer.value}</h3>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{offer.text}</p>
                </article>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/access/register" className="rounded bg-slate-950 px-5 py-3 text-sm font-black text-white hover:bg-cyan-700">
                Cadastrar profissional
              </Link>
              <Link to="/login" className="rounded border border-slate-300 px-5 py-3 text-sm font-black text-slate-900 hover:bg-slate-100">
                Ja tenho acesso
              </Link>
            </div>
          </div>
        </section>

        <section className="bg-slate-50">
          <div className="mx-auto max-w-7xl px-5 py-12">
            <div className="mb-5">
              <h2 className="text-2xl font-black text-slate-950">LGPD, governanca e limites clinicos</h2>
              <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-600">
                O FROID deve operar com consentimento, minimizacao de dados, segregacao de
                trilhas, registro auditavel, anonimato para pesquisa e controle formal de
                exclusao quando solicitado. As informacoes produzidas sao apoio ao profissional
                habilitado, nao diagnostico automatico.
              </p>
            </div>
            <LgpdNotice audience="home" />
          </div>
        </section>
      </main>
    </div>
  );
};
