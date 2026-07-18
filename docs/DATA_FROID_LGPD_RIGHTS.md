# Data-FROID e Portal de Direitos LGPD

## Decisões aprovadas

- Blockchain e smart contracts não integram esta arquitetura.
- O repositório clínico identificado preserva a fala profissional, a transcrição e as mídias efetivamente configuradas, conforme a política clínica aplicável.
- O Data-FROID recebe somente registros que passaram pelo gate técnico de anonimização.
- O ingresso no Data-FROID não depende de consentimento específico de pesquisa; a base legal e a finalidade devem permanecer documentadas pelo controlador.
- Não foi adicionada generalização obrigatória de idade, localidade ou data nesta etapa.
- Consultas populacionais exigem coorte estritamente maior que 50.
- A taxa de quarentena/supressão possui alvo operacional máximo de 10%. Esse alvo nunca autoriza a entrada de uma linha insegura; excesso gera revisão do pipeline.

## Proteções do Data-FROID v3

- pseudônimo de sessão por HMAC-SHA256 com chave exclusiva;
- nenhuma fala literal ou resumo livre de paciente/profissional;
- categorias semânticas limitadas a rótulos normalizados;
- ausência de áudio, vídeo e transcrição no DuckDB;
- trilha de aprovação ou quarentena sem PII;
- auditoria executável por `tools/audit_data_froid_privacy.py`;
- remoção segura de linhas legadas por `tools/sanitize_data_froid.py`, sempre com cópia anterior.

O Data-FROID v3 usa por padrão `/data/datamart_anonymous_v3.duckdb`. O arquivo anterior permanece preservado e inativo até reprocessamento. O higienizador bloqueia qualquer remoção superior a 10%; nesse caso, os dados devem ser reconstruídos no arquivo v3 em vez de apagados em massa.

`FROID_DATAMART_PSEUDONYM_KEY` deve ser uma chave aleatória exclusiva, protegida no `.env`. A chave não deve ser reutilizada em Stripe, banco, backups ou criptografia clínica.

## Portal de direitos

O paciente autenticado pode:

- consultar organizações que tratam seus dados;
- conhecer categorias e finalidade operacional do tratamento;
- exportar imediatamente cadastro, consentimentos, resultados métricos disponíveis e protocolos, sem texto clínico livre ou dados de terceiros;
- protocolar acesso, correção, portabilidade, informação, revogação, restrição, eliminação, anonimização ou revisão automatizada;
- acompanhar status, prazo, resposta e eventual exceção de retenção.

Proprietário e administrador podem processar pedidos. Supervisor e auditor possuem somente leitura. Detalhes do pedido e resposta ao titular são criptografados com a chave clínica. Mudanças de status produzem eventos append-only e auditoria organizacional.

Eliminação, anonimização, bloqueio e revogação não são executados automaticamente ao protocolar. A organização deve validar identidade, escopo, base legal, obrigações de conservação e dados de terceiros. Uma decisão negativa ou parcial exige fundamento ou exceção de retenção registrados.

## Implantação gradual

1. Fazer backup integral criptografado e validar restauração.
2. Gerar e configurar `FROID_DATAMART_PSEUDONYM_KEY`.
3. Aplicar a migração `008_data_subject_rights` em homologação.
4. Executar `sanitize_data_froid.py` primeiro sem `--apply`.
5. Confirmar a prévia e executar novamente com `--apply`.
6. Reprocessar fontes clínicas pelo pipeline v3 para reconstruir o Data-FROID.
7. Executar `audit_data_froid_privacy.py`; o resultado deve ser `passed`.
8. Testar isolamento de solicitações entre duas organizações.
9. Testar pedido e exportação com um paciente controlado.
10. Liberar gradualmente, mantendo autorização tenant em `observe` até a evidência operacional.

## Rotina periódica

- auditoria do Data-FROID após cada reprocessamento e ao menos diariamente;
- revisão mensal de risco de reidentificação;
- revisão de pedidos próximos do prazo;
- teste de restauração seguido de reaplicação das decisões de bloqueio/eliminação;
- revisão trimestral de permissões de proprietário, administrador, supervisor e auditor.
