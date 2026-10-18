# Agenda da clinica no painel — desenho

Pedido do dono em 18/10/2026 (item 4 da revisao do fluxo de visibilidade):
"o gerenciamento das agendas de cada profissional e geral da clinica pode ser
uma configuracao de atribuicoes de competencias do gestor". Resposta curta:
o servidor ja tem a agenda e as competencias; o que falta e o painel e a
ativacao. Lido contra `main` (`9749d0c3`) e contra producao.

## O que JA existe (Psique V2, Fase 4, 30/09/2026)

- **Agenda interna como autoridade** (`migrations/044`, `045`;
  `psique_scheduling.py`): unidades da organizacao, disponibilidade semanal
  por clinico com fuso, atendimentos com dupla marcacao impossivel no banco,
  trilha de eventos, vinculo atendimento -> sessao, espelho Google por outbox.
- **Competencias por papel (RBAC V2, `psique_rbac.py`):** `SECRETARY` e
  `ORG_ADMIN` criam, reagendam e cancelam qualquer agenda da organizacao;
  `CLINICIAN` so a propria; `CLINICAL_SUPERVISOR`, `FINANCE` e
  `AUDITOR_COMPLIANCE` existem para outros fins. E exatamente "a competencia
  do gestor" que o dono descreveu — ja decidida por papel, sem configuracao
  extra.
- **Rotas** sob `/api/psique/v2/scheduling/*` (`psique_api.py`), montadas
  quando `FROID_PSIQUE_V2_BILLING_ENABLED=true` — e em producao esta `true`.
- **Fronteira clinica**: eventos e espelho carregam horario, status, clinico
  e unidade; nunca paciente.

## O que NAO existe

- **Nenhuma tela do painel chama a agenda interna** (nenhum arquivo em
  `froid-dashboard/src` referencia `scheduling/`). A unica agenda visivel e a
  do Google Calendar de cada profissional (`AgendaDoProfissional.tsx`), que
  o gestor nao ve.
- **Nenhuma disponibilidade e nenhum atendimento em producao** (0 linhas em
  `psique_clinician_availability` e `psique_appointments`).
- **RBAC V2 por organizacao** (`psique_organization_settings.rbac_version`):
  organizacoes V1 recebem `RBAC_V2_NOT_ENABLED`. Quais estao em V2 e dado a
  conferir antes de ativar.
- Excecoes de disponibilidade (feriados, ferias) e o worker real do espelho
  Google: limites declarados na Fase 4.

## O que entra (Psique V2, Fase 5 — agenda no painel)

1. **Tela "Agenda da clinica"** para quem tem `SECRETARY` ou `ORG_ADMIN`:
   semana por profissional (colunas) e visao geral da clinica; marcar,
   reagendar e cancelar pelas rotas existentes; disponibilidade de cada
   clinico editavel pelo proprio clinico (regra `OWN_AVAILABILITY_ONLY`).
2. **Tela "Minha agenda"** para `CLINICIAN`: a propria semana, a partir da
   agenda interna; o Google passa a espelho, nao fonte.
3. **Atribuicao de competencias** = conceder `SECRETARY`/`ORG_ADMIN` ao
   membro, na tela de membros que ja existe (`members.manage`).
4. **Ativacao por organizacao**: `rbac_version=2` na organizacao da clinica,
   conferida em producao antes de ligar a tela.

## Decisoes do dono antes de comecar

| Decisao | Opcao recomendada |
|---|---|
| A agenda interna vira a fonte e o Google so espelha? | Sim; e o desenho da Fase 4 |
| Quem pode ver a agenda geral: so SECRETARY/ORG_ADMIN, ou tambem CLINICAL_SUPERVISOR? | Supervisor ve, nao marca (leitura), como ve relatorios |
| O paciente aparece na agenda do gestor pelo nome ou por id? | Nome so para SECRETARY/ORG_ADMIN da mesma clinica; o espelho Google continua sem paciente |

## Estimativa

Painel: duas telas e a concessao de papel; servidor: nada novo alem da
ativacao e, se decidido, a leitura para supervisor. E uma fase com gate
proprio, como as anteriores.
