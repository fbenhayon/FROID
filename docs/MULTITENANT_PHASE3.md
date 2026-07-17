# FROID — Operação clínica multiusuário, Fase 3

## Objetivo

Transformar a fundação de organizações e permissões em operação diária segura:

- carteira de sessões compartilhada por clínica;
- consumo concorrente e idempotente de créditos;
- auditoria consultável de acessos e alterações;
- ativação de pilotos por organização com implantação gradual.

## Carteira compartilhada e operação gradual

As migrações `004_shared_credit_wallet.sql` e
`005_wallet_activation_safety.sql` implementam uma carteira que:

- exige contexto de organização, vínculo autenticado e papel autorizado;
- bloqueia a linha com `FOR UPDATE` e impede saldo negativo;
- consome exatamente um crédito por nova sessão;
- usa chave de idempotência, inclusive após adquirir o bloqueio;
- atualiza carteira e razão contábil na mesma transação;
- só aceita eventos pelo usuário PostgreSQL runtime não proprietário;
- mantém o legado como autoridade até a ativação explícita e reconciliada.

Depois da ativação por proprietário ou administrador, o backfill deixa de alterar
o saldo. Compras Stripe e consumos passam a usar o razão transacional. O backend
exige `FROID_RUNTIME_DATABASE_URL`; não há fallback para a conexão proprietária.

Configuração gradual:

- `FROID_SHARED_CREDITS_MODE=off|observe|enforce`;
- `FROID_SHARED_CREDITS_ORGANIZATIONS` limita `enforce` às organizações piloto;
- `FROID_ALLOW_LOCAL_BILLING_FALLBACK=false` impede crédito sem Stripe por padrão.

## Auditoria

Os endpoints organizacionais permitem consultar e ativar a carteira e consultar
a trilha append-only. Criação, leitura, atualização e exclusão de relatórios
registram eventos de sucesso; decisões negadas são registradas desde a Fase 2.

## Entregas e portão da próxima fase

1. débito organizacional com rollback do relatório quando o crédito falha;
2. compra Stripe reconciliada com a carteira compartilhada;
3. ativação explícita e consulta administrativa da carteira;
4. trilha consultável por proprietário, administrador e auditor;
5. testes estáticos de invariantes e testes unitários sem PostgreSQL.

O modo legado permanece autoritativo por organização até a reconciliação e a
ativação explícita. Testes reais de concorrência, RLS, backup e recuperação
exigem PostgreSQL disponível e são portão obrigatório da implantação da Fase 4.
