# FROID Psique V2.1 — resultado da Fase 4 (agenda organizacional)

Data: 30/09/2026, America/Sao_Paulo. Autorização do proprietário nesta data ("aprovo o gate da Fase 4"), precedida da revisão registrada no [checklist](psique-v2-checklist-execucao.md) (complemento RBAC 043 + guardas de espelho).

**Resultado:** agenda organizacional implementada com o Appointment interno como autoridade — a dupla marcação é impossível **no próprio banco** (exclusion constraint `tstzrange` por clínico, com o slot liberado quando o atendimento sai dos estados ocupantes) — e o espelho Google como outbox pós-commit cuja falha é estado visível, nunca perda de agendamento. **11 testes novos; 175 testes Psique verdes no total, zero skips, validados em Windows e dentro de contêiner Linux (Docker).** A execução PARA aqui; a Fase 5 (app/site) exige nova aprovação.

## Desenho (migration 044 + psique_scheduling.py)

- **Escopo por RBAC V2 obrigatório**: toda operação exige `rbac_version=2` (organizações V1 recebem `RBAC_V2_NOT_ENABLED` e mantêm o comportamento atual). SECRETARY/ORG_ADMIN criam, reagendam e cancelam qualquer agenda; CLINICIAN somente a própria (`OWN_AGENDA_ONLY`). O vínculo atendimento→fonte de análise é exclusivo do clínico do atendimento — secretaria nunca toca em vínculo clínico.
- **Fronteira clínica**: trilha de eventos e payload do espelho carregam apenas horários, status, clínico, unidade e versão — sem `patient_id`, sem nome, sem payload de paciente (testado por asserção de conteúdo).
- **Disponibilidade**: janelas semanais por fuso IANA do slot; a checagem converte o horário do atendimento para o fuso da janela (dia local único); fora da janela → `OUTSIDE_AVAILABILITY`. Exceções pontuais (feriados/férias) ficam para a ativação — limite declarado.
- **Concorrência e versão**: criação idempotente por organização+chave; edição/cancelamento com `expected_version` — conflito devolve `applied=false` (rota → 409) sem sobrescrever; corrida de dois agendamentos no mesmo horário termina com exatamente um criado e um `APPOINTMENT_CONFLICT`.
- **Outbox do espelho**: `UPSERT`/`CANCEL` gravados na mesma transação do agendamento; worker consome com `FOR UPDATE SKIP LOCKED` (take concorrente sem duplicata), liquida com `DELIVERED` (idempotente) ou `FAILED` com erro sanitizado visível em `calendar-sync/status`. Reprocessar um `FAILED` é decisão do operador, não retry silencioso. Nenhum token/credencial existe nestas tabelas; a entrega real usará o OAuth já existente, fora deste domínio.
- **Unidades**: cadastro mínimo (`psique_organization_units`) para o `unit_id` do atendimento; gestão por ORG_ADMIN.
- Rotas sob a mesma flag desligada: units, availability, appointments (list/create/patch/cancel/history/session-link) e calendar-sync/status; corpos estritos e `X-Idempotency-Key` obrigatório na criação.

## Testes (11 novos, PostgreSQL real; domínios com guarda de drift)

Org V1 recusada; secretária opera o ciclo completo com trilha `CREATED→RESCHEDULED→CANCELLED` e outbox `UPSERT/UPSERT/CANCEL` sem dado clínico; clínico vê/opera só a própria agenda e staff vê todas; dupla marcação impossível + slot liberado por cancelamento + clínicos diferentes convivem no mesmo horário; fora da disponibilidade recusado (hora e dia), disponibilidade própria vs alheia, disponibilidade exige CLINICIAN; criação idempotente; conflito de versão e estado terminal; vínculo de sessão só do clínico dono, único; falha do espelho visível com agendamento intacto e `FAILED` fora da fila; take concorrente sem duplicata e entrega idempotente; corrida do mesmo slot com exatamente um vencedor.

Qualidade: Ruff/Mypy limpos; `git diff --check` aprovado; regressão V1 selecionada verde; TypeScript não aplicável.

## Limites e pendências

- Worker Google real (OAuth existente) e a projeção administrativa de pacientes para a SECRETARY chegam na ativação/UI — a secretária agenda por `patient_id` sem ler a tabela de pacientes até lá.
- Exceções de disponibilidade (datas específicas) ficam para a ativação.
- Sem LIVE, sem produção, sem publicação. **Fase 5 (app e website V2) somente com nova aprovação explícita.**
