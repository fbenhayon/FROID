import { normalizeSessionLocale, SessionLocale } from "./localization";

// Traduções dos tooltips clínicos do dashboard. O texto em pt-BR é a fonte
// de verdade e a chave de busca; EN/FR/ES são fornecidos por entrada. Quando
// não houver tradução para o locale, o texto em português é usado como
// fallback (mesmo comportamento de dashboardText).
type TooltipTranslations = Partial<Record<Exclude<SessionLocale, "pt-BR">, string>>;

const TOOLTIP_I18N: Record<string, TooltipTranslations> = {
  // ----- Sessão ao vivo: barra de métricas simplificadas -----
  "Intervalo temporal em análise desde o último corte semântico, seja automático ou executado pelo profissional.":
    {
      "en-US":
        "Time window under analysis since the last semantic cut, whether automatic or made by the professional.",
      "fr-FR":
        "Intervalle de temps analysé depuis la dernière coupe sémantique, automatique ou effectuée par le professionnel.",
      "es-ES":
        "Intervalo temporal en análisis desde el último corte semántico, sea automático o realizado por el profesional.",
    },
  "Índice de Potência Multimodal. Funciona como o velocímetro emocional: indica a intensidade global da energia vocal, facial e semântica do paciente.":
    {
      "en-US":
        "Multimodal Power Index. Works as the emotional speedometer: it shows the overall intensity of the patient's vocal, facial and semantic energy.",
      "fr-FR":
        "Indice de Puissance Multimodale. Il agit comme le compteur de vitesse émotionnel : il indique l'intensité globale de l'énergie vocale, faciale et sémantique du patient.",
      "es-ES":
        "Índice de Potencia Multimodal. Funciona como el velocímetro emocional: indica la intensidad global de la energía vocal, facial y semántica del paciente.",
    },
  "Índice de Desvio Multimodal. Indica a direção e o grau de afastamento entre voz, face, semântica e zonas FROID.":
    {
      "en-US":
        "Multimodal Deviation Index. Shows the direction and degree of divergence among voice, face, semantics and FROID zones.",
      "fr-FR":
        "Indice d'Écart Multimodal. Indique la direction et le degré d'écart entre la voix, le visage, la sémantique et les zones FROID.",
      "es-ES":
        "Índice de Desvío Multimodal. Indica la dirección y el grado de alejamiento entre voz, rostro, semántica y zonas FROID.",
    },
  "Zona FROID predominante no corte atual, calculada pela composição das métricas bioacústicas, semânticas e multimodais.":
    {
      "en-US":
        "Predominant FROID zone in the current cut, computed from the combination of bioacoustic, semantic and multimodal metrics.",
      "fr-FR":
        "Zone FROID prédominante dans la coupe actuelle, calculée à partir de la combinaison des métriques bioacoustiques, sémantiques et multimodales.",
      "es-ES":
        "Zona FROID predominante en el corte actual, calculada por la composición de las métricas bioacústicas, semánticas y multimodales.",
    },
  "Tom emocional predominante inferido pela composição entre fala transcrita, marcadores acústicos e contexto do corte.":
    {
      "en-US":
        "Predominant emotional tone inferred from the combination of transcribed speech, acoustic markers and cut context.",
      "fr-FR":
        "Tonalité émotionnelle prédominante déduite de la combinaison entre la parole transcrite, les marqueurs acoustiques et le contexte de la coupe.",
      "es-ES":
        "Tono emocional predominante inferido por la composición entre habla transcrita, marcadores acústicos y contexto del corte.",
    },
  "Palavras por minuto no corte atual. Ajuda a identificar aceleração, lentificação, bloqueios ou mudanças de cadência.":
    {
      "en-US":
        "Words per minute in the current cut. Helps identify acceleration, slowing, blocks or changes in cadence.",
      "fr-FR":
        "Mots par minute dans la coupe actuelle. Aide à repérer une accélération, un ralentissement, des blocages ou des changements de cadence.",
      "es-ES":
        "Palabras por minuto en el corte actual. Ayuda a identificar aceleración, lentificación, bloqueos o cambios de cadencia.",
    },
  "Quantidade de dissonâncias confirmadas acima da métrica definida no corte atual. Exibe somente apontamentos efetivamente detectados.":
    {
      "en-US":
        "Number of confirmed dissonances above the defined threshold in the current cut. Shows only findings that were actually detected.",
      "fr-FR":
        "Nombre de dissonances confirmées au-dessus du seuil défini dans la coupe actuelle. N'affiche que les détections effectivement relevées.",
      "es-ES":
        "Cantidad de disonancias confirmadas por encima del umbral definido en el corte actual. Muestra solo los hallazgos efectivamente detectados.",
    },
  "Coeficiente cepstral vocal associado ao timbre e à energia espectral. No FROID, ganha relevância quando cruza valência semântica negativa e marcadores de retardo ou tensão.":
    {
      "en-US":
        "Vocal cepstral coefficient associated with timbre and spectral energy. In FROID it becomes relevant when it coincides with negative semantic valence and markers of psychomotor slowing or tension.",
      "fr-FR":
        "Coefficient cepstral vocal associé au timbre et à l'énergie spectrale. Dans FROID, il devient pertinent lorsqu'il croise une valence sémantique négative et des marqueurs de ralentissement ou de tension.",
      "es-ES":
        "Coeficiente cepstral vocal asociado al timbre y a la energía espectral. En FROID cobra relevancia cuando cruza valencia semántica negativa y marcadores de retardo o tensión.",
    },
  "Coeficiente cepstral vocal usado como marcador complementar de tensão autônoma, especialmente quando observado em trechos semanticamente neutros.":
    {
      "en-US":
        "Vocal cepstral coefficient used as a complementary marker of autonomic tension, especially when observed in semantically neutral passages.",
      "fr-FR":
        "Coefficient cepstral vocal utilisé comme marqueur complémentaire de tension autonome, surtout lorsqu'il est observé dans des passages sémantiquement neutres.",
      "es-ES":
        "Coeficiente cepstral vocal usado como marcador complementario de tensión autónoma, especialmente cuando se observa en tramos semánticamente neutros.",
    },
  "Delta do MFCC7. Mede a variação de primeira ordem do coeficiente durante o corte.":
    {
      "en-US": "MFCC7 delta. Measures the first-order variation of the coefficient during the cut.",
      "fr-FR": "Delta du MFCC7. Mesure la variation de premier ordre du coefficient pendant la coupe.",
      "es-ES": "Delta del MFCC7. Mide la variación de primer orden del coeficiente durante el corte.",
    },
  "Delta do MFCC9. Mede a variação de primeira ordem do coeficiente durante o corte.":
    {
      "en-US": "MFCC9 delta. Measures the first-order variation of the coefficient during the cut.",
      "fr-FR": "Delta du MFCC9. Mesure la variation de premier ordre du coefficient pendant la coupe.",
      "es-ES": "Delta del MFCC9. Mide la variación de primer orden del coeficiente durante el corte.",
    },
  "Delta-delta do MFCC7. Indica aceleração ou desaceleração da mudança cepstral.":
    {
      "en-US": "MFCC7 delta-delta. Indicates acceleration or deceleration of the cepstral change.",
      "fr-FR": "Delta-delta du MFCC7. Indique l'accélération ou la décélération du changement cepstral.",
      "es-ES": "Delta-delta del MFCC7. Indica aceleración o desaceleración del cambio cepstral.",
    },
  "Delta-delta do MFCC9. Indica aceleração ou desaceleração da mudança cepstral.":
    {
      "en-US": "MFCC9 delta-delta. Indicates acceleration or deceleration of the cepstral change.",
      "fr-FR": "Delta-delta du MFCC9. Indique l'accélération ou la décélération du changement cepstral.",
      "es-ES": "Delta-delta del MFCC9. Indica aceleración o desaceleración del cambio cepstral.",
    },
  "Frequência fundamental média da voz. Ajuda a observar elevação de pitch, queda vocal, tensão ou variações de ativação.":
    {
      "en-US":
        "Average fundamental frequency of the voice. Helps observe pitch rise, vocal drop, tension or shifts in activation.",
      "fr-FR":
        "Fréquence fondamentale moyenne de la voix. Aide à observer une élévation du pitch, une chute vocale, une tension ou des variations d'activation.",
      "es-ES":
        "Frecuencia fundamental media de la voz. Ayuda a observar elevación de pitch, caída vocal, tensión o variaciones de activación.",
    },
  "Taxa de cruzamento por zero. Aponta irregularidade acústica e componentes de aspereza, ruído ou tensão vocal.":
    {
      "en-US":
        "Zero-crossing rate. Points to acoustic irregularity and components of harshness, noise or vocal tension.",
      "fr-FR":
        "Taux de passage par zéro. Signale une irrégularité acoustique et des composantes de rugosité, de bruit ou de tension vocale.",
      "es-ES":
        "Tasa de cruce por cero. Señala irregularidad acústica y componentes de aspereza, ruido o tensión vocal.",
    },
  "Índice interno normalizado de perturbação de frequência, derivado para comparação longitudinal no FROID. Não é percentual acústico bruto.":
    {
      "en-US":
        "Normalized internal index of frequency perturbation, derived for longitudinal comparison within FROID. It is not a raw acoustic percentage.",
      "fr-FR":
        "Indice interne normalisé de perturbation de fréquence, dérivé pour la comparaison longitudinale dans FROID. Ce n'est pas un pourcentage acoustique brut.",
      "es-ES":
        "Índice interno normalizado de perturbación de frecuencia, derivado para la comparación longitudinal en FROID. No es un porcentaje acústico bruto.",
    },
  "Índice interno normalizado de variação de amplitude vocal, derivado para comparação longitudinal no FROID. Não é medida bruta em dB.":
    {
      "en-US":
        "Normalized internal index of vocal amplitude variation, derived for longitudinal comparison within FROID. It is not a raw measure in dB.",
      "fr-FR":
        "Indice interne normalisé de variation d'amplitude vocale, dérivé pour la comparaison longitudinale dans FROID. Ce n'est pas une mesure brute en dB.",
      "es-ES":
        "Índice interno normalizado de variación de amplitud vocal, derivado para la comparación longitudinal en FROID. No es una medida bruta en dB.",
    },
  "Energia de modulação vocal na faixa delta. No FROID, representa modulação bioacústica lenta, não atividade EEG direta.":
    {
      "en-US":
        "Vocal modulation energy in the delta band. In FROID it represents slow bioacoustic modulation, not direct EEG activity.",
      "fr-FR":
        "Énergie de modulation vocale dans la bande delta. Dans FROID, elle représente une modulation bioacoustique lente, non une activité EEG directe.",
      "es-ES":
        "Energía de modulación vocal en la banda delta. En FROID representa modulación bioacústica lenta, no actividad EEG directa.",
    },
  "Energia de modulação vocal na faixa theta. Usada como marcador de oscilação lenta da expressão vocal.":
    {
      "en-US":
        "Vocal modulation energy in the theta band. Used as a marker of slow oscillation of vocal expression.",
      "fr-FR":
        "Énergie de modulation vocale dans la bande thêta. Utilisée comme marqueur d'oscillation lente de l'expression vocale.",
      "es-ES":
        "Energía de modulación vocal en la banda theta. Usada como marcador de oscilación lenta de la expresión vocal.",
    },
  "Energia de modulação vocal na faixa alpha. Ajuda a compor estabilidade, ritmo e organização da emissão.":
    {
      "en-US":
        "Vocal modulation energy in the alpha band. Helps compose stability, rhythm and organization of the vocal output.",
      "fr-FR":
        "Énergie de modulation vocale dans la bande alpha. Aide à composer la stabilité, le rythme et l'organisation de l'émission.",
      "es-ES":
        "Energía de modulación vocal en la banda alpha. Ayuda a componer estabilidad, ritmo y organización de la emisión.",
    },
  "Energia de modulação vocal na faixa beta. Ajuda a compor índices de ativação, esforço e tensão cognitiva.":
    {
      "en-US":
        "Vocal modulation energy in the beta band. Helps compose indices of activation, effort and cognitive tension.",
      "fr-FR":
        "Énergie de modulation vocale dans la bande bêta. Aide à composer des indices d'activation, d'effort et de tension cognitive.",
      "es-ES":
        "Energía de modulación vocal en la banda beta. Ayuda a componer índices de activación, esfuerzo y tensión cognitiva.",
    },
  "Energia de modulação vocal na faixa gama. Ajuda a observar ativação rápida e instabilidade espectral fina.":
    {
      "en-US":
        "Vocal modulation energy in the gamma band. Helps observe fast activation and fine spectral instability.",
      "fr-FR":
        "Énergie de modulation vocale dans la bande gamma. Aide à observer une activation rapide et une instabilité spectrale fine.",
      "es-ES":
        "Energía de modulación vocal en la banda gamma. Ayuda a observar activación rápida e inestabilidad espectral fina.",
    },
  "Índice composto das bandas espectrais vocais, usado para sintetizar o perfil de modulação bioacústica do corte.":
    {
      "en-US":
        "Composite index of the vocal spectral bands, used to summarize the bioacoustic modulation profile of the cut.",
      "fr-FR":
        "Indice composite des bandes spectrales vocales, utilisé pour synthétiser le profil de modulation bioacoustique de la coupe.",
      "es-ES":
        "Índice compuesto de las bandas espectrales vocales, usado para sintetizar el perfil de modulación bioacústica del corte.",
    },
  "Energia sub-harmônica entre 5 e 12 Hz. No FROID, integra o núcleo de leitura autônoma e sinais de sobrecarga profunda.":
    {
      "en-US":
        "Sub-harmonic energy between 5 and 12 Hz. In FROID it integrates the core autonomic reading and signals of deep overload.",
      "fr-FR":
        "Énergie sous-harmonique entre 5 et 12 Hz. Dans FROID, elle intègre le noyau de lecture autonome et les signes de surcharge profonde.",
      "es-ES":
        "Energía subarmónica entre 5 y 12 Hz. En FROID integra el núcleo de lectura autónoma y señales de sobrecarga profunda.",
    },
  "Energia sub-harmônica entre 12 e 20 Hz. Complementa a leitura de tremor, tensão e modulação involuntária.":
    {
      "en-US":
        "Sub-harmonic energy between 12 and 20 Hz. Complements the reading of tremor, tension and involuntary modulation.",
      "fr-FR":
        "Énergie sous-harmonique entre 12 et 20 Hz. Complète la lecture du tremblement, de la tension et de la modulation involontaire.",
      "es-ES":
        "Energía subarmónica entre 12 y 20 Hz. Complementa la lectura de temblor, tensión y modulación involuntaria.",
    },
  "Energia sub-harmônica entre 20 e 40 Hz. Complementa a leitura de excitação, instabilidade e microtremores vocais.":
    {
      "en-US":
        "Sub-harmonic energy between 20 and 40 Hz. Complements the reading of excitation, instability and vocal micro-tremors.",
      "fr-FR":
        "Énergie sous-harmonique entre 20 et 40 Hz. Complète la lecture de l'excitation, de l'instabilité et des micro-tremblements vocaux.",
      "es-ES":
        "Energía subarmónica entre 20 y 40 Hz. Complementa la lectura de excitación, inestabilidad y microtemblores vocales.",
    },
  "Banda basal de tensão vocal. Ajuda a identificar sustentação, constrição e esforço na base da emissão.":
    {
      "en-US":
        "Basal band of vocal tension. Helps identify sustaining, constriction and effort at the base of the vocal output.",
      "fr-FR":
        "Bande basale de tension vocale. Aide à identifier le soutien, la constriction et l'effort à la base de l'émission.",
      "es-ES":
        "Banda basal de tensión vocal. Ayuda a identificar sostén, constricción y esfuerzo en la base de la emisión.",
    },
  "Componente nuclear de infrassom vocal usado na matriz bioacústica do FROID.":
    {
      "en-US": "Core vocal infrasound component used in FROID's bioacoustic matrix.",
      "fr-FR": "Composante nucléaire d'infrason vocal utilisée dans la matrice bioacoustique de FROID.",
      "es-ES": "Componente nuclear de infrasonido vocal usado en la matriz bioacústica de FROID.",
    },
  "Componente de modulação límbica estimado pela combinação de sub-harmônicos, voz e contexto emocional.":
    {
      "en-US":
        "Limbic modulation component estimated from the combination of sub-harmonics, voice and emotional context.",
      "fr-FR":
        "Composante de modulation limbique estimée à partir de la combinaison des sous-harmoniques, de la voix et du contexte émotionnel.",
      "es-ES":
        "Componente de modulación límbica estimado por la combinación de subarmónicos, voz y contexto emocional.",
    },
  "Componente de tensão vocal basal usado para compor riscos, dissonâncias e estado de ativação.":
    {
      "en-US":
        "Basal vocal tension component used to compose risks, dissonances and activation state.",
      "fr-FR":
        "Composante de tension vocale basale utilisée pour composer les risques, les dissonances et l'état d'activation.",
      "es-ES":
        "Componente de tensión vocal basal usado para componer riesgos, disonancias y estado de activación.",
    },
  "Indicador composto de flooding autonômico, sugerindo sobrecarga ou intensificação fisiológica relevante.":
    {
      "en-US":
        "Composite indicator of autonomic flooding, suggesting overload or relevant physiological intensification.",
      "fr-FR":
        "Indicateur composite de débordement autonome (flooding), suggérant une surcharge ou une intensification physiologique notable.",
      "es-ES":
        "Indicador compuesto de flooding autonómico, sugiriendo sobrecarga o intensificación fisiológica relevante.",
    },
  "Indicador composto de retraimento ou desligamento dissociativo, quando a assinatura bioacústica sugere queda defensiva.":
    {
      "en-US":
        "Composite indicator of withdrawal or dissociative shutdown, when the bioacoustic signature suggests a defensive drop.",
      "fr-FR":
        "Indicateur composite de retrait ou de désactivation dissociative, lorsque la signature bioacoustique suggère une chute défensive.",
      "es-ES":
        "Indicador compuesto de retraimiento o apagado disociativo, cuando la firma bioacústica sugiere una caída defensiva.",
    },
  "Índice de ressonância neurogênica estimado por combinações sub-harmônicas e estabilidade vocal.":
    {
      "en-US":
        "Neurogenic resonance index estimated from sub-harmonic combinations and vocal stability.",
      "fr-FR":
        "Indice de résonance neurogène estimé à partir des combinaisons sous-harmoniques et de la stabilité vocale.",
      "es-ES":
        "Índice de resonancia neurogénica estimado por combinaciones subarmónicas y estabilidad vocal.",
    },
  "Índice de dissonância somatoafetiva, usado para cruzar expressão vocal, tensão e marcadores corporais inferidos.":
    {
      "en-US":
        "Somatoaffective dissonance index, used to cross-reference vocal expression, tension and inferred bodily markers.",
      "fr-FR":
        "Indice de dissonance somato-affective, utilisé pour croiser l'expression vocale, la tension et les marqueurs corporels inférés.",
      "es-ES":
        "Índice de disonancia somatoafectiva, usado para cruzar expresión vocal, tensión y marcadores corporales inferidos.",
    },
  "Métrica do corte atual da sessão simplificada.": {
    "en-US": "Metric of the current cut in the simplified session view.",
    "fr-FR": "Métrique de la coupe actuelle dans la vue simplifiée de la séance.",
    "es-ES": "Métrica del corte actual de la sesión simplificada.",
  },
  "O corte organiza a sessão em janelas analisáveis. A cada fechamento, o FROID consolida tema, resumo da fala, métricas vocais, indicadores bioacústicos e dissonâncias relevantes.":
    {
      "en-US":
        "The cut organizes the session into analyzable windows. At each close, FROID consolidates the theme, speech summary, vocal metrics, bioacoustic indicators and relevant dissonances.",
      "fr-FR":
        "La coupe organise la séance en fenêtres analysables. À chaque clôture, FROID consolide le thème, le résumé de la parole, les métriques vocales, les indicateurs bioacoustiques et les dissonances pertinentes.",
      "es-ES":
        "El corte organiza la sesión en ventanas analizables. En cada cierre, FROID consolida tema, resumen del habla, métricas vocales, indicadores bioacústicos y disonancias relevantes.",
    },

  // ----- Painel de transcrição: biomarcadores -----
  "MFCC7 indica componentes espectrais associados a valência negativa e risco depressivo quando se eleva em fala emocionalmente negativa.":
    {
      "en-US":
        "MFCC7 reflects spectral components associated with negative valence and depressive risk when it rises during emotionally negative speech.",
      "fr-FR":
        "Le MFCC7 traduit des composantes spectrales associées à une valence négative et à un risque dépressif lorsqu'il s'élève dans un discours émotionnellement négatif.",
      "es-ES":
        "El MFCC7 refleja componentes espectrales asociados a valencia negativa y riesgo depresivo cuando se eleva en habla emocionalmente negativa.",
    },
  "MFCC9 é acompanhado em fala neutra; quedas ou desvios podem sugerir tensão autonômica latente e ansiedade somática.":
    {
      "en-US":
        "MFCC9 is tracked in neutral speech; drops or deviations may suggest latent autonomic tension and somatic anxiety.",
      "fr-FR":
        "Le MFCC9 est suivi dans la parole neutre ; des baisses ou des écarts peuvent suggérer une tension autonome latente et une anxiété somatique.",
      "es-ES":
        "El MFCC9 se acompaña en habla neutra; caídas o desvíos pueden sugerir tensión autonómica latente y ansiedad somática.",
    },
  "Jitter no FROID é um índice proxy interno normalizado, derivado de ZCR escalado, útil para observar instabilidade vocal relativa. Não equivale diretamente ao jitter percentual normativo de Praat.":
    {
      "en-US":
        "Jitter in FROID is a normalized internal proxy index, derived from scaled ZCR, useful to observe relative vocal instability. It does not directly correspond to Praat's normative percentage jitter.",
      "fr-FR":
        "Dans FROID, le jitter est un indice proxy interne normalisé, dérivé du ZCR mis à l'échelle, utile pour observer l'instabilité vocale relative. Il ne correspond pas directement au jitter en pourcentage normatif de Praat.",
      "es-ES":
        "En FROID, el jitter es un índice proxy interno normalizado, derivado del ZCR escalado, útil para observar inestabilidad vocal relativa. No equivale directamente al jitter porcentual normativo de Praat.",
    },
  "Shimmer no FROID é um índice proxy interno normalizado da variação relativa do envelope RMS, útil para observar instabilidade de energia vocal. Não equivale diretamente ao shimmer em dB.":
    {
      "en-US":
        "Shimmer in FROID is a normalized internal proxy index of the relative variation of the RMS envelope, useful to observe vocal energy instability. It does not directly correspond to shimmer in dB.",
      "fr-FR":
        "Dans FROID, le shimmer est un indice proxy interne normalisé de la variation relative de l'enveloppe RMS, utile pour observer l'instabilité de l'énergie vocale. Il ne correspond pas directement au shimmer en dB.",
      "es-ES":
        "En FROID, el shimmer es un índice proxy interno normalizado de la variación relativa de la envolvente RMS, útil para observar inestabilidad de energía vocal. No equivale directamente al shimmer en dB.",
    },

  // ----- Carteira (Dashboard): sinais e métricas -----
  "Prioridade atual do paciente na carteira. Sobe quando há maior ativação, risco, baixa estabilidade ou necessidade de revisão.":
    {
      "en-US":
        "Patient's current priority in the caseload. Rises with greater activation, risk, low stability or need for review.",
      "fr-FR":
        "Priorité actuelle du patient dans le portefeuille. Augmente en cas d'activation accrue, de risque, de faible stabilité ou de besoin de révision.",
      "es-ES":
        "Prioridad actual del paciente en la cartera. Sube cuando hay mayor activación, riesgo, baja estabilidad o necesidad de revisión.",
    },
  "Esforço clínico estimado a partir da intensidade multimodal, dissonâncias, risco agregado e marcadores de tensão.":
    {
      "en-US":
        "Estimated clinical effort based on multimodal intensity, dissonances, aggregate risk and tension markers.",
      "fr-FR":
        "Effort clinique estimé à partir de l'intensité multimodale, des dissonances, du risque agrégé et des marqueurs de tension.",
      "es-ES":
        "Esfuerzo clínico estimado a partir de la intensidad multimodal, disonancias, riesgo agregado y marcadores de tensión.",
    },
  "Disponibilidade de conteúdo clínico interpretável: resumos, cortes, anotações e consistência semântica das sessões.":
    {
      "en-US":
        "Availability of interpretable clinical content: summaries, cuts, notes and semantic consistency across sessions.",
      "fr-FR":
        "Disponibilité de contenu clinique interprétable : résumés, coupes, notes et cohérence sémantique des séances.",
      "es-ES":
        "Disponibilidad de contenido clínico interpretable: resúmenes, cortes, anotaciones y consistencia semántica de las sesiones.",
    },
  "Grau de sustentação do acompanhamento no tempo, considerando quantidade de sessões e comparabilidade longitudinal.":
    {
      "en-US":
        "Degree of continuity of follow-up over time, considering the number of sessions and longitudinal comparability.",
      "fr-FR":
        "Degré de continuité du suivi dans le temps, compte tenu du nombre de séances et de la comparabilité longitudinale.",
      "es-ES":
        "Grado de sostenimiento del seguimiento en el tiempo, considerando la cantidad de sesiones y la comparabilidad longitudinal.",
    },
  "Índice de material analítico disponível para apoiar hipóteses clínicas, FROID Explica e revisão entre sessões.":
    {
      "en-US":
        "Index of analytical material available to support clinical hypotheses, FROID Explains and between-session review.",
      "fr-FR":
        "Indice de matériel analytique disponible pour étayer les hypothèses cliniques, FROID Explique et la révision entre les séances.",
      "es-ES":
        "Índice de material analítico disponible para apoyar hipótesis clínicas, FROID Explica y revisión entre sesiones.",
    },
  "IPM mede a intensidade global da energia emocional empregada na sessão.": {
    "en-US": "The IPM measures the overall intensity of emotional energy engaged in the session.",
    "fr-FR": "L'IPM mesure l'intensité globale de l'énergie émotionnelle mobilisée pendant la séance.",
    "es-ES": "El IPM mide la intensidad global de la energía emocional empleada en la sesión.",
  },
  "IDM aponta direção e magnitude do desequilíbrio multimodal entre voz, face, zonas e baseline.": {
    "en-US": "The IDM shows the direction and magnitude of the multimodal imbalance among voice, face, zones and baseline.",
    "fr-FR": "L'IDM indique la direction et l'ampleur du déséquilibre multimodal entre voix, visage, zones et ligne de base.",
    "es-ES": "El IDM señala dirección y magnitud del desequilibrio multimodal entre voz, rostro, zonas y baseline.",
  },
  "Zona FROID dominante observada no período analisado.": {
    "en-US": "Dominant FROID zone observed in the analyzed period.",
    "fr-FR": "Zone FROID dominante observée sur la période analysée.",
    "es-ES": "Zona FROID dominante observada en el período analizado.",
  },
  "Tom emocional inferido a partir da composição vocal e semântica.": {
    "en-US": "Emotional tone inferred from the vocal and semantic composition.",
    "fr-FR": "Tonalité émotionnelle déduite de la composition vocale et sémantique.",
    "es-ES": "Tono emocional inferido a partir de la composición vocal y semántica.",
  },
  "Palavras por minuto, usado como indicador de cadência, aceleração, lentificação ou carga discursiva.": {
    "en-US": "Words per minute, used as an indicator of cadence, acceleration, slowing or discursive load.",
    "fr-FR": "Mots par minute, utilisé comme indicateur de cadence, d'accélération, de ralentissement ou de charge discursive.",
    "es-ES": "Palabras por minuto, usado como indicador de cadencia, aceleración, lentificación o carga discursiva.",
  },
  "Quantidade de dissonâncias facial-vocais persistentes acima do limiar configurado.": {
    "en-US": "Number of persistent facial-vocal dissonances above the configured threshold.",
    "fr-FR": "Nombre de dissonances faciales-vocales persistantes au-dessus du seuil configuré.",
    "es-ES": "Cantidad de disonancias facial-vocales persistentes por encima del umbral configurado.",
  },
  "Biomarcador acústico acompanhado em contextos de valência negativa e risco depressivo quando combinado a outros sinais.": {
    "en-US": "Acoustic biomarker tracked in contexts of negative valence and depressive risk when combined with other signals.",
    "fr-FR": "Biomarqueur acoustique suivi dans des contextes de valence négative et de risque dépressif lorsqu'il est combiné à d'autres signaux.",
    "es-ES": "Biomarcador acústico acompañado en contextos de valencia negativa y riesgo depresivo cuando se combina con otras señales.",
  },
  "Biomarcador acústico relevante para tensão autônoma e ansiedade somática em fala neutra/controlada.": {
    "en-US": "Acoustic biomarker relevant to autonomic tension and somatic anxiety in neutral/controlled speech.",
    "fr-FR": "Biomarqueur acoustique pertinent pour la tension autonome et l'anxiété somatique dans une parole neutre/contrôlée.",
    "es-ES": "Biomarcador acústico relevante para tensión autónoma y ansiedad somática en habla neutra/controlada.",
  },
  "Frequência fundamental média da voz, associada a variação de pitch e ativação.": {
    "en-US": "Average fundamental frequency of the voice, associated with pitch variation and activation.",
    "fr-FR": "Fréquence fondamentale moyenne de la voix, associée à la variation du pitch et à l'activation.",
    "es-ES": "Frecuencia fundamental media de la voz, asociada a variación de pitch y activación.",
  },
  "Taxa de cruzamento por zero, relacionada a textura acústica, ruído e dinâmica vocal.": {
    "en-US": "Zero-crossing rate, related to acoustic texture, noise and vocal dynamics.",
    "fr-FR": "Taux de passage par zéro, lié à la texture acoustique, au bruit et à la dynamique vocale.",
    "es-ES": "Tasa de cruce por cero, relacionada con textura acústica, ruido y dinámica vocal.",
  },
  "Índice proxy interno normalizado, derivado de ZCR escalado, útil para observar instabilidade vocal relativa. Não equivale diretamente a jitter percentual normativo.": {
    "en-US": "Normalized internal proxy index, derived from scaled ZCR, useful to observe relative vocal instability. It does not directly correspond to normative percentage jitter.",
    "fr-FR": "Indice proxy interne normalisé, dérivé du ZCR mis à l'échelle, utile pour observer l'instabilité vocale relative. Il ne correspond pas directement au jitter en pourcentage normatif.",
    "es-ES": "Índice proxy interno normalizado, derivado del ZCR escalado, útil para observar inestabilidad vocal relativa. No equivale directamente al jitter porcentual normativo.",
  },
  "Índice proxy interno normalizado da variação relativa do envelope RMS, útil para observar instabilidade de energia vocal. Não equivale diretamente a shimmer em dB.": {
    "en-US": "Normalized internal proxy index of the relative variation of the RMS envelope, useful to observe vocal energy instability. It does not directly correspond to shimmer in dB.",
    "fr-FR": "Indice proxy interne normalisé de la variation relative de l'enveloppe RMS, utile pour observer l'instabilité de l'énergie vocale. Il ne correspond pas directement au shimmer en dB.",
    "es-ES": "Índice proxy interno normalizado de la variación relativa de la envolvente RMS, útil para observar inestabilidad de energía vocal. No equivale directamente al shimmer en dB.",
  },
  "Energia sub-harmônica de 5-12 Hz, usada para rastrear tremores autonômicos da voz.": {
    "en-US": "Sub-harmonic energy of 5-12 Hz, used to track autonomic tremors of the voice.",
    "fr-FR": "Énergie sous-harmonique de 5-12 Hz, utilisée pour suivre les tremblements autonomes de la voix.",
    "es-ES": "Energía subarmónica de 5-12 Hz, usada para rastrear temblores autonómicos de la voz.",
  },
  "Energia sub-harmônica de 12-20 Hz, complementar na leitura bioacústica e límbica.": {
    "en-US": "Sub-harmonic energy of 12-20 Hz, complementary in bioacoustic and limbic reading.",
    "fr-FR": "Énergie sous-harmonique de 12-20 Hz, complémentaire dans la lecture bioacoustique et limbique.",
    "es-ES": "Energía subarmónica de 12-20 Hz, complementaria en la lectura bioacústica y límbica.",
  },
  "Indicador médio da carteira do paciente.": {
    "en-US": "Average indicator for the patient's caseload.",
    "fr-FR": "Indicateur moyen du portefeuille du patient.",
    "es-ES": "Indicador medio de la cartera del paciente.",
  },
  "Métrica média consolidada das sessões do paciente.": {
    "en-US": "Consolidated average metric across the patient's sessions.",
    "fr-FR": "Métrique moyenne consolidée des séances du patient.",
    "es-ES": "Métrica media consolidada de las sesiones del paciente.",
  },
  "Métrica desta sessão no acompanhamento do paciente.": {
    "en-US": "Metric of this session within the patient's follow-up.",
    "fr-FR": "Métrique de cette séance dans le suivi du patient.",
    "es-ES": "Métrica de esta sesión en el seguimiento del paciente.",
  },

  // ----- Relatório da sessão: títulos de blocos -----
  "Compara o baseline inicial de 60 segundos com a média consolidada da sessão.": {
    "en-US": "Compares the initial 60-second baseline with the consolidated session average.",
    "fr-FR": "Compare la ligne de base initiale de 60 secondes avec la moyenne consolidée de la séance.",
    "es-ES": "Compara el baseline inicial de 60 segundos con la media consolidada de la sesión.",
  },
  "Gráfico normalizado pelo baseline inicial. A linha 100 representa o ponto de partida da sessão.": {
    "en-US": "Chart normalized by the initial baseline. The 100 line represents the session's starting point.",
    "fr-FR": "Graphique normalisé par la ligne de base initiale. La ligne 100 représente le point de départ de la séance.",
    "es-ES": "Gráfico normalizado por el baseline inicial. La línea 100 representa el punto de partida de la sesión.",
  },
  "Resume baseline, média, último corte, delta e escore-z das métricas evolutivas do FROID.": {
    "en-US": "Summarizes baseline, average, last cut, delta and z-score of FROID's evolving metrics.",
    "fr-FR": "Résume la ligne de base, la moyenne, la dernière coupe, le delta et le score-z des métriques évolutives de FROID.",
    "es-ES": "Resume baseline, media, último corte, delta y puntuación-z de las métricas evolutivas de FROID.",
  },
  "Permite escolher quais blocos entram na visualização e no relatório da consulta.": {
    "en-US": "Lets you choose which blocks appear in the view and in the consultation report.",
    "fr-FR": "Permet de choisir quels blocs figurent dans l'affichage et dans le rapport de consultation.",
    "es-ES": "Permite elegir qué bloques entran en la visualización y en el informe de la consulta.",
  },
  "Primeira fotografia bioacústica e multimodal da sessão, tomada após a ativação do áudio do paciente.": {
    "en-US": "First bioacoustic and multimodal snapshot of the session, taken after the patient's audio is enabled.",
    "fr-FR": "Première photographie bioacoustique et multimodale de la séance, prise après l'activation de l'audio du patient.",
    "es-ES": "Primera fotografía bioacústica y multimodal de la sesión, tomada tras la activación del audio del paciente.",
  },
  "Média consolidada dos marcadores coletados durante todo o período analisado da sessão.": {
    "en-US": "Consolidated average of the markers collected throughout the analyzed session period.",
    "fr-FR": "Moyenne consolidée des marqueurs collectés pendant toute la période analysée de la séance.",
    "es-ES": "Media consolidada de los marcadores recogidos durante todo el período analizado de la sesión.",
  },
  "Cortes temporais da sessão, incluindo cortes manuais do profissional e cortes automáticos obrigatórios a cada 10 minutos após o último corte.": {
    "en-US": "Time cuts of the session, including the professional's manual cuts and mandatory automatic cuts every 10 minutes after the last cut.",
    "fr-FR": "Coupes temporelles de la séance, y compris les coupes manuelles du professionnel et les coupes automatiques obligatoires toutes les 10 minutes après la dernière coupe.",
    "es-ES": "Cortes temporales de la sesión, incluyendo cortes manuales del profesional y cortes automáticos obligatorios cada 10 minutos tras el último corte.",
  },
  "Síntese analítica final da sessão, limitada a 300 palavras, com tema predominante de até 6 palavras.": {
    "en-US": "Final analytical synthesis of the session, limited to 300 words, with a predominant theme of up to 6 words.",
    "fr-FR": "Synthèse analytique finale de la séance, limitée à 300 mots, avec un thème prédominant d'au plus 6 mots.",
    "es-ES": "Síntesis analítica final de la sesión, limitada a 300 palabras, con tema predominante de hasta 6 palabras.",
  },
  "Resumo e métricas de cada corte temporal, alinhando tema, síntese semântica e marcadores multimodais do mesmo período.": {
    "en-US": "Summary and metrics of each time cut, aligning theme, semantic synthesis and multimodal markers from the same period.",
    "fr-FR": "Résumé et métriques de chaque coupe temporelle, alignant thème, synthèse sémantique et marqueurs multimodaux de la même période.",
    "es-ES": "Resumen y métricas de cada corte temporal, alineando tema, síntesis semántica y marcadores multimodales del mismo período.",
  },
  "Anotações clínicas registradas manualmente pelo profissional durante a sessão.": {
    "en-US": "Clinical notes recorded manually by the professional during the session.",
    "fr-FR": "Notes cliniques saisies manuellement par le professionnel pendant la séance.",
    "es-ES": "Anotaciones clínicas registradas manualmente por el profesional durante la sesión.",
  },
  "Lista apenas dissonâncias persistentes acima do limiar clínico configurado.": {
    "en-US": "Lists only persistent dissonances above the configured clinical threshold.",
    "fr-FR": "Ne liste que les dissonances persistantes au-dessus du seuil clinique configuré.",
    "es-ES": "Lista solo disonancias persistentes por encima del umbral clínico configurado.",
  },
  "Campo editável para o profissional montar texto a copiar, enviar ou futuramente imprimir.": {
    "en-US": "Editable field for the professional to compose text to copy, send or later print.",
    "fr-FR": "Champ éditable permettant au professionnel de rédiger un texte à copier, envoyer ou imprimer ultérieurement.",
    "es-ES": "Campo editable para que el profesional redacte texto para copiar, enviar o imprimir posteriormente.",
  },
  "Informação do bloco.": {
    "en-US": "Block information.",
    "fr-FR": "Information du bloc.",
    "es-ES": "Información del bloque.",
  },

  // ----- Relatório da sessão: métricas -----
  "Intervalo temporal efetivamente analisado no corte da sessão.": {
    "en-US": "Time interval effectively analyzed in the session cut.",
    "fr-FR": "Intervalle de temps effectivement analysé dans la coupe de la séance.",
    "es-ES": "Intervalo temporal efectivamente analizado en el corte de la sesión.",
  },
  "Índice de Potência Multimodal: intensidade global ou energia emocional empregada.": {
    "en-US": "Multimodal Power Index: overall intensity or emotional energy engaged.",
    "fr-FR": "Indice de Puissance Multimodale : intensité globale ou énergie émotionnelle mobilisée.",
    "es-ES": "Índice de Potencia Multimodal: intensidad global o energía emocional empleada.",
  },
  "Índice de Desvio Multimodal: direção e grau do desequilíbrio multimodal.": {
    "en-US": "Multimodal Deviation Index: direction and degree of the multimodal imbalance.",
    "fr-FR": "Indice d'Écart Multimodal : direction et degré du déséquilibre multimodal.",
    "es-ES": "Índice de Desvío Multimodal: dirección y grado del desequilibrio multimodal.",
  },
  "Zona FROID dominante no período analisado.": {
    "en-US": "Dominant FROID zone in the analyzed period.",
    "fr-FR": "Zone FROID dominante sur la période analysée.",
    "es-ES": "Zona FROID dominante en el período analizado.",
  },
  "Tema predominante consolidado da sessão ou do bloco analisado.": {
    "en-US": "Consolidated predominant theme of the session or analyzed block.",
    "fr-FR": "Thème prédominant consolidé de la séance ou du bloc analysé.",
    "es-ES": "Tema predominante consolidado de la sesión o del bloque analizado.",
  },
  "Tom emocional inferido pela combinação vocal e semântica.": {
    "en-US": "Emotional tone inferred from the vocal and semantic combination.",
    "fr-FR": "Tonalité émotionnelle déduite de la combinaison vocale et sémantique.",
    "es-ES": "Tono emocional inferido por la combinación vocal y semántica.",
  },
  "Palavras por minuto no período analisado.": {
    "en-US": "Words per minute in the analyzed period.",
    "fr-FR": "Mots par minute sur la période analysée.",
    "es-ES": "Palabras por minuto en el período analizado.",
  },
  "Quantidade de dissonâncias facial-vocais persistentes registradas.": {
    "en-US": "Number of persistent facial-vocal dissonances recorded.",
    "fr-FR": "Nombre de dissonances faciales-vocales persistantes enregistrées.",
    "es-ES": "Cantidad de disonancias facial-vocales persistentes registradas.",
  },
  "Biomarcador acústico associado a conteúdo de valência negativa e risco depressivo quando combinado a outros sinais.": {
    "en-US": "Acoustic biomarker associated with negative-valence content and depressive risk when combined with other signals.",
    "fr-FR": "Biomarqueur acoustique associé à un contenu de valence négative et à un risque dépressif lorsqu'il est combiné à d'autres signaux.",
    "es-ES": "Biomarcador acústico asociado a contenido de valencia negativa y riesgo depresivo cuando se combina con otras señales.",
  },
  "Biomarcador acústico acompanhado em fala neutra, relevante para tensão autonômica e ansiedade somática.": {
    "en-US": "Acoustic biomarker tracked in neutral speech, relevant to autonomic tension and somatic anxiety.",
    "fr-FR": "Biomarqueur acoustique suivi dans la parole neutre, pertinent pour la tension autonome et l'anxiété somatique.",
    "es-ES": "Biomarcador acústico acompañado en habla neutra, relevante para tensión autonómica y ansiedad somática.",
  },
  "Frequência fundamental média da voz no período.": {
    "en-US": "Average fundamental frequency of the voice in the period.",
    "fr-FR": "Fréquence fondamentale moyenne de la voix sur la période.",
    "es-ES": "Frecuencia fundamental media de la voz en el período.",
  },
  "Taxa de cruzamento por zero, relacionada a textura/ruído e dinâmica acústica.": {
    "en-US": "Zero-crossing rate, related to texture/noise and acoustic dynamics.",
    "fr-FR": "Taux de passage par zéro, lié à la texture/au bruit et à la dynamique acoustique.",
    "es-ES": "Tasa de cruce por cero, relacionada con textura/ruido y dinámica acústica.",
  },
  "Índice proxy interno normalizado de instabilidade vocal relativa; não equivale diretamente a jitter percentual normativo.": {
    "en-US": "Normalized internal proxy index of relative vocal instability; it does not directly correspond to normative percentage jitter.",
    "fr-FR": "Indice proxy interne normalisé d'instabilité vocale relative ; il ne correspond pas directement au jitter en pourcentage normatif.",
    "es-ES": "Índice proxy interno normalizado de inestabilidad vocal relativa; no equivale directamente al jitter porcentual normativo.",
  },
  "Índice proxy interno normalizado de variação relativa do envelope RMS; não equivale diretamente a shimmer em dB.": {
    "en-US": "Normalized internal proxy index of relative RMS-envelope variation; it does not directly correspond to shimmer in dB.",
    "fr-FR": "Indice proxy interne normalisé de la variation relative de l'enveloppe RMS ; il ne correspond pas directement au shimmer en dB.",
    "es-ES": "Índice proxy interno normalizado de variación relativa de la envolvente RMS; no equivale directamente al shimmer en dB.",
  },
  "Índice proxy interno normalizado de instabilidade vocal relativa.": {
    "en-US": "Normalized internal proxy index of relative vocal instability.",
    "fr-FR": "Indice proxy interne normalisé d'instabilité vocale relative.",
    "es-ES": "Índice proxy interno normalizado de inestabilidad vocal relativa.",
  },
  "Índice proxy interno normalizado de variação relativa do envelope RMS.": {
    "en-US": "Normalized internal proxy index of relative RMS-envelope variation.",
    "fr-FR": "Indice proxy interne normalisé de la variation relative de l'enveloppe RMS.",
    "es-ES": "Índice proxy interno normalizado de variación relativa de la envolvente RMS.",
  },
  "Energia sub-harmônica baixa, usada no cruzamento com sinais autonômicos.": {
    "en-US": "Low sub-harmonic energy, used in cross-reference with autonomic signals.",
    "fr-FR": "Énergie sous-harmonique basse, utilisée en recoupement avec les signaux autonomes.",
    "es-ES": "Energía subarmónica baja, usada en el cruce con señales autonómicas.",
  },
  "Energia sub-harmônica complementar para leitura bioacústica.": {
    "en-US": "Complementary sub-harmonic energy for bioacoustic reading.",
    "fr-FR": "Énergie sous-harmonique complémentaire pour la lecture bioacoustique.",
    "es-ES": "Energía subarmónica complementaria para la lectura bioacústica.",
  },
  "Nome da métrica estatística analisada pelo motor evolutivo.": {
    "en-US": "Name of the statistical metric analyzed by the evolving engine.",
    "fr-FR": "Nom de la métrique statistique analysée par le moteur évolutif.",
    "es-ES": "Nombre de la métrica estadística analizada por el motor evolutivo.",
  },
  "Valor inicial de referência, apurado no baseline da sessão.": {
    "en-US": "Initial reference value, measured at the session baseline.",
    "fr-FR": "Valeur de référence initiale, mesurée à la ligne de base de la séance.",
    "es-ES": "Valor inicial de referencia, medido en el baseline de la sesión.",
  },
  "Média consolidada da sessão para a métrica.": {
    "en-US": "Consolidated session average for the metric.",
    "fr-FR": "Moyenne consolidée de la séance pour la métrique.",
    "es-ES": "Media consolidada de la sesión para la métrica.",
  },
  "Valor mais recente observado nos cortes temporais.": {
    "en-US": "Most recent value observed across the time cuts.",
    "fr-FR": "Valeur la plus récente observée dans les coupes temporelles.",
    "es-ES": "Valor más reciente observado en los cortes temporales.",
  },
  "Variação percentual do último corte em relação ao baseline.": {
    "en-US": "Percentage change of the last cut relative to the baseline.",
    "fr-FR": "Variation en pourcentage de la dernière coupe par rapport à la ligne de base.",
    "es-ES": "Variación porcentual del último corte respecto al baseline.",
  },
  "Desvio padronizado do último corte em relação ao comportamento de referência.": {
    "en-US": "Standardized deviation of the last cut relative to the reference behavior.",
    "fr-FR": "Écart standardisé de la dernière coupe par rapport au comportement de référence.",
    "es-ES": "Desvío estandarizado del último corte respecto al comportamiento de referencia.",
  },
  "Alertas estatísticos ou clínicos levantados para a métrica.": {
    "en-US": "Statistical or clinical alerts raised for the metric.",
    "fr-FR": "Alertes statistiques ou cliniques signalées pour la métrique.",
    "es-ES": "Alertas estadísticas o clínicas levantadas para la métrica.",
  },
  "Índice de Potência Multimodal no motor estatístico.": {
    "en-US": "Multimodal Power Index in the statistical engine.",
    "fr-FR": "Indice de Puissance Multimodale dans le moteur statistique.",
    "es-ES": "Índice de Potencia Multimodal en el motor estadístico.",
  },
  "Índice de Desvio Multimodal no motor estatístico.": {
    "en-US": "Multimodal Deviation Index in the statistical engine.",
    "fr-FR": "Indice d'Écart Multimodal dans le moteur statistique.",
    "es-ES": "Índice de Desvío Multimodal en el motor estadístico.",
  },
  "Velocidade média de fala em palavras por minuto.": {
    "en-US": "Average speech rate in words per minute.",
    "fr-FR": "Débit de parole moyen en mots par minute.",
    "es-ES": "Velocidad media de habla en palabras por minuto.",
  },
  "Dissonância entre expressão facial e trilha vocal.": {
    "en-US": "Dissonance between facial expression and the vocal track.",
    "fr-FR": "Dissonance entre l'expression faciale et la piste vocale.",
    "es-ES": "Disonancia entre expresión facial y pista vocal.",
  },
  "Risco clínico agregado calculado pelo motor FROID.": {
    "en-US": "Aggregate clinical risk computed by the FROID engine.",
    "fr-FR": "Risque clinique agrégé calculé par le moteur FROID.",
    "es-ES": "Riesgo clínico agregado calculado por el motor FROID.",
  },
  "Modulação lenta do envelope vocal, associada a carga vegetativa basal.": {
    "en-US": "Slow modulation of the vocal envelope, associated with basal vegetative load.",
    "fr-FR": "Modulation lente de l'enveloppe vocale, associée à une charge végétative basale.",
    "es-ES": "Modulación lenta de la envolvente vocal, asociada a carga vegetativa basal.",
  },
  "Faixa de modulação lenta relacionada a flutuação afetiva e organização narrativa.": {
    "en-US": "Slow-modulation band related to affective fluctuation and narrative organization.",
    "fr-FR": "Bande de modulation lente liée à la fluctuation affective et à l'organisation narrative.",
    "es-ES": "Banda de modulación lenta relacionada con la fluctuación afectiva y la organización narrativa.",
  },
  "Faixa intermediária de estabilização autônoma e transição rítmica.": {
    "en-US": "Intermediate band of autonomic stabilization and rhythmic transition.",
    "fr-FR": "Bande intermédiaire de stabilisation autonome et de transition rythmique.",
    "es-ES": "Banda intermedia de estabilización autónoma y transición rítmica.",
  },
  "Faixa de ativação rápida ligada a tensão cognitiva, vigilância e mobilização autônoma.": {
    "en-US": "Fast-activation band linked to cognitive tension, vigilance and autonomic mobilization.",
    "fr-FR": "Bande d'activation rapide liée à la tension cognitive, à la vigilance et à la mobilisation autonome.",
    "es-ES": "Banda de activación rápida ligada a tensión cognitiva, vigilancia y movilización autónoma.",
  },
  "Faixa alta de energia espectral, interpretada como tensão fina, aspereza ou descarga rápida.": {
    "en-US": "High spectral-energy band, interpreted as fine tension, harshness or fast discharge.",
    "fr-FR": "Bande haute d'énergie spectrale, interprétée comme une tension fine, une rugosité ou une décharge rapide.",
    "es-ES": "Banda alta de energía espectral, interpretada como tensión fina, aspereza o descarga rápida.",
  },
  "Índice ponderado das bandas Delta, Theta, Alpha, Beta e Gama.": {
    "en-US": "Weighted index of the Delta, Theta, Alpha, Beta and Gamma bands.",
    "fr-FR": "Indice pondéré des bandes Delta, Thêta, Alpha, Bêta et Gamma.",
    "es-ES": "Índice ponderado de las bandas Delta, Theta, Alpha, Beta y Gamma.",
  },
  "Derivada temporal do MFCC7, comparando a janela atual com a anterior.": {
    "en-US": "Temporal derivative of MFCC7, comparing the current window with the previous one.",
    "fr-FR": "Dérivée temporelle du MFCC7, comparant la fenêtre actuelle à la précédente.",
    "es-ES": "Derivada temporal del MFCC7, comparando la ventana actual con la anterior.",
  },
  "Derivada temporal do MFCC9, comparando a janela atual com a anterior.": {
    "en-US": "Temporal derivative of MFCC9, comparing the current window with the previous one.",
    "fr-FR": "Dérivée temporelle du MFCC9, comparant la fenêtre actuelle à la précédente.",
    "es-ES": "Derivada temporal del MFCC9, comparando la ventana actual con la anterior.",
  },
  "Aceleração cepstral do MFCC7, usada para detectar mudanças abruptas no marcador.": {
    "en-US": "Cepstral acceleration of MFCC7, used to detect abrupt changes in the marker.",
    "fr-FR": "Accélération cepstrale du MFCC7, utilisée pour détecter des changements brusques du marqueur.",
    "es-ES": "Aceleración cepstral del MFCC7, usada para detectar cambios abruptos en el marcador.",
  },
  "Aceleração cepstral do MFCC9, usada para detectar mudanças abruptas no marcador.": {
    "en-US": "Cepstral acceleration of MFCC9, used to detect abrupt changes in the marker.",
    "fr-FR": "Accélération cepstrale du MFCC9, utilisée pour détecter des changements brusques du marqueur.",
    "es-ES": "Aceleración cepstral del MFCC9, usada para detectar cambios abruptos en el marcador.",
  },
  "Métrica FROID.": {
    "en-US": "FROID metric.",
    "fr-FR": "Métrique FROID.",
    "es-ES": "Métrica FROID.",
  },

  // ----- IPM (gráfico de linha) -----
  'O Papel do IPM (O "Velocímetro")': {
    "en-US": 'The role of the IPM (the "speedometer")',
    "fr-FR": 'Le rôle de l\'IPM (le « compteur de vitesse »)',
    "es-ES": 'El papel del IPM (el "velocímetro")',
  },
  'O Papel do IPM (O "Velocímetro"): enquanto o IDM aponta a direção do desequilíbrio, o IPM indica a intensidade ou energia global, servindo como velocímetro emocional. Ele é um índice composto atualizado a cada 1 segundo que funde magnitude acústica da voz, comportamento facial e substância semântica transcrita. Assim, o IPM mede quanto combustível emocional o paciente está empregando, independentemente de estar sendo coerente ou não.':
    {
      "en-US":
        'The role of the IPM (the "speedometer"): while the IDM points to the direction of the imbalance, the IPM indicates the overall intensity or energy, acting as an emotional speedometer. It is a composite index updated every second that fuses the acoustic magnitude of the voice, facial behavior and transcribed semantic substance. Thus the IPM measures how much emotional fuel the patient is spending, regardless of whether they are being coherent or not.',
      "fr-FR":
        "Le rôle de l'IPM (le « compteur de vitesse ») : alors que l'IDM indique la direction du déséquilibre, l'IPM indique l'intensité ou l'énergie globale, tel un compteur de vitesse émotionnel. C'est un indice composite mis à jour chaque seconde qui fusionne l'amplitude acoustique de la voix, le comportement facial et la substance sémantique transcrite. Ainsi, l'IPM mesure la quantité de carburant émotionnel que le patient dépense, qu'il soit cohérent ou non.",
      "es-ES":
        'El papel del IPM (el "velocímetro"): mientras el IDM señala la dirección del desequilibrio, el IPM indica la intensidad o energía global, funcionando como velocímetro emocional. Es un índice compuesto actualizado cada 1 segundo que fusiona la magnitud acústica de la voz, el comportamiento facial y la sustancia semántica transcrita. Así, el IPM mide cuánto combustible emocional está empleando el paciente, independientemente de si es coherente o no.',
    },

  // ----- Bandas neuroacústicas (gráfico) -----
  "Delta (0,5–4 Hz): oscilação lenta do envelope vocal, usada como marcador de carga vegetativa basal e de baixa variabilidade dinâmica. Valores altos sugerem lentificação e retraimento; valores baixos, maior mobilização.":
    {
      "en-US":
        "Delta (0.5–4 Hz): slow oscillation of the vocal envelope, used as a marker of basal vegetative load and low dynamic variability. High values suggest slowing and withdrawal; low values, greater mobilization.",
      "fr-FR":
        "Delta (0,5–4 Hz) : oscillation lente de l'enveloppe vocale, utilisée comme marqueur de charge végétative basale et de faible variabilité dynamique. Des valeurs élevées suggèrent un ralentissement et un retrait ; des valeurs basses, une mobilisation accrue.",
      "es-ES":
        "Delta (0,5–4 Hz): oscilación lenta de la envolvente vocal, usada como marcador de carga vegetativa basal y de baja variabilidad dinámica. Valores altos sugieren lentificación y retraimiento; valores bajos, mayor movilización.",
    },
  "Theta (4–8 Hz): componente de modulação lenta relacionado a flutuações afetivas e à organização narrativa sob esforço emocional. Realça quando o paciente elabora conteúdo emocionalmente carregado.":
    {
      "en-US":
        "Theta (4–8 Hz): slow-modulation component related to affective fluctuations and to narrative organization under emotional effort. It stands out when the patient elaborates emotionally charged content.",
      "fr-FR":
        "Thêta (4–8 Hz) : composante de modulation lente liée aux fluctuations affectives et à l'organisation narrative sous effort émotionnel. Elle ressort lorsque le patient élabore un contenu émotionnellement chargé.",
      "es-ES":
        "Theta (4–8 Hz): componente de modulación lenta relacionado con fluctuaciones afectivas y con la organización narrativa bajo esfuerzo emocional. Resalta cuando el paciente elabora contenido emocionalmente cargado.",
    },
  "Alpha (8–12 Hz): faixa de estabilização moduladora entre os ritmos lentos e a resposta autônoma mais ativa. Serve de referência de equilíbrio entre relaxamento e ativação.":
    {
      "en-US":
        "Alpha (8–12 Hz): modulating stabilization band between the slow rhythms and the more active autonomic response. It serves as a reference of balance between relaxation and activation.",
      "fr-FR":
        "Alpha (8–12 Hz) : bande de stabilisation modulatrice entre les rythmes lents et la réponse autonome plus active. Elle sert de référence d'équilibre entre relaxation et activation.",
      "es-ES":
        "Alpha (8–12 Hz): banda de estabilización moduladora entre los ritmos lentos y la respuesta autónoma más activa. Sirve de referencia de equilibrio entre relajación y activación.",
    },
  "Beta (12–30 Hz): ativação rápida associada a tensão cognitiva, vigilância, pressão articulatória e mobilização autônoma. Picos acompanham momentos de alerta, esforço ou ansiedade.":
    {
      "en-US":
        "Beta (12–30 Hz): fast activation associated with cognitive tension, vigilance, articulatory pressure and autonomic mobilization. Peaks accompany moments of alertness, effort or anxiety.",
      "fr-FR":
        "Bêta (12–30 Hz) : activation rapide associée à la tension cognitive, à la vigilance, à la pression articulatoire et à la mobilisation autonome. Les pics accompagnent les moments d'alerte, d'effort ou d'anxiété.",
      "es-ES":
        "Beta (12–30 Hz): activación rápida asociada a tensión cognitiva, vigilancia, presión articulatoria y movilización autónoma. Los picos acompañan momentos de alerta, esfuerzo o ansiedad.",
    },
  "Gama (30–80 Hz): energia espectral de alta frequência, interpretada com cautela como indicador de descarga fina, tensão e aspereza vocal. É a banda mais exploratória — leia sempre junto às demais.":
    {
      "en-US":
        "Gamma (30–80 Hz): high-frequency spectral energy, interpreted cautiously as an indicator of fine discharge, tension and vocal harshness. It is the most exploratory band — always read it alongside the others.",
      "fr-FR":
        "Gamma (30–80 Hz) : énergie spectrale de haute fréquence, interprétée avec prudence comme un indicateur de décharge fine, de tension et de rugosité vocale. C'est la bande la plus exploratoire — à lire toujours avec les autres.",
      "es-ES":
        "Gamma (30–80 Hz): energía espectral de alta frecuencia, interpretada con cautela como indicador de descarga fina, tensión y aspereza vocal. Es la banda más exploratoria — léela siempre junto a las demás.",
    },
  "Bandas neuroacústicas": {
    "en-US": "Neuroacoustic bands",
    "fr-FR": "Bandes neuroacoustiques",
    "es-ES": "Bandas neuroacústicas",
  },
  "Leitura das modulações vocais Delta, Theta, Alpha, Beta e Gama da trilha do paciente. A nomenclatura é analógica para bandas de voz, não EEG, consolidada a cada 1 segundo e cruzada com os deltas cepstrais MFCC7/MFCC9.":
    {
      "en-US":
        "Reading of the Delta, Theta, Alpha, Beta and Gamma vocal modulations from the patient's track. The nomenclature is analogical for voice bands, not EEG, consolidated every second and cross-referenced with the MFCC7/MFCC9 cepstral deltas.",
      "fr-FR":
        "Lecture des modulations vocales Delta, Thêta, Alpha, Bêta et Gamma de la piste du patient. La nomenclature est analogique pour les bandes de voix, non l'EEG, consolidée chaque seconde et croisée avec les deltas cepstraux MFCC7/MFCC9.",
      "es-ES":
        "Lectura de las modulaciones vocales Delta, Theta, Alpha, Beta y Gamma de la pista del paciente. La nomenclatura es analógica para bandas de voz, no EEG, consolidada cada 1 segundo y cruzada con los deltas cepstrales MFCC7/MFCC9.",
    },
  "Índice geral das bandas": {
    "en-US": "Overall band index",
    "fr-FR": "Indice global des bandes",
    "es-ES": "Índice general de las bandas",
  },
  "Média ponderada da energia das cinco bandas neuroacústicas em 0–100%. Sintetiza o nível global de modulação vocal do momento — útil como leitura rápida antes de detalhar banda a banda.":
    {
      "en-US":
        "Weighted average of the energy of the five neuroacoustic bands on 0–100%. It summarizes the overall level of vocal modulation at the moment — useful as a quick read before detailing band by band.",
      "fr-FR":
        "Moyenne pondérée de l'énergie des cinq bandes neuroacoustiques sur 0–100 %. Elle synthétise le niveau global de modulation vocale du moment — utile comme lecture rapide avant de détailler bande par bande.",
      "es-ES":
        "Media ponderada de la energía de las cinco bandas neuroacústicas en 0–100%. Sintetiza el nivel global de modulación vocal del momento — útil como lectura rápida antes de detallar banda a banda.",
    },
  "ΔMFCC7 — velocidade do MFCC7": {
    "en-US": "ΔMFCC7 — MFCC7 velocity",
    "fr-FR": "ΔMFCC7 — vitesse du MFCC7",
    "es-ES": "ΔMFCC7 — velocidad del MFCC7",
  },
  "Primeira derivada (taxa de variação) do coeficiente cepstral MFCC7. É o marcador que o FROID isola na fala de valência negativa: quando se eleva, contribui para o risco depressivo.":
    {
      "en-US":
        "First derivative (rate of change) of the MFCC7 cepstral coefficient. It is the marker FROID isolates in negative-valence speech: when it rises, it contributes to depressive risk.",
      "fr-FR":
        "Dérivée première (taux de variation) du coefficient cepstral MFCC7. C'est le marqueur que FROID isole dans la parole à valence négative : lorsqu'il s'élève, il contribue au risque dépressif.",
      "es-ES":
        "Primera derivada (tasa de variación) del coeficiente cepstral MFCC7. Es el marcador que FROID aísla en el habla de valencia negativa: cuando se eleva, contribuye al riesgo depresivo.",
    },
  "ΔMFCC9 — velocidade do MFCC9": {
    "en-US": "ΔMFCC9 — MFCC9 velocity",
    "fr-FR": "ΔMFCC9 — vitesse du MFCC9",
    "es-ES": "ΔMFCC9 — velocidad del MFCC9",
  },
  "Primeira derivada do coeficiente cepstral MFCC9. Quedas em discurso neutro sugerem tensão autônoma latente nas pregas vocais, associada à ansiedade somática.":
    {
      "en-US":
        "First derivative of the MFCC9 cepstral coefficient. Drops in neutral speech suggest latent autonomic tension in the vocal folds, associated with somatic anxiety.",
      "fr-FR":
        "Dérivée première du coefficient cepstral MFCC9. Des baisses dans un discours neutre suggèrent une tension autonome latente dans les plis vocaux, associée à l'anxiété somatique.",
      "es-ES":
        "Primera derivada del coeficiente cepstral MFCC9. Caídas en discurso neutro sugieren tensión autónoma latente en los pliegues vocales, asociada a la ansiedad somática.",
    },
  "ΔΔMFCC7 — aceleração do MFCC7": {
    "en-US": "ΔΔMFCC7 — MFCC7 acceleration",
    "fr-FR": "ΔΔMFCC7 — accélération du MFCC7",
    "es-ES": "ΔΔMFCC7 — aceleración del MFCC7",
  },
  "Segunda derivada do MFCC7: captura mudanças bruscas na trajetória do timbre. Realça transições rápidas de estado emocional, não apenas o nível sustentado.":
    {
      "en-US":
        "Second derivative of MFCC7: captures abrupt changes in the timbre trajectory. It highlights fast transitions of emotional state, not just the sustained level.",
      "fr-FR":
        "Dérivée seconde du MFCC7 : capte les changements brusques de la trajectoire du timbre. Elle met en évidence les transitions rapides d'état émotionnel, et pas seulement le niveau soutenu.",
      "es-ES":
        "Segunda derivada del MFCC7: capta cambios bruscos en la trayectoria del timbre. Resalta transiciones rápidas de estado emocional, no solo el nivel sostenido.",
    },
  "ΔΔMFCC9 — aceleração do MFCC9": {
    "en-US": "ΔΔMFCC9 — MFCC9 acceleration",
    "fr-FR": "ΔΔMFCC9 — accélération du MFCC9",
    "es-ES": "ΔΔMFCC9 — aceleración del MFCC9",
  },
  "Segunda derivada do MFCC9: mede a rapidez com que a tensão vocal latente muda ao longo da fala, complementando a leitura de ansiedade somática.":
    {
      "en-US":
        "Second derivative of MFCC9: measures how quickly the latent vocal tension changes over speech, complementing the reading of somatic anxiety.",
      "fr-FR":
        "Dérivée seconde du MFCC9 : mesure la rapidité avec laquelle la tension vocale latente change au fil de la parole, complétant la lecture de l'anxiété somatique.",
      "es-ES":
        "Segunda derivada del MFCC9: mide la rapidez con que la tensión vocal latente cambia a lo largo del habla, complementando la lectura de ansiedad somática.",
    },

  // ----- Sub-harmônicos (gráfico) -----
  "Infrassom Nuclear: leitura da faixa 5–12 Hz, associada a tremor profundo do Sistema Nervoso Autônomo e à ativação inconsciente. Valores altos sinalizam mobilização autonômica ainda não verbalizada.":
    {
      "en-US":
        "Nuclear Infrasound: reading of the 5–12 Hz band, associated with deep tremor of the Autonomic Nervous System and unconscious activation. High values signal autonomic mobilization not yet verbalized.",
      "fr-FR":
        "Infrason nucléaire : lecture de la bande 5–12 Hz, associée à un tremblement profond du système nerveux autonome et à une activation inconsciente. Des valeurs élevées signalent une mobilisation autonome pas encore verbalisée.",
      "es-ES":
        "Infrasonido Nuclear: lectura de la banda 5–12 Hz, asociada a temblor profundo del Sistema Nervioso Autónomo y a la activación inconsciente. Valores altos señalan movilización autonómica aún no verbalizada.",
    },
  "Modulação Límbica: faixa 12–20 Hz, usada para estimar a reatividade afetiva e a variação autônoma ligada a estados emocionais. Acompanha a intensidade da resposta emocional em curso.":
    {
      "en-US":
        "Limbic Modulation: 12–20 Hz band, used to estimate affective reactivity and the autonomic variation linked to emotional states. It tracks the intensity of the ongoing emotional response.",
      "fr-FR":
        "Modulation limbique : bande 12–20 Hz, utilisée pour estimer la réactivité affective et la variation autonome liée aux états émotionnels. Elle suit l'intensité de la réponse émotionnelle en cours.",
      "es-ES":
        "Modulación Límbica: banda 12–20 Hz, usada para estimar la reactividad afectiva y la variación autónoma ligada a estados emocionales. Acompaña la intensidad de la respuesta emocional en curso.",
    },
  "Tensão Vocal Basal: faixa 85–165 Hz, relacionada a rigidez laríngea, hipercontrole vocal e esforço de sustentação. Sobe quando o paciente contém ou controla excessivamente a fala.":
    {
      "en-US":
        "Basal Vocal Tension: 85–165 Hz band, related to laryngeal rigidity, vocal over-control and sustaining effort. It rises when the patient holds back or over-controls speech.",
      "fr-FR":
        "Tension vocale basale : bande 85–165 Hz, liée à la rigidité laryngée, au sur-contrôle vocal et à l'effort de soutien. Elle augmente lorsque le patient retient ou contrôle excessivement la parole.",
      "es-ES":
        "Tensión Vocal Basal: banda 85–165 Hz, relacionada con rigidez laríngea, hipercontrol vocal y esfuerzo de sostén. Sube cuando el paciente contiene o controla excesivamente el habla.",
    },
  "Flooding Autonômico: colisão entre a energia de 5–12 Hz e a tensão vocal basal, indicando sobrecarga neurofisiológica ativa. Sugere que o paciente pode estar sendo inundado por ativação — considere regular o ritmo da sessão.":
    {
      "en-US":
        "Autonomic Flooding: collision between the 5–12 Hz energy and the basal vocal tension, indicating active neurophysiological overload. It suggests the patient may be flooded by activation — consider regulating the session's pace.",
      "fr-FR":
        "Débordement autonome : collision entre l'énergie 5–12 Hz et la tension vocale basale, indiquant une surcharge neurophysiologique active. Cela suggère que le patient peut être submergé par l'activation — envisagez de réguler le rythme de la séance.",
      "es-ES":
        "Flooding Autonómico: colisión entre la energía de 5–12 Hz y la tensión vocal basal, indicando sobrecarga neurofisiológica activa. Sugiere que el paciente puede estar siendo inundado por activación — considere regular el ritmo de la sesión.",
    },
  "Shutdown Dissociativo: queda energética com redução de coerência, sugerindo supressão defensiva, embotamento ou retraimento autonômico. É o oposto do flooding — o paciente pode estar se desconectando.":
    {
      "en-US":
        "Dissociative Shutdown: energy drop with reduced coherence, suggesting defensive suppression, blunting or autonomic withdrawal. It is the opposite of flooding — the patient may be disconnecting.",
      "fr-FR":
        "Désactivation dissociative : chute d'énergie avec réduction de la cohérence, suggérant une suppression défensive, un émoussement ou un retrait autonome. C'est l'inverse du débordement — le patient peut être en train de se déconnecter.",
      "es-ES":
        "Shutdown Disociativo: caída energética con reducción de coherencia, sugiriendo supresión defensiva, embotamiento o retraimiento autonómico. Es lo opuesto al flooding — el paciente puede estar desconectándose.",
    },
  "Ressonância Neurogênica: faixa 20–40 Hz, associada a descarga vegetativa, regulação autônoma e reorganização neurofisiológica. Tende a acompanhar momentos de reprocessamento e alívio.":
    {
      "en-US":
        "Neurogenic Resonance: 20–40 Hz band, associated with vegetative discharge, autonomic regulation and neurophysiological reorganization. It tends to accompany moments of reprocessing and relief.",
      "fr-FR":
        "Résonance neurogène : bande 20–40 Hz, associée à la décharge végétative, à la régulation autonome et à la réorganisation neurophysiologique. Elle tend à accompagner les moments de retraitement et de soulagement.",
      "es-ES":
        "Resonancia Neurogénica: banda 20–40 Hz, asociada a descarga vegetativa, regulación autónoma y reorganización neurofisiológica. Tiende a acompañar momentos de reprocesamiento y alivio.",
    },
  "Dissonância Somatoafetiva: contraste entre a calma verbal aparente e a tensão sub-harmônica, indicando possível conflito corpo-fala — o que é dito não coincide com o que o corpo sinaliza.":
    {
      "en-US":
        "Somatoaffective Dissonance: contrast between apparent verbal calm and sub-harmonic tension, indicating a possible body-speech conflict — what is said does not match what the body signals.",
      "fr-FR":
        "Dissonance somato-affective : contraste entre le calme verbal apparent et la tension sous-harmonique, indiquant un possible conflit corps-parole — ce qui est dit ne coïncide pas avec ce que le corps signale.",
      "es-ES":
        "Disonancia Somatoafectiva: contraste entre la calma verbal aparente y la tensión subarmónica, indicando un posible conflicto cuerpo-habla — lo que se dice no coincide con lo que el cuerpo señala.",
    },
  "Sub-harmônicos vocais": {
    "en-US": "Vocal sub-harmonics",
    "fr-FR": "Sous-harmoniques vocales",
    "es-ES": "Subarmónicos vocales",
  },
  "Componentes de infra-tremor da voz nas faixas de 5 a 165 Hz, usados como pistas de ativação e regulação do Sistema Nervoso Autônomo. É o pilar mais exploratório do FROID — leia como apoio à escuta, nunca como diagnóstico isolado. Quando há sinal acústico real usa-se a medida direta; caso contrário, um proxy derivado das zonas.":
    {
      "en-US":
        "Infra-tremor components of the voice in the 5 to 165 Hz ranges, used as cues of activation and regulation of the Autonomic Nervous System. It is FROID's most exploratory pillar — read it as listening support, never as an isolated diagnosis. When a real acoustic signal exists the direct measure is used; otherwise, a proxy derived from the zones.",
      "fr-FR":
        "Composantes d'infra-tremblement de la voix dans les plages de 5 à 165 Hz, utilisées comme indices d'activation et de régulation du système nerveux autonome. C'est le pilier le plus exploratoire de FROID — à lire comme un appui à l'écoute, jamais comme un diagnostic isolé. Lorsqu'un signal acoustique réel existe, la mesure directe est utilisée ; sinon, un proxy dérivé des zones.",
      "es-ES":
        "Componentes de infra-temblor de la voz en las bandas de 5 a 165 Hz, usados como pistas de activación y regulación del Sistema Nervioso Autónomo. Es el pilar más exploratorio de FROID — léelo como apoyo a la escucha, nunca como diagnóstico aislado. Cuando hay señal acústica real se usa la medida directa; de lo contrario, un proxy derivado de las zonas.",
    },
  "Índice geral sub-harmônico": {
    "en-US": "Overall sub-harmonic index",
    "fr-FR": "Indice global sous-harmonique",
    "es-ES": "Índice general subarmónico",
  },
  "Média dos componentes sub-harmônicos em 0–100%. Resume a carga autonômica global do momento — útil para perceber tendência antes de detalhar cada componente.":
    {
      "en-US":
        "Average of the sub-harmonic components on 0–100%. It summarizes the overall autonomic load of the moment — useful to sense the trend before detailing each component.",
      "fr-FR":
        "Moyenne des composantes sous-harmoniques sur 0–100 %. Elle résume la charge autonome globale du moment — utile pour percevoir la tendance avant de détailler chaque composante.",
      "es-ES":
        "Media de los componentes subarmónicos en 0–100%. Resume la carga autonómica global del momento — útil para percibir la tendencia antes de detallar cada componente.",
    },

  // ----- Riscos clínicos (gráfico) -----
  "Risco de Depressão (Depression Risk): deriva diretamente da predição matemática da escala PHQ-9. O algoritmo isola o biomarcador MFCC7 durante a verbalização de conteúdos com valência semântica negativa. Quando este coeficiente se eleva junto a marcadores de retardo psicomotor, como ZCR, pausas prolongadas e menor variação de F0, o percentual de risco depressivo escala.":
    {
      "en-US":
        "Depression Risk: derives directly from the mathematical prediction of the PHQ-9 scale. The algorithm isolates the MFCC7 biomarker during the verbalization of content with negative semantic valence. When this coefficient rises together with markers of psychomotor slowing, such as ZCR, prolonged pauses and reduced F0 variation, the depressive-risk percentage scales up.",
      "fr-FR":
        "Risque de dépression (Depression Risk) : découle directement de la prédiction mathématique de l'échelle PHQ-9. L'algorithme isole le biomarqueur MFCC7 pendant la verbalisation de contenus à valence sémantique négative. Lorsque ce coefficient s'élève avec des marqueurs de ralentissement psychomoteur, comme le ZCR, des pauses prolongées et une moindre variation de F0, le pourcentage de risque dépressif augmente.",
      "es-ES":
        "Riesgo de Depresión (Depression Risk): deriva directamente de la predicción matemática de la escala PHQ-9. El algoritmo aísla el biomarcador MFCC7 durante la verbalización de contenidos con valencia semántica negativa. Cuando este coeficiente se eleva junto a marcadores de retardo psicomotor, como ZCR, pausas prolongadas y menor variación de F0, el porcentaje de riesgo depresivo escala.",
    },
  'Risco de Ansiedade Somática (Anxiety Risk): espelha subescalas de ansiedade e somatização da HAMD. O sistema busca o coeficiente MFCC9 em discurso "neutro"; quedas nos valores acústicos sugerem tensão autônoma latente nas pregas vocais, elevando o risco.':
    {
      "en-US":
        'Somatic Anxiety Risk: mirrors the anxiety and somatization subscales of the HAMD. The system looks for the MFCC9 coefficient in "neutral" speech; drops in the acoustic values suggest latent autonomic tension in the vocal folds, raising the risk.',
      "fr-FR":
        "Risque d'anxiété somatique (Anxiety Risk) : reflète les sous-échelles d'anxiété et de somatisation de la HAMD. Le système recherche le coefficient MFCC9 dans un discours « neutre » ; des baisses des valeurs acoustiques suggèrent une tension autonome latente dans les plis vocaux, augmentant le risque.",
      "es-ES":
        'Riesgo de Ansiedad Somática (Anxiety Risk): refleja las subescalas de ansiedad y somatización de la HAMD. El sistema busca el coeficiente MFCC9 en discurso "neutro"; caídas en los valores acústicos sugieren tensión autónoma latente en los pliegues vocales, elevando el riesgo.',
    },
  'Ativação de Mania (Mania Activation): baseada em preditores vocais da YMRS. Monitora pitch/F0 elevado, loudness, taxa acelerada de fala e fluxo espectral mais incisivo ("sharper voice").':
    {
      "en-US":
        'Mania Activation: based on vocal predictors of the YMRS. It monitors elevated pitch/F0, loudness, accelerated speech rate and a sharper spectral flux ("sharper voice").',
      "fr-FR":
        "Activation maniaque (Mania Activation) : basée sur des prédicteurs vocaux de la YMRS. Elle surveille un pitch/F0 élevé, l'intensité (loudness), un débit de parole accéléré et un flux spectral plus incisif (« sharper voice »).",
      "es-ES":
        'Activación de Manía (Mania Activation): basada en predictores vocales de la YMRS. Monitorea pitch/F0 elevado, loudness, tasa acelerada de habla y flujo espectral más incisivo ("sharper voice").',
    },
  "Estresse Cognitivo (Stress Cognitive): reflete workload contínuo. É estimado por F0 sustentado, ZCR e índices proxy internos de Jitter/Shimmer alterados, sem equivaler diretamente a medidas normativas em % ou dB.":
    {
      "en-US":
        "Cognitive Stress (Stress Cognitive): reflects continuous workload. It is estimated from sustained F0, ZCR and altered internal Jitter/Shimmer proxy indices, without directly corresponding to normative measures in % or dB.",
      "fr-FR":
        "Stress cognitif (Stress Cognitive) : reflète une charge de travail continue. Il est estimé à partir d'un F0 soutenu, du ZCR et d'indices proxy internes de Jitter/Shimmer altérés, sans correspondre directement à des mesures normatives en % ou dB.",
      "es-ES":
        "Estrés Cognitivo (Stress Cognitive): refleja workload continuo. Se estima por F0 sostenido, ZCR e índices proxy internos de Jitter/Shimmer alterados, sin equivaler directamente a medidas normativas en % o dB.",
    },
  "Risco de Dissociação e Trauma: deriva do cruzamento entre infrassom vocal e FACS. Energia sub-harmônica de 5 a 12 Hz, AU15/AU20 e tensão vocal em 85-165 Hz elevam o alerta para flooding, sobrecarga autonômica ou retraumatização.":
    {
      "en-US":
        "Dissociation and Trauma Risk: derives from the cross-reference between vocal infrasound and FACS. Sub-harmonic energy of 5 to 12 Hz, AU15/AU20 and vocal tension at 85-165 Hz raise the alert for flooding, autonomic overload or retraumatization.",
      "fr-FR":
        "Risque de dissociation et de trauma : découle du recoupement entre l'infrason vocal et le FACS. L'énergie sous-harmonique de 5 à 12 Hz, les AU15/AU20 et la tension vocale à 85-165 Hz augmentent l'alerte de débordement, de surcharge autonome ou de retraumatisation.",
      "es-ES":
        "Riesgo de Disociación y Trauma: deriva del cruce entre infrasonido vocal y FACS. Energía subarmónica de 5 a 12 Hz, AU15/AU20 y tensión vocal en 85-165 Hz elevan la alerta de flooding, sobrecarga autonómica o retraumatización.",
    },
  "Riscos clínicos": {
    "en-US": "Clinical risks",
    "fr-FR": "Risques cliniques",
    "es-ES": "Riesgos clínicos",
  },
  "Estimativa relativa de cinco padrões de risco (depressão, ansiedade somática, mania, estresse cognitivo e dissociação/trauma) a partir do cruzamento entre voz, face e zonas. Cada barra é apoio à escuta, não um diagnóstico — passe o mouse em cada risco para ver a base de cálculo e a escala de referência.":
    {
      "en-US":
        "Relative estimate of five risk patterns (depression, somatic anxiety, mania, cognitive stress and dissociation/trauma) from the cross-reference of voice, face and zones. Each bar is listening support, not a diagnosis — hover over each risk to see the basis of calculation and the reference scale.",
      "fr-FR":
        "Estimation relative de cinq schémas de risque (dépression, anxiété somatique, manie, stress cognitif et dissociation/trauma) à partir du recoupement entre voix, visage et zones. Chaque barre est un appui à l'écoute, non un diagnostic — survolez chaque risque pour voir la base de calcul et l'échelle de référence.",
      "es-ES":
        "Estimación relativa de cinco patrones de riesgo (depresión, ansiedad somática, manía, estrés cognitivo y disociación/trauma) a partir del cruce entre voz, rostro y zonas. Cada barra es apoyo a la escucha, no un diagnóstico — pasa el ratón por cada riesgo para ver la base de cálculo y la escala de referencia.",
    },
  "Índice geral de risco": {
    "en-US": "Overall risk index",
    "fr-FR": "Indice global de risque",
    "es-ES": "Índice general de riesgo",
  },
  "Média da participação relativa das cinco categorias. Dá uma leitura rápida da carga de risco global do momento; para conduta, observe qual categoria específica está elevada.":
    {
      "en-US":
        "Average of the relative share of the five categories. It gives a quick read of the overall risk load of the moment; for clinical decisions, note which specific category is elevated.",
      "fr-FR":
        "Moyenne de la part relative des cinq catégories. Elle donne une lecture rapide de la charge de risque globale du moment ; pour la conduite, observez quelle catégorie spécifique est élevée.",
      "es-ES":
        "Media de la participación relativa de las cinco categorías. Da una lectura rápida de la carga de riesgo global del momento; para la conducta, observa qué categoría específica está elevada.",
    },

  // ----- Mapa Zonal: ajuda do IDM -----
  "O Índice de Desvio Multimodal (IDM) é uma métrica central na arquitetura diagnóstica do sistema FROID, projetada para medir a direção e o grau de desequilíbrio da energia de um paciente nas 12 zonas específicas de percepção psíquica. Maiores detalhes Pergunte ao FROID.":
    {
      "en-US":
        "The Multimodal Deviation Index (IDM) is a central metric in FROID's diagnostic architecture, designed to measure the direction and degree of imbalance of a patient's energy across the 12 specific zones of psychic perception. For more details, Ask FROID.",
      "fr-FR":
        "L'Indice d'Écart Multimodal (IDM) est une métrique centrale de l'architecture diagnostique de FROID, conçue pour mesurer la direction et le degré de déséquilibre de l'énergie d'un patient dans les 12 zones spécifiques de perception psychique. Pour plus de détails, Demandez à FROID.",
      "es-ES":
        "El Índice de Desvío Multimodal (IDM) es una métrica central en la arquitectura diagnóstica de FROID, diseñada para medir la dirección y el grado de desequilibrio de la energía de un paciente en las 12 zonas específicas de percepción psíquica. Más detalles, Pregunta a FROID.",
    },
};

/**
 * Retorna o texto do tooltip no idioma do profissional. Usa o texto em
 * português como chave e fallback: se não houver tradução para o locale, o
 * próprio texto em português é devolvido.
 */
export function tooltipText(locale: unknown, portugueseText: string): string {
  const normalized = normalizeSessionLocale(locale);
  if (normalized === "pt-BR") return portugueseText;
  return TOOLTIP_I18N[portugueseText]?.[normalized] ?? portugueseText;
}
