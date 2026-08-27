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

# Escritas apenas pela conexao de OWNER, e por isso corretamente sem GRANT.
#
# Estas quatro entraram na lista como divida herdada, com a suspeita de serem
# defeito. Foram verificadas uma a uma, rastreando qual conexao escreve cada
# uma: nenhuma passa pelo papel de runtime.
#
# E o resultado inverte a conclusao intuitiva. Conceder acesso de runtime a
# elas nao teria corrigido nada — teria aberto escrita em deduplicacao de
# webhook de pagamento, em contabilidade de migracao e no livro imutavel de
# aceites legais. A ausencia de GRANT aqui e a decisao certa, e o teste
# generico nao tinha como distinguir "faltou" de "nao deve ter".
#
# legal_acceptance_events era a mais suspeita, porque o aceite acontece em
# tempo de execucao. Mas record_legal_acceptance usa _connect() sem
# runtime=True, de proposito: evidencia legal imutavel nao se grava pelo papel
# que atende requisicao web.
ESCRITAS_PELO_OWNER = {
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
            and t not in ESCRITAS_PELO_OWNER
        )
        self.assertEqual(
            faltando, [],
            "tabela sem GRANT para froid_runtime — a escrita vai falhar em "
            "producao, longe do deploy que a criou:\n  " + "\n  ".join(faltando),
        )


    def test_as_tabelas_de_owner_nao_ganham_acesso_de_runtime(self):
        """A ausencia de GRANT aqui e decisao, e conceder seria regressao.

        Dar escrita de runtime a estas quatro abriria deduplicacao de webhook
        de pagamento, contabilidade de migracao e o livro imutavel de aceites
        legais ao papel que atende requisicao web.
        """
        concedidas = tabelas_com_grant()
        for tabela in ESCRITAS_PELO_OWNER:
            self.assertNotIn(tabela, concedidas, tabela)

    def test_o_codigo_confirma_que_sao_escritas_pelo_owner(self):
        # A verificacao que resolveu a duvida, mantida executavel: se alguem
        # mover uma destas escritas para uma conexao de runtime, o teste
        # aponta antes que a falha de permissao apareca em producao.
        fonte = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        for tabela in ESCRITAS_PELO_OWNER:
            for trecho in re.finditer(
                rf"(INSERT INTO|UPDATE)\s+{tabela}(?![A-Za-z0-9_])", fonte
            ):
                antes = fonte[max(0, trecho.start() - 2500):trecho.start()]
                metodo = antes.rfind("    def ")
                corpo = antes[metodo:] if metodo >= 0 else antes
                self.assertNotIn(
                    "runtime=True", corpo,
                    f"{tabela} passou a ser escrita pelo papel de runtime",
                )

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

    def test_o_codigo_de_runtime_nao_consulta_a_tabela_revogada(self):
        """A revogacao no banco so vira defeito quando o codigo a ignora.

        E foi o que aconteceu: nr1_campaign_progress passou a contar respostas
        com dois subselects diretos em assessment_responses. A suite continuou
        verde — ela abre a conexao de OWNER, que enxerga tudo — e producao,
        que roda pelo papel de runtime, devolveu 503 em TODO painel NR-1 com
        "permission denied for table assessment_responses". O sintoma ficou a
        tres camadas do erro: a empresa via "painel NR-1 indisponivel" e nao
        conseguia gerar o inventario, que chama o mesmo progresso.

        Este teste e estatico de proposito. Um teste de integracao so acusaria
        isto rodando como froid_runtime contra um Postgres real, que e
        exatamente a configuracao que a suite nao tem.
        """
        codigo = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
        for tabela in ("assessment_responses", "assessment_response_items"):
            for verbo in ("FROM", "JOIN", "UPDATE", "INTO"):
                self.assertNotIn(
                    f"{verbo} {tabela}", codigo,
                    f"tenant_store consulta {tabela} direto, e o papel de "
                    f"runtime nao tem acesso a ela desde a migration 014. "
                    f"O agregado precisa sair por funcao SECURITY DEFINER.",
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
