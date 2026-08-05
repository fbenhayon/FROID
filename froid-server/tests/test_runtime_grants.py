"""Toda tabela criada precisa dizer quem pode escrever nela.

Esta classe de defeito e traicoeira porque nao aparece no deploy: a migration
aplica, a tabela entra em schema_migrations, tudo parece pronto — e a primeira
escrita falha por permissao, longe da mudanca que a causou.

Foi o que aconteceu com as migrations 018 a 021. Quatro tabelas criadas com
politica de RLS e nenhum GRANT. O formulario de captacao devolveu 503 com a
tabela ja criada e vazia, e o modulo de validade teria feito o mesmo no
primeiro uso real — so que na frente de um profissional, e nao num curl.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MIGRATIONS = SERVER_DIR / "migrations"

# Tabelas que o runtime deliberadamente nao acessa.
#
# assessment_responses e assessment_response_items sao o caso mais importante:
# a migration 014 REVOGA o acesso de propósito, para que resposta crua de
# trabalhador nao seja legivel em tempo de execucao por caminho nenhum. O
# agregado sai por funcao SECURITY DEFINER.
SEM_ACESSO_DE_RUNTIME = {
    # Concedidas na 010 e revogadas na 014: o runtime grava a resposta do
    # trabalhador e nao pode le-la de volta.
    "assessment_responses",
    "assessment_response_items",
    "schema_migrations",
}

# Divida herdada, listada em vez de escondida.
#
# Estas quatro sao anteriores a este teste e nao vieram da mudanca que o
# motivou. Podem estar certas — migration_runs e escrita pelo papel de
# migracao, e o webhook do Stripe provavelmente usa conexao administrativa —
# mas ninguem verificou, e legal_acceptance_events e a que mais merece olhar,
# porque o aceite dos termos acontece em tempo de execucao.
#
# Ficam nomeadas aqui para que encolher a lista seja possivel. Um conjunto
# vazio de excecoes seria mais bonito e teria custado esconde-las.
PENDENTE_DE_VERIFICACAO = {
    "automatic_recharges",
    "legal_acceptance_events",
    "migration_runs",
    "stripe_webhook_events",
}


def tabelas_criadas() -> dict:
    """Tabela -> migration que a criou."""
    encontradas = {}
    for sql in sorted(MIGRATIONS.glob("*.sql")):
        texto = sql.read_text(encoding="utf-8")
        for m in re.finditer(
            r"CREATE TABLE (?:IF NOT EXISTS )?([a-z_]+)", texto, re.I
        ):
            encontradas.setdefault(m.group(1).lower(), sql.name)
    return encontradas


def tabelas_com_grant() -> set:
    """Tabelas concedidas ao runtime.

    Duas armadilhas ja custaram uma versao deste teste cada.

    Regex com quantificador aninhado travou em backtracking. E partir por
    ponto-e-virgula nao funciona: dentro de um bloco DO, o "IF EXISTS (...)
    THEN" nao termina em ponto-e-virgula, entao o GRANT seguinte fica no meio
    do fragmento em vez de no comeco dele.

    O que funciona: achar cada "TO froid_runtime" e varrer para tras ate o
    GRANT mais proximo.
    """
    concedidas = set()
    for sql in sorted(MIGRATIONS.glob("*.sql")):
        # Comentarios primeiro: um "--" corre ate o fim da linha, e sem
        # remove-lo o comentario engole o GRANT que vem embaixo dele.
        # Depois de remover os comentarios, colapsa o espaco em branco: os
        # GRANT do repositorio quebram a linha logo apos o ON, e procurar
        # " ON " num texto com "ON\n" nao acha nada — a versao anterior deste
        # teste acusou como sem GRANT ate a tabela organizations.
        texto = " ".join(
            "\n".join(
                linha.split("--")[0]
                for linha in sql.read_text(encoding="utf-8").splitlines()
            ).split()
        )
        alto = texto.upper()
        pos = 0
        while True:
            fim_g = alto.find("TO FROID_RUNTIME", pos)
            if fim_g < 0:
                break
            pos = fim_g + 1
            ini_g = alto.rfind("GRANT", 0, fim_g)
            if ini_g < 0:
                continue
            corpo = alto[ini_g:fim_g]
            if " ON FUNCTION" in corpo or " ON SCHEMA" in corpo:
                continue
            onde = corpo.find(" ON ")
            if onde < 0:
                continue
            for nome in texto[ini_g + onde + 4:fim_g].split(","):
                limpo = nome.strip().lower()
                if limpo:
                    concedidas.add(limpo)
    return concedidas


class GrantsTests(unittest.TestCase):
    def test_toda_tabela_declara_o_acesso_do_runtime(self):
        criadas = tabelas_criadas()
        concedidas = tabelas_com_grant()
        faltando = sorted(
            f"{t} (criada em {criadas[t]})"
            for t in criadas
            if t not in concedidas
            and t not in SEM_ACESSO_DE_RUNTIME
            and t not in PENDENTE_DE_VERIFICACAO
        )
        self.assertEqual(
            faltando, [],
            "tabela sem GRANT para froid_runtime — a escrita vai falhar em "
            "producao, longe do deploy que a criou:\n  " + "\n  ".join(faltando),
        )


    def test_a_divida_herdada_nao_cresce(self):
        # A lista pode encolher; nao pode ganhar nome novo. Toda tabela criada
        # daqui em diante declara seu acesso na propria migration.
        self.assertEqual(len(PENDENTE_DE_VERIFICACAO), 4)
        criadas = tabelas_criadas()
        for tabela in PENDENTE_DE_VERIFICACAO:
            self.assertIn(tabela, criadas, f"{tabela} nao existe mais; remova da lista")

    def test_a_revogacao_das_respostas_cruas_continua_de_pe(self):
        """O runtime grava resposta e nao pode le-la de volta.

        A migration 010 concede INSERT — e o trabalhador gravando a propria
        resposta. A 014 vem depois e REVOGA tudo, porque o que importa nao e
        impedir a escrita, e sim a leitura: se o runtime puder consultar a
        tabela, o k-anonimato deixa de ser estrutural e passa a depender de
        ninguem escrever a query errada.

        A primeira versao deste teste procurava a ausencia do GRANT e falhava,
        acusando um sistema correto.
        """
        texto = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS.glob("*.sql"))
        )
        for tabela in ("assessment_responses", "assessment_response_items"):
            self.assertIn(
                f"REVOKE ALL ON {tabela} FROM froid_runtime", texto, tabela
            )
        # E a revogacao precisa vir depois da concessao, ou nao revoga nada.
        self.assertGreater(
            texto.index("REVOKE ALL ON assessment_responses"),
            texto.index("GRANT INSERT ON assessment_responses"),
        )

    def test_purga_so_acontece_pela_funcao(self):
        # DELETE direto em assessment_responses contornaria as duas travas da
        # purga: campanha encerrada e inventario consolidado.
        texto = "\n".join(
            p.read_text(encoding="utf-8") for p in MIGRATIONS.glob("*.sql")
        )
        self.assertNotRegex(
            texto, r"GRANT\s+[A-Z, ]*DELETE[A-Z, ]*\s+ON\s+assessment_responses"
        )
        self.assertIn("froid_purge_campaign_responses", texto)


if __name__ == "__main__":
    unittest.main()
