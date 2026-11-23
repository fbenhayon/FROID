#!/usr/bin/env bash
# Relatorio de acessos e cadastros de clientes do FROID (19/11/2026).
#
# RODA NO CONSOLE DO SERVIDOR (depois de `ssh froid`):
#     bash /root/froid-project/ops/relatorio-acessos.sh           so clientes
#     bash /root/froid-project/ops/relatorio-acessos.sh --todos   inclui contas internas
# ou direto do computador:
#     ssh froid bash /root/froid-project/ops/relatorio-acessos.sh
#
# Tem nomes e e-mails de clientes: a saida e para o dono, nao para circular.
# So LE o banco (transacao READ ONLY); nao altera nada.
#
# CONTAS INTERNAS (do dono e de teste) ficam fora do relatorio. A lista e o
# arquivo /root/.froid-contas-internas no servidor, um e-mail por linha, FORA
# do repositorio para nao versionar e-mails. Conta que nao esta na lista conta
# como cliente, entao cadastros novos aparecem sem precisar mexer em nada.
# Para marcar mais uma conta como interna, acrescentar o e-mail ao arquivo.
# Empresa interna = empresa com membros ativos, todos internos.
#
# De onde vem cada coluna:
#   ultimo acesso    ultima acao do usuario registrada em audit_events. O
#                    sistema nao grava um evento "login"; toda chamada
#                    autenticada vira um registro, entao a ultima delas e
#                    o ultimo uso real. Contam so os eventos http.* e
#                    websocket.* (pedidos do navegador da pessoa): acoes do
#                    sistema em nome dela, como a migracao psique.V2_MIGRATION_OPENING
#                    de 05/10/2026, nao sao acesso.
#   dias ativos      dias distintos (horario de Brasilia) com alguma acao,
#                    nos ultimos 30 dias.
#   relatorios       relatorios de sessao do FROID Psique (session_reports,
#                    sem os apagados), atribuidos ao profissional.
#   campanhas NR-1   assessment_campaigns da empresa; respostas = assessment_responses.
#   teste gratis     psique_trials: situacao (creditos usados/concedidos).
#   (Na tabela de empresas, "ultimo uso" conta so acoes de clientes.)
#
# Visitas ao site e cliques em "Teste gratis" ficam no Umami
# (https://estatisticas.froid.com.br), nao aqui.
set -euo pipefail

CONTEINER=${FROID_PG_CONTEINER:-froid-postgres-1}
BANCO=${FROID_PG_BANCO:-froid_homologacao}
ARQ_INTERNAS=${FROID_CONTAS_INTERNAS:-/root/.froid-contas-internas}

INTERNAS=""
if [ "${1:-}" != "--todos" ] && [ -f "$ARQ_INTERNAS" ]; then
  INTERNAS=$(tr 'A-Z' 'a-z' < "$ARQ_INTERNAS" | tr -s '[:space:]' ',' | sed 's/^,//; s/,$//')
fi

# A lista entra como variavel do psql (:'internas'), citada pelo proprio psql.
docker exec -i "$CONTEINER" sh -c \
  'psql -X -q -v ON_ERROR_STOP=1 -v internas="$2" -U "$POSTGRES_USER" -d "$1"' _ "$BANCO" "$INTERNAS" <<'SQL'
\pset footer off
\pset null '-'
set timezone = 'America/Sao_Paulo';
begin read only;

\echo
\echo '=== RESUMO (so clientes) ==='
with clientes as (
  select * from users where lower(email) <> all (string_to_array(:'internas', ','))
),
ultimo as (
  select a.actor_user_id u, max(a.occurred_at) t
  from audit_events a join clientes c on c.id = a.actor_user_id
  where a.action like 'http.%' or a.action like 'websocket.%' group by 1
)
select
  (select count(*) from clientes)                                               as "clientes",
  (select count(*) from clientes where created_at > now() - interval '7 days')  as "novos 7d",
  (select count(*) from clientes where created_at > now() - interval '30 days') as "novos 30d",
  (select count(*) from ultimo where t > now() - interval '7 days')             as "ativos 7d",
  (select count(*) from ultimo where t > now() - interval '30 days')            as "ativos 30d",
  (select to_char(max(t), 'DD/MM/YYYY HH24:MI') from ultimo)                    as "ultimo uso de cliente",
  (select count(*) from users) - (select count(*) from clientes)                as "contas internas ocultas";

\echo
\echo '=== CLIENTES (acesso mais recente primeiro) ==='
with clientes as (
  select * from users where lower(email) <> all (string_to_array(:'internas', ','))
),
ultimo as (
  select actor_user_id u, max(occurred_at) t,
         count(distinct (occurred_at at time zone 'America/Sao_Paulo')::date)
           filter (where occurred_at > now() - interval '30 days') dias30
  from audit_events where actor_user_id is not null
    and (action like 'http.%' or action like 'websocket.%') group by 1
),
emp as (
  select m.user_id,
         string_agg(distinct coalesce(nullif(o.display_name, ''), o.legal_name), ', ') nomes
  from organization_memberships m
  join organizations o on o.id = m.organization_id
  where m.revoked_at is null
  group by 1
),
rel as (
  select m.user_id, count(*) n
  from session_reports r
  join organization_memberships m on m.id = r.professional_membership_id
  where r.deleted_at is null
  group by 1
)
select coalesce(nullif(u.display_name, ''), '-')          as "nome",
       u.email                                            as "e-mail",
       coalesce(emp.nomes, '-')                           as "empresa",
       to_char(u.created_at, 'DD/MM/YYYY')                as "cadastro",
       coalesce(to_char(ultimo.t, 'DD/MM/YYYY HH24:MI'), 'nunca') as "ultimo acesso",
       coalesce(ultimo.dias30, 0)                         as "dias ativos 30d",
       coalesce(rel.n, 0)                                 as "relatorios Psique"
from clientes u
left join ultimo on ultimo.u = u.id
left join emp    on emp.user_id = u.id
left join rel    on rel.user_id = u.id
order by ultimo.t desc nulls last, u.created_at desc;

\echo
\echo '=== EMPRESAS E CONSULTORIOS DE CLIENTES (uso mais recente primeiro) ==='
with clientes as (
  select * from users where lower(email) <> all (string_to_array(:'internas', ','))
)
select coalesce(nullif(o.display_name, ''), o.legal_name)      as "nome",
       o.organization_type                                     as "tipo",
       to_char(o.created_at, 'DD/MM/YYYY')                     as "cadastro",
       mem.n                                                   as "membros",
       coalesce(to_char(uso.t, 'DD/MM/YYYY'), 'nunca')         as "ultimo uso",
       rel.n                                                   as "relatorios Psique",
       camp.n                                                  as "campanhas NR-1",
       resp.n                                                  as "respostas NR-1",
       coalesce(tr.status || ' (' || tr.credits_used || '/' || tr.credits_granted || ')', '-') as "teste gratis"
from organizations o
cross join lateral (select count(*) n, count(c.id) n_cli
                    from organization_memberships m
                    left join clientes c on c.id = m.user_id
                    where m.organization_id = o.id and m.revoked_at is null) mem
cross join lateral (select max(a.occurred_at) t from audit_events a
                    join clientes c on c.id = a.actor_user_id
                    where a.organization_id = o.id
                      and (a.action like 'http.%' or a.action like 'websocket.%')) uso
cross join lateral (select count(*) n from session_reports r
                    where r.organization_id = o.id and r.deleted_at is null) rel
cross join lateral (select count(*) n from assessment_campaigns c
                    where c.organization_id = o.id) camp
cross join lateral (select count(*) n from assessment_responses ar
                    join assessment_campaigns c on c.id = ar.campaign_id
                    where c.organization_id = o.id) resp
left join psique_trials tr on tr.organization_id = o.id
where mem.n_cli > 0 or mem.n = 0
order by uso.t desc nulls last, o.created_at desc;

\echo
\echo '=== CONTATOS DEIXADOS NO SITE (marketing_leads) ==='
select to_char(created_at, 'DD/MM/YYYY') as "data", nome, email as "e-mail",
       empresa, cargo, origem
from marketing_leads
where opt_out_at is null
  and lower(email) <> all (string_to_array(:'internas', ','))
order by created_at desc;

rollback;
SQL
