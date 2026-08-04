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
  "ΔMFCC9 — velocidade do MFCC9": {
    "en-US": "ΔMFCC9 — MFCC9 velocity",
    "fr-FR": "ΔMFCC9 — vitesse du MFCC9",
    "es-ES": "ΔMFCC9 — velocidad del MFCC9",
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

  // ----- Sub-harmônicos (gráfico) -----
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
  "Ressonância Neurogênica: faixa 20–40 Hz, associada a descarga vegetativa, regulação autônoma e reorganização neurofisiológica. Tende a acompanhar momentos de reprocessamento e alívio.":
    {
      "en-US":
        "Neurogenic Resonance: 20–40 Hz band, associated with vegetative discharge, autonomic regulation and neurophysiological reorganization. It tends to accompany moments of reprocessing and relief.",
      "fr-FR":
        "Résonance neurogène : bande 20–40 Hz, associée à la décharge végétative, à la régulation autonome et à la réorganisation neurophysiologique. Elle tend à accompagner les moments de retraitement et de soulagement.",
      "es-ES":
        "Resonancia Neurogénica: banda 20–40 Hz, asociada a descarga vegetativa, regulación autónoma y reorganización neurofisiológica. Tiende a acompañar momentos de reprocesamiento y alivio.",
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
  "Riscos clínicos": {
    "en-US": "Clinical risks",
    "fr-FR": "Risques cliniques",
    "es-ES": "Riesgos clínicos",
  },
  "Índice geral de risco": {
    "en-US": "Overall risk index",
    "fr-FR": "Indice global de risque",
    "es-ES": "Índice general de riesgo",
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

  // ----- Mapa Zonal: descrições clínicas das 12 zonas -----
  "Lentificação psicomotora vocal: composto de MFCC7, ZCR, pausas e variação de F0, lido contra a linha de base deste paciente. O componente sobe quando o MFCC7 se eleva durante fala de valência negativa junto a fala mais lenta, pausas mais longas e menor variação de altura. A literatura associa esse padrão acústico à lentificação psicomotora descrita em quadros depressivos. Associação observada em nível de grupo na literatura; não constitui inferência sobre este paciente. A leitura clínica é do profissional.":
    {
      "en-US":
        "Vocal psychomotor slowing: a composite of MFCC7, ZCR, pauses and F0 variation, read against the patient own baseline. The component rises when MFCC7 increases during negative-valence speech alongside slower speech, longer pauses and reduced pitch variation. The literature associates this acoustic pattern with the psychomotor slowing described in depressive states. Association observed at group level in the literature; it is not an inference about this patient. The clinical reading belongs to the professional.",
      "fr-FR":
        "Ralentissement psychomoteur vocal : composite de MFCC7, ZCR, pauses et variation de F0, lu par rapport à la ligne de base du patient. La composante augmente lorsque le MFCC7 s’élève pendant un discours à valence négative, avec une parole plus lente, des pauses plus longues et une moindre variation de hauteur. La littérature associe ce motif acoustique au ralentissement psychomoteur décrit dans les états dépressifs. Association observée au niveau du groupe dans la littérature ; elle ne constitue pas une inférence sur ce patient. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Enlentecimiento psicomotor vocal: compuesto de MFCC7, ZCR, pausas y variación de F0, leído contra la línea de base del propio paciente. El componente sube cuando el MFCC7 se eleva durante habla de valencia negativa junto a habla más lenta, pausas más largas y menor variación de tono. La literatura asocia este patrón acústico al enlentecimiento psicomotor descrito en cuadros depresivos. Asociación observada a nivel de grupo en la literatura; no constituye inferencia sobre este paciente. La lectura clínica es del profesional.",
    },
  "Tensão laríngea sustentada: acompanha o coeficiente MFCC9 em fala neutra, contra a referência do próprio paciente. Quedas sustentadas nesse coeficiente são descritas na literatura como correlato acústico de tensão na musculatura laríngea. Associação observada em nível de grupo na literatura; não constitui inferência sobre este paciente. A leitura clínica é do profissional.":
    {
      "en-US":
        "Sustained laryngeal tension: tracks the MFCC9 coefficient in neutral speech against the patient own reference. Sustained drops in this coefficient are described in the literature as an acoustic correlate of tension in the laryngeal musculature. Association observed at group level in the literature; it is not an inference about this patient. The clinical reading belongs to the professional.",
      "fr-FR":
        "Tension laryngée soutenue : suit le coefficient MFCC9 dans un discours neutre, par rapport à la référence du patient. Des baisses soutenues de ce coefficient sont décrites dans la littérature comme un corrélat acoustique de la tension de la musculature laryngée. Association observée au niveau du groupe dans la littérature ; elle ne constitue pas une inférence sur ce patient. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Tensión laríngea sostenida: sigue el coeficiente MFCC9 en habla neutra, contra la referencia del propio paciente. Caídas sostenidas en este coeficiente se describen en la literatura como correlato acústico de tensión en la musculatura laríngea. Asociación observada a nivel de grupo en la literatura; no constituye inferencia sobre este paciente. La lectura clínica es del profesional.",
    },
  "Ativação prosódica: composto de F0, loudness e taxa de fala, com fluxo espectral mais incisivo. Mede elevação simultânea de altura, intensidade e velocidade em relação à linha de base deste paciente. Associação observada em nível de grupo na literatura; não constitui inferência sobre este paciente. A leitura clínica é do profissional.":
    {
      "en-US":
        "Prosodic activation: a composite of F0, loudness and speech rate, with sharper spectral flux. It measures simultaneous rises in pitch, intensity and speed relative to this patient baseline. Association observed at group level in the literature; it is not an inference about this patient. The clinical reading belongs to the professional.",
      "fr-FR":
        "Activation prosodique : composite de F0, d’intensité sonore et de débit de parole, avec un flux spectral plus incisif. Elle mesure l’élévation simultanée de la hauteur, de l’intensité et de la vitesse par rapport à la ligne de base du patient. Association observée au niveau du groupe dans la littérature ; elle ne constitue pas une inférence sur ce patient. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Activación prosódica: compuesto de F0, loudness y tasa de habla, con flujo espectral más incisivo. Mide la elevación simultánea de tono, intensidad y velocidad respecto a la línea de base de este paciente. Asociación observada a nivel de grupo en la literatura; no constituye inferencia sobre este paciente. La lectura clínica es del profesional.",
    },
  "Esforço vocal sustentado: composto de F0 sustentado, ZCR e os índices proxy de jitter e shimmer. Descreve carga articulatória contínua. Os índices são estimativas por quadros e não equivalem a medidas normativas de laboratório em % ou dB.":
    {
      "en-US":
        "Sustained vocal effort: a composite of sustained F0, ZCR and the proxy jitter and shimmer indices. It describes continuous articulatory load. The indices are frame-based estimates and are not equivalent to normative laboratory measurements in % or dB.",
      "fr-FR":
        "Effort vocal soutenu : composite de F0 soutenue, de ZCR et des indices proxy de jitter et de shimmer. Il décrit une charge articulatoire continue. Les indices sont des estimations par trames et n’équivalent pas à des mesures normatives de laboratoire en % ou dB.",
      "es-ES":
        "Esfuerzo vocal sostenido: compuesto de F0 sostenida, ZCR y los índices proxy de jitter y shimmer. Describe carga articulatoria continua. Los índices son estimaciones por cuadros y no equivalen a medidas normativas de laboratorio en % o dB.",
    },
  "Assinatura sub-harmônica com retração facial: cruzamento entre energia sub-harmônica de 5 a 12 Hz, as Unidades de Ação AU15 e AU20 e tensão vocal na faixa de 85 a 165 Hz. Mede co-ocorrência entre canais, não estado interno. Associação observada em nível de grupo na literatura; não constitui inferência sobre este paciente. A leitura clínica é do profissional.":
    {
      "en-US":
        "Sub-harmonic signature with facial retraction: a cross-reference between sub-harmonic energy from 5 to 12 Hz, Action Units AU15 and AU20, and vocal tension in the 85 to 165 Hz range. It measures co-occurrence across channels, not internal state. Association observed at group level in the literature; it is not an inference about this patient. The clinical reading belongs to the professional.",
      "fr-FR":
        "Signature sous-harmonique avec rétraction faciale : croisement entre l’énergie sous-harmonique de 5 à 12 Hz, les Unités d’Action AU15 et AU20 et la tension vocale dans la plage de 85 à 165 Hz. Elle mesure la co-occurrence entre canaux, et non un état interne. Association observée au niveau du groupe dans la littérature ; elle ne constitue pas une inférence sur ce patient. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Firma subarmónica con retracción facial: cruce entre energía subarmónica de 5 a 12 Hz, las Unidades de Acción AU15 y AU20 y tensión vocal en la franja de 85 a 165 Hz. Mide co-ocurrencia entre canales, no estado interno. Asociación observada a nivel de grupo en la literatura; no constituye inferencia sobre este paciente. La lectura clínica es del profesional.",
    },
  "Padrões de sinal":
    {
      "en-US":
        "Signal patterns",
      "fr-FR":
        "Motifs de signal",
      "es-ES":
        "Patrones de señal",
    },
  "Intensidade agregada":
    {
      "en-US":
        "Aggregate intensity",
      "fr-FR":
        "Intensité agrégée",
      "es-ES":
        "Intensidad agregada",
    },
  "Participação relativa de cinco padrões acústicos e faciais medidos, a partir do cruzamento entre voz, face e zonas, sempre contra a linha de base deste paciente. Nenhuma barra nomeia condição clínica nem constitui diagnóstico: passe o mouse em cada padrão para ver quais sinais o compõem e o que a literatura associa a ele.":
    {
      "en-US":
        "Relative share of five measured acoustic and facial patterns, from the cross-reference among voice, face and zones, always against the patient own baseline. No bar names a clinical condition and none constitutes a diagnosis: hover over each pattern to see which signals compose it and what the literature associates with it.",
      "fr-FR":
        "Part relative de cinq motifs acoustiques et faciaux mesurés, issus du croisement entre la voix, le visage et les zones, toujours par rapport à la ligne de base du patient. Aucune barre ne nomme une condition clinique ni ne constitue un diagnostic : survolez chaque motif pour voir quels signaux le composent et ce que la littérature y associe.",
      "es-ES":
        "Participación relativa de cinco patrones acústicos y faciales medidos, a partir del cruce entre voz, rostro y zonas, siempre contra la línea de base de este paciente. Ninguna barra nombra condición clínica ni constituye diagnóstico: pase el ratón por cada patrón para ver qué señales lo componen y qué asocia la literatura.",
    },
  "Média da participação relativa dos cinco padrões. Dá uma leitura rápida da carga de sinal do momento; para detalhar, observe qual padrão específico está elevado.":
    {
      "en-US":
        "Average relative share of the five patterns. It gives a quick reading of the signal load at the moment; to detail it, look at which specific pattern is elevated.",
      "fr-FR":
        "Moyenne de la part relative des cinq motifs. Elle donne une lecture rapide de la charge de signal du moment ; pour détailler, regardez quel motif précis est élevé.",
      "es-ES":
        "Media de la participación relativa de los cinco patrones. Da una lectura rápida de la carga de señal del momento; para detallar, observe qué patrón específico está elevado.",
    },
  "Zona 1 — Reconhecimento. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a reconhecimento e validacao. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 1 — Recognition. It aggregates vocal, facial and semantic signals associated in the FROID model with recognition and validation. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 1 — Reconnaissance. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a la reconnaissance et la validation. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 1 — Reconocimiento. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a reconocimiento y validacion. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 2 — Ruminacao. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a circuitos repetitivos de pensamento e fadiga mental. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 2 — Rumination. It aggregates vocal, facial and semantic signals associated in the FROID model with repetitive thought loops and mental fatigue. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 2 — Rumination. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a des boucles de pensee repetitives et une fatigue mentale. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 2 — Rumiacion. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a circuitos repetitivos de pensamiento y fatiga mental. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 3 — Ancoragem no passado. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a conteudo verbal ancorado em eventos passados. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 3 — Anchoring in the past. It aggregates vocal, facial and semantic signals associated in the FROID model with verbal content anchored in past events. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 3 — Ancrage dans le passe. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a un contenu verbal ancre dans des evenements passes. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 3 — Anclaje en el pasado. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a contenido verbal anclado en eventos pasados. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 4 — Distanciamento afetivo. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a distanciamento entre relato e expressao afetiva. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 4 — Affective distancing. It aggregates vocal, facial and semantic signals associated in the FROID model with distance between report and affective expression. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 4 — Distanciation affective. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a une distance entre le recit et l'expression affective. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 4 — Distanciamiento afectivo. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a distancia entre el relato y la expresion afectiva. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 5 — Autocritica. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a foco verbal em falhas e defeitos proprios. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 5 — Self-criticism. It aggregates vocal, facial and semantic signals associated in the FROID model with verbal focus on one's own flaws. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 5 — Autocritique. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a une focalisation verbale sur ses propres defauts. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 5 — Autocritica. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a foco verbal en los propios defectos. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 6 — Vinculo condicional. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a exigencia e controle na descricao de vinculos. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 6 — Conditional bonding. It aggregates vocal, facial and semantic signals associated in the FROID model with demand and control in describing bonds. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 6 — Lien conditionnel. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a de l'exigence et du controle dans la description des liens. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 6 — Vinculo condicional. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a exigencia y control al describir vinculos. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 7 — Raiva defensiva. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a irritacao sustentada com tensao muscular captavel. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 7 — Defensive anger. It aggregates vocal, facial and semantic signals associated in the FROID model with sustained irritation with detectable muscular tension. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 7 — Colere defensive. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a une irritation soutenue avec tension musculaire detectable. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 7 — Ira defensiva. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a irritacion sostenida con tension muscular captable. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 8 — Passividade. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a posicao passiva diante dos proprios eventos. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 8 — Passivity. It aggregates vocal, facial and semantic signals associated in the FROID model with a passive stance towards one's own events. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 8 — Passivite. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a une posture passive face a ses propres evenements. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 8 — Pasividad. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a posicion pasiva ante los propios eventos. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 9 — Negacao de sentimentos. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a supressao verbal do que a expressao sinaliza. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 9 — Suppression of feelings. It aggregates vocal, facial and semantic signals associated in the FROID model with verbal suppression of what the expression signals. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 9 — Suppression des sentiments. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a la suppression verbale de ce que l'expression signale. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 9 — Negacion de sentimientos. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a supresion verbal de lo que la expresion senala. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 10 — Merecimento. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a desqualificacao do proprio merecimento. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 10 — Deservingness. It aggregates vocal, facial and semantic signals associated in the FROID model with disqualification of one's own deservingness. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 10 — Merite. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a la disqualification de son propre merite. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 10 — Merecimiento. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a descalificacion del propio merecimiento. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 11 — Rigidez cognitiva. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a regras absolutas e baixa tolerancia a ambiguidade. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 11 — Cognitive rigidity. It aggregates vocal, facial and semantic signals associated in the FROID model with absolute rules and low tolerance for ambiguity. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 11 — Rigidite cognitive. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a des regles absolues et une faible tolerance a l'ambiguite. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 11 — Rigidez cognitiva. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a reglas absolutas y baja tolerancia a la ambiguedad. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Zona 12 — Incongruencia desejo-crenca. Agrega sinais vocais, faciais e semanticos associados no modelo FROID a divergencia entre o desejo declarado e a crenca expressa. Desvio sustentado indica concentracao do sinal nesta regiao, sempre contra a linha de base do proprio paciente. O tema da zona e uma dimensao do modelo FROID, nao uma conclusao sobre a pessoa. A leitura clinica e do profissional.":
    {
      "en-US":
        "Zone 12 — Desire-belief incongruence. It aggregates vocal, facial and semantic signals associated in the FROID model with divergence between stated desire and expressed belief. A sustained deviation indicates concentration of the signal in this region, always against the patient own baseline. The zone theme is a dimension of the FROID model, not a conclusion about the person. The clinical reading belongs to the professional.",
      "fr-FR":
        "Zone 12 — Incongruence desir-croyance. Elle agrege des signaux vocaux, faciaux et semantiques associes dans le modele FROID a une divergence entre le desir declare et la croyance exprimee. Un ecart soutenu indique une concentration du signal dans cette region, toujours par rapport a la ligne de base du patient. Le theme de la zone est une dimension du modele FROID, et non une conclusion sur la personne. La lecture clinique appartient au professionnel.",
      "es-ES":
        "Zona 12 — Incongruencia deseo-creencia. Agrega senales vocales, faciales y semanticas asociadas en el modelo FROID a divergencia entre el deseo declarado y la creencia expresada. Una desviacion sostenida indica concentracion de la senal en esta region, siempre contra la linea de base del propio paciente. El tema de la zona es una dimension del modelo FROID, no una conclusion sobre la persona. La lectura clinica es del profesional.",
    },
  "Infrassom nuclear: energia medida na faixa de 5 a 12 Hz da envoltoria vocal. Valores altos indicam elevacao dessa banda contra a referencia do paciente. Nao mede atividade do sistema nervoso autonomo nem conteudo nao verbalizado.":
    {
      "en-US":
        "Nuclear infrasound: energy measured in the 5 to 12 Hz band of the vocal envelope. High values indicate a rise in this band against the patient reference. It does not measure autonomic nervous system activity nor unverbalised content.",
      "fr-FR":
        "Infrason nucleaire : energie mesuree dans la bande de 5 a 12 Hz de l'enveloppe vocale. Des valeurs elevees indiquent une hausse de cette bande par rapport a la reference du patient. Elle ne mesure ni l'activite du systeme nerveux autonome ni un contenu non verbalise.",
      "es-ES":
        "Infrasonido nuclear: energia medida en la banda de 5 a 12 Hz de la envolvente vocal. Valores altos indican elevacion de esa banda contra la referencia del paciente. No mide actividad del sistema nervioso autonomo ni contenido no verbalizado.",
    },
  "Elevacao multimodal simultanea: coincidencia entre a energia de 5 a 12 Hz e a tensao vocal basal na mesma janela. Mede co-ocorrencia entre canais, nao estado interno, e nao indica conduta.":
    {
      "en-US":
        "Simultaneous multimodal rise: coincidence between the 5 to 12 Hz energy and basal vocal tension in the same window. It measures co-occurrence across channels, not internal state, and does not indicate any course of action.",
      "fr-FR":
        "Elevation multimodale simultanee : coincidence entre l'energie de 5 a 12 Hz et la tension vocale basale dans la meme fenetre. Elle mesure la co-occurrence entre canaux, et non un etat interne, et n'indique aucune conduite.",
      "es-ES":
        "Elevacion multimodal simultanea: coincidencia entre la energia de 5 a 12 Hz y la tension vocal basal en la misma ventana. Mide co-ocurrencia entre canales, no estado interno, y no indica conducta.",
    },
  "Queda multimodal sustentada: reducao simultanea de energia expressiva e de coerencia entre canais, contra a linha de base do paciente. E o inverso do padrao de elevacao simultanea.":
    {
      "en-US":
        "Sustained multimodal drop: simultaneous reduction of expressive energy and of coherence across channels, against the patient baseline. It is the inverse of the simultaneous rise pattern.",
      "fr-FR":
        "Baisse multimodale soutenue : reduction simultanee de l'energie expressive et de la coherence entre canaux, par rapport a la ligne de base du patient. C'est l'inverse du motif d'elevation simultanee.",
      "es-ES":
        "Caida multimodal sostenida: reduccion simultanea de energia expresiva y de coherencia entre canales, contra la linea de base del paciente. Es el inverso del patron de elevacion simultanea.",
    },
  "Divergencia entre canais: contraste entre a calma medida na fala e a tensao medida na faixa sub-harmonica, na mesma janela. Mede divergencia entre canais, nao conteudo reprimido.":
    {
      "en-US":
        "Divergence across channels: contrast between the calm measured in speech and the tension measured in the sub-harmonic band, within the same window. It measures divergence across channels, not repressed content.",
      "fr-FR":
        "Divergence entre canaux : contraste entre le calme mesure dans la parole et la tension mesuree dans la bande sous-harmonique, dans la meme fenetre. Elle mesure une divergence entre canaux, et non un contenu refoule.",
      "es-ES":
        "Divergencia entre canales: contraste entre la calma medida en el habla y la tension medida en la banda subarmonica, en la misma ventana. Mide divergencia entre canales, no contenido reprimido.",
    },
  "MFCC7: coeficiente cepstral do envelope espectral. O FROID acompanha sua elevacao durante fala de valencia negativa. A literatura associa esse padrao a lentificacao psicomotora. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "MFCC7: cepstral coefficient of the spectral envelope. FROID tracks its rise during negative-valence speech. The literature associates this pattern with psychomotor slowing. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "MFCC7 : coefficient cepstral de l'enveloppe spectrale. FROID suit son elevation pendant un discours a valence negative. La litterature associe ce motif au ralentissement psychomoteur. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "MFCC7: coeficiente cepstral de la envolvente espectral. FROID sigue su elevacion durante habla de valencia negativa. La literatura asocia ese patron al enlentecimiento psicomotor. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
    },
  "MFCC9: coeficiente cepstral acompanhado em fala neutra, contra a referencia do proprio paciente. Quedas sustentadas sao descritas na literatura como correlato acustico de tensao laringea. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "MFCC9: cepstral coefficient tracked in neutral speech against the patient own reference. Sustained drops are described in the literature as an acoustic correlate of laryngeal tension. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "MFCC9 : coefficient cepstral suivi dans un discours neutre, par rapport a la reference du patient. Des baisses soutenues sont decrites dans la litterature comme un correlat acoustique de la tension laryngee. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "MFCC9: coeficiente cepstral seguido en habla neutra, contra la referencia del propio paciente. Caidas sostenidas se describen en la literatura como correlato acustico de tension laringea. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
    },
  "Beta (12-30 Hz): energia nessa faixa de modulacao da envoltoria vocal. Nao corresponde a ritmo cortical de EEG — a homonimia e coincidencia de nomenclatura de faixa. Picos indicam elevacao contra a referencia do paciente. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "Beta (12-30 Hz): energy in this modulation band of the vocal envelope. It does not correspond to an EEG cortical rhythm; the shared name is a coincidence of frequency-band nomenclature. Peaks indicate a rise against the patient reference. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "Beta (12-30 Hz) : energie dans cette bande de modulation de l'enveloppe vocale. Elle ne correspond pas a un rythme cortical d'EEG ; l'homonymie est une coincidence de nomenclature de bande. Les pics indiquent une hausse par rapport a la reference du patient. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "Beta (12-30 Hz): energia en esa banda de modulacion de la envolvente vocal. No corresponde a ritmo cortical de EEG; la homonimia es coincidencia de nomenclatura de banda. Los picos indican elevacion contra la referencia del paciente. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
    },
  "Indicador composto de elevacao multimodal simultanea: varios canais medidos sobem juntos na mesma janela.":
    {
      "en-US":
        "Composite indicator of a simultaneous multimodal rise: several measured channels increase together within the same window.",
      "fr-FR":
        "Indicateur composite d'elevation multimodale simultanee : plusieurs canaux mesures augmentent ensemble dans la meme fenetre.",
      "es-ES":
        "Indicador compuesto de elevacion multimodal simultanea: varios canales medidos suben juntos en la misma ventana.",
    },
  "Indicador composto de queda multimodal sustentada: varios canais medidos caem juntos, com reducao de coerencia entre eles.":
    {
      "en-US":
        "Composite indicator of a sustained multimodal drop: several measured channels fall together, with reduced coherence among them.",
      "fr-FR":
        "Indicateur composite de baisse multimodale soutenue : plusieurs canaux mesures diminuent ensemble, avec une coherence reduite entre eux.",
      "es-ES":
        "Indicador compuesto de caida multimodal sostenida: varios canales medidos caen juntos, con reduccion de coherencia entre ellos.",
    },
  "Primeira derivada do coeficiente cepstral MFCC7: a taxa de variacao do coeficiente ao longo do tempo. O FROID a acompanha em fala de valencia negativa. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "First derivative of the MFCC7 cepstral coefficient: the rate of change of the coefficient over time. FROID tracks it during negative-valence speech. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "Derivee premiere du coefficient cepstral MFCC7 : le taux de variation du coefficient au cours du temps. FROID la suit dans un discours a valence negative. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "Primera derivada del coeficiente cepstral MFCC7: la tasa de variacion del coeficiente a lo largo del tiempo. FROID la sigue en habla de valencia negativa. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
    },
  "Primeira derivada do coeficiente cepstral MFCC9: taxa de variacao ao longo do tempo. Quedas em discurso neutro sao descritas na literatura como correlato de tensao laringea. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "First derivative of the MFCC9 cepstral coefficient: rate of change over time. Drops in neutral speech are described in the literature as a correlate of laryngeal tension. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "Derivee premiere du coefficient cepstral MFCC9 : taux de variation au cours du temps. Les baisses dans un discours neutre sont decrites dans la litterature comme un correlat de la tension laryngee. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "Primera derivada del coeficiente cepstral MFCC9: tasa de variacion a lo largo del tiempo. Caidas en discurso neutro se describen en la literatura como correlato de tension laringea. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
    },
  "Segunda derivada do MFCC9: a aceleracao da variacao do coeficiente ao longo da fala. Descreve dinamica do sinal, e complementa a leitura da primeira derivada. Associacao descrita na literatura em nivel de grupo; nao constitui inferencia sobre este paciente.":
    {
      "en-US":
        "Second derivative of MFCC9: the acceleration of the coefficient variation across speech. It describes signal dynamics and complements the first-derivative reading. Association described in the literature at group level; it is not an inference about this patient.",
      "fr-FR":
        "Derivee seconde du MFCC9 : l'acceleration de la variation du coefficient au fil de la parole. Elle decrit la dynamique du signal et complete la lecture de la derivee premiere. Association decrite dans la litterature au niveau du groupe ; elle ne constitue pas une inference sur ce patient.",
      "es-ES":
        "Segunda derivada del MFCC9: la aceleracion de la variacion del coeficiente a lo largo del habla. Describe dinamica de la senal y complementa la lectura de la primera derivada. Asociacion descrita en la literatura a nivel de grupo; no constituye inferencia sobre este paciente.",
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
