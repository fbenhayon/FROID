"""Fonte unica da migration 051: multimoeda do Psique por transformacao declarada.

Mesmo pacto da 046 (tools/psique_live_mode_sync.py): a 051 nao reescreve a
funcao financeira de cabeca. O corpo de psique_v2_seat_confirm e extraido do
texto REAL da 046 e recebe uma lista fechada de substituicoes, cada uma com
contagem exigida; o teste de espelho refaz a mesma geracao e compara byte a
byte com migrations/051_psique_multimoeda.sql. Mudou a origem? A 051 denuncia
em vez de divergir em silencio.

O que a 051 faz (decisao do dono, 06 e 07/10/2026 — docs/multimoeda-psique-nr1-desenho.md):
- amplia os tres CHECK (currency='brl') para brl/usd/eur, sem tocar linha
  existente (ampliar nunca falha sobre dados BRL);
- a licenca passa a gravar a moeda da tabela de precos do preview, em vez do
  literal 'brl', e exige que o Price assinado pertenca a essa mesma tabela.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERSAO = "051_psique_multimoeda"
ORIGEM = "046_psique_live_mode"
MOEDAS = ("brl", "usd", "eur")

# (texto_antigo, texto_novo, ocorrencias_exigidas)
Trocas = list[tuple[str, str, int]]

TRANSFORMACOES_046: dict[str, Trocas] = {
    "psique_v2_seat_confirm": [
        ("    new_billed integer; new_next integer; new_status text;",
         "    new_billed integer; new_next integer; new_status text; moeda text;", 1),
        ("        INSERT INTO psique_organization_licenses(organization_id,pricing_version,pricing_hash,\n",
         ("        -- Multimoeda (051): a moeda da licenca e a da tabela de precos do\n"
          "        -- preview, e o Price assinado precisa pertencer a essa mesma tabela.\n"
          "        SELECT t.currency INTO moeda FROM psique_pricing_tables t\n"
          "            WHERE t.code='FROID_PSIQUE_V2' AND t.version=preview.pricing_version;\n"
          "        IF moeda IS NULL THEN RAISE EXCEPTION 'PREVIEW_PRICING_VERSION_NOT_INSTALLED'; END IF;\n"
          "        IF NOT EXISTS (SELECT 1 FROM psique_stripe_price_mappings m\n"
          "                JOIN psique_pricing_tables t ON t.id=m.pricing_table_id\n"
          "                WHERE m.stripe_price_id=payload->>'price_id'\n"
          "                AND t.version=preview.pricing_version) THEN\n"
          "            RAISE EXCEPTION 'LICENSE_PRICE_NOT_FROM_PREVIEW_CATALOG';\n"
          "        END IF;\n"
          "        INSERT INTO psique_organization_licenses(organization_id,pricing_version,pricing_hash,\n"), 1),
        ("        VALUES(org,preview.pricing_version,preview.pricing_hash,'brl',payload->>'account_id',",
         "        VALUES(org,preview.pricing_version,preview.pricing_hash,moeda,payload->>'account_id',", 1),
    ],
}

LISTA = ",".join("'%s'" % m for m in MOEDAS)

PREAMBULO = f"""BEGIN;

-- Multimoeda do FROID Psique (decisao do dono, 06 e 07/10/2026): o mesmo
-- numero em BRL, USD e EUR, sem conversao, moeda escolhida pelo idioma. Cada
-- moeda e uma tabela de precos propria (versao "2.1", "2.1-usd", "2.1-eur";
-- uma ativa por moeda pelo indice da 035). Este arquivo e GERADO por
-- tools/psique_multimoeda_sync.py a partir do texto real da 046 (teste de
-- espelho garante a igualdade); nao editar a mao.

-- 1. Os tres CHECK (currency = 'brl') viram CHECK (currency IN (...)).
--    Ampliar nunca falha sobre as linhas BRL existentes.
DO $$
DECLARE c record;
BEGIN
    FOR c IN SELECT conrelid::regclass::text AS tabela, conname
        FROM pg_constraint
        WHERE conrelid IN ('psique_pricing_tables'::regclass,
                           'psique_purchases'::regclass,
                           'psique_organization_licenses'::regclass)
          AND contype='c'
          AND pg_get_constraintdef(oid) ILIKE '%currency = ''brl''%'
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', c.tabela, c.conname);
    END LOOP;
END $$;

ALTER TABLE psique_pricing_tables ADD CONSTRAINT psique_pricing_tables_moeda
    CHECK (currency IN ({LISTA}));
ALTER TABLE psique_purchases ADD CONSTRAINT psique_purchases_moeda
    CHECK (currency IN ({LISTA}));
ALTER TABLE psique_organization_licenses ADD CONSTRAINT psique_organization_licenses_moeda
    CHECK (currency IN ({LISTA}));

-- 2. A licenca grava a moeda da tabela do preview (antes: literal 'brl').
"""

POSFACIO = f"""
-- 3. A confirmacao da licenca le a tabela de precos DO PREVIEW antes de
--    tocar o Stripe: o Price certo e resolvido pela versao gravada no preview,
--    nunca repetido pelo cliente.
CREATE FUNCTION psique_v2_seat_preview_catalog(org uuid, member uuid, actor uuid, preview_ref uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE preview psique_seat_changes%ROWTYPE;
BEGIN
    PERFORM psique_v2_require_billing_member(org,member,actor);
    SELECT * INTO preview FROM psique_seat_changes WHERE id=preview_ref AND organization_id=org;
    IF NOT FOUND THEN RAISE EXCEPTION 'PREVIEW_ACCESS_DENIED' USING ERRCODE='42501'; END IF;
    RETURN jsonb_build_object('preview_id',preview.id,'change_status',preview.change_status,
        'pricing_version',preview.pricing_version,'pricing_hash',preview.pricing_hash);
END $$;

REVOKE ALL ON FUNCTION psique_v2_seat_preview_catalog(uuid,uuid,uuid,uuid) FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='froid_runtime') THEN
    GRANT EXECUTE ON FUNCTION psique_v2_seat_preview_catalog(uuid,uuid,uuid,uuid) TO froid_runtime;
END IF; END $$;

INSERT INTO schema_migrations(version) VALUES('{VERSAO}');
COMMIT;
"""


def extrair_funcao(texto: str, nome: str) -> str:
    inicio = texto.index(f"CREATE OR REPLACE FUNCTION {nome}(")
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
    texto_046 = (RAIZ / "migrations" / (ORIGEM + ".sql")).read_text(encoding="utf-8")
    partes = [PREAMBULO]
    for nome, trocas in TRANSFORMACOES_046.items():
        partes.append("\n" + transformar(texto_046, nome, trocas) + "\n")
    partes.append(POSFACIO)
    return "".join(partes)


if __name__ == "__main__":
    destino = RAIZ / "migrations" / (VERSAO + ".sql")
    destino.write_text(gerar(), encoding="utf-8", newline="\n")
    print(destino.name, "gerado:", len(gerar().splitlines()), "linhas")
