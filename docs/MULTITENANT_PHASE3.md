# FROID — Operação clínica multiusuário, Fase 3

## Objetivo

Transformar a fundação de organizações e permissões em operação diária segura:

- carteira de sessões compartilhada por clínica;
- consumo concorrente e idempotente de créditos;
- telas de seleção da organização, membros e atribuições;
- auditoria consultável de acessos, exportações e compartilhamentos;
- ativação de pilotos por organização com métricas operacionais.

## Primeiro checkpoint: carteira compartilhada

A migração `004_shared_credit_wallet.sql` introduz uma função transacional que:

- exige contexto de organização e vínculo autenticado;
- valida o papel para compra, ajuste, reembolso ou consumo;
- bloqueia a linha da carteira com `FOR UPDATE`;
- impede saldo negativo;
- consome exatamente um crédito por sessão;
- usa chave de idempotência para impedir cobrança duplicada;
- atualiza carteira e razão contábil na mesma transação;
- só pode ser chamada pelo usuário PostgreSQL runtime não proprietário.

O backend exige `FROID_RUNTIME_DATABASE_URL` para qualquer evento da carteira.
Não existe fallback para a conexão proprietária, evitando contornar o RLS.

## Próximos incrementos desta fase

1. substituir o débito legado por `apply_credit_event` no modo piloto;
2. reconciliar compras Stripe com a carteira organizacional;
3. criar testes PostgreSQL concorrentes e de idempotência;
4. implementar as telas administrativas;
5. registrar eventos de exportação e compartilhamento;
6. criar painel de auditoria e alertas de acesso negado.

O modo legado permanece autoritativo até a reconciliação financeira demonstrar
equivalência entre perfil, carteira e razão de créditos.
