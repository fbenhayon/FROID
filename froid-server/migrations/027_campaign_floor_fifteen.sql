-- O piso de campanha cai de 50 para 15, e nenhuma outra protecao se move.
--
-- POR QUE ELE EXISTIA EM 50
--
-- Em migrations/010 havia um portao so, de contagem absoluta: 50 respostas na
-- campanha, 10 por recorte. Os dois numeros protegiam a mesma coisa, anonimato,
-- e nenhum deles olhava para o tamanho da empresa. O de 50 carregava sozinho
-- duas funcoes que so pareciam uma: impedir reidentificacao E impedir que
-- pouca resposta virasse inventario. Ele nao servia bem para a segunda, e a
-- migration 025 resolveu isso com o portao de representatividade, que compara a
-- coorte com o efetivo declarado. Desde 025, uma empresa de 3.000 pessoas com
-- 50 respostas e barrada pela amostra exigida (341), nao pelo piso de 50.
--
-- POR QUE ELE VIRA UM BLOQUEIO PURO
--
-- Com a representatividade no lugar, restou ao piso de 50 uma unica faixa de
-- efeito: organizacoes de 10 a 49 trabalhadores. Nessa faixa a amostra exigida
-- ja e o CENSO — a formula pede todo mundo, e o portao de representatividade
-- portanto exige 100% de adesao. O piso de 50 nao acrescenta protecao ali:
-- acrescenta impossibilidade aritmetica. Uma empresa de 30 pessoas nunca reune
-- 50 respostas, por mais que todas respondam. Ela ficava fora do modulo nao por
-- ter falhado em algum criterio, mas por existir.
--
-- Essas sao exatamente as empresas que a NR-1 tambem obriga. A norma nao
-- dispensa organizacao pequena de gerenciar risco psicossocial; ME e EPP sao
-- dispensadas do PGR, e nem elas sao dispensadas da AEP.
--
-- O QUE **NAO** MUDA, E ESSA E A PARTE QUE IMPORTA
--
-- 1. froid_nr1_min_cohort_cut() continua em 10. Ele e o piso que protege
--    PESSOA, porque e ele que decide o tamanho de cada coorte publicada. Um
--    recorte de 12 pessoas ja podia publicar antes desta migration, desde que a
--    campanha inteira somasse 50; o que muda aqui e quanta resposta a campanha
--    precisa somar, nao quao pequeno pode ser um grupo publicado.
--
-- 2. O portao de representatividade continua igual, e continua sendo o que
--    barra campanha rala em empresa grande. Efetivo nao declarado devolve NULL
--    em froid_nr1_required_sample e o recorte nao aparece: sem denominador nao
--    ha o que representar.
--
-- 3. As linhas do agregado particionam as respostas por unit_id. Nao existe
--    linha "organizacao inteira" convivendo com as linhas das unidades, entao
--    nao ha o que subtrair de que: o ataque por diferenca nao tem superficie.
--
-- A ORDEM IMPORTOU
--
-- Esta reducao so e segura porque a proporcao passou a ser publicada em faixa.
-- Enquanto o painel devolvia critical_ratio com tres casas ao lado do tamanho
-- exato da coorte, uma multiplicacao recuperava a contagem de pessoas na faixa
-- critica — e numa empresa de 15, onde a chefia conhece todo mundo, "uma
-- pessoa" esta a um passo de um nome. Baixar o piso primeiro teria aberto o
-- mercado das empresas pequenas entregando contagem de cabecas ao empregador.
--
-- Nada em 1.5 prescreve taxa de resposta ou tamanho minimo de coorte. Este
-- numero e escolha metodologica desta plataforma, e continua declarado como tal
-- no documento de criterios, onde pode ser auditado e contestado.

BEGIN;

CREATE OR REPLACE FUNCTION froid_nr1_min_cohort_total() RETURNS integer
LANGUAGE sql IMMUTABLE AS $$ SELECT 15 $$;

-- Um piso de campanha abaixo do piso de recorte seria incoerente: liberaria uma
-- campanha que nenhum recorte dela poderia publicar. A verificacao roda agora,
-- na migration, e nao em tempo de consulta — se alguem editar um dos dois
-- numeros no futuro, o deploy para aqui em vez de servir resultado torto.
DO $$
BEGIN
    IF froid_nr1_min_cohort_total() < froid_nr1_min_cohort_cut() THEN
        RAISE EXCEPTION
            'piso de campanha (%) nao pode ser menor que o piso de recorte (%)',
            froid_nr1_min_cohort_total(), froid_nr1_min_cohort_cut();
    END IF;
END
$$;

INSERT INTO schema_migrations (version)
VALUES ('027_campaign_floor_fifteen')
ON CONFLICT (version) DO NOTHING;

COMMIT;
