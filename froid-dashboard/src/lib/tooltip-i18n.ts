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
