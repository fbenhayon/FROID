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

function DarkImagePanel({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="rounded-lg border border-cyan-300/20 bg-slate-950 p-4 shadow-2xl shadow-cyan-950/30">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-black uppercase tracking-[0.2em] text-cyan-300">
          matriz visual tecnica
        </p>
        <span className="rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-xs font-black text-slate-300">
          FACS / AUs
        </span>
      </div>
      <div className="grid min-h-[320px] place-items-center rounded-md border border-white/10 bg-slate-900 p-3">
        <img src={src} alt={alt} className="h-auto max-h-[360px] w-full object-contain" />
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-400">
        Referencia visual de unidades de acao e descritores faciais. A leitura tecnica
        do FROID ocorre pela composicao temporal entre AUs, voz, semantica e baseline.
      </p>
    </div>
  );
}

const technologyStack = [
  ["STT semantico", "GPT-4o Transcribe para transcricao temporal da fala, preservando a distincao DR/PAC e alimentando tema, resumo e relatorio."],
  ["LLM explicativa", "FROID Explica com orquestracao por LLMs para responder perguntas, interpretar metricas, executar correlacoes e explicar achados tecnicos."],
  ["RAG clinico", "ChromaDB para indexacao vetorial de manuais, FACS, zonas FROID, regras internas, especificacoes tecnicas e fontes cientificas curadas."],
  ["Data Mart anonimo", "DuckDB local para cortes anonimizados, benchmarks populacionais, coortes, comparacoes longitudinais e k-anonimato."],
  ["Bioacustica", "Extracao de F0, energia, ZCR, Jitter, Shimmer, MFCC7, MFCC9, pausas, speech rate e sub-harmonicos de 5-20 Hz."],
  ["Visao facial", "FACS/AUs, intensidade A-E, simetria, onset-apex-offset, descritores de acao e composicao temporal das expressoes."],
  ["Fusao multimodal", "Normalizacao robusta por baseline, ponderacao por confiabilidade, janelas temporais e inferencia de dissonancia por divergencia entre canais."],
  ["Infraestrutura", "FastAPI, React, Docker, Caddy, WebRTC/media streams, APIs protegidas, auditoria e segregacao entre dados identificados e anonimos."],
];

const captureArchitectureItems = [
  [
    "Captura presencial dedicada",
    "O FROID admite sessao presencial com camera e microfone externos orientados ao paciente, reduzindo ruido de sala e aumentando a qualidade do vetor facial-vocal usado nos graficos.",
  ],
  [
    "Celular do paciente como sensor",
    "No modo Presencial com celular do paciente, o telefone do paciente abre o link FROID e se torna fonte dedicada de video e audio do paciente dentro do consultorio.",
  ],
  [
    "Lapela do profissional",
    "A recomendacao tecnica e que o profissional use microfone de lapela proprio. Assim, a fala do DR fica mais controlada e a trilha do celular permanece predominantemente vinculada ao paciente.",
  ],
  [
    "Separacao de trilhas",
    "A transcricao preserva a conversa DR/PAC, enquanto os biomarcadores, riscos, IPM, IDM, sub-harmonicos e dissonancias devem priorizar exclusivamente a trilha do paciente.",
  ],
  [
    "Cadastro vocal do DR",
    "A assinatura vocal do profissional pode ser cadastrada antes da consulta para apoiar a identificacao automatica e reduzir contaminacao acustica na leitura bioacustica do paciente.",
  ],
  [
    "Qualidade e confiabilidade",
    "A arquitetura pondera confiabilidade de canal: proximidade do microfone, enquadramento facial, perdas de midia, audio insuficiente e estabilidade do baseline afetam a forca dos sinais.",
  ],
];

const researchReferences = [
  ["FACS", "Ekman, Friesen e Hager: Facial Action Coding System, base para AUs, intensidade, combinacoes e codificacao temporal facial."],
  ["MFCC", "Davis e Mermelstein: representacoes cepstrais em escala Mel para modelagem espectral da fala e reconhecimento automatico."],
  ["openSMILE", "Eyben, Wollmer e Schuller: extracao automatica em larga escala de parametros acusticos para fala, musica e estados afetivos."],
  ["PHQ-9", "Kroenke, Spitzer e Williams: escala breve de gravidade depressiva, usada como matriz psicometrica para calibracao de risco depressivo."],
  ["HAM-D / HAMD", "Hamilton: escala clinica de depressao, incluindo dimensoes somaticas, ansiedade, retardo e sintomas vegetativos."],
  ["YMRS", "Young, Biggs, Ziegler e Meyer: escala de mania para severidade de ativacao, energia, fala acelerada e excitacao psicomotora."],
  ["Affective Computing", "Literatura de reconhecimento afetivo multimodal: fusao de voz, face, texto, tempo e confiabilidade de canal."],
  ["Clinimetria", "Uso de escalas como referencia, nao como substituto diagnostico: o FROID converte sinais em hipoteses auditaveis."],
];

const metricFamilies = [
  ["Voz espectral", "MFCC7, MFCC9, centroides, roll-off, fluxo espectral, energia RMS, loudness e variabilidade interjanelas."],
  ["Voz temporal", "Pausas, speech rate, palavras/minuto, ZCR, duracao de fonacao, silabacao estimada e irregularidade ritmica."],
  ["Perturbacao laringea", "Jitter, Shimmer, instabilidade ciclo-a-ciclo, F0 medio, F0 range, tremor e bandas sub-harmonicas."],
  ["Face muscular", "AU1, AU2, AU4, AU5, AU6, AU7, AU9, AU10, AU12, AU15, AU20, AU23/24, AU25/26 e combinacoes."],
  ["Semantica", "Valencia, tema em ate cinco palavras, densidade verbal, contradicao narrativa, mudanca de topico e resumo por corte."],
  ["Sessao", "Baseline de 60s, cortes de 10min, cortes profissionais, media global, delta interjanelas e tendencia longitudinal."],
];

const formulaBlocks = [
  {
    name: "Normalizacao por baseline individual",
    formula: "z_i(t) = (x_i(t) - median(x_i[0:60s])) / (MAD(x_i[0:60s]) + eps)",
    text:
      "Cada marcador e comparado ao proprio paciente, reduzindo vieses de timbre, anatomia facial, idade, habito vocal e estilo expressivo.",
  },
  {
    name: "Indice de Potencia Multimodal",
    formula: "IPM(t) = 100 * sigmoid(sum_i w_i * r_i(t) * |z_i(t)|)",
    text:
      "O IPM agrega magnitude vocal, facial e semantica ponderada por confiabilidade do canal, funcionando como medidor de energia emocional.",
  },
  {
    name: "Direcao dinamica do mapa zonal",
    formula: "IDM(t) = argmax_z P(z | V_audio(t), V_face(t), V_sem(t), B_60s)",
    text:
      "O IDM estima a zona dominante a partir da composicao probabilistica dos vetores de audio, face, semantica e baseline.",
  },
  {
    name: "Dissonancia intermodal",
    formula: "D(t) = JS(P_sem || P_face) + JS(P_sem || P_audio) + lambda * Delta_zone(t)",
    text:
      "A divergencia Jensen-Shannon entre distribuicoes semanticas, faciais e acusticas fornece uma medida de contradicao entre canais.",
  },
  {
    name: "Risco clinico calibrado",
    formula: "R_k(t) = sigmoid(beta0 + beta^T Z(t) + gamma^T C(t) + eta * H_sub(t))",
    text:
      "Riscos sao tratados como scores de apoio, combinando biomarcadores normalizados, contexto semantico e energia sub-harmonica.",
  },
  {
    name: "Confiabilidade de canal",
    formula: "r_i(t) = q_audio * q_face * q_text * (1 - missing_i(t))",
    text:
      "Baixa qualidade de microfone, oclusao facial, silencio ou perda de transcricao reduzem automaticamente a influencia do canal.",
  },
];

const professionalFlow = [
  ["1. Cadastro profissional", "O profissional completa perfil, LGPD, plano de acesso e dados operacionais para usar o FROID em sua rotina."],
  ["2. Convite ao paciente", "Cria convite, define pacote ou sessao avulsa, informa valor, PIX quando aplicavel e envia mensagem pronta pelo WhatsApp."],
  ["3. Cadastro do paciente", "O paciente acessa link, completa dados, aceita termos e entra em fluxo protegido de consentimento e identificacao."],
  ["4. Sala online", "Profissional e paciente entram em video e audio bidirecional, preservando a trilha do paciente para avaliacao FROID."],
  ["5. Monitoramento multimodal", "Durante a sessao, o profissional acompanha transcricao, biomarcadores, IPM, IDM, riscos, zonas e dissonancias."],
  ["6. Cortes e relatorio", "Cortes obrigatorios e profissionais alimentam o Relatorio da Consulta, com metricas, resumos e observacoes clinicas."],
];

const professionalLayoutItems = [
  ["Resumo profissional", "Pacientes, atencao media, carga clinica, comunicacao, continuidade e itens para revisao em leitura compacta."],
  ["Indicadores medios", "Consolida indicadores das sessoes recentes para sinalizar tendencia, estabilidade, risco e mudancas de percurso."],
  ["Pacientes e sessoes", "Acesso a historico, ultimas sessoes, relatorios, convites e detalhes individuais de cada paciente."],
  ["FROID Explica", "Segunda coluna para perguntas, revisao de metricas, correlacoes e apoio interpretativo sem sair do painel."],
];

const liveSessionItems = [
  ["Coluna 1", "Tempo de sessao, transcricao DR/PAC, tom, palavras/minuto, biomarcadores vocais, resumos por cortes e anotacoes clinicas."],
  ["Coluna 2", "Video, biofeedback facial, mapa zonal, IPM/IDM, zonas dominantes, baseline e leitura grafica da dinamica emocional."],
  ["Coluna 3", "IPM ampliado, riscos clinicos, sub-harmonicos, dissonancias, FROID Explica e paineis de investigacao interativa."],
  ["Interatividade", "Cortes profissionais, perguntas ao FROID Explica, consulta a base anonima, comparacao com baseline e registro de observacoes."],
];

const presentialSessionItems = [
  [
    "Sessao presencial com captura externa",
    "Modo indicado para consultorios com camera e microfone externos posicionados para o paciente. A captura deve priorizar rosto e voz do paciente; a voz do profissional pode ser mitigada pelo cadastro previo da voz do DR e, quando possivel, por microfone de lapela separado.",
  ],
  [
    "Presencial com celular do paciente",
    "O paciente abre o link FROID no proprio celular dentro do consultorio. O telefone funciona como camera e microfone dedicados ao paciente, aproximando a captura facial e vocal da fonte real que alimenta os graficos.",
  ],
  [
    "Microfone de lapela do profissional",
    "Quando o paciente usa o celular como captura dedicada, recomenda-se que o profissional utilize microfone de lapela proprio. Isso reduz vazamento da voz do DR na trilha do paciente e melhora a separacao entre transcricao conversacional e bioacustica do paciente.",
  ],
];

const reportItems = [
  ["Parametros iniciais", "Linha de 60 segundos com todas as metricas basais para comparacao posterior."],
  ["Medias da sessao", "Media consolidada de IPM, IDM, zona, tom, palavras/minuto, biomarcadores, sub-harmonicos e dissonancias."],
  ["Cortes da sessao", "Tabela temporal com cortes obrigatorios e profissionais, mantendo valores tecnicos abertos e legiveis."],
  ["Resumo geral", "Sintese narrativa da consulta, tema predominante, progressao dos blocos e orientacao para continuidade."],
  ["Analise individual", "Comparacao longitudinal de um paciente ao longo das sessoes."],
  ["Analise conjunta", "Discussao com pares e supervisao usando dados selecionados, anonimizados quando necessario."],
];

function ProfessionalSystemImage() {
  const nodes = [
    ["Convite", "Paciente"],
    ["Sessao", "FROID"],
    ["Cortes", "Relatorio"],
  ];
  return (
    <div className="rounded-lg border border-cyan-300/20 bg-slate-950 p-5 shadow-2xl shadow-cyan-950/30">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-300">imagem conceitual do fluxo</p>
        <span className="rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-xs font-black text-slate-300">
          profissional + paciente
        </span>
      </div>
      <div className="grid gap-4 rounded-md border border-white/10 bg-slate-900 p-4">
        {nodes.map((row, rowIndex) => (
          <div key={row.join("-")} className="grid grid-cols-[1fr_44px_1fr] items-center gap-3">
            <div className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 p-4 text-center">
              <p className="text-sm font-black text-cyan-100">{row[0]}</p>
            </div>
            <div className="flex items-center justify-center">
              <span className="h-px w-full bg-cyan-300/40" />
            </div>
            <div className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 p-4 text-center">
              <p className="text-sm font-black text-emerald-100">{row[1]}</p>
            </div>
            {rowIndex < nodes.length - 1 && (
              <div className="col-span-3 flex justify-center">
                <span className="h-8 w-px bg-white/20" />
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-400">
        Do convite ao relatorio, o FROID conecta operacao clinica, sessao online,
        inteligencia explicativa e analise longitudinal.
      </p>
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
      title="Engenharia matematica para uma clinica multimodal de altissima resolucao."
      intro="O FROID foi concebido para uma classe de problema que, ate a convergencia recente entre IA generativa, transcricao neural, visao computacional, bioacustica, bancos vetoriais e analitica local, era impraticavel em escala clinica: fundir voz, face, semantica, tempo, baseline individual, psicometria e Data Mart anonimo em um algoritmo proprietario de leitura dinamica da sessao."
    >
      <section className="mx-auto max-w-7xl px-5 py-12">
        <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-6">
          <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300">Tese tecnologica</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">
            O algoritmo FROID nasce da fusao entre clinimetria, sinais humanos e inteligencia interrogavel.
          </h2>
          <p className="mt-5 text-sm leading-7 text-slate-300 md:text-base">
            A originalidade tecnica nao esta em medir uma variavel isolada. A ruptura esta
            em compor dezenas de familias de marcadores, com confiabilidade de canal,
            normalizacao individual, janelas temporais, escalas clinicas de referencia,
            FACS/AUs, sub-harmonicos, transcricao e interpretacao por IA. O resultado e
            uma arquitetura proprietaria de suporte clinico que transforma sinais dispersos
            em hipoteses auditaveis, metricas comparaveis e perguntas respondiveis.
          </p>
        </div>
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Ferramentas e infraestrutura</p>
          <h2 className="mt-3 text-3xl font-black text-white">Stack tecnico usado para viabilizar a complexidade matematica.</h2>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {technologyStack.map(([title, text]) => (
              <TextBlock key={title} title={title} text={text} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-12">
        <p className="text-xs font-black uppercase tracking-[0.32em] text-emerald-300">Arquitetura de captura</p>
        <h2 className="mt-3 max-w-5xl text-3xl font-black leading-tight text-white">
          Presencial, online e celular do paciente como fonte dedicada de sinais.
        </h2>
        <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
          A precisao do FROID depende da qualidade das trilhas que entram no sistema.
          Por isso a engenharia de captura diferencia a conversa clinica completa da
          trilha bioacustica prioritariamente atribuida ao paciente, permitindo
          configuracoes presenciais com sensores externos ou com o proprio celular do
          paciente no consultorio.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {captureArchitectureItems.map(([title, text]) => (
            <TextBlock key={title} title={title} text={text} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-12">
        <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Fontes cientificas</p>
        <h2 className="mt-3 max-w-5xl text-3xl font-black leading-tight text-white">
          Referencias adotadas como matriz de metricas, nao como diagnostico automatico.
        </h2>
        <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
          O FROID utiliza escalas, modelos e literatura como estruturas de calibracao,
          nomenclatura e interpretabilidade. O sistema nao substitui instrumentos
          validados nem a avaliacao do especialista; ele traduz sinais da sessao em
          vetores comparaveis, explicaveis e interrogaveis.
        </p>
        <div className="mt-8">
          <DarkImagePanel src={facsImage} alt="Mapa FACS, AUs e descritores de acao integrados ao FROID" />
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {researchReferences.map(([title, text]) => (
            <div key={title} className="rounded-lg border border-white/10 bg-slate-900 p-4">
              <p className="text-sm font-black text-cyan-200">{title}</p>
              <p className="mt-2 text-sm leading-7 text-slate-300">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Familias metricas</p>
          <h2 className="mt-3 text-3xl font-black text-white">Parametros tecnicos revelados ao profissional.</h2>
          <div className="mt-8 rounded-lg border border-white/10 bg-slate-950 px-5">
            {metricFamilies.map(([label, value]) => (
              <DataRow key={label} label={label} value={value} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-12">
        <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Formulacao matematica</p>
        <h2 className="mt-3 max-w-5xl text-3xl font-black leading-tight text-white">
          Exemplos de composicao formal do algoritmo multimodal.
        </h2>
        <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
          As formulas abaixo sao uma representacao publica de alto nivel. A implementacao
          proprietaria inclui calibracao por canal, pesos condicionais, thresholds
          clinimetricos, filtros de qualidade, regularizacao temporal e auditoria de corte.
        </p>
        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          {formulaBlocks.map((block) => (
            <article key={block.name} className="rounded-lg border border-white/10 bg-slate-900 p-5">
              <h3 className="text-base font-black text-white">{block.name}</h3>
              <pre className="mt-4 overflow-x-auto rounded-md border border-cyan-300/20 bg-slate-950 p-4 text-xs font-bold leading-6 text-cyan-100">
                {block.formula}
              </pre>
              <p className="mt-4 text-sm leading-7 text-slate-300">{block.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-cyan-300/20 bg-cyan-300/5">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">FROID Explica</p>
            <h2 className="mt-3 text-3xl font-black leading-tight text-white">
              Uma inteligencia criada para dialogar com doutores, pesquisadores e especialistas.
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-300 md:text-base">
              O FROID Explica e a interface epistemica da plataforma. Ele existe para
              responder duvidas, explicar metricas, justificar alertas, recuperar fontes,
              executar correlacoes propostas pelo profissional e transformar a matematica
              multimodal em raciocinio clinico compreensivel para qualquer especialidade
              da saude mental.
            </p>
            <div className="mt-6 grid gap-3">
              {[
                "Explique por que o IPM subiu no corte 20-30min apesar de o tema verbal permanecer estavel.",
                "Correlacione AU15 + AU20 com sub-harmonicos de 5-12 Hz e mudanca de ZCR no ultimo corte.",
                "Compare o baseline de 60s com a media da sessao e aponte quais marcadores sustentam a dissonancia.",
                "Gere uma hipotese tecnica sobre divergencia entre valencia semantica positiva e tensionamento vocal.",
                "Recupere fontes cientificas usadas para MFCC, FACS, PHQ-9, HAMD ou YMRS dentro do repositorio FROID.",
              ].map((item) => (
                <p key={item} className="rounded-lg border border-white/10 bg-slate-950 p-4 text-sm leading-7 text-slate-300">
                  {item}
                </p>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-cyan-300/20 bg-slate-950 p-5">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-300">Modelo interrogavel</p>
            <div className="mt-5 grid gap-3">
              {[
                ["Entrada", "Pergunta do profissional + contexto da sessao + cortes selecionados."],
                ["Grounding", "Busca vetorial em fontes tecnicas, manuais e parametros FROID."],
                ["Analitica", "Consulta a metricas, Data Mart anonimo e series temporais autorizadas."],
                ["Resposta", "Explicacao tecnica, limites, correlacoes e proximas perguntas possiveis."],
              ].map(([title, text]) => (
                <div key={title} className="rounded border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-sm font-black text-cyan-100">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-12">
        <div className="rounded-lg border border-rose-300/20 bg-rose-400/5 p-6">
          <p className="text-xs font-black uppercase tracking-[0.28em] text-rose-200">Limite epistemologico</p>
          <h2 className="mt-3 text-2xl font-black text-white">Sofisticacao nao autoriza automatismo diagnostico.</h2>
          <p className="mt-4 text-sm leading-7 text-slate-300">
            O FROID foi desenhado para um publico altamente qualificado: doutores,
            mestres, pesquisadores, psiquiatras, psicologos, psicanalistas,
            neurocientistas, terapeutas e demais profissionais da saude mental. Sua
            linguagem pode ser tecnica porque seu usuario e sofisticado. Ainda assim,
            todo score, formula, correlacao ou alerta deve ser entendido como apoio
            investigativo e nao como sentenca clinica automatica.
          </p>
        </div>
      </section>
    </PageShell>
  );
};

export const FroidProfessionalsPage: React.FC = () => {
  return (
    <PageShell
      eyebrow="Profissionais"
      title="Da primeira mensagem ao relatorio: o fluxo clinico completo do FROID."
      intro="O FROID foi desenhado para entrar na rotina real do profissional de saude mental: convidar o paciente, realizar sessao online, capturar sinais multimodais, interagir com o FROID Explica, consultar bases anonimizadas e produzir um relatorio pos-sessao util para acompanhamento individual, supervisao e analise conjunta."
    >
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[1fr_0.9fr]">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Dinamica operacional</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">Um sistema de trabalho, nao apenas uma tela de sessao.</h2>
          <p className="mt-5 text-sm leading-7 text-slate-300">
            A experiencia do FROID comeca antes da consulta e continua depois dela. O
            profissional controla convite, pagamento, consentimento, sessao, cortes,
            relatorio, analise longitudinal e perguntas ao FROID Explica em um unico
            ecossistema clinico.
          </p>
          <div className="mt-6 grid gap-3">
            {professionalFlow.map(([title, text]) => (
              <div key={title} className="rounded-lg border border-white/10 bg-slate-900 p-4">
                <p className="text-sm font-black text-cyan-200">{title}</p>
                <p className="mt-2 text-sm leading-7 text-slate-300">{text}</p>
              </div>
            ))}
          </div>
        </div>
        <ProfessionalSystemImage />
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Layout do profissional</p>
          <h2 className="mt-3 text-3xl font-black text-white">Painel de gestao clinica, continuidade e decisao.</h2>
          <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
            O dashboard profissional organiza a visao geral da pratica: pacientes,
            sessoes, indicadores medios, itens de revisao e FROID Explica em uma segunda
            coluna. O objetivo e oferecer contexto antes de entrar na sessao, e nao
            apenas uma lista administrativa.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {professionalLayoutItems.map(([title, text]) => (
              <TextBlock key={title} title={title} text={text} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Layout da sessao</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">Consulta online com graficos, video, voz e inteligencia ativa.</h2>
          <p className="mt-5 text-sm leading-7 text-slate-300">
            Durante a sessao, profissional e paciente se veem e se ouvem. A trilha de
            audio do paciente alimenta os parametros FROID; a fala de ambos permanece
            preservada na transcricao. A interface permite cortes, anotacoes clinicas,
            perguntas ao FROID Explica e consulta a base anonima quando autorizada.
          </p>
          <div className="mt-6 grid gap-3">
            {liveSessionItems.map(([title, text]) => (
              <div key={title} className="rounded-lg border border-white/10 bg-slate-900 p-4">
                <p className="text-sm font-black text-cyan-200">{title}</p>
                <p className="mt-2 text-sm leading-7 text-slate-300">{text}</p>
              </div>
            ))}
          </div>
        </div>
        <ImagePanel src={auImage} alt="Unidades de acao facial aplicadas ao layout de sessao FROID" />
      </section>

      <section className="border-y border-emerald-300/20 bg-emerald-300/5">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-emerald-300">Atendimento presencial</p>
          <h2 className="mt-3 text-3xl font-black text-white">
            Captura dedicada ao paciente sem exigir operacao manual durante a consulta.
          </h2>
          <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
            O fluxo presencial do FROID foi desenhado para nao depender de cliques do
            profissional durante a sessao. A melhor configuracao e aquela em que a
            voz e a imagem do paciente chegam ao sistema por uma fonte dedicada, enquanto
            a fala do profissional permanece identificavel para transcricao e contexto.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {presentialSessionItems.map(([title, text]) => (
              <TextBlock key={title} title={title} text={text} />
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-white/10 bg-slate-900/70">
        <div className="mx-auto max-w-7xl px-5 py-12">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Relatorio pos-sessao</p>
          <h2 className="mt-3 text-3xl font-black text-white">Memoria tecnica para analise individual e discussao clinica conjunta.</h2>
          <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-300">
            Ao encerrar a consulta, o FROID disponibiliza um layout proprio para composicao
            do Relatorio da Consulta. O profissional seleciona o que deseja incluir:
            metricas, cortes, temas, resumos, dissonancias, observacoes e dados uteis
            para acompanhamento longitudinal ou discussao com pares.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {reportItems.map(([title, text]) => (
              <TextBlock key={title} title={title} text={text} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-12">
        <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-6">
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Analise e pesquisa</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">
            Individual, longitudinal, conjunta e anonima.
          </h2>
          <p className="mt-5 text-sm leading-7 text-slate-300 md:text-base">
            O FROID permite acompanhar um paciente ao longo de sessoes, comparar cortes
            dentro da mesma consulta, discutir relatorios com pares, consultar benchmarks
            anonimizados e propor novas correlacoes ao FROID Explica. Assim, a pratica
            individual do profissional pode dialogar com uma base populacional protegida,
            sem expor dados identificaveis do paciente.
          </p>
        </div>
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
