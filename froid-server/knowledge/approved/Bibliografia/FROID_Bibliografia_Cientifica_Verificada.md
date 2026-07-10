# FROID - Bibliografia Cientifica Verificada

Fonte original: FROID_Bibliografia_Cientifica_Verificada.xlsx.
Status de curadoria: approved.
Area: Bibliografia cientifica; Bioacustica; FACS; IPM/IDM; STT/IA; LGPD.
Uso no FROID Explica: base cientifica citavel. Citar somente referencias diretamente relacionadas ao tema da pergunta.

## FROID — Sustentação Científica por Pilar Tecnológico

Verificação independente por Claude — DOIs conferidos, Zhao et al. 2022 lido na íntegra na fonte original

### 1. Depressão e Retardo Psicomotor (PMR)

- Forca da evidencia: Strong
- Sustentacao cientifica: F0 menos variável, mais pausas, fala mais lenta em deprimidos; MFCC4/7 correlacionam com PHQ-9; correlações replicadas em múltiplos estudos independentes.
- Ressalva ou limite: Mesmos achados (prosódia achatada, F0 reduzida) aparecem também em Parkinson, DFT, ELA e esquizofrenia — não é um marcador específico de depressão isoladamente.
- Citacoes-chave: Zhao 2022; Taguchi 2018; Quatieri & Malyska 2012; Wadle 2024; Nilsonne 1988; Cohen 2024; Williamson 2013
- Recomendacao de enquadramento: Afirmar com confiança, citando Zhao et al. 2022 como estudo-âncora. Reconhecer explicitamente que é transdiagnóstico (reforça rigor científico).

### 2. MFCC e Derivadas (Delta/Delta-Delta)

- Forca da evidencia: Strong
- Sustentacao cientifica: MFCC discrimina depressão (Zhao: 89,66% acurácia; Taguchi: sens. 77,8%/espec. 86,1%); delta-MFCC captura dinâmica temporal ausente no coeficiente estático.
- Ressalva ou limite: Deltas nem sempre superam MFCC estático — depende da tarefa e do classificador (Pangestu 2025).
- Citacoes-chave: Zhao 2022; Taguchi 2018; Palo 2017; Ruckchopsanti 2025; Williamson 2013
- Recomendacao de enquadramento: Pode manter a engenharia matemática (fonte-filtro, DCT, deltas) como está — é processamento de sinal padrão, não precisa de ressalva.

### 3. Prosódia na Mania / Bipolaridade (YMRS)

- Forca da evidencia: Moderate
- Sustentacao cientifica: F0 dinâmico e velocidade de fala mudam com o estado de humor; protocolo CALIBER (2024) correlaciona atributos vocais com YMRS/HDRS.
- Ressalva ou limite: Evidência preliminar/protocolar, forte variabilidade intra e interindividual; Pal et al. 2025 NÃO encontrou diferença significativa em F0/jitter/shimmer entre mania, depressão e eutimia.
- Citacoes-chave: Guidi 2015; Anmella (CALIBER) 2024; Pal 2025 (resultado negativo)
- Recomendacao de enquadramento: Apresentar como 'correlação emergente monitorada longitudinalmente', não como limiar diagnóstico validado.

### 4. Dinâmica Facial (FACS + HMM)

- Forca da evidencia: Strong (infraestrutura) / Weak (dissimulação via AU6)
- Sustentacao cientifica: Modelagem de onset/apex/offset de AUs com HMM/HSMM é metodologia madura e bem estabelecida na visão computacional.
- Ressalva ou limite: Nenhum estudo do corpus valida especificamente 'AU6 ausente = dissimulação'. Pesquisa recente (2020) desafia a própria hipótese do sorriso de Duchenne como marcador de autenticidade.
- Citacoes-chave: Valstar & Pantic 2012; Jiang 2014; Gonzalez 2015; Hamm 2011; Kawulok 2021
- Recomendacao de enquadramento: Manter a infraestrutura técnica (FACS, HMM, onset/apex/offset) como fato. Reformular 'detecção de dissimulação' como hipótese de trabalho proprietária, não achado consolidado.

### 5. Micro-tremor Vocal 4–15 Hz (autonômico)

- Forca da evidencia: Weak
- Sustentacao cientifica: Existe literatura real sobre microtremor vocal fisiológico (Schoentgen 2002) e sobre F0/jitter/shimmer reagindo a estresse em geral.
- Ressalva ou limite: Nenhuma fonte valida o vínculo específico entre a faixa 4–15 Hz e ativação autonômica/estresse psiquiátrico em tempo real. Meta-análises mostram heterogeneidade alta e viés de publicação.
- Citacoes-chave: Schoentgen 2002; Schewski 2025; De Lacerda Veiga 2025; Calić 2022
- Recomendacao de enquadramento: É o pilar que precisa de mais cautela no site — apresentar como camada experimental/exploratória, não como biomarcador validado.

### 6. 12 Zonas Psíquicas (Hz → emoção)

- Forca da evidencia: 
- Sustentacao cientifica: A física acústica por trás (FFT, densidade espectral de potência) é real e mensurável.
- Ressalva ou limite: O mapeamento específico de faixas de Hz/notas musicais para dicotomias emocionais não tem nenhuma fonte revisada por pares — segue o padrão de frequências solfeggio/chakra, e a origem real é a tecnologia comercial de biofeedback EVOX/ZYTO.
- Citacoes-chave: — (sem citação científica aplicável)
- Recomendacao de enquadramento: Declarar explicitamente como 'Heurística de Apoio Visual Proprietária FROID', nunca como neurociência validada.

## FROID — Bibliografia Verificada (citação pronta para rodapé)

As referencias abaixo foram estruturadas para uso do FROID Explica como base cientifica citavel.

### Zhao, Q., Fan, H.-Z., Li, Y., Liu, L., Wu, Y.-X., Zhao, Y.-L., Tian, Z., Wang, Z.-R., Tan, Y., & Tan, S. (2022). Vocal A

- Pilar: 1
- Referencia: Zhao, Q., Fan, H.-Z., Li, Y., Liu, L., Wu, Y.-X., Zhao, Y.-L., Tian, Z., Wang, Z.-R., Tan, Y., & Tan, S. (2022). Vocal Acoustic Features as Potential Biomarkers for Identifying/Diagnosing Depression: A Cross-Sectional Study.
- Ano: 2022
- Periodico: Frontiers in Psychiatry
- DOI: 10.3389/fpsyt.2022.815678
- Amostra/Populacao: 71 deprimidos, 62 controles (n=133)
- Achado principal aplicavel ao FROID: MFCC7 prediz PHQ-9 (β=0.90, p=0.01); MFCC9 correlaciona com HAMD ansiedade/somatização (r=-0.34, β=-0.45, p=0.049); ZCR correlaciona com HAMA somática (r=0.34); acurácia discriminante 89,66%.
- Forca da evidencia: Strong
- Verificacao: Lido na íntegra por Claude na fonte original — números conferem exatamente

### Taguchi, T., Tachikawa, H., Nemoto, K., Suzuki, M., Nagano, T., Tachibana, R., Nishimura, M., & Arai, T. (2018). Major d

- Pilar: 1/2
- Referencia: Taguchi, T., Tachikawa, H., Nemoto, K., Suzuki, M., Nagano, T., Tachibana, R., Nishimura, M., & Arai, T. (2018). Major depressive disorder discrimination using vocal acoustic features.
- Ano: 2018
- Periodico: Journal of Affective Disorders
- DOI: 10.1016/j.jad.2017.08.038
- Amostra/Populacao: MDD vs. controles
- Achado principal aplicavel ao FROID: MFCC2 discrimina depressão com sensibilidade 77,8% e especificidade 86,1%.
- Forca da evidencia: Strong
- Verificacao: Confirmado via busca independente

### Quatieri, T., & Malyska, N. (2012). Vocal-Source Biomarkers for Depression: A Link to Psychomotor Activity

- Pilar: 1
- Referencia: Quatieri, T., & Malyska, N. (2012). Vocal-Source Biomarkers for Depression: A Link to Psychomotor Activity.
- Ano: 2012
- Periodico: Interspeech
- DOI: 10.21437/interspeech.2012-311
- Amostra/Populacao: 35 sujeitos; HAMD, QIDS
- Achado principal aplicavel ao FROID: Biomarcadores da fonte vocal correlacionam com atividade psicomotora e severidade depressiva.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Wadle, L.-M. et al. (2024). Speech Features as Predictors of Momentary Depression Severity in Patients With Depressive D

- Pilar: 1
- Referencia: Wadle, L.-M. et al. (2024). Speech Features as Predictors of Momentary Depression Severity in Patients With Depressive Disorder Undergoing Sleep Deprivation Therapy.
- Ano: 2024
- Periodico: JMIR Mental Health
- DOI: 10.2196/49222
- Amostra/Populacao: 30 pacientes, 716 gravações repetidas
- Achado principal aplicavel ao FROID: Variabilidade de pitch, pausas e taxa de fala associadas à gravidade momentânea da depressão.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Nilsonne, Å. (1988). Speech characteristics as indicators of depressive illness

- Pilar: 1
- Referencia: Nilsonne, Å. (1988). Speech characteristics as indicators of depressive illness.
- Ano: 1988
- Periodico: Acta Psychiatrica Scandinavica
- DOI: 10.1111/j.1600-0447.1988.tb05118.x
- Amostra/Populacao: 28 deprimidos, 13 controles
- Achado principal aplicavel ao FROID: Estudo clássico: variáveis de F0 menores e pausas resposta-pergunta mais longas em deprimidos.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Cohen, A.S. et al. (2024). Evaluating speech latencies during structured psychiatric interviews as an automated objectiv

- Pilar: 1
- Referencia: Cohen, A.S. et al. (2024). Evaluating speech latencies during structured psychiatric interviews as an automated objective measure of psychomotor slowing.
- Ano: 2024
- Periodico: Psychiatry Research
- DOI: 10.1016/j.psychres.2024.116104
- Amostra/Populacao: 274 sujeitos bipolar I depressivo (MADRS)
- Achado principal aplicavel ao FROID: Latência de fala explica quase 1/3 da variância de depressão; cai com melhora clínica; AUC > 0,85.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Williamson, J., Quatieri, T., Helfer, B.S., Horwitz, R., Yu, B., & Mehta, D.D. (2013). Vocal biomarkers of depression ba

- Pilar: 1/2
- Referencia: Williamson, J., Quatieri, T., Helfer, B.S., Horwitz, R., Yu, B., & Mehta, D.D. (2013). Vocal biomarkers of depression based on motor incoordination.
- Ano: 2013
- Periodico: Proc. 3rd ACM AVEC Workshop
- DOI: 10.1145/2512530.2512531
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Mudanças na coordenação entre canais delta-mel-cepstrum refletem coordenação do trato vocal associada a MDD.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Skodda, S., Rinsche, H., & Schlegel, U. (2009). Progression of dysprosody in Parkinson's disease over time

- Pilar: 1-caveat
- Referencia: Skodda, S., Rinsche, H., & Schlegel, U. (2009). Progression of dysprosody in Parkinson's disease over time.
- Ano: 2009
- Periodico: Movement Disorders
- DOI: 10.1002/mds.22430
- Amostra/Populacao: Estudo longitudinal, Parkinson
- Achado principal aplicavel ao FROID: F0 variability reduzida também em Parkinson — reforça que o marcador é transdiagnóstico, não específico de depressão.
- Forca da evidencia: Moderate
- Verificacao: Presente no corpus do usuário (Consensus) — usar como ressalva de especificidade

### Berardi, M. et al. (2023). Relative importance of speech and voice features in the classification of schizophrenia and d

- Pilar: 1-caveat
- Referencia: Berardi, M. et al. (2023). Relative importance of speech and voice features in the classification of schizophrenia and depression.
- Ano: 2023
- Periodico: Translational Psychiatry
- DOI: 10.1038/s41398-023-02594-0
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Prosódia achatada também discrimina esquizofrenia — mesmo tipo de marcador, população diferente.
- Forca da evidencia: Moderate
- Verificacao: Presente no corpus do usuário (Consensus) — usar como ressalva de especificidade

### Guidi, A., Vanello, N., Bertschy, G., Gentili, C., Landini, L., & Scilingo, E. (2015). Automatic analysis of speech F0 c

- Pilar: 3
- Referencia: Guidi, A., Vanello, N., Bertschy, G., Gentili, C., Landini, L., & Scilingo, E. (2015). Automatic analysis of speech F0 contour for the characterization of mood changes in bipolar patients.
- Ano: 2015
- Periodico: Biomedical Signal Processing and Control
- DOI: 10.1016/j.bspc.2014.10.011
- Amostra/Populacao: Pacientes bipolares, modelo intraindivíduo
- Achado principal aplicavel ao FROID: Mudanças significativas na dinâmica de F0 entre estados de humor (mania/depressão/eutimia).
- Forca da evidencia: Moderate
- Verificacao: Presente no corpus do usuário (Consensus)

### Anmella, G. et al. (2024). Automated Speech Analysis in Bipolar Disorder: The CALIBER Study Protocol and Preliminary Res

- Pilar: 3
- Referencia: Anmella, G. et al. (2024). Automated Speech Analysis in Bipolar Disorder: The CALIBER Study Protocol and Preliminary Results.
- Ano: 2024
- Periodico: Journal of Clinical Medicine
- DOI: 10.3390/jcm13174997
- Amostra/Populacao: YMRS médio 22,9 na mania; HDRS-17
- Achado principal aplicavel ao FROID: Protocolo correlaciona taxa de fala, pitch e loudness com YMRS/HDRS — resultados preliminares.
- Forca da evidencia: Moderate
- Verificacao: Presente no corpus do usuário (Consensus) — é protocolo, não validação final

### Pal, A., Jotdar, A., Shukla, R., & Soni, A. (2025). Assessment of Voice Parameters of Symptomatic and Remitted Patients 

- Pilar: 3-contra
- Referencia: Pal, A., Jotdar, A., Shukla, R., & Soni, A. (2025). Assessment of Voice Parameters of Symptomatic and Remitted Patients of Bipolar Disorder.
- Ano: 2025
- Periodico: Annals of Indian Psychiatry
- DOI: 10.4103/aip.aip_221_24
- Amostra/Populacao: BPAD sintomático e remitido
- Achado principal aplicavel ao FROID: NÃO encontrou diferença significativa em F0, intensidade, jitter ou shimmer entre mania, depressão e eutimia.
- Forca da evidencia: Weak/Negativo
- Verificacao: Presente no corpus do usuário — resultado contrário, incluir por honestidade científica

### Valstar, M., & Pantic, M. (2012). Fully Automatic Recognition of the Temporal Phases of Facial Actions

- Pilar: 4
- Referencia: Valstar, M., & Pantic, M. (2012). Fully Automatic Recognition of the Temporal Phases of Facial Actions.
- Ano: 2012
- Periodico: IEEE Trans. Systems, Man, and Cybernetics, Part B
- DOI: 10.1109/tsmcb.2011.2163710
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Reconhece 22 AUs e modela neutral/onset/apex/offset com SVM+HMM.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Jiang, B., Valstar, M., Martínez, B., & Pantic, M. (2014). A Dynamic Appearance Descriptor Approach to Facial Actions Te

- Pilar: 4
- Referencia: Jiang, B., Valstar, M., Martínez, B., & Pantic, M. (2014). A Dynamic Appearance Descriptor Approach to Facial Actions Temporal Modeling.
- Ano: 2014
- Periodico: IEEE Transactions on Cybernetics
- DOI: 10.1109/tcyb.2013.2249063
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Informação dinâmica e modelos de Markov melhoram a detecção de segmentos de AU.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Gonzalez, I., Cartella, F., Enescu, V., & Sahli, H. (2015). Recognition of facial actions and their temporal segments ba

- Pilar: 4
- Referencia: Gonzalez, I., Cartella, F., Enescu, V., & Sahli, H. (2015). Recognition of facial actions and their temporal segments based on duration models.
- Ano: 2015
- Periodico: Multimedia Tools and Applications
- DOI: 10.1007/s11042-014-2320-8
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: HSMM/VDHMM reduzem erro de duração e melhoram reconhecimento do offset facial.
- Forca da evidencia: Strong
- Verificacao: Presente no corpus do usuário (Consensus)

### Hamm, J., Kohler, C.G., Gur, R.C., & Verma, R. (2011). Automated Facial Action Coding System for dynamic analysis of fac

- Pilar: 4
- Referencia: Hamm, J., Kohler, C.G., Gur, R.C., & Verma, R. (2011). Automated Facial Action Coding System for dynamic analysis of facial expressions in neuropsychiatric disorders.
- Ano: 2011
- Periodico: Journal of Neuroscience Methods
- DOI: 10.1016/j.jneumeth.2011.06.023
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Classificadores de ML sobre dinâmica de AUs discriminam padrões sutis em transtornos psiquiátricos.
- Forca da evidencia: Strong
- Verificacao: Verificado por Claude via busca independente

### Kawulok, M., Nalepa, J., Kawulok, J., & Smolka, B. (2021). Dynamics of facial actions for assessing smile genuineness

- Pilar: 4
- Referencia: Kawulok, M., Nalepa, J., Kawulok, J., & Smolka, B. (2021). Dynamics of facial actions for assessing smile genuineness.
- Ano: 2021
- Periodico: PLoS ONE
- DOI: 10.1371/journal.pone.0244647
- Amostra/Populacao: Bases BBC e UvA-NEMO
- Achado principal aplicavel ao FROID: Extrai características discriminativas da dinâmica de AUs para distinguir sorriso espontâneo de posado.
- Forca da evidencia: Moderate
- Verificacao: Verificado por Claude — apoia a abordagem geral, não é validação definitiva do par AU6+AU12

### (busca independente, 2020, PMC7193529) Reconsidering the Duchenne Smile: Indicator of Positive Emotion or Artifact of Sm

- Pilar: 4-contra
- Referencia: (busca independente, 2020, PMC7193529) Reconsidering the Duchenne Smile: Indicator of Positive Emotion or Artifact of Smile Intensity?
- Ano: 2020
- Periodico: —
- DOI: —
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Desafia diretamente a hipótese clássica: AU6 não discriminou sorrisos genuínos de forçados, correlacionando com intensidade do sorriso, não autenticidade.
- Forca da evidencia: Contested
- Verificacao: Encontrado por Claude — usar para hedgear a alegação de 'detecção de dissimulação'

### Schoentgen, J. (2002). Modulation frequency and modulation level owing to vocal microtremor

- Pilar: 5
- Referencia: Schoentgen, J. (2002). Modulation frequency and modulation level owing to vocal microtremor.
- Ano: 2002
- Periodico: Journal of the Acoustical Society of America
- DOI: 10.1121/1.1492820
- Amostra/Populacao: Falantes normofônicos e disfônicos leves
- Achado principal aplicavel ao FROID: Caracteriza o microtremor vocal como modulação lenta normal do ciclo vocal — não estabelece o vínculo psiquiátrico/autonômico específico do FROID.
- Forca da evidencia: Weak (para o claim específico)
- Verificacao: Verificado por Claude via busca independente

### Schewski, L., Doss, M., Beldi, G., & Keller, S. (2025). Measuring negative emotions and stress through acoustic correlat

- Pilar: 5
- Referencia: Schewski, L., Doss, M., Beldi, G., & Keller, S. (2025). Measuring negative emotions and stress through acoustic correlates in speech: A systematic review.
- Ano: 2025
- Periodico: PLOS One
- DOI: 10.1371/journal.pone.0328833
- Amostra/Populacao: Revisão sistemática
- Achado principal aplicavel ao FROID: Estresse associado a F0/intensidade; não identificou padrão consistente de ansiedade nem microtremor infrassônico.
- Forca da evidencia: Weak
- Verificacao: Presente no corpus do usuário (Consensus)

### De Lacerda Veiga, D., Almeida, T.M., Uchida, R.R., & Cordeiro, Q. (2025). The Fundamental Frequency of Voice as a Potent

- Pilar: 5
- Referencia: De Lacerda Veiga, D., Almeida, T.M., Uchida, R.R., & Cordeiro, Q. (2025). The Fundamental Frequency of Voice as a Potential Stress Biomarker: A Systematic Review and Meta-Analysis.
- Ano: 2025
- Periodico: Stress and Health
- DOI: 10.1002/smi.70112
- Amostra/Populacao: Meta-análise
- Achado principal aplicavel ao FROID: F0 aumenta com estresse, mas com heterogeneidade alta e viés de publicação — evidência insuficiente para uso clínico.
- Forca da evidencia: Weak
- Verificacao: Presente no corpus do usuário (Consensus)

### Calić, G., Petrović-Lazić, M., Mentus, T., & Babac, S. (2022). Acoustic features of voice in adults suffering from depre

- Pilar: 5
- Referencia: Calić, G., Petrović-Lazić, M., Mentus, T., & Babac, S. (2022). Acoustic features of voice in adults suffering from depression.
- Ano: 2022
- Periodico: Psiholoska istraživanja
- DOI: 10.5937/psistra25-39224
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Jitter/shimmer/tremor alterados em depressão, mas tremor tratado como parâmetro de voz, não oscilação autonômica 4–15Hz validada.
- Forca da evidencia: Weak
- Verificacao: Presente no corpus do usuário (Consensus)

### — (sem fonte científica aplicável) — origem real: tecnologia de biofeedback comercial EVOX/ZYTO

- Pilar: 6
- Referencia: — (sem fonte científica aplicável) — origem real: tecnologia de biofeedback comercial EVOX/ZYTO
- Ano: —
- Periodico: —
- DOI: —
- Amostra/Populacao: —
- Achado principal aplicavel ao FROID: Mapeamento de 12 zonas Hz→emoção segue o padrão de frequências solfeggio/chakra — sem evidência publicada de efeito fisiológico/psicológico específico.
- Forca da evidencia: 
- Verificacao: Confirmado por busca independente — tratar exclusivamente como heurística proprietária FROID
