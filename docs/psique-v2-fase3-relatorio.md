# FROID Psique V2.1 — resultado da Fase 3 (RBAC V2)

Data: 30/09/2026, America/Sao_Paulo. Autorização do proprietário nesta data, precedida da revisão financeira registrada no [checklist](psique-v2-checklist-execucao.md).

**Resultado:** RBAC V2 implementado como opt-in por organização, com a matriz papel×recurso imposta **no banco** (RLS e funções de comando) e provada por **19 testes novos executados como `froid_runtime`** — o que se afirma é o que o PostgreSQL devolve ao membro, não o que a camada Python promete. Regressão completa: **158 testes Psique verdes, zero skips**, mais 37 da regressão V1 selecionada. **A execução PARA aqui; a Fase 4 (agenda organizacional) exige nova aprovação.**

## Desenho

Migration aditiva `042_psique_rbac_v2.sql`:

- `psique_organization_settings`: `rbac_version` 1→2 por comando do **owner V1** (a ponte de bootstrap), serializado por lock e auditado; trigger recusa organização `enterprise` (NR-1 jamais entra no ramo) e **proíbe downgrade** — reverter RBAC nunca pode ampliar leitura clínica.
- `psique_membership_role_grants`: papéis cumulativos (`CLINICIAN, SECRETARY, FINANCE, ORG_ADMIN, CLINICAL_SUPERVISOR, AUDITOR_COMPLIANCE`), um grant ativo por par via índice parcial, histórico imutável (revogação é o único update, uma vez). **SUPERADMIN está fora do domínio por desenho** — exceção de plataforma, não papel organizacional.
- `psique_supervision_assignments`: escopo explícito supervisor→supervisionado, exigindo os dois papéis, concedido só por ORG_ADMIN, revogável e auditado.
- A ativação faz snapshot explícito e auditado: `professional`→CLINICIAN, `owner/administrator`→ORG_ADMIN. Ninguém ganha acesso clínico por inferência — o dono que atende precisa do próprio grant CLINICIAN.

**RLS com dois ramos mutuamente exclusivos** em `session_reports`, `patients`, `patient_assignments`, `consents`, `organization_wallets`, `credit_ledger` e `audit_events`: o corpo V1 ficou textualmente idêntico atrás de `NOT psique_rbac_v2_active(organization_id)` — como policies permissivas se combinam por OR, essa era a única forma de o papel V1 não contornar o V2. No ramo V2: CLINICIAN lê o próprio e o atribuído; CLINICAL_SUPERVISOR somente supervisionados; ORG_ADMIN/SECRETARY/FINANCE/AUDITOR **zero linhas clínicas**; extrato é de FINANCE/ORG_ADMIN; auditoria é de ORG_ADMIN/AUDITOR_COMPLIANCE; DELETE de histórico clínico é negado a todos em org V2 (retenção vira procedimento explícito futuro).

**Portões de comando:** `psique_v2_credit_command` (cópia programática da 038, mudando só o bloco de papéis) passa a ramificar por versão — conteúdo (`BEGIN/DELIVER/READ_DELIVERY/CONSUME/…`) exige CLINICIAN; `ENROLL/GRANT_TRIAL/RESTORE/ADJUST` exigem ORG_ADMIN; saldo é de CLINICIAN/ORG_ADMIN/FINANCE. O gate de billing (checkout/licença) aceita ORG_ADMIN|FINANCE em org V2; a habilitação clínica de assento exige ORG_ADMIN (FINANCE compra créditos, não habilita profissional). Proteção operacional: o último ORG_ADMIN ativo não pode ser revogado — a regra mais rígida trancaria a organização para fora de si mesma.

`psique_rbac.py` + rotas sob a mesma flag desligada: `GET /capabilities` (papéis efetivos e capacidades derivadas — o frontend apresenta, o servidor decide), `POST /rbac/enable`, `/rbac/role-grants`, `/rbac/role-revocations`, `/rbac/supervisions` (corpos estritos; SUPERADMIN e papéis desconhecidos recusados antes do SQL com `RBAC_ROLE_UNKNOWN`).

## Testes (19 novos; probes como `froid_runtime` com GUCs do membro)

Ativação (owner-only, idempotente, snapshot, corrida dupla com uma só ativação); org V1 e NR-1 intactas; dono/admin de org V2 sem leitura clínica; CLINICIAN próprio+atribuído (e papel V1 `professional` sem grant → nada); SECRETARY/FINANCE/AUDITOR zero linhas clínicas; supervisor sem vínculo → nada, com vínculo → só o supervisionado, revogação corta; supervisão exige papéis e ORG_ADMIN; papéis cumulativos e re-concessão pós-revogação; SUPERADMIN/papéis V1 não concedíveis; último ORG_ADMIN protegido; cross-org e contexto forjado negados; comando de crédito por papel (FINANCE lê saldo mas não `READ_DELIVERY`; SECRETARY nem saldo; ADJUST só ORG_ADMIN); gate de billing (FINANCE sim, SECRETARY não, ponte V1 preservada, `clinical_set` só ORG_ADMIN); leituras de carteira/extrato/auditoria por papel; DELETE clínico negado; grant duplicado concorrente aplicado uma vez.

Qualidade: Ruff e Mypy limpos nos módulos novos/tocados; `git diff --check` aprovado; TypeScript não aplicável (painel intocado). Guards de drift cobrem `v2_role`.

## Limites e pendências

- A **ativação pública** (rotas antigas, WebSockets e onboarding consultando capabilities V2) permanece para a fase de ativação/integração, como nas fases anteriores: a RLS já decide no banco para qualquer caminho que chegue com o contexto do membro, e nenhuma organização tem `rbac_version=2` até o comando explícito do owner.
- Projeção administrativa de pacientes para SECRETARY (sem `legacy_payload`) chega com a agenda (Fase 4), via função de projeção estrita — até lá a secretaria não lê a tabela de pacientes.
- Falhas preexistentes conhecidas seguem inalteradas e fora do escopo.
- Sem LIVE, sem produção, sem publicação. **Fase 4 (agenda organizacional) somente com nova aprovação explícita.**
