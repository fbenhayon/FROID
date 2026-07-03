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

      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-12 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.32em] text-cyan-300">Fontes cientificas</p>
          <h2 className="mt-3 text-3xl font-black leading-tight text-white">Referencias adotadas como matriz de metricas, nao como diagnostico automatico.</h2>
          <p className="mt-5 text-sm leading-7 text-slate-300">
            O FROID utiliza escalas, modelos e literatura como estruturas de calibracao,
            nomenclatura e interpretabilidade. O sistema nao substitui instrumentos
            validados nem a avaliacao do especialista; ele traduz sinais da sessao em
            vetores comparaveis, explicaveis e interrogaveis.
          </p>
          <div className="mt-6 grid gap-3">
            {researchReferences.map(([title, text]) => (
              <div key={title} className="rounded-lg border border-white/10 bg-slate-900 p-4">
                <p className="text-sm font-black text-cyan-200">{title}</p>
                <p className="mt-2 text-sm leading-7 text-slate-300">{text}</p>
              </div>
            ))}
          </div>
        </div>
        <DarkImagePanel src={facsImage} alt="Mapa FACS, AUs e descritores de acao integrados ao FROID" />
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
