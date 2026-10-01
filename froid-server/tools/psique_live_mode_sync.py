"""Fonte unica da migration 046: o modo LIVE por transformacao declarada.

A 046 nao reescreve as funcoes financeiras de cabeca: ela e GERADA daqui,
aplicando sobre o texto real das 039/040 uma lista fechada de substituicoes,
cada uma com contagem exigida. O teste de espelho refaz a MESMA geracao e
compara byte a byte com o arquivo em migrations/ — igual ao pacto 042<->038.
Mudou a origem? A 046 denuncia em vez de divergir em silencio.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSAO = "046_psique_live_mode"

# (texto_antigo, texto_novo, ocorrencias_exigidas)
Trocas = list[tuple[str, str, int]]

TRANSFORMACOES_039: dict[str, Trocas] = {
    "psique_v2_checkout_prepare": [
        ("    code text, version text, account text, idem text)",
         "    code text, version text, account text, idem text, live boolean)", 1),
        ("        AND stripe_account_id=account AND livemode=false AND active AND lookup_key IS NOT NULL;",
         "        AND stripe_account_id=account AND livemode=live AND active AND lookup_key IS NOT NULL;", 1),
        ("    IF NOT FOUND THEN RAISE EXCEPTION 'STRIPE_TEST_MAPPING_REQUIRED'; END IF;",
         ("    IF NOT FOUND THEN RAISE EXCEPTION '%', CASE WHEN live\n"
          "        THEN 'STRIPE_LIVE_MAPPING_REQUIRED' ELSE 'STRIPE_TEST_MAPPING_REQUIRED' END; END IF;"), 1),
        ("        mapping.stripe_account_id,false,idem,'CREATED',actor::text)",
         "        mapping.stripe_account_id,live,idem,'CREATED',actor::text)", 1),
    ],
    "psique_v2_stripe_event": [
        ("CREATE FUNCTION psique_v2_stripe_event(",
         "CREATE OR REPLACE FUNCTION psique_v2_stripe_event(", 1),
        ("    IF live IS DISTINCT FROM false THEN RAISE EXCEPTION 'LIVE_EVENT_REFUSED'; END IF;\n",
         "", 1),
        ("    VALUES(evt,account,false,etype,session,linked,payload_hash)",
         "    VALUES(evt,account,live,etype,session,linked,payload_hash)", 1),
        ("        OR row_record.stripe_account_id<>account THEN",
         "        OR row_record.stripe_account_id<>account OR row_record.livemode<>live THEN", 1),
    ],
    "psique_v2_apply_purchase": [
        ("CREATE FUNCTION psique_v2_apply_purchase(",
         "CREATE OR REPLACE FUNCTION psique_v2_apply_purchase(", 1),
        ("    IF (session->>'livemode')::boolean IS DISTINCT FROM false THEN failure:='LIVE_SESSION_REFUSED';",
         ("    IF (session->>'livemode')::boolean IS DISTINCT FROM purchase.livemode THEN\n"
          "        failure:=CASE WHEN purchase.livemode THEN 'TEST_SESSION_REFUSED' ELSE 'LIVE_SESSION_REFUSED' END;"), 1),
    ],
}

TRANSFORMACOES_040: dict[str, Trocas] = {
    "psique_v2_license_price_mapping": [
        ("    catalog_version text, account text)",
         "    catalog_version text, account text, live boolean)", 1),
        ("        AND m.stripe_account_id=account AND m.livemode=false AND m.active",
         "        AND m.stripe_account_id=account AND m.livemode=live AND m.active", 1),
    ],
    "psique_v2_seat_confirm": [
        ("CREATE FUNCTION psique_v2_seat_confirm(",
         "CREATE OR REPLACE FUNCTION psique_v2_seat_confirm(", 1),
        ("        IF payload IS NULL OR (payload->>'livemode')::boolean IS DISTINCT FROM false",
         ("        IF payload IS NULL OR (payload->>'livemode')::boolean\n"
          "                IS DISTINCT FROM (args->>'expected_livemode')::boolean"), 1),
        ("        VALUES(org,preview.pricing_version,preview.pricing_hash,'brl',payload->>'account_id',false,",
         ("        VALUES(org,preview.pricing_version,preview.pricing_hash,'brl',payload->>'account_id',\n"
          "            (payload->>'livemode')::boolean,"), 1),
    ],
}

PREAMBULO = """BEGIN;

-- Fase 6: o modo LIVE passa a existir por decisao explicita do operador.
-- Este arquivo e GERADO por tools/psique_live_mode_sync.py a partir do texto
-- real das migrations 039/040 (teste de espelho garante a igualdade); nao
-- editar a mao. As travas CHECK(livemode=false) viram travas de coerencia:
-- cada linha continua declarando seu modo, e a sessao precisa do prefixo
-- (cs_test_/cs_live_) do modo que a linha declara.

DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conrelid::regclass::text AS tabela, conname
        FROM pg_constraint
        WHERE conrelid IN ('psique_stripe_price_mappings'::regclass,
                           'psique_purchases'::regclass,
                           'psique_stripe_events'::regclass,
                           'psique_organization_licenses'::regclass)
          AND contype='c'
          AND (pg_get_constraintdef(oid) ILIKE '%livemode = false%'
               OR pg_get_constraintdef(oid) LIKE '%cs\\_test\\_%')
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tabela, c.conname);
    END LOOP;
END $$;

ALTER TABLE psique_purchases ADD CONSTRAINT psique_purchases_sessao_por_modo
    CHECK (stripe_checkout_session_id IS NULL OR stripe_checkout_session_id ~
        (CASE WHEN livemode THEN '^cs_live_[A-Za-z0-9]+$' ELSE '^cs_test_[A-Za-z0-9]+$' END));
ALTER TABLE psique_stripe_events ADD CONSTRAINT psique_stripe_events_sessao_por_modo
    CHECK (checkout_session_id IS NULL OR checkout_session_id ~
        (CASE WHEN livemode THEN '^cs_live_[A-Za-z0-9]+$' ELSE '^cs_test_[A-Za-z0-9]+$' END));

-- Assinaturas antigas saem antes das novas (parametro live adicionado).
DROP FUNCTION psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text);
DROP FUNCTION psique_v2_license_price_mapping(uuid,uuid,uuid,text,text);
"""

POSFACIO = f"""
REVOKE ALL ON FUNCTION
    psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text,boolean),
    psique_v2_license_price_mapping(uuid,uuid,uuid,text,text,boolean)
    FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION
        psique_v2_checkout_prepare(uuid,uuid,uuid,text,text,text,text,boolean),
        psique_v2_license_price_mapping(uuid,uuid,uuid,text,text,boolean)
    TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('{VERSAO}');
COMMIT;
"""


def extrair_funcao(texto: str, nome: str) -> str:
    inicio = texto.index(f"CREATE FUNCTION {nome}(")
    fim = texto.index("END $$;", inicio) + len("END $$;")
    return texto[inicio:fim]


def transformar(origem: str, nome: str, trocas: Trocas) -> str:
    corpo = extrair_funcao(origem, nome)
    for antigo, novo, exigidas in trocas:
        encontradas = corpo.count(antigo)
        if encontradas != exigidas:
            raise AssertionError(
                f"{nome}: '{antigo[:60]}...' aparece {encontradas}x, exigidas {exigidas}")
        corpo = corpo.replace(antigo, novo)
    return corpo


def gerar() -> str:
    texto_039 = (RAIZ / "migrations" / "039_psique_stripe_test_checkout.sql").read_text(encoding="utf-8")
    texto_040 = (RAIZ / "migrations" / "040_psique_org_license_test.sql").read_text(encoding="utf-8")
    partes = [PREAMBULO]
    for nome, trocas in TRANSFORMACOES_039.items():
        partes.append("\n" + transformar(texto_039, nome, trocas) + "\n")
    for nome, trocas in TRANSFORMACOES_040.items():
        partes.append("\n" + transformar(texto_040, nome, trocas) + "\n")
    partes.append(POSFACIO)
    return "".join(partes)


if __name__ == "__main__":
    destino = RAIZ / "migrations" / (VERSAO + ".sql")
    destino.write_text(gerar(), encoding="utf-8", newline="\n")
    print(destino.name, "gerado:", len(gerar().splitlines()), "linhas")
