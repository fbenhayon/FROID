# FROID Psique — migração V1/V2 e operação de schema

Estado em 29/09/2026: código local e PostgreSQL descartável, até a Fase 2A. Nenhuma migration ou configuração de produção foi aplicada nesta entrega. [Relatório da Fase 1](psique-v2-fase1-relatorio.md) e [relatório da Fase 2A](psique-v2-fase2a-relatorio.md).

## Separação entre aplicação e migração

`TenantStore.ensure_schema()` agora verifica versões com SELECT. Não executa arquivos SQL, bootstrap, commit de migration ou DDL. A falta de migrations obrigatórias gera `SchemaNotReady` com as versões ausentes. O processo V1/NR-1 exige o schema legado; 035–038 são opcionais para ele. O leitor do catálogo exige 035/036; o serviço de créditos exige 037/038. Esses leitores recusam schema ausente sem aplicá-lo e sem bloquear V1 por ausência de V2.

`FROID_AUTO_APPLY_MIGRATIONS` é `false` por padrão. Qualquer outro valor é recusado por `TenantStore.from_env()`. O Compose transmite literalmente `false`, sem substituição pelo ambiente. Essa chave impede configuração enganosa; não existe ramo que volte a executar migrations automaticamente.

O comando separado `tools/migrate_schema.py` usa exclusivamente `FROID_MIGRATION_DATABASE_URL`. Por padrão apenas planeja, com transação somente leitura. Escrita exige `--apply`, `--through` com nome exato e `--confirm-database` igual ao banco conectado. Não reutiliza implicitamente credenciais do runtime.

Execuções são serializadas pelo advisory lock histórico. `schema_migration_execution_log` registra versão, SHA-256, usuário do PostgreSQL, início, fim, estado e classe do erro. Uma versão aplicada com hash registrado não pode receber outro arquivo silenciosamente. Migrations antigas sem registro de execução não recebem um hash retroativo inventado. Uma falha transacional deixa registro `failed`, com rollback do arquivo que falhou.

## Novas migrations

| Arquivo | Estruturas adicionadas |
|---|---|
| `035_psique_v2_pricing.sql` | `psique_pricing_tables`, `psique_pricing_offers`, verificações de hash e imutabilidade |
| `036_psique_v2_purchases.sql` | `psique_stripe_price_mappings`, `psique_purchases`, integridade do snapshot e limite TEST |
| `037_psique_trial_credit_state.sql` | Extensões da carteira/ledger, Trial, elegibilidade histórica, fontes, tentativas e reservas |
| `038_psique_credit_commands.sql` | Comando autorizado/transacional, entrega, reconciliação, auditoria e grants restritos |

Não há backfill, conversão automática de carteiras ou reclassificação de organizações. As migrations não concedem crédito, não substituem preços V1 e não alteram funções clínicas/NR-1. A adesão posterior a créditos V2 é um comando explícito, limitado a carteira vazia sem ledger anterior. Carteiras V1 usadas são recusadas. A FK de Purchase para organização adiciona os gatilhos internos de integridade referencial esperados no PostgreSQL, sem ampliar privilégios.

As tabelas novas têm RLS e não possuem grants diretos para o runtime. O catálogo só é instalado por comando explícito, em rascunho. Aplicar SQL, instalar catálogo e aderir a uma carteira V2 são ações distintas.

## Privilégios da Fase 2A

O runtime restrito recebe apenas os novos grants de `SELECT ON schema_migrations` e `EXECUTE ON psique_v2_credit_command(uuid,uuid,uuid,text,jsonb)`, além dos grants legados. Não recebe escrita direta na carteira/ledger/tabelas 2A, execução das primitivas `psique_v2_append`/`psique_v2_expire`, CREATE no schema ou criação de bancos. A fronteira do comando confere organização, usuário, vínculo e papel persistidos. O contexto autenticado e os provedores de evidência são responsabilidades do backend; não expor o comando genérico ao navegador.

O papel de migração precisa ser proprietário das estruturas afetadas, poder executar DDL e registrar a auditoria. Deve permanecer separado da credencial da aplicação. A função de comando usa `SECURITY DEFINER` com search path fixo; seu owner precisa acessar as estruturas necessárias, sem conceder esse privilégio diretamente ao runtime. O papel `froid_runtime` precisa existir antes da migration 038 para receber os grants condicionais. Validar privilégios reais na homologação; a existência local desses grants não comprova a configuração de produção.

Criar/remover bancos filhos foi privilégio exclusivo da credencial de testes descartáveis. Todas as transições da aplicação nos testes 2A rodaram como `froid_runtime`, sem SUPERUSER/BYPASSRLS. Os testes verificaram ausência de DDL e escrita financeira direta.

## Reprodução local

Usar banco descartável vazio com nome `psique_v2_test_...`, credencial local própria e papel `froid_runtime` sem SUPERUSER/BYPASSRLS para conferir grants. Nunca apontar testes destrutivos para banco de cliente. Com as variáveis dedicadas já configuradas, os comandos são:

```powershell
python froid-server/tools/migrate_schema.py --through 036_psique_v2_purchases
python froid-server/tools/migrate_schema.py --through 036_psique_v2_purchases --apply --confirm-database psique_v2_test_phase1
python froid-server/tools/psique_pricing_catalog.py --install-draft --confirm-database psique_v2_test_phase1 --actor operador-local
```

O primeiro comando não escreve. Os demais são exemplos exclusivos para o banco descartável confirmado. `test_psique_phase1_postgres.py` exige a variável dedicada, host local e prefixo seguro; cria bancos filhos com nomes aleatórios e os remove ao terminar. Não utiliza `FROID_DATABASE_URL` nem credenciais implícitas do produto.

Para um novo banco descartável 2A, com `FROID_MIGRATION_DATABASE_URL` apontando explicitamente para ele:

```powershell
python froid-server/tools/migrate_schema.py --through 038_psique_credit_commands
python froid-server/tools/migrate_schema.py --through 038_psique_credit_commands --apply --confirm-database psique_v2_test_phase2a
```

Conferir o nome efetivo do banco antes de usar o exemplo. Nesta entrega, `test_psique_phase2a.py` fez essa aplicação em seus próprios bancos aleatórios, removidos no encerramento. O banco local de conexão da Fase 1 não recebeu 037/038. Sempre conferir a sequência final de migrations antes do merge/aplicação: 037/038 foram os números disponíveis na criação desta entrega.

## Produção: pré-requisito pendente

A seção 50A proíbe entregar migrations V2 ao ambiente de produção enquanto a autoaplicação antiga não estiver neutralizada. O teste local prova a segurança do código novo; **não prova que a instância em produção já o executa**.

Uma publicação futura precisa separar primeiro o código/configuração de neutralização, sem distribuir 035–038 no artefato inicial. Após aprovação e implantação dessa etapa, confirmar a versão realmente executada, a variável dentro do contêiner, as credenciais/permissões e a ausência de DDL em leitura/startup. Só depois considerar a entrega dos arquivos V2 e sua aplicação explícita em uma janela autorizada. Nada disso foi executado nesta fase.

Não há novas flags de Trial, créditos, licença, RBAC, agenda, FLEX ou recomendação instaladas sem consumidores. Elas pertencem às fases operacionais futuras e devem iniciar desativadas, com passagem explícita pelo Compose quando forem utilizadas.

As variáveis HMAC de Trial 2A têm consumidor no serviço interno e foram encaminhadas pelo Compose. Estão vazias nos exemplos; não existe segredo de produção instalado. Configuração de segredo não ativa rotas V2. O contrato de carregamento e rotação está no [protocolo de créditos](psique-credits-v2.md).

## Retorno seguro

Enquanto V2 não tem rotas/consumidores públicos, manter V1 e não instalar/ativar catálogo V2 é suficiente para sua indisponibilidade. Preservar tabelas e histórico: não executar DROP ou apagar compras como rollback. A aplicação explícita é idempotente por versão; os SQL não devem ser reaplicados manualmente fora do runner.

Se uma carteira controlada já aderiu à V2, interromper novas execuções e reconciliar suas reservas com o código 2A. Preservar ledger, fontes e elegibilidade. Não trocar `credit_model` para V1 nem permitir débito legado como atalho: a semântica e os bloqueios financeiros devem continuar válidos. O retorno exige procedimento específico antes de qualquer piloto com saldo real; não foi feita migração reversa nesta fase.

Não restaurar o `ensure_schema()` antigo enquanto arquivos V2 estiverem presentes: isso recria a possibilidade de aplicar schema durante login. O mecanismo de verificação sem escrita deve permanecer. Uma futura mudança de schema ou habilitação de LIVE requer nova migration e autorização; não editar 035–038 após sua aplicação em ambiente compartilhado.
