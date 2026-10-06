# Interpretação facial única: sete famílias

DECIDIDO em 06/10/2026 pelo dono: substituir a interpretação facial atual,
unificar em sete famílias, preservar medidas e melhorar os mecanismos de alerta.
Não criar motor paralelo. Na decisão inicial, commit, push e publicação não
estavam autorizados.

Autorização posterior do dono: executar commit e push das alterações desta
tarefa. Publicação depende da confirmação do ambiente e de janela sem sessão
clínica ativa; essa janela não foi confirmada nesta entrega.

## Apuração anterior à alteração

- `froid-server/froid_facs.py:43`: 16 estimativas de AU, provenientes de 30
  coeficientes distintos. Coeficiente ausente era convertido em zero (`:73`).
- `froid-server/froid_facs.py:114`: seis regras atribuíam combinações faciais
  às zonas 3, 6, 7, 8, 9 e 12, afirmando mascaramento/conflito sem comparação.
- `froid-server/froid_core.py:320`: quadro armazenado e reutilizado por ticks;
  `:1216` contava regras como divergência; `:1224` confirmava por ticks.
- `froid-server/main.py:7930`: entrada facial com autorização por convite aceito
  ou autoria profissional. Essas guardas devem permanecer intactas.
- `froid-dashboard/src/lib/froid-face.ts:96`: envio sem identidade de quadro;
  erros de captura e HTTP eram silenciados.
- `froid-dashboard/src/pages/LiveSession.tsx:340`: segunda interpretação no
  navegador; `:6133` gerava registros; `:7195` apresentava os alertas.
- `froid-dashboard/src/lib/report-pdf.ts:1022`: relatório consumia esses textos.
- `froid-server/froid_voice.py:29`: 12 bandas espectrais entre 65,4 e 1975,5 Hz;
  `:224` normaliza por pico. Não são 12 emoções nem 12 regiões anatômicas.

## Contrato e fases locais autorizadas

1. Uma tabela canônica de sete famílias: sorriso, tristeza, raiva, medo,
   surpresa, nojo e desprezo. São hipóteses morfológicas, não emoções certas,
   diagnóstico, mentira ou leitura do subconsciente. Preservar ambiguidades.
2. Ausência e coeficiente inválido ficam nulos; zeros medidos ficam zeros.
   Preservar coeficientes brutos, lateralidade e estimativas anteriores
   identificadas como legado. AU23 não é mouthRoll (rolamento labial);
   AU17 passa a usar apenas mouthShrugLower como proxy explícito.
3. Regras com variantes do anexo, declarando AU25/27 não instrumentadas e AU23
   sem correspondência defensável. Não importar as alegações do anexo sobre
   genuinidade, confiança de ápice >75% ou duração universal <1 s.
4. Confirmação por observações distintas, nunca por releitura de cache. Reusar
   a contagem existente de duas observações e validade de 2,5 s, sem inventar
   calibração clínica. Identificar fluxo, sequência e tempo do vídeo; rejeitar
   repetição/ordem inválida. Ausência encerra continuidade e explica o motivo.
5. Backend publica famílias, variantes, limitações e eventos com textos
   canônicos profissionais e para paciente. Painel e PDF consomem esses textos,
   sem novo classificador. A família pode ser apurada mesmo sem voz.
6. Uma combinação facial não liga flags de zonas nem multiplica desvio vocal
   por 2,5. Divergência facial-vocal permanece não apurada, por faltar relação
   validada entre canais. Não confundir ausência de regra com embotamento.
7. Testes do contrato, ausência, lateralidade, ambiguidades, identidade temporal,
   integração, consumidores e segurança. Relatórios antigos mantêm leitura
   histórica; novos eventos são versionados e não reclassificam o passado.

## Reavaliação da fusão das 12 zonas

Há oportunidade de fundir a apresentação/interpretação facial em sete famílias.
Isso não exige eliminar nenhuma medida. Reduzir também as 12 bandas acústicas
não é uma simplificação equivalente: não existe correspondência validada de
banda de frequência para emoção. Somar/médias de desvios normalizados pode
cancelar alterações opostas. Uma alteração dimensional global requer escolha
de bandas, preservação de potência bruta e nova validação das baselines/índices.
Não há evidência local que permita afirmar benefício ou impossibilidade desse
experimento; nesta autorização preserva-se a dimensionalidade acústica.

## Limites e verificação

Os limiares 0,30/0,25 são legados, não limiares clínicos validados. O fluxo a
3 Hz não prova detecção de microexpressões de 40–200 ms. Não inventar confiança
de ápice, intensidades FACS A–E ou taxa de acerto. Testes automatizados verificam
o funcionamento, não precisão clínica; esta exige vídeos anotados, diversidade
de condições e avaliação por pessoa fora da amostra de calibração.

Referências primárias: [FACS](https://www.paulekman.com/facial-action-coding-system/),
[MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker),
[AU6 e sorriso](https://pmc.ncbi.nlm.nih.gov/articles/PMC7193529/).

Publicação exige autorização e janela sem sessão clínica ativa; não ocorrerá
reinício, rebuild, migração de dados ou mudança de controle de acesso aqui.

## Evidência local de implementação — 06/10/2026

Um único motor no backend publica as sete famílias, as medidas e o acervo de
eventos. Captura serializada identifica quadros distintos; confirmação deixa
de depender de releitura por ticks. Ausência e expiração encerram os eventos.
Envio por delta evita duplicatas, mantém eventos entre ticks e ressincroniza
o acervo na reconexão. Face pode viajar enquanto a DSP vocal está pendente,
sem fabricar uma leitura acústica. Falha no envio não avança o cursor.

Painel ao vivo, relatório profissional e PDF consomem o texto canônico.
Leitura vencida não é atual; a leitura arquivada é identificada como histórica.
Paciente recebe apenas tradução explícita, com seleção e sanitização servidoras.
Permissões, limites de entrada e testes de segurança não foram enfraquecidos.
Testes comuns de regras revogadas foram atualizados para a decisão do dono;
a garantia de ausência passa a exigir dissonância nula mesmo com bandas medidas.

Verificação em Windows: 315 testes de backend e 79 subtestes aprovados na suíte
alvo de motor, integração, transporte, glossário, procedência e segurança.
Build local final do painel aprovado. A suíte completa final do painel
aprovou 845/846 testes; a única falha está em
`retencao-da-apuracao.test.tsx:276`, expectativa de texto vazio do gráfico IPM.
Esse teste e `IPMLineChart.tsx` são idênticos ao HEAD, e a falha também foi
reproduzida isoladamente. Não foi alterado código alheio para mascará-la.

O gráfico de padrões deixou de anunciar AU15/AU20 e retração facial onde sua
fórmula apenas compõe bandas vocais; traduções seguem o mesmo significado.
O estado descritivo de energia vocal reduzida não acrescenta automaticamente
carga de alerta de coerência. Essa equivalência foi verificada por renderização.

Não houve validação em Linux, sessão real com câmera/navegador, base de vídeos
anotados ou medição de precisão/recall. A melhoria de acurácia é hipótese a
avaliar, não resultado demonstrado. A cadência continua em 3 Hz, sem promessa
de microexpressões; baseline facial pessoal, compensação de pose/iluminação,
controle de fala e calibração de limiares exigem medidas e validação próprias.
Na verificação acima, não houve commit, push, publicação ou modificação de
registros históricos.

## Recorte da entrega autorizada

Dois commits: motor/API com testes e desenho; painel/relatórios com captura,
consumidores e testes. São partes da mesma mudança de contrato e precisam de
publicação coordenada de backend e frontend. O website não foi editado: seu
texto foi entregue como proposta na conversa, não como HTML implementado.

Uma reversão integral restauraria a interpretação facial anterior por zonas,
o multiplicador vocal condicionado à face e os consumidores anteriores. Não
há ensaio de reversão nem reclassificação de relatórios históricos nesta entrega.
