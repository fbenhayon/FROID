# FROID — protocolo inicial de testes com profissionais

Versão: 19 de julho de 2026
Idiomas: inglês dos EUA, francês da França e espanhol da Espanha

## Objetivo

Validar transcrição, resumo semântico, interface e estabilidade das trilhas de áudio antes de qualquer declaração de validação clínica internacional. Esta etapa não recalibra nem comprova biomarcadores clínicos; ela produz evidência para decidir a etapa de calibração.

## Preparação de cada profissional

1. Assinar o termo de participação e confidencialidade aplicável.
2. Usar conta e organização exclusivas de homologação.
3. Confirmar idioma nativo, região/sotaque, profissão e experiência clínica.
4. Confirmar navegador atualizado, microfone, câmera e rede.
5. Não utilizar paciente real na primeira rodada. Usar caso simulado e dados fictícios.
6. Ler o roteiro jurídico-operacional em `INTERNATIONAL_AGENT_LEGAL_PLAYBOOK.md`.
7. Receber um identificador de avaliador, sem inserir nome no conjunto analítico.

## Matriz mínima por idioma

Cada profissional executa, na ordem:

1. sessão remota em computador, 20 minutos;
2. sessão presencial com um microfone, 20 minutos;
3. sessão com paciente em celular, 20 minutos;
4. repetição de um roteiro de 10 minutos em dispositivo ou rede diferente;
5. um bloco controlado de *code-switching* com no máximo dois idiomas;
6. um bloco com negação, números, datas, dosagens fictícias e termos críticos.

Na sessão remota, verificar separadamente que a fala do profissional aparece como `DR.` e a do paciente simulado como `PC`/`PAC`. Biomarcadores devem usar exclusivamente a trilha identificada como paciente.

## Roteiro de conteúdo

O caso simulado deve conter:

- apresentação e contexto de vida;
- relato emocional neutro e relato emocionalmente carregado;
- pausas naturais e interrupções;
- uma negação crítica, por exemplo “não tenho intenção de me ferir”;
- números, data e duração;
- pelo menos 15 termos clínicos predefinidos por idioma;
- fala rápida, fala lenta e volume moderadamente baixo;
- encerramento e resumo do profissional.

Não introduzir emergência real, dados pessoais reais ou instruções terapêuticas para uma pessoa identificável.

## Conferência durante a sessão

O observador registra:

- áudio e vídeo local e remoto presentes;
- fonte ativa do STT;
- identificação correta do falante;
- ausência de duplicação entre blocos;
- idioma de voz e idioma de relatório corretos;
- atraso percebido;
- reinício de gravador ou reconexão WebRTC;
- silêncio corretamente descartado;
- qualquer perda, troca de falante ou tradução indevida.

## Conferência após a sessão

1. Abrir o relatório e confirmar que a transcrição integral contém a fala do paciente e do profissional.
2. Comparar uma transcrição de referência humana com a hipótese do FROID.
3. Avaliar fidelidade do resumo, omissões, afirmações não sustentadas e adequação cultural.
4. Conferir `spokenLanguage`, `analysisLanguage` e `reportLocale` no relatório.
5. Conferir qualidade da transcrição: segmentos bem-sucedidos, vazios, silenciosos, falhos e latências p50/p95.
6. Exportar somente o registro autorizado para a pasta segura da validação.
7. Registrar defeitos com idioma, modalidade, navegador, dispositivo, instante e severidade; nunca anexar segredos ou dados reais.

## Registro JSONL para o avaliador determinístico

Um registro por bloco:

```json
{"locale":"en-US","reference":"human reviewed reference","hypothesis":"FROID transcript","critical_terms":["term one","term two"],"latency_ms":1840,"status":"ok","subgroups":{"accent_region":"US-Midwest","modality":"remote","browser":"Chrome"}}
```

Estados aceitos incluem `ok`, `empty`, `truncated`, `duplicated` e `delayed`. O relatório é produzido por:

```bash
python froid-server/tools/evaluate_language_validation.py batch.jsonl --output report.json
```

## Classificação de defeitos

- **Crítico:** trilha de outro paciente/organização, troca sistemática de falante, negação invertida, conteúdo inventado, ausência da transcrição integral ou exposição de dado sensível.
- **Alto:** perda recorrente de blocos, idioma errado, termos críticos omitidos, vídeo/áudio remoto instável ou resumo clinicamente enganoso.
- **Médio:** atraso elevado, duplicidade pontual, texto de interface não traduzido ou erro importante de pontuação.
- **Baixo:** preferência estilística ou terminológica sem alteração de sentido.

Um defeito crítico interrompe imediatamente a rodada daquele idioma e preserva logs e identificadores técnicos para investigação.

## Gate para ampliar o piloto

O responsável pela validação deve aprovar por idioma:

- zero falha crítica aberta;
- zero vazamento entre organizações;
- transcrição integral recuperável nos relatórios testados;
- métricas de WER/CER e termos críticos calculadas sobre referência humana;
- p50/p95 e taxas de vazio, truncamento, duplicidade e atraso documentadas;
- revisão independente de resumos por dois profissionais nativos, com adjudicação;
- diferenças entre subgrupos documentadas e plano de correção quando excederem o limite registrado;
- parecer de privacidade/contrato para a próxima modalidade de uso.

O resultado do piloto deve ser descrito como validação controlada. Ele não autoriza, sozinho, alegação diagnóstica, eficácia terapêutica ou validação populacional.
