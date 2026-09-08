# Revisão dos percursos e instruções do website — 07/09/2026

Revisão local do site confrontada com o código disponível neste checkout. Não é uma certificação clínica, jurídica ou de segurança, nem evidência de configuração em produção. A skill mestre e `revisar-servicos` orientaram a revisão; a regra do repositório de não commitar sem pedido prevalece sobre a rotina de commits da segunda skill.

## Os dois produtos e seus percursos

| Produto | Público e objetivo | Percurso apresentado no site |
|---|---|---|
| FROID Psique | Profissional autônomo ou clínica; apoio à observação e documentação do atendimento | Conta → escolha do perfil → cadastro e condições de acesso → paciente e convite → autorizações e captura → sessão → revisão do relatório → composição e liberação do documento do paciente |
| FROID Psicossocial | Organização empregadora; avaliação coletiva de condições de trabalho e documentação das medidas | Conta empresarial → organização e estabelecimentos → setores e efetivos → preparação e abertura da campanha → convites → encerramento → conferência dos portões → inventário, AEP e plano → execução e acompanhamento de eficácia |

Pacientes acessam o convite e o portal próprio. Trabalhadores respondem pelo link da campanha. Clínica e empresa empregadora não são variações intercambiáveis de um cadastro: a segunda não recebe acesso ao prontuário nem a respostas individuais.

## Capacidades conferidas e consequência editorial

| Capacidade | Fonte aberta na revisão | Correção aplicada |
|---|---|---|
| Escolha de perfil e destino após autenticação | `froid-dashboard/src/pages/ProductChoice.tsx`, `src/lib/product-choice.ts`, `src/App.tsx` | Abertura identifica os dois produtos; guia profissional explica cadastro autônomo/clínica; guia empresarial segue estrutura própria |
| Convite e autorizações do paciente | `src/pages/PatientInvitePage.tsx`, `LiveSession.tsx` | Preparação não promete ocorrer em segundos; exige conferir autorização e captura |
| Cortes automáticos, manuais e de encerramento | `src/pages/LiveSession.tsx`, `closeFinalSemanticCut` e tratamento dos cortes | Relatório deixa de ser descrito como uma sequência exclusivamente fixa; ausência não vira zero |
| Composição e liberação do documento do paciente | `src/pages/SessionReport.tsx`, `PatientPortalPage.tsx`; `froid-server/main.py`, `set_session_report_patient_release` | Encerrar/salvar não equivale a liberar; revisão, seleção e liberação são explícitas |
| Créditos, cotas, equipe e visibilidade | `src/pages/ClinicManagement.tsx`; `main.py`, `set_organization_report_visibility`; `subscriptions.py` | Sai “a confirmar”; entram as opções restrita/compartilhada e a decisão auditada do gestor |
| Perguntas nativas do Explica | `src/components/panels/AIInsights.tsx`, `PRESETS` | Sai a lista antiga de 22 promessas; exemplos não prometem escore de risco ou predição terapêutica |
| Prompts pessoais | `src/lib/professional-prompts.ts`, `readStore`/`writeStore` | Armazenamento descrito como local ao navegador, separado por e-mail; não se promete sincronização |
| Contexto recebido pelo Explica | `LiveSession.tsx`, construção de `panel_metrics` e `panel_metrics_window`; `explica_clinico.py` | Distingue corte atual, sessão documentada e consulta agregada; não promete leitura automática de toda a carteira |
| Consulta ao Data-Froid | `main.py`, `_query_froid_analytics`; `docker-compose.yml` | Sai volume não apurado, tamanho de modelo e liderança mundial. Resultado depende da base, das medidas e da coorte. O bloqueio usa `<= FROID_ANALYTICS_MIN_K`, e não apenas `<` |
| Captura acústica e transcrição | `main.py`, ingestão PCM com `extract_voice_features` e `transcribe_audio` | Corrigida a descrição de processamento exclusivamente local; áudio pode seguir ao servidor e provedor de transcrição |
| Campanha, convites e encerramento | `src/pages/Nr1Campaign.tsx`; `main.py`, `close_nr1_campaign` | Sequência operacional, distribuição e descarte do CSV; encerramento definitivo e resultado condicionado aos portões |
| Inventário, AEP e plano | `Nr1Inventario.tsx`, `Nr1Aep.tsx`, `Nr1ActionPlan.tsx` e respectivas rotas em `main.py` | São etapas e documentos próprios; questionário não preenche sozinho a observação da atividade nem as responsabilidades do plano |
| Portões e eficácia | `nr1_compliance.py`, `nr1_effectiveness.py`, `Nr1Effectiveness.tsx` | Sem calendário universal de implantação; insuficiência não significa risco baixo e comparação não prova causalidade |
| Explica NR-1 | `nr1_explica.py`, `src/lib/nr1-explica-conteudo.ts` | Consulta revisada já carregada separada de acesso inicial e consulta aberta; removida contagem de indexação não verificada |

Os caminhos `src/` da tabela são relativos a `froid-dashboard/`.

## Correções complementares

- A chamada corporativa para “Ver planos” passou a apontar para os preços do próprio Psicossocial.
- O índice progressivo reconhece tanto títulos com `id` quanto seções com `id`, incluindo o guia empresarial.
- Foram corrigidos os espelhos EN/ES/FR das promessas removidas do Explica, da visibilidade clínica, da liberação de relatórios, dos rótulos de prazo e da dispensa de PGR. O percurso internacional pela ISO foi preservado.
- A dispensa de PGR não foi mantida como automática para toda pequena empresa. Fonte oficial consultada: [MTE — Programa de Gerenciamento de Riscos](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/inspecao-do-trabalho/pgr). O enquadramento concreto precisa observar as condições normativas.
- Os quatro demonstradores continham geradores aleatórios de índices e um relatório fictício. Foram retirados, junto com o CSS exclusivo e os scripts sem consumidor. As mesmas âncoras agora levam ao guia de leitura sem medições fabricadas. Um comentário registra o motivo para impedir reintrodução.

## Verificação e limites da evidência

`python docs/verificar-site.py` verifica estrutura de tags, IDs duplicados, links e âncoras locais, mapa `NAV_SECOES`, codificação, sintaxe dos scripts embutidos e regressões das simulações e promessas removidas. Não faz requisições ao servidor.

Resultado: 84 páginas, 7.291 links locais, 98 âncoras do menu e 16 scripts embutidos; nenhuma falha na execução registrada. Os testes existentes `test_nr1_espelhos_do_portao.py` e `test_precos_nr1_espelhados.py` passaram: 17 testes. Nenhum teste de segurança foi alterado.

A revisão editorial se concentra nos percursos de produto e nos defeitos identificados acima. Não foi feita revalidação externa integral da bibliografia científica, dos contratos, das alegações históricas internacionais ou da infraestrutura. Termos e Privacidade não receberam alteração de conteúdo nesta rodada. O estado de implantação, a disponibilidade efetiva do acervo e a quantidade de sessões em produção não foram verificados. Não houve commit, push ou deploy. A validação visual em navegador segue distinta da verificação estrutural aqui registrada.
