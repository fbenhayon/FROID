-- Permite no banco os dois papeis do modulo NR-1.
--
-- Defeito encontrado no piloto contra o banco real, e que nenhum dos 433
-- testes pegou porque todos rodam sem PostgreSQL.
--
-- Eu acrescentei 'compliance_manager' e 'occupational_health' a VALID_ROLES em
-- tenant_access.py e construi toda a separacao empregador/clinico em cima
-- deles — mas nunca ampliei o CHECK da tabela, que segue como foi criado na
-- migration 001. Na pratica:
--
--   * nenhuma pessoa jamais poderia receber um dos dois papeis;
--   * as policies de RLS das migrations 010 a 012 que chamam
--     froid_has_role(ARRAY['compliance_manager','occupational_health'])
--     nunca casariam, porque linhas assim nao podem existir;
--   * o modulo corporativo inteiro seria inacessivel, e a razao ficaria
--     escondida atras de um "acesso restrito nesta organizacao".
--
-- A ampliacao e aditiva: nenhum papel existente muda de significado e nenhuma
-- linha ja gravada se torna invalida.

BEGIN;

ALTER TABLE membership_roles
  DROP CONSTRAINT IF EXISTS membership_roles_role_check;

ALTER TABLE membership_roles
  ADD CONSTRAINT membership_roles_role_check
  CHECK (role IN (
      'owner',
      'administrator',
      'supervisor',
      'professional',
      'auditor',
      -- Conduz o programa NR-1 para o empregador. Em organizacao enterprise
      -- nao carrega nenhuma permissao clinica.
      'compliance_manager',
      -- SESMT / medico do trabalho: mesma visao agregada, mais o dever de
      -- agir. Leitura clinica continua exigindo o papel 'professional' e
      -- atribuicao ativa.
      'occupational_health'
  ));

INSERT INTO schema_migrations (version)
VALUES ('016_nr1_roles_check')
ON CONFLICT (version) DO NOTHING;

COMMIT;
