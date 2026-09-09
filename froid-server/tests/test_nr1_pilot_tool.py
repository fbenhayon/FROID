from pathlib import Path
import re
import sys
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

TOOL = SERVER_DIR / "tools" / "nr1_pilot_dryrun.py"
SOURCE = TOOL.read_text(encoding="utf-8")

# Tudo que guarda dado de pessoa real. O piloto escreve num banco de producao:
# encostar em qualquer uma destas seria inaceitavel.
CLINICAL_TABLES = {
    "patients",
    "patient_assignments",
    "session_reports",
    "consents",
    "credit_ledger",
    "organization_wallets",
    "subscription_plans",
    "organization_subscriptions",
    "automatic_recharges",
    "stripe_webhook_events",
    "data_subject_requests",
    "data_subject_request_events",
    "legal_acceptance_events",
    "audit_events",
    "membership_invitations",
}

# Fora do NR-1, o piloto so pode criar o proprio usuario e vinculo — sem eles a
# agregacao nao roda, porque froid_nr1_dimension_scores exige vinculo ativo.
ALLOWED_NON_NR1 = {"organizations", "users", "organization_memberships", "membership_roles"}


def written_tables():
    return set(
        re.findall(r"(?:INSERT INTO|DELETE FROM|UPDATE)\s+([a-z_]+)", SOURCE)
    ) | set(re.findall(r'\("([a-z_]+)", "organization_id=%s"\)', SOURCE))


class PilotSafetyTests(unittest.TestCase):
    def test_never_writes_to_a_clinical_table(self):
        invadidas = written_tables() & CLINICAL_TABLES
        self.assertEqual(
            invadidas, set(),
            f"O piloto escreve em tabela com dado de pessoa real: {sorted(invadidas)}",
        )

    def test_only_touches_nr1_tables_plus_the_declared_exceptions(self):
        fora = {
            table
            for table in written_tables()
            if table not in ALLOWED_NON_NR1
            and not table.startswith(("assessment_", "aep_", "psychosocial_", "gro_", "measure_", "organization_unit", "worker_"))
        }
        self.assertEqual(fora, set(), f"tabelas inesperadas: {sorted(fora)}")

    def test_everything_it_creates_is_removed(self):
        criadas = set(re.findall(r"INSERT INTO\s+([a-z_]+)", SOURCE))
        destroy = SOURCE[SOURCE.index("def destroy("):SOURCE.index("def main(")]
        removidas = set(re.findall(r"(?:DELETE FROM)\s+([a-z_]+)", destroy)) | set(
            re.findall(r'\("([a-z_]+)", "organization_id=%s"\)', SOURCE)
        )
        # assessment_response_items sai pelo subselect de responses.
        removidas.add("assessment_response_items")
        faltando = criadas - removidas
        self.assertEqual(
            faltando, set(),
            f"O piloto cria mas nao remove: {sorted(faltando)}",
        )

    def test_removal_is_scoped_to_the_pilot(self):
        destroy = SOURCE[SOURCE.index("def destroy("):SOURCE.index("def main(")]
        for statement in re.findall(r"DELETE FROM [a-z_]+[^\"']*", destroy):
            self.assertIn(
                "WHERE", statement,
                f"DELETE sem WHERE apagaria a tabela inteira: {statement}",
            )

    def test_pilot_email_cannot_belong_to_a_real_person(self):
        # .invalid e reservado por RFC 2606 e nunca resolve.
        self.assertIn("@teste.invalid", SOURCE)

    def test_schema_is_ensured_for_every_mode_including_destroy(self):
        """A limpeza também depende de migration.

        A 017 corrige o gatilho que impedia remover os critérios do GRO. Como
        o schema só era aplicado em --create e --report, o --destroy continuava
        batendo no gatilho antigo mesmo com o conserto publicado: a correção
        existia e não chegava a quem precisava dela.
        """
        main = SOURCE[SOURCE.index("def main("):]
        chamada = main.index("ensure_migrations()")
        conexao = main.index("with connect()")
        self.assertLess(
            chamada, conexao,
            "ensure_migrations deve rodar antes de abrir a transação do piloto",
        )
        # A trava era por texto — proibia a frase "if args.create or
        # args.report:" em qualquer lugar do arquivo. Guardava o certo pelo
        # motivo errado: qualquer código novo que use essa condição para outra
        # coisa reprova, e foi o que aconteceu quando `--grant` passou a decidir
        # se o relatório sai. A invariante real é a chamada estar no corpo de
        # main() e não dentro de um `if` — verificável pela indentação.
        linhas = [
            linha for linha in main.splitlines()
            if linha.strip() == "ensure_migrations()"
        ]
        self.assertEqual(len(linhas), 1, "ensure_migrations deve ser chamada uma vez")
        recuo = len(linhas[0]) - len(linhas[0].lstrip())
        self.assertEqual(
            recuo, 4,
            "ensure_migrations não pode ser condicionada ao modo: recuo maior "
            "que 4 significa que ela está dentro de um if",
        )

    def test_uses_a_fixed_namespace_so_removal_is_exact(self):
        self.assertIn("PILOT_NAMESPACE", SOURCE)
        self.assertIn("uuid.uuid5(PILOT_NAMESPACE", SOURCE)

    def test_simulated_answers_are_deterministic(self):
        # Duas execucoes precisam dar o mesmo numero, senao nao ha conferencia.
        self.assertIn("random.Random(", SOURCE)
        self.assertNotIn("random.seed()", SOURCE)


class PilotScenarioTests(unittest.TestCase):
    """O cenario simulado precisa exercitar os tres vereditos de eficacia."""

    def setUp(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("nr1_pilot_dryrun", TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)

    def _mean(self, code, polarity, unit, wave, draws=400):
        import random

        rng = random.Random(f"{code}|{wave}")
        dimension = {"code": code, "polarity": polarity}
        valores = [
            self.tool.answer_for(rng, dimension, unit, wave) for _ in range(draws)
        ]
        return sum(valores) / len(valores)

    def test_overload_improves_between_waves(self):
        antes = self._mean("sobrecarga", "risk", self.tool.UNIT_ATENDIMENTO, "baseline")
        depois = self._mean("sobrecarga", "risk", self.tool.UNIT_ATENDIMENTO, "followup")
        self.assertGreater(
            antes - depois, 0.8,
            "o cenario precisa produzir uma melhora clara em sobrecarga",
        )

    def test_harassment_worsens_between_waves(self):
        antes = self._mean("assedio", "risk", self.tool.UNIT_ATENDIMENTO, "baseline")
        depois = self._mean("assedio", "risk", self.tool.UNIT_ATENDIMENTO, "followup")
        self.assertGreater(
            depois - antes, 0.8,
            "o cenario precisa produzir uma piora clara em assedio",
        )

    def test_other_dimensions_stay_inside_the_noise(self):
        antes = self._mean("relacoes", "risk", self.tool.UNIT_LOGISTICA, "baseline")
        depois = self._mean("relacoes", "risk", self.tool.UNIT_LOGISTICA, "followup")
        self.assertLess(
            abs(antes - depois), 0.3,
            "as demais dimensoes devem oscilar dentro do ruido, para que o "
            "veredito 'sem mudanca' seja exercitado",
        )

    def test_answers_stay_inside_the_scale(self):
        import random

        rng = random.Random("escala")
        for code, polarity in (("sobrecarga", "risk"), ("suporte_social", "protective")):
            for wave in ("baseline", "followup"):
                for _ in range(300):
                    valor = self.tool.answer_for(
                        rng, {"code": code, "polarity": polarity},
                        self.tool.UNIT_ATENDIMENTO, wave,
                    )
                    self.assertTrue(1 <= valor <= 5, f"{code} gerou {valor}")

    def test_pseudonyms_are_unique_across_the_whole_population(self):
        """O banco impõe um pseudônimo por pessoa por campanha.

        A primeira versão do roteiro numerava a partir de zero em cada unidade
        e colidia na segunda — simulava duas pessoas com o mesmo crachá. A
        restrição do banco estava certa; o gerador é que estava errado.
        """
        gerados = [
            self.tool.pseudonym_for(unit_id, indice)
            for unit_id, total in self.tool.POPULATION.items()
            for indice in range(total)
        ]
        self.assertEqual(
            len(gerados), len(set(gerados)),
            "pseudônimos colidem entre unidades da mesma campanha",
        )

    def test_pseudonym_is_deterministic(self):
        unit = self.tool.UNIT_ATENDIMENTO
        self.assertEqual(
            self.tool.pseudonym_for(unit, 7), self.tool.pseudonym_for(unit, 7)
        )

    def test_ids_are_unique_across_units(self):
        """Convite e resposta também derivam de (campanha, unidade, índice)."""
        import uuid as uuid_module

        vistos = set()
        for campaign in (self.tool.CAMPAIGN_BASE, self.tool.CAMPAIGN_FOLLOW):
            for unit_id, total in self.tool.POPULATION.items():
                for indice in range(total):
                    for prefixo in ("invite", "response"):
                        gerado = uuid_module.uuid5(
                            self.tool.PILOT_NAMESPACE,
                            f"{prefixo}/{campaign}/{unit_id}/{indice}",
                        )
                        self.assertNotIn(gerado, vistos, f"{prefixo} duplicado")
                        vistos.add(gerado)

    def test_population_crosses_both_cohort_floors(self):
        from nr1_compliance import MIN_COHORT_CUT, MIN_COHORT_TOTAL

        total = sum(self.tool.POPULATION.values())
        self.assertGreaterEqual(total, MIN_COHORT_TOTAL)
        for unit, count in self.tool.POPULATION.items():
            self.assertGreaterEqual(count, MIN_COHORT_CUT, f"{unit} abaixo do piso")


if __name__ == "__main__":
    unittest.main()


class ORenomearNaoDeixaPilotoOrfao(unittest.TestCase):
    """Renomear a organizacao do piloto sem cuidar da remocao a deixa no banco.

    `destroy` confere o nome antes de apagar — e a trava e certa: e o que
    impede o script de remover uma organizacao real que por acaso tivesse o
    mesmo id. Mas trocar a constante sozinha faria o --destroy nao encontrar a
    organizacao criada com o nome anterior, e ela ficaria para sempre no banco,
    com nome de demonstracao, aparecendo na lista de alguem.

    Apurado em 27/08/2026, ao renomear para "FROID NR-1 Piloto 01".
    """

    def setUp(self):
        self.fonte = SOURCE

    def test_a_remocao_aceita_os_nomes_anteriores(self):
        self.assertIn("NOMES_ANTERIORES", self.fonte)
        self.assertIn("legal_name = ANY(%s)", self.fonte)

    def test_a_criacao_renomeia_organizacao_ja_existente(self):
        # Sem isto a primeira execucao fixa o nome e as seguintes so parecem
        # funcionar: o ON CONFLICT antigo so atualizava organization_type.
        self.assertIn("legal_name=EXCLUDED.legal_name", self.fonte)
        self.assertIn("display_name=EXCLUDED.display_name", self.fonte)

    def test_o_nome_atual_nao_esta_vazio(self):
        self.assertIn(
            'ORG_LEGAL_NAME = "FROID NR-1 Piloto 01 — DADOS SIMULADOS"',
            self.fonte,
        )


class DocumentoCompletoDoPiloto(unittest.TestCase):
    """O cenário precisa fechar documentos sem esconder que é simulação."""

    def setUp(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("nr1_pilot_documentos", TOOL)
        self.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool)

    def test_toda_informacao_complementar_e_marcada_como_demonstracao(self):
        campos = self.tool._aep_text("Unidade fictícia", "baseline")
        for nome, valor in campos.items():
            self.assertTrue(valor.strip(), f"campo AEP vazio: {nome}")
            self.assertTrue(
                "DEMONSTRA" in valor or "simulad" in valor.lower(),
                f"campo AEP poderia ser lido como fato real: {nome}",
            )

    def test_ciclo_liga_as_duas_campanhas_a_documentos(self):
        fonte = SOURCE[SOURCE.index("def complete_cycle("):SOURCE.index("def _json(")]
        self.assertIn("_create_aep_documents", fonte)
        self.assertIn("_store_inventory", fonte)
        self.assertIn("_store_action_plan", fonte)
        self.assertIn("_store_effectiveness", fonte)
        self.assertIn("CAMPAIGN_BASE", fonte)
        self.assertIn("CAMPAIGN_FOLLOW", fonte)

    def test_inventario_recebe_o_vinculo_com_a_aep(self):
        fonte = SOURCE[SOURCE.index("def _store_inventory("):SOURCE.index("def _create_aep_documents(")]
        self.assertIn("criteria_id, aep_id", fonte)
        self.assertIn("aep_by_unit[risk.unit_id]", fonte)

    def test_reavaliacao_abre_correcao_sem_inventar_terceira_medicao(self):
        fonte = SOURCE[SOURCE.index("def complete_cycle("):SOURCE.index("def _json(")]
        self.assertIn("implemented=False", fonte)
        self.assertNotIn("CAMPAIGN_FOLLOW, follow_graded, implemented=True", fonte)

    def test_sql_dos_documentos_recebe_todos_os_parametros(self):
        """Falha antes do servidor se qualquer INSERT tiver marcador sem valor."""
        class Connection:
            def execute(self, query, params=()):
                self.assertEqual(query.count("%s"), len(params), query)
                return self

            def assertEqual(self, left, right, query):
                if left != right:
                    raise AssertionError(
                        f"SQL tem {left} marcadores e recebeu {right} valores: {query}"
                    )

        risk = self.tool.nr1_compliance.GradedRisk(
            dimension_id="00000000-0000-4000-8000-000000000001",
            nr1_factor="work_organization",
            unit_id=self.tool.UNIT_ATENDIMENTO,
            cohort_size=64,
            mean_score=3.2,
            critical_ratio=0.4,
            exposure_level=4,
            severity=4,
            probability=4,
            risk_level="critical",
            consequence="transtorno_mental",
            consequences_considered=("transtorno_mental",),
            measure_efficacy="none",
            exposed_workers=64,
            criteria_version=1,
            rationale="dado calculado de teste",
        )
        verdict = self.tool.nr1_effectiveness.EffectivenessVerdict(
            unit_id=self.tool.UNIT_ATENDIMENTO,
            dimension_id=risk.dimension_id,
            baseline_cohort=64,
            followup_cohort=64,
            baseline_mean=4.0,
            followup_mean=3.0,
            baseline_position=0.8,
            followup_position=0.5,
            effect_size=0.9,
            effect_margin=0.3,
            significant=True,
            verdict="effective",
            measure_efficacy="effective",
            requires_correction=False,
            triggers_review=False,
            rationale="comparação de teste",
        )
        connection = Connection()
        self.tool._create_aep_documents(connection, self.tool.CAMPAIGN_BASE, "baseline")
        self.tool._store_inventory(
            connection,
            self.tool.CAMPAIGN_BASE,
            [risk],
            {self.tool.UNIT_ATENDIMENTO: self.tool.pilot_id("aep/test")},
        )
        self.tool._store_action_plan(
            connection, self.tool.CAMPAIGN_BASE, [risk], implemented=True
        )
        self.tool._store_effectiveness(connection, [verdict])

    def test_varias_contas_recebem_acesso_na_mesma_transacao(self):
        main = SOURCE[SOURCE.index("def main("):]
        self.assertIn('action="append"', main)
        self.assertIn("for email in args.grant or []", main)
        self.assertIn("grant_access(connection, email)", main)
