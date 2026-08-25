"""O plano de acao como documento, e nao como rascunho de resposta HTTP.

1.5.7.1 lista DOIS documentos minimos do PGR: inventario de riscos e plano de
acao. O FROID gravava o primeiro e nao o segundo — action_plan_seed() devolvia um
rascunho no corpo da resposta e ele evaporava. A tabela existia desde a migration
010, com RLS, com grants ao froid_runtime e com permissao propria em
tenant_access.py, e nunca recebeu um INSERT.

Estes testes cobrem tres coisas distintas, e a distincao importa:

  1. Que a migration 026 declara cada exigencia da norma como restricao de banco.
     E ali que a garantia vive: nenhum caminho de codigo contorna um CHECK.
  2. Que a camada Python nao reintroduz por engano o que a 026 impede, e que a
     mensagem de erro devolvida ao gestor diz QUAL exigencia foi tocada.
  3. Que os campos de 1.5.7.3.2 calculados no endpoint chegam ao INSERT — eram
     calculados e descartados, e o inventario ia para o auditor pela metade.

O comportamento real das restricoes contra um Postgres de verdade esta em
tests/test_nr1_plano_de_acao_postgres.py, que pula sem banco configurado.
"""

import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nr1_compliance  # noqa: E402

MIGRATIONS = SERVER_DIR / "migrations"
MIGRACAO = (MIGRATIONS / "026_action_plan_documento.sql").read_text(encoding="utf-8")
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
ACCESS = (SERVER_DIR / "tenant_access.py").read_text(encoding="utf-8")


class ExigenciasViramRestricaoDeBanco(unittest.TestCase):
    """Cada linha da norma que o documento tem de cumprir, como CHECK.

    Validacao em Python e conselho; CHECK e regra. A diferenca aparece no dia em
    que alguem escreve um script de migracao de dados, um endpoint novo, ou um
    UPDATE manual em producao para "resolver rapido".
    """

    def test_concluir_exige_data_de_implementacao(self):
        # 1.5.5.3.1: a implementacao deve ser REGISTRADA. Medida concluida sem
        # data e afirmacao sem registro.
        self.assertIn("psychosocial_action_plan_done_needs_implementation", MIGRACAO)
        self.assertIn(
            "CHECK (status <> 'done' OR implemented_at IS NOT NULL)", MIGRACAO
        )

    def test_concluir_exige_responsavel_e_prazo(self):
        # 1.5.5.2.2: cronograma COM RESPONSAVEIS.
        self.assertIn("psychosocial_action_plan_done_needs_schedule", MIGRACAO)
        self.assertIn("responsible_membership_id IS NOT NULL", MIGRACAO)
        self.assertIn("due_date IS NOT NULL", MIGRACAO)

    def test_concluir_exige_acompanhamento_e_afericao(self):
        # 1.5.5.2.2 pede as duas: como se verifica que a medida esta de pe, e
        # como se mede se ela produziu efeito. Sem a segunda nao ha o que
        # comparar no ciclo seguinte e a prova de eficacia deixa de existir.
        self.assertIn("psychosocial_action_plan_done_needs_monitoring", MIGRACAO)
        self.assertIn("btrim(monitoring_method) <> ''", MIGRACAO)
        self.assertIn("btrim(result_measurement) <> ''", MIGRACAO)

    def test_cancelar_exige_justificativa(self):
        self.assertIn("psychosocial_action_plan_cancel_needs_reason", MIGRACAO)
        self.assertIn("status <> 'cancelled' OR btrim(evidence) <> ''", MIGRACAO)

    def test_eficacia_so_depois_de_implementar(self):
        # 1.5.4.4.5.3 usa a eficacia para calcular a probabilidade do risco. Um
        # veredito dado antes da implementacao rebaixa o risco no inventario com
        # dado que nao existe.
        self.assertIn(
            "psychosocial_action_plan_efficacy_after_implementation", MIGRACAO
        )
        self.assertIn("effectiveness IS NULL", MIGRACAO)

    def test_a_data_de_implementacao_nao_pode_ser_apagada(self):
        # E a unica forma de fazer a obrigacao de reavaliar risco residual
        # desaparecer sem deixar rastro.
        self.assertIn("froid_nr1_action_plan_guard", MIGRACAO)
        self.assertIn(
            "a data de implementacao registrada nao pode ser apagada", MIGRACAO
        )
        self.assertIn("1.5.5.3.1", MIGRACAO)

    def test_uma_medida_nao_muda_de_risco(self):
        self.assertIn("NEW.inventory_id <> OLD.inventory_id", MIGRACAO)

    def test_as_restricoes_sao_not_valid(self):
        """Migration que quebra o primeiro login e pior que restricao tardia.

        A tabela nunca recebeu escrita da aplicacao, mas pode ter linha de piloto
        inserida a mao. NOT VALID aplica a regra ao futuro sem reprovar o
        passado, e ensure_schema() roda no primeiro login do tenant.
        """
        restricoes = re.findall(
            r"ADD CONSTRAINT (psychosocial_action_plan_\w+)", MIGRACAO
        )
        # plan_action_check e a unica validada: a coluna acabou de nascer com
        # DEFAULT valido, entao nao ha linha antiga que possa reprova-la.
        esperadas_not_valid = [
            nome for nome in restricoes if nome != "psychosocial_action_plan_plan_action_check"
        ]
        self.assertGreaterEqual(len(esperadas_not_valid), 6)
        for nome in esperadas_not_valid:
            with self.subTest(restricao=nome):
                trecho = MIGRACAO[MIGRACAO.index(f"ADD CONSTRAINT {nome}"):]
                trecho = trecho[: trecho.index(";")]
                self.assertIn("NOT VALID", trecho)


class GatilhoDaAlineaA(unittest.TestCase):
    """1.5.4.4.6 "a": apos implementar, reavaliar o risco residual.

    Nao ha prazo na norma porque nao ha data — o gatilho e um EVENTO. Este e o
    ponto em que o produto faz o que planilha nenhuma faz: a obrigacao nasce
    sozinha no instante da implementacao.
    """

    def test_a_implementacao_marca_a_revisao_de_risco_residual(self):
        self.assertIn("froid_nr1_flag_residual_risk_review", MIGRACAO)
        self.assertIn("review_trigger = 'residual_risk'", MIGRACAO)
        self.assertIn("AFTER INSERT OR UPDATE OF implemented_at", MIGRACAO)

    def test_a_revisao_residual_antecipa_a_programada_e_nunca_a_adia(self):
        # LEAST entre o teto programado (24 ou 36 meses) e a data desta
        # implementacao. Usar o maior faria implementar uma medida ADIAR a
        # revisao, que e o oposto do que a alinea "a" determina.
        trecho = MIGRACAO[MIGRACAO.index("froid_nr1_flag_residual_risk_review"):]
        trecho = trecho[: trecho.index("$residual$;")]
        self.assertIn("LEAST(", trecho)
        self.assertNotIn("GREATEST(", trecho)

    def test_regerar_o_inventario_nao_apaga_uma_revisao_ja_devida(self):
        # A obrigacao nasceu de um evento que aconteceu. Regerar o inventario e
        # rotina; apagar a pendencia por causa dela seria perder o registro.
        self.assertIn("WHEN psychosocial_risk_inventory.review_trigger", STORE)
        self.assertIn("= 'residual_risk' THEN 'residual_risk'", STORE)

    def test_o_teto_de_revisao_e_gravado_na_geracao_do_inventario(self):
        self.assertIn("make_interval(months => %s)", STORE)
        self.assertIn("'scheduled'", STORE)
        self.assertIn("_nr1_review_interval_months", MAIN)


class OsNoveCamposDeixamDeSerDescartados(unittest.TestCase):
    """Regressao: o endpoint calculava e o store jogava fora.

    generate_nr1_inventory montava selected_consequence, possible_harms,
    exposed_workers, measure_efficacy, exposure_level e risk_classification — e o
    INSERT de nr1_store_inventory nao listava nenhuma dessas colunas. O
    inventario ia para o auditor com as alineas "d", "e", "f" e "g" de 1.5.7.3.2
    vazias.
    """

    def test_o_insert_persiste_o_que_o_endpoint_calcula(self):
        trecho = STORE[STORE.index("INSERT INTO psychosocial_risk_inventory"):]
        trecho = trecho[: trecho.index("ON CONFLICT")]
        for coluna in (
            "possible_harms", "selected_consequence", "exposed_workers",
            "measure_efficacy", "exposure_level", "risk_classification",
        ):
            with self.subTest(coluna=coluna):
                self.assertIn(coluna, trecho)

    def test_o_inventario_guarda_os_criterios_que_o_produziram(self):
        # gro_risk_criteria e imutavel depois de publicado justamente para que um
        # inventario continue explicavel pela regua que o gerou.
        self.assertIn("campanha.criteria_id", STORE)


class TresVerbosDeUmCincoCincoDoisUm(unittest.TestCase):
    """1.5.5.2.1: medidas a serem introduzidas, aprimoradas ou mantidas."""

    def test_o_python_e_o_banco_concordam_sobre_os_tres(self):
        self.assertEqual(
            set(nr1_compliance.PLAN_ACTIONS),
            {"introduce", "improve", "maintain"},
        )
        self.assertIn("plan_action IN ('introduce', 'improve', 'maintain')", MIGRACAO)

    def test_a_regra_esta_documentada_no_documento_de_criterios(self):
        # Regra aplicada num lugar e declarada noutro diverge com o tempo.
        documento = nr1_compliance.DEFAULT_CRITERIA.as_document()
        self.assertIn("measure_hierarchy", documento["decision_rules"])


class SuperficieDaApi(unittest.TestCase):
    def test_as_quatro_rotas_existem(self):
        for rota in (
            'get("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/action-plan")',
            'post("/api/organizations/{organization_id}/nr1/campaigns/{campaign_id}/action-plan")',
            'post("/api/organizations/{organization_id}/nr1/action-plan/items"',
            'patch("/api/organizations/{organization_id}/nr1/action-plan/items/{item_id}")',
        ):
            with self.subTest(rota=rota):
                self.assertIn(rota, MAIN)

    def test_escrever_o_plano_exige_a_permissao_que_ja_existia(self):
        # nr1.action_plan.manage estava declarada em tenant_access.py desde
        # sempre, concedida a compliance_manager e occupational_health, e nao era
        # usada em endpoint nenhum.
        self.assertIn('"nr1.action_plan.manage"', ACCESS)
        self.assertGreaterEqual(MAIN.count('"nr1.action_plan.manage"'), 3)

    def test_a_leitura_do_plano_nao_exige_permissao_de_escrita(self):
        # Auditor e owner leem o documento sem poder alterar. A politica de RLS
        # da 010 ja separa os dois; o endpoint tem de refletir isso.
        trecho = MAIN[MAIN.index("async def list_nr1_action_plan"):]
        trecho = trecho[: trecho.index("@app.post")]
        self.assertIn('"nr1.aggregate.read"', trecho)
        self.assertNotIn("nr1.action_plan.manage", trecho)

    def test_nao_existe_rota_que_apague_medida(self):
        # Apagar reescreve a historia do que foi feito; cancelar a preserva, e a
        # 026 exige justificativa para cancelar.
        self.assertNotIn("delete(\"/api/organizations/{organization_id}/nr1/action-plan", MAIN)

    def test_implementacao_no_futuro_e_recusada(self):
        self.assertIn("não se registra implementação no futuro", MAIN)

    def test_toda_restricao_da_migration_tem_mensagem_para_o_gestor(self):
        """"violates check constraint" nao ensina ninguem a preencher o documento.

        Se alguem acrescentar um CHECK na tabela sem escrever a frase que explica
        qual exigencia foi tocada, este teste reprova — e a frase e mais barata
        de escrever agora que de descobrir num suporte.
        """
        declaradas = set(
            re.findall(r"ADD CONSTRAINT (psychosocial_action_plan_\w+)", MIGRACAO)
        )
        traduzidas = set(
            re.findall(r'"(psychosocial_action_plan_\w+)":', MAIN)
        )
        self.assertEqual(
            declaradas - traduzidas, set(),
            "CHECK sem mensagem em _ACTION_PLAN_CONSTRAINT_MESSAGES",
        )


class FronteiraClinicaIntacta(unittest.TestCase):
    """O plano de acao nao pode virar porta para dado de pessoa."""

    def test_nenhuma_consulta_do_plano_faz_join_com_users(self):
        # Nao ha GRANT SELECT em users para o froid_runtime, e as consultas que
        # resolvem nome de pessoa neste arquivo correm pela conexao
        # administrativa. Um JOIN aqui aplicaria limpo em desenvolvimento e
        # falharia por permissao no primeiro uso em producao.
        trecho = STORE[STORE.index("def nr1_generate_action_plan"):]
        trecho = trecho[: trecho.index("def mark_mirrored_report_deleted")]
        self.assertNotIn("JOIN users", trecho)
        self.assertNotIn("users.email", trecho)
        self.assertNotIn("display_name", trecho)

    def test_o_plano_nao_expoe_resposta_individual(self):
        trecho = STORE[STORE.index("def nr1_list_action_plan"):]
        trecho = trecho[: trecho.index("def nr1_update_action_plan_item")]
        self.assertNotIn("assessment_responses", trecho)
        self.assertNotIn("assessment_response_items", trecho)

    def test_a_lista_branca_impede_coluna_vinda_do_corpo_da_requisicao(self):
        self.assertIn("ACTION_PLAN_UPDATABLE", STORE)
        trecho = STORE[STORE.index("ACTION_PLAN_UPDATABLE = {"):]
        trecho = trecho[: trecho.index("}")]
        self.assertNotIn("organization_id", trecho)
        self.assertNotIn("inventory_id", trecho)
        self.assertNotIn("id", re.findall(r'"(\w+)"', trecho))


if __name__ == "__main__":
    unittest.main()


class OQueOCadastroDaEmpresaConcede(unittest.TestCase):
    """O dono de uma empresa NR-1 nao pode receber papel clinico.

    O cadastro concedia ("owner", "professional") a qualquer conta, inclusive a
    nr1_company. 'professional' NAO esta em EMPLOYER_SIDE_ROLES, entao ele
    conserva patients.read_assigned, reports.read_assigned e reports.write mesmo
    numa organizacao 'enterprise': o estreitamento que retira as permissoes
    clinicas so alcanca os papeis do lado do empregador, e o dono carregava os
    dois, escapando por cima dele.

    E o mesmo defeito bloqueava a operacao: com 'owner' o dono so tinha
    nr1.unit.*, e nao conseguia abrir campanha, gerar inventario nem preencher o
    plano do produto que acabara de contratar.
    """

    def test_empresa_recebe_compliance_manager_e_nao_professional(self):
        trecho = STORE[STORE.index("papeis = ("):]
        trecho = trecho[: trecho.index("for role in papeis")]
        self.assertIn('("owner", "compliance_manager")', trecho)
        self.assertIn('organization_type == "enterprise"', trecho)
        self.assertIn('("owner", "professional")', trecho)

    def test_o_papel_clinico_e_removido_de_quem_ja_o_tinha(self):
        # Preventivo nao basta: quem se cadastrou antes ja tem a linha gravada.
        self.assertIn("DELETE FROM membership_roles", STORE)
        self.assertIn("AND role='professional'", STORE)

    def test_compliance_manager_alcanca_o_modulo_inteiro(self):
        import tenant_access

        permissoes = tenant_access.effective_role_permissions(
            "compliance_manager", "enterprise"
        )
        for necessaria in (
            "nr1.unit.manage", "nr1.campaigns.manage", "nr1.aggregate.read",
            "nr1.inventory.manage", "nr1.action_plan.manage",
        ):
            with self.subTest(permissao=necessaria):
                self.assertIn(necessaria, permissoes)

    def test_compliance_manager_nao_le_prontuario(self):
        import tenant_access

        permissoes = tenant_access.effective_role_permissions(
            "compliance_manager", "enterprise"
        )
        vazamento = permissoes & tenant_access.CLINICAL_IDENTIFIED_PERMISSIONS
        self.assertEqual(vazamento, frozenset())
        # E nao pode se autoatribuir um colaborador para ler pelo escopo de
        # profissional: 'assignments.manage' fica fora de proposito.
        self.assertNotIn("assignments.manage", permissoes)

    def test_professional_em_org_enterprise_ainda_e_clinico(self):
        """O papel continua existindo, e e assim que tem de ser.

        O colaborador e paciente de um profissional da empresa. O que nao pode e
        o EMPREGADOR carregar esse papel — a fronteira depende de serem pessoas
        distintas, e por isso o clinico entra por convite.
        """
        import tenant_access

        permissoes = tenant_access.effective_role_permissions(
            "professional", "enterprise"
        )
        self.assertIn("patients.read_assigned", permissoes)
        self.assertNotIn("professional", tenant_access.EMPLOYER_SIDE_ROLES)


class OCadastroDaEmpresaConsegueTerminar(unittest.TestCase):
    """O cadastro da empresa NR-1 nunca completou uma vez sequer.

    Cinco condicoes do produto CLINICO eram aplicadas ao cadastro da empresa, e
    as cinco falhavam para ela por definicao:

      CPF de conferencia   — a empresa responde por CNPJ, nao por pessoa
      plano selecionado    — ela nao compra pacote de sessoes
      pagamento do pacote  — idem
      credito de sessao    — idem
      contrato profissional — ela nao presta servico clinico

    A primeira barrava no POST do perfil. As quatro seguintes mantinham
    `onboarding_required` verdadeiro para sempre, e o painel NR-1 devolvia a
    empresa toda vez que ela tentava entrar.
    """

    def test_a_chave_da_empresa_e_o_cnpj_e_nao_um_cpf(self):
        trecho = MAIN[MAIN.index('if account_type == "nr1_company":'):]
        trecho = trecho[: trecho.index("legal_acceptances = ")]
        self.assertIn("organization_document", trecho)
        self.assertIn("14", trecho)
        # O responsavel pelo programa e registrado por nome e cargo (1.5.7.2),
        # nao por documento de identidade.
        self.assertIn("professional_cpf = \"\"", trecho)

    def test_o_cadastro_clinico_continua_exigindo_cpf(self):
        # A correcao nao pode afrouxar o outro produto.
        self.assertIn(
            "CPF obrigatório como chave de conferência do profissional", MAIN
        )

    def test_a_empresa_nao_precisa_de_plano_pagamento_nem_credito(self):
        trecho = MAIN[MAIN.index("is_nr1_company = account_type =="):]
        trecho = trecho[: trecho.index("    else:")]
        self.assertIn("organization_document", trecho)
        self.assertIn("lgpd_acknowledged", trecho)
        for clinico in ("selected_plan", "payment_status", "remaining_sessions"):
            with self.subTest(campo=clinico):
                self.assertNotIn(clinico, trecho)

    def test_o_clinico_continua_precisando_de_tudo_isso(self):
        trecho = MAIN[MAIN.index("is_nr1_company = account_type =="):]
        trecho = trecho[trecho.index("    else:"):]
        trecho = trecho[: trecho.index("# Sessoes entregues")]
        for clinico in ("selected_plan", "payment_status", "remaining_sessions",
                        "professional_cpf"):
            with self.subTest(campo=clinico):
                self.assertIn(clinico, trecho)

    def test_a_empresa_nao_assina_contrato_de_profissional(self):
        """Aceite de contrato que nao se aplica e registro juridico falso.

        Os dois contratos do catalogo declaram audiencia — "professional" e
        "organization" — e nenhuma delas e o empregador que contrata a avaliacao.
        """
        import legal_documents

        chaves = legal_documents.required_document_keys("nr1_company")
        # Desde 25/08/2026 nem os TERMOS sao os mesmos: "terms" fala de gravacao
        # de sessao, transcricao, prontuario e habilitacao profissional, e nada
        # disso alcanca quem so vai abrir campanha.
        self.assertIn("terms_nr1", chaves)
        self.assertIn("privacy", chaves)
        self.assertIn("nr1_company_contract", chaves)
        for clinico in ("terms", "professional_contract", "organization_contract"):
            with self.subTest(documento=clinico):
                self.assertNotIn(clinico, chaves)

    def test_todo_documento_exigido_declara_a_audiencia_de_quem_o_assina(self):
        """A trava que teria pego dois defeitos que ficaram meses no ar.

        "terms" declarava audiencias professional, organization e patient — e
        NAO nr1_company — enquanto required_document_keys obrigava a empresa a
        aceita-lo. Ela assinava um documento que dizia, no proprio corpo, nao
        ser para ela. A politica de privacidade tinha o mesmo defeito.

        Aceite de documento inaplicavel nao protege ninguem: dilui o que e
        aplicavel e da ao advogado da outra parte a primeira frase para
        sustentar que o aceite foi generico.
        """
        import legal_documents

        catalogo = legal_documents.public_legal_catalog()["documents"]
        # O tipo de conta e a audiencia declarada nao usam o mesmo vocabulario:
        # 'individual' cria um profissional, e e assim que o catalogo o nomeia.
        audiencia_de = {
            "individual": "professional",
            "organization": "organization",
            "nr1_company": "nr1_company",
        }
        for tipo, audiencia in audiencia_de.items():
            for chave in legal_documents.required_document_keys(tipo):
                with self.subTest(conta=tipo, documento=chave):
                    self.assertIn(
                        audiencia,
                        catalogo[chave]["audiences"],
                        f"{tipo} e obrigado a aceitar {chave}, que nao declara "
                        f"a audiencia {audiencia}",
                    )
        self.assertIn(
            "professional_contract",
            legal_documents.required_document_keys("individual"),
        )
        self.assertIn(
            "organization_contract",
            legal_documents.required_document_keys("organization"),
        )


class LiberacaoPendenteFalaComQuemLe(unittest.TestCase):
    """"acesso profissional aguardando aprovacao" dito a uma empresa.

    A middleware bloqueia toda rota /api/ fora de uma lista de excecoes enquanto
    a aprovacao manual nao sai. /api/professional/profile esta na lista, entao o
    passo 1 do cadastro da empresa passava; /nr1/units nao esta, e o passo 2
    devolvia uma frase que fala de "acesso profissional" a quem acabou de
    cadastrar um CNPJ — e nao dizia o que fazer a seguir.

    O portao esta certo e fica: a avaliacao e servico contratado, e a liberacao e
    o ponto em que o FROID confirma a contratacao. O que estava errado era a
    palavra e a ausencia de saida.
    """

    def test_a_mensagem_muda_conforme_quem_esta_bloqueado(self):
        trecho = MAIN[MAIN.index('content={\n                    "detail": ('):]
        trecho = trecho[: trecho.index("},")]
        self.assertIn("cadastro da empresa recebido", trecho)
        self.assertIn('== "nr1_company"', trecho)
        # E o caminho clinico continua com a frase dele.
        self.assertIn("acesso profissional aguardando aprovação FROID", trecho)

    def test_a_resposta_diz_que_e_liberacao_pendente_e_nao_erro_de_dado(self):
        # Sem esse sinal a tela nao consegue distinguir "falta liberar" de
        # "voce preencheu errado", e manda a pessoa reler o formulario atras de
        # um erro que nao esta la.
        self.assertIn('"approval_pending": True', MAIN)


class CadaServicoTemOContratoDele(unittest.TestCase):
    """O objeto de cada servico, dito no contrato dele.

    Os dois produtos tratam de coisas incompativeis: o Psique olha para UMA
    PESSOA, com as autorizacoes dela e sob responsabilidade de profissional
    habilitado; o NR-1 olha para o TRABALHO, de forma anonima e agregada, e nao
    pode chegar perto de pessoa nenhuma. Um contrato que nao diz qual dos dois
    esta sendo contratado deixa a fronteira depender de quem le.

    E ate 22/08/2026 a empresa nao assinava contrato nenhum:
    required_document_keys devolvia o contrato de PROFISSIONAL para ela.
    """

    def setUp(self):
        import legal_documents

        self.legal = legal_documents
        self.catalogo = legal_documents.public_legal_catalog()

    def test_a_empresa_assina_o_contrato_dela(self):
        chaves = self.legal.required_document_keys("nr1_company")
        self.assertIn("nr1_company_contract", chaves)
        self.assertNotIn("professional_contract", chaves)
        self.assertNotIn("organization_contract", chaves)

    def test_o_contrato_do_nr1_existe_no_catalogo(self):
        documento = self.catalogo["documents"].get("nr1_company_contract")
        self.assertIsNotNone(documento)
        self.assertEqual(documento["audiences"], ["nr1_company"])
        self.assertTrue(documento["sha256"])

    def test_o_objeto_do_nr1_diz_que_avalia_trabalho_e_nao_pessoa(self):
        objeto = self.legal.OBJETO_NR1
        self.assertIn("CONDIÇÃO DE TRABALHO", objeto)
        self.assertIn("nunca a pessoa do trabalhador", objeto)
        self.assertIn("1.419/2024", objeto)

    def test_o_objeto_do_nr1_nao_promete_assumir_o_GRO_da_empresa(self):
        """O Manual e explicito: a responsabilidade final e sempre da organizacao.

        Um contrato que sugerisse o contrario venderia uma isencao que nao existe
        — e que a fiscalizacao desmonta na primeira pergunta.
        """
        objeto = self.legal.OBJETO_NR1
        self.assertIn("responsabilidade pelo GRO", objeto)
        self.assertRegex(objeto, r"responsabilidade pelo GRO.*é da contratante")

    def test_o_objeto_do_psique_exclui_avaliacao_a_pedido_do_empregador(self):
        objeto = self.legal.OBJETO_PSIQUE
        self.assertIn("FROID Psique", objeto)
        self.assertRegex(objeto, r"NÃO abrange")
        self.assertIn("a pedido de empregador", objeto)
        self.assertIn("triagem admissional", objeto)

    def test_os_dois_contratos_clinicos_declaram_o_objeto(self):
        for chave in ("professional_contract", "organization_contract"):
            with self.subTest(documento=chave):
                titulos = [
                    secao["heading"]
                    for secao in self.catalogo["documents"][chave]["sections"]
                ]
                self.assertEqual(titulos[0], "Objeto e finalidade")

    def test_o_contrato_do_nr1_nomeia_a_fronteira_como_estrutural(self):
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        fronteira = secoes["Dados não disponibilizados à contratante"]
        for proibido in ("respostas individualizadas", "prontuário", "diagnóstico clínico"):
            with self.subTest(item=proibido):
                self.assertIn(proibido, fronteira)
        # A vedacao vale sobre a COLETA DO FROID, e nao sobre o mundo.
        self.assertIn("relacionado à coleta FROID", fronteira)

    def test_a_vedacao_nao_e_mais_absoluta_e_isso_foi_de_proposito(self):
        """"não pode obter por outro caminho" era promessa que nao nos cabia.

        O parecer de 25/08/2026 apontou que a redacao antiga contradizia outras
        obrigacoes do proprio empregador: ele PODE receber dado individual de
        trabalhador por relato espontaneo, denuncia de assedio, investigacao de
        acidente, processo trabalhista, ordem judicial ou atendimento
        ocupacional. Prometer que ele nao pode obter "por outro caminho" era
        assumir contratualmente algo que nao esta sob nosso controle — e que,
        se cumprido ao pe da letra, atrapalharia a apuracao de um assedio.

        O que continua absoluto e o que de fato controlamos: a vinculacao entre
        identidade e resposta nao sai do FROID por funcionalidade, exportacao,
        integracao, suporte ou cruzamento.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        fronteira = secoes["Dados não disponibilizados à contratante"]
        self.assertNotIn("não pode obter por outro caminho", fronteira)
        self.assertIn("investigação de acidente", fronteira)
        self.assertIn("ordem de autoridade competente", fronteira)

    def test_o_contrato_nao_promete_arquitetura_que_nao_podemos_garantir(self):
        """"as tabelas não são legíveis pela aplicação" virava garantia de arquitetura.

        Bastaria uma rotina de manutencao, um backup, um subprocessador ou um
        console de banco alcancar o dado para a frase se revelar falsa — e uma
        afirmacao tecnica falsa num contrato e pior que nenhuma afirmacao.
        Trocada por obrigacoes verificaveis, e por uma ressalva explicita de que
        acesso tecnico excepcional do fornecedor existe e e controlado.
        """
        todas = " ".join(
            secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        )
        self.assertNotIn("não são legíveis pela aplicação", todas)
        self.assertIn("privilégio mínimo", todas)
        self.assertIn("não será interpretada como declaração de inexistência", todas)

    def test_o_contrato_do_nr1_declara_a_base_legal_correta(self):
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        base = secoes["Proteção de dados pessoais: papéis e bases legais"]
        # A citacao agora e CONDICIONAL, como o parecer pediu: art. 7 para dado
        # comum, art. 11 so quando houver dado sensivel e ele for indispensavel.
        # Invocar os dois em bloco afirmava que a coleta trata dado sensivel
        # sempre, que e o oposto do que o produto sustenta.
        self.assertIn("art. 7º, II", base)
        self.assertIn("art. 11, II, alínea a", base)
        self.assertIn("Sempre que a coleta se restringir a dados pessoais comuns", base)
        self.assertIn("não no consentimento do trabalhador", base)
        self.assertIn("que a relação de hierarquia comprometeria", base)
        # E a razao de a distincao existir: quem decide a natureza do dado e a
        # pergunta que foi feita, nao o rotulo que o contrato deu a ela.
        self.assertIn("conteúdo real das perguntas", base)

    def test_o_contrato_admite_que_os_pisos_sao_escolha_nossa(self):
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        pisos = secoes["Pisos de coorte, agregação e supressão"]
        self.assertIn("critérios metodológicos e de proteção definidos pelo FORNECEDOR", pisos)
        self.assertIn("não serão apresentados como tamanho mínimo de coorte", pisos)

    def test_o_contrato_separa_as_duas_finalidades_dos_pisos(self):
        """Anonimato e representatividade sao problemas diferentes.

        O parecer foi explicito: um piso de 5, 7 ou 10 pessoas pode reduzir o
        risco de identificacao sem que a amostra seja representativa. Apresentar
        os dois como se fossem a mesma coisa e o erro que faz um perito derrubar
        a defesa inteira — e e por isso que o documento de criterios declara
        qual piso serve a qual finalidade.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        pisos = secoes["Pisos de coorte, agregação e supressão"]
        self.assertIn("reduzir o risco de identificação ou reidentificação", pisos)
        self.assertIn("suficiência metodológica mínima", pisos)
        self.assertIn("distinguir essas finalidades", pisos)

    def test_ausencia_de_dado_nao_vira_ausencia_de_risco(self):
        """A frase que muda o produto, e nao so o contrato.

        Hoje o painel devolve vazio quando o piso nao e atingido, e vazio se le
        como "nao ha risco aqui". O contrato agora proibe isso expressamente e
        cria a terceira saida: declarar o recorte insuficiente para
        classificacao. Suprimir e ocultar; declarar insuficiente e documentar.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        pisos = secoes["Pisos de coorte, agregação e supressão"]
        self.assertIn("declarado insuficiente para classificação", pisos)
        self.assertIn(
            "Não será criada artificialmente conclusão sobre ausência ou baixo nível de risco",
            pisos,
        )
        inconclusivo = secoes["Resultado inconclusivo não é ausência de risco"]
        self.assertIn(
            "não será automaticamente interpretada como inexistência de risco", inconclusivo
        )

    def test_a_versao_subiu_porque_os_contratos_clinicos_mudaram(self):
        # Regra do proprio arquivo: mudanca material sobe a versao, senao aceites
        # antigos provariam um texto que nao e mais o vigente.
        self.assertNotEqual(self.legal.LEGAL_DOCUMENT_VERSION, "2026-08-04.br-pf-v2")

    def test_cada_documento_tem_hash_proprio(self):
        hashes = {
            chave: documento["sha256"]
            for chave, documento in self.catalogo["documents"].items()
        }
        self.assertEqual(len(set(hashes.values())), len(hashes))


class SinergiaEntreOsDoisProdutos(unittest.TestCase):
    """Os dois servicos cooperam por finalidade, e nunca por dado.

    A primeira redacao do objeto dizia que "os dois servicos nao se comunicam",
    o que era verdade sobre DADO e falso sobre PRODUTO — e lido por um cliente
    soava como se contratar os dois fosse proibido. Isso jogava fora a unica
    articulacao que a norma nao so permite como exige: a campanha do NR-1 nao
    abre sem canal de apoio ao trabalhador declarado (trigger da migration 013),
    e todo cliente do NR-1 precisa nomear um.
    """

    def setUp(self):
        import legal_documents

        self.legal = legal_documents
        self.catalogo = legal_documents.public_legal_catalog()
        self.nr1 = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }

    def test_o_psique_pode_ser_o_canal_de_apoio(self):
        objeto = self.legal.OBJETO_PSIQUE
        self.assertIn("canal de apoio ao trabalhador", objeto)
        self.assertIn("articulação é de finalidade, nunca de", objeto)

    def test_o_contrato_do_nr1_descreve_a_articulacao(self):
        clausula = self.nr1["FROID Psique e serviços assistenciais"]
        self.assertIn("FROID Psique", clausula)
        self.assertIn("instrumento próprio", clausula)
        # O que a empresa NAO recebe por essa porta.
        for vedado in ("prontuário", "conteúdo de sessão", "diagnóstico individual"):
            with self.subTest(item=vedado):
                self.assertIn(vedado, clausula)

    def test_o_froid_nao_pode_empurrar_o_proprio_psique(self):
        """Item 15 do parecer, acatado em 25/08/2026.

        A hierarquia de 1.5.5.1.2 manda agir sobre a fonte. Sobrecarga, meta
        impossivel, subdimensionamento e jornada excessiva nao se "tratam"
        oferecendo psicoterapia a quem adoeceu por causa delas — e um algoritmo
        que recomendasse o servico assistencial do proprio fornecedor diante de
        um problema de organizacao do trabalho seria indefensavel em pericia,
        porque a recomendacao teria motivo comercial e nao tecnico.

        A regra nao fecha o funil do Psique: o canal de apoio continua sendo
        requisito de abertura de campanha, e a contratante pode escolher o
        Psique para esse papel. O que ela impede e o FROID escolher por ela.
        """
        clausula = self.nr1["FROID Psique e serviços assistenciais"]
        self.assertIn("não poderá favorecer serviço assistencial do próprio FORNECEDOR", clausula)
        self.assertIn("em detrimento de medida organizacional mais adequada", clausula)
        # E a contrapartida: escolher o Psique como canal continua permitido.
        self.assertIn("salvo se expressamente escolhido pela contratante", clausula)

        plano = self.nr1["Plano de ação e medidas de prevenção"]
        self.assertIn(
            "Medidas individuais de acolhimento, orientação ou assistência não serão tratadas "
            "como substitutas automáticas de correções organizacionais",
            plano,
        )

    def test_a_eficacia_deixou_de_ser_afirmada_so_pela_campanha_seguinte(self):
        """O contrato dizia "é aferida pela campanha seguinte". Categorico demais.

        1.5.5.3.2 exige acompanhamento PLANEJADO do desempenho: verificacao da
        execucao, inspecoes, monitoramento quando aplicavel e participacao dos
        trabalhadores e da CIPA. A campanha seguinte e uma dessas evidencias, e
        prometer que ela basta transferia para o FROID uma afirmacao que a norma
        atribui ao conjunto do acompanhamento.

        Comercialmente a mudanca tambem e boa: acompanhamento continuo e servico
        recorrente, enquanto "espere dois anos" e uma venda a cada dois anos.
        """
        clausula = self.nr1["Acompanhamento, risco residual e eficácia"]
        self.assertIn("uma das evidências", clausula)
        self.assertIn("não constitui necessariamente o único ou suficiente meio", clausula)
        # E o risco residual nao espera o proximo ciclo.
        self.assertIn("não deverá ser automaticamente postergada", clausula)
        # Resultado ruim continua saindo.
        self.assertIn("não condicionará a emissão", clausula)

    def test_a_procura_pelo_canal_e_ato_do_trabalhador(self):
        # Encaminhamento disparado pela resposta individual seria triagem
        # individual, que e o que o Guia MTE afasta como objeto do processo.
        clausula = self.nr1["FROID Psique e serviços assistenciais"]
        self.assertIn("a procura será ato do trabalhador", clausula)
        self.assertIn(
            "informações clínicas não serão reutilizadas para classificar individualmente",
            clausula,
        )

    def test_o_canal_deixou_de_ser_justificado_por_uma_frase_que_nos_contradizia(self):
        """"perguntar a alguém como ele está" descrevia outro produto.

        O FROID NR-1 nao pergunta como o trabalhador esta — pergunta sobre a
        condicao de trabalho. A justificativa antiga do canal de apoio afirmava
        o contrario e, num contrato, uma frase dessas e a primeira coisa que a
        parte adversa cita para dizer que o instrumento faz avaliacao clinica.
        """
        canal = self.nr1["Canal de apoio ao trabalhador"]
        self.assertNotIn("como ele está", canal)
        self.assertIn("revelar ou provocar relatos de sofrimento", canal)
        # E o canal continua sendo escolha metodologica nossa, nao exigencia da norma.
        self.assertIn("não será apresentada como obrigação autônoma", canal)
        # Canal individual nao substitui medida sobre a organizacao do trabalho.
        self.assertIn("não substitui medidas destinadas a eliminar", canal)


class AdminVemDoServidor(unittest.TestCase):
    """Quem e administrador nao pode estar fixo no pacote do navegador.

    A lista estava escrita em TRES telas, com um unico endereco. O Fabio entrou
    com fbenhayon@froid.com.br e recebeu "acesso restrito" nas tres, sem que nada
    explicasse por que — enquanto o backend ja lia FROID_ADMIN_EMAILS e ja
    devolvia access_status.admin. Acrescentar um administrador exigiria build do
    painel em vez de uma variavel de ambiente.
    """

    TELAS = ("AdminDashboard.tsx", "AdminPatientDetail.tsx", "AdminProfessionalDetail.tsx")

    def _fonte(self, nome):
        caminho = SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / nome
        return caminho.read_text(encoding="utf-8")

    def test_nenhuma_tela_carrega_lista_fixa_de_administrador(self):
        for nome in self.TELAS:
            with self.subTest(tela=nome):
                fonte = self._fonte(nome)
                self.assertNotIn("adminEmails", fonte)
                self.assertNotIn("fbenhayon@gmail.com", fonte)

    def test_as_tres_telas_perguntam_ao_servidor(self):
        for nome in self.TELAS:
            with self.subTest(tela=nome):
                self.assertIn(
                    "Boolean(user?.access_status?.admin)", self._fonte(nome)
                )

    def test_o_servidor_deriva_o_admin_de_variavel_de_ambiente(self):
        self.assertIn('os.getenv("FROID_ADMIN_EMAILS"', MAIN)
        self.assertIn('"admin": _is_admin_email(owner_email)', MAIN)

    def test_aprovar_e_suspender_nao_tem_a_mesma_cor(self):
        """Acao destrutiva com a aparencia da construtiva, no mesmo lugar.

        O botao trocava o verbo e mantinha o ciano. Quem clicasse duas vezes por
        duvida derrubava o acesso de um cliente sem perceber que tinha mudado de
        acao.
        """
        fonte = self._fonte("AdminProfessionalDetail.tsx")
        trecho = fonte[fonte.index("disabled={approvalLoading}"):]
        trecho = trecho[: trecho.index("</button>")]
        self.assertIn("red", trecho)
        self.assertIn("emerald", trecho)


class SiglasSeExplicam(unittest.TestCase):
    """AEP, GRO, PGR nao fazem parte do vocabulario de RH nem de diretoria.

    A plateia do modulo corporativo nao e a do produto clinico. Uma tela que diz
    "gerar a AEP" a quem nunca viu a sigla transfere ao leitor o trabalho de
    descobrir do que se trata — e, numa apresentacao comercial, quem nao entende
    nao pergunta: conclui que o produto nao e para ele.
    """

    PAINEL = SERVER_DIR.parent / "froid-dashboard" / "src"

    def _fonte(self, caminho):
        return (self.PAINEL / caminho).read_text(encoding="utf-8")

    def test_o_glossario_cobre_as_siglas_usadas_nas_telas(self):
        glossario = self._fonte("lib/nr1-glossario.ts")
        for sigla in ("AEP", "AET", "GRO", "PGR", "CIPA", "SESMT", "PCMSO",
                      "LGPD", "DPO", "MTE", "CAT", "DORT", "EPI", "TCLE"):
            with self.subTest(sigla=sigla):
                self.assertIn(f'{sigla}: {{' if sigla.isalpha() else sigla, glossario)

    def test_a_primeira_aparicao_de_cada_tela_e_por_extenso(self):
        """Em celular nao ha como passar o mouse sobre uma sigla."""
        self.assertIn(
            "Avaliação Ergonômica Preliminar (AEP) psicossocial",
            self._fonte("pages/Nr1Aep.tsx"),
        )
        self.assertIn(
            "Programa de Gerenciamento de Riscos (PGR)",
            self._fonte("pages/Nr1ActionPlan.tsx"),
        )

    def test_o_botao_de_sigla_curta_carrega_a_explicacao(self):
        # No cabecalho o espaco e curto e a sigla fica; a explicacao vai no
        # title, que e onde o navegador e o leitor de tela a procuram.
        painel = self._fonte("pages/Nr1Dashboard.tsx")
        self.assertIn("Avaliação Ergonômica Preliminar: o método da NR-17", painel)

    def test_o_componente_usa_abbr_e_nao_um_span_qualquer(self):
        # <abbr> e o elemento que existe para isto: leitor de tela anuncia a
        # expansao, e o sublinhado pontilhado sinaliza que ha algo a revelar.
        componente = self._fonte("components/Sigla.tsx")
        self.assertIn("<abbr", componente)
        self.assertIn("decoration-dotted", componente)


class AProporcaoSaiEmFaixa(unittest.TestCase):
    """O painel publicava o tamanho da coorte E a proporcao exata.

    Multiplicar um pelo outro devolvia a CONTAGEM DE PESSOAS na faixa critica.
    Numa coorte de 15, uma proporcao de 0,067 e exatamente uma pessoa — e numa
    empresa desse tamanho, onde a chefia conhece todo mundo, "exatamente uma
    pessoa" esta a um passo de um nome.

    Esta e a mudanca que precisa vir ANTES de qualquer reducao do piso de
    coorte: baixar o piso sem ela abriria o mercado das empresas pequenas
    entregando contagem de cabecas ao empregador.
    """

    def test_nenhuma_e_uma_pessoa_caem_na_mesma_faixa(self):
        """A propriedade que faz a faixa proteger alguma coisa.

        Se 0 e 1 caissem em faixas diferentes, ainda seria possivel CONFIRMAR
        que existe alguem na faixa critica — que e justamente a informacao que
        aponta para uma pessoa.
        """
        for n in range(nr1_compliance.MIN_COHORT_CUT, 400):
            with self.subTest(coorte=n):
                self.assertEqual(
                    nr1_compliance.critical_ratio_band(0 / n)["label"],
                    nr1_compliance.critical_ratio_band(1 / n)["label"],
                )

    def test_nenhuma_faixa_permite_recuperar_uma_contagem(self):
        """Faixa que contem uma unica contagem possivel nao e faixa."""
        for n in range(nr1_compliance.MIN_COHORT_CUT, 60):
            contagens_por_faixa = {}
            for k in range(n + 1):
                rotulo = nr1_compliance.critical_ratio_band(k / n)["label"]
                contagens_por_faixa.setdefault(rotulo, []).append(k)
            for rotulo, contagens in contagens_por_faixa.items():
                with self.subTest(coorte=n, faixa=rotulo):
                    self.assertGreaterEqual(len(contagens), 2)

    def test_nenhuma_resposta_da_api_carrega_a_proporcao_exata(self):
        """Trava do arquivo inteiro, nao do endpoint que eu conhecia.

        Escrever este teste olhando so o painel deixaria a porta aberta para o
        proximo endpoint: quem adicionasse uma exportacao, um comparativo ou um
        relatorio novo copiaria o dicionario de campos e reabriria a inversao
        sem que nada reclamasse.
        """
        emissoes = re.findall(r'"critical_ratio"\s*:', MAIN)
        self.assertEqual(emissoes, [], "algum payload voltou a publicar a proporcao exata")
        self.assertIn("critical_ratio_band", MAIN)

    def test_a_faixa_e_o_unico_caminho_de_saida_da_proporcao(self):
        """A proporcao exata pode circular DENTRO do servidor — e precisa.

        O que nao pode e atravessar a fronteira da API. Este teste fixa onde
        fica essa fronteira: nr1_compliance calcula com o valor exato, e a unica
        funcao autorizada a converte-lo em algo publicavel e critical_ratio_band.
        """
        fonte = (SERVER_DIR / "nr1_compliance.py").read_text(encoding="utf-8")
        self.assertIn("critical_ratio=float(score.critical_ratio)", fonte)
        self.assertIn("spread = max(0.0, min(1.0, float(score.critical_ratio)))", fonte)

    def test_a_justificativa_gravada_tambem_sai_em_faixa(self):
        """A justificativa e GRAVADA no inventario e e o texto do auditor.

        Citar ali a proporcao exata anularia a faixa do painel: bastaria abrir o
        documento para recuperar a contagem.
        """
        fonte = (SERVER_DIR / "nr1_compliance.py").read_text(encoding="utf-8")
        self.assertNotIn("score.critical_ratio * 100", fonte)
        self.assertIn("critical_ratio_band(score.critical_ratio)['label']", fonte)

    def test_a_gradacao_continua_usando_o_valor_exato(self):
        """A faixa e controle de DIVULGACAO, nao de calculo.

        Arredondar antes de graduar degradaria a avaliacao de risco: duas
        coortes com proporcoes distintas dentro da mesma faixa passariam a
        receber o mesmo nivel de exigencia, e o nivel de risco junto.
        """
        def score(ratio):
            return nr1_compliance.DimensionScore(
                dimension_id="d", nr1_factor="work_organization", polarity="risk",
                cut_favorable=2.0, cut_critical=4.0, cohort_size=50,
                mean_score=3.0, critical_ratio=ratio,
            )
        # 0,05 e 0,19 estao na MESMA faixa publicada e produzem exigencias
        # diferentes, porque o calculo nao passa pela faixa.
        mesma_faixa = (
            nr1_compliance.critical_ratio_band(0.05)["label"]
            == nr1_compliance.critical_ratio_band(0.19)["label"]
        )
        self.assertTrue(mesma_faixa)
        combinado_baixo = nr1_compliance.exposure_level(score(0.05))
        combinado_alto = nr1_compliance.exposure_level(score(0.95))
        self.assertNotEqual(combinado_baixo, combinado_alto)

    def test_as_faixas_nao_sao_configuraveis_pelo_cliente(self):
        """Controle de privacidade que o cliente afrouxa nao e controle."""
        fonte = (SERVER_DIR / "nr1_compliance.py").read_text(encoding="utf-8")
        assinatura = fonte[fonte.index("def critical_ratio_band"):]
        assinatura = assinatura[: assinatura.index(":\n")]
        self.assertNotIn("criteria", assinatura)
        self.assertNotIn("margin", assinatura)

    def test_o_documento_de_criterios_declara_o_controle(self):
        documento = nr1_compliance.DEFAULT_CRITERIA.as_document()
        controle = documento["classification_rules"]["cohort_floors"]["disclosure_control"]
        self.assertIn("faixas de 20 pontos", controle)
        self.assertIn("nao configuraveis", controle)
        self.assertIn("valor exato, que nao sai do banco", controle)


class OsTermosSeSepararamDeVerdade(unittest.TestCase):
    """Separacao que so troca o titulo nao separa nada.

    Ate 25/08/2026 havia um documento de termos so, e ele pedia ao psicologo
    autonomo que aceitasse piso de coorte e inventario de riscos, e ao gestor de
    RH que aceitasse regras de gravacao de sessao e habilitacao profissional.
    Aceite de clausula inaplicavel nao protege: dilui o que e aplicavel e da a
    outra parte a primeira frase para sustentar que o aceite foi generico.
    """

    def setUp(self):
        import legal_documents

        self.legal = legal_documents
        self.catalogo = legal_documents.public_legal_catalog()["documents"]
        self.psique = " ".join(
            s["body"] for s in self.catalogo["terms"]["sections"]
        )
        self.nr1 = " ".join(
            s["body"] for s in self.catalogo["terms_nr1"]["sections"]
        )

    def test_os_termos_do_psique_nao_falam_do_mundo_da_empresa(self):
        for estranho in ("piso de coorte", "inventário de riscos", "PGR", "NR-1"):
            with self.subTest(termo=estranho):
                self.assertNotIn(estranho, self.psique)

    def test_os_termos_do_nr1_nao_impoem_obrigacao_clinica_a_empresa(self):
        """A empresa nao grava sessao, nao transcreve e nao tem CRP.

        `prontuario` e `diagnostico` APARECEM no texto do NR-1, e devem: estao
        na lista do que a contratante nao recebe. O que nao pode aparecer e
        obrigacao clinica dirigida a ela.
        """
        for estranho in ("gravação", "transcrição", "habilitação profissional"):
            with self.subTest(termo=estranho):
                self.assertNotIn(estranho, self.nr1)
        # E o que TEM de aparecer, justamente como vedacao.
        self.assertIn("não receberá", self.nr1)
        self.assertIn("prontuário", self.nr1)

    def test_cada_termo_declara_a_audiencia_dele(self):
        self.assertNotIn("nr1_company", self.catalogo["terms"]["audiences"])
        self.assertEqual(self.catalogo["terms_nr1"]["audiences"], ["nr1_company"])

    def test_os_dois_preservam_a_responsabilidade_propria_do_froid(self):
        """Prioridade 4 do parecer, e a que mais protege a CONTRATANTE.

        Um contrato que joga tudo no cliente parece bom para o fornecedor e e
        ruim: transforma cada erro tecnico nosso numa discussao sobre se o
        contrato valia, em vez de numa correcao.
        """
        self.assertIn("não exclui a responsabilidade própria do FROID", self.psique)
        self.assertIn("não exclui a responsabilidade própria do FROID", self.nr1)

    def test_o_nr1_carrega_a_frase_que_o_produto_agora_cumpre(self):
        """Ausencia de evidencia nao e ausencia de risco.

        Deixou de ser promessa em 25/08/2026: a migration 028 fez o recorte
        reprovado virar linha declarada no painel e no inventario, com o portao
        que reprovou e o caminho indicado.
        """
        self.assertIn("não equivale a ausência de risco", self.nr1)
        self.assertIn("classificado como insuficiente", self.nr1)
        import nr1_compliance

        self.assertEqual(nr1_compliance.UNCLASSIFIABLE_LEVEL, "insuficiente")

    def test_a_prova_do_aceite_promete_o_hash_porque_nos_ja_guardamos_o_hash(self):
        """Os termos que o assessor mandou listavam so a VERSAO aceita.

        O produto ja guarda o sha256 do texto e o confere na revalidacao, que e
        evidencia mais forte: versao prova qual rotulo estava no ar, hash prova
        qual TEXTO a pessoa aceitou. Prometer menos do que se entrega, num
        documento probatorio, e desperdicar a prova que existe.
        """
        for texto in (self.psique, self.nr1):
            with self.subTest():
                self.assertIn("resumo criptográfico", texto)
        # E o hash existe mesmo, por documento.
        for chave, documento in self.catalogo.items():
            with self.subTest(documento=chave):
                self.assertEqual(len(documento["sha256"]), 64)

    def test_todo_documento_do_catalogo_tem_rota_para_ser_lido(self):
        """Link de contrato que da 404 na frente do cliente.

        legalRouteByKey apontava para /contrato-nr1 desde 22/08/2026 e a rota
        nunca foi registrada em App.tsx: quem clicasse no contrato durante o
        cadastro caia numa pagina em branco.
        """
        painel = SERVER_DIR.parent / "froid-dashboard" / "src"
        rotas = (painel / "lib" / "legal.ts").read_text(encoding="utf-8")
        app = (painel / "App.tsx").read_text(encoding="utf-8")
        mapeadas = re.findall(r'^\s+(\w+): "(/[\w-]+)",$', rotas, re.MULTILINE)
        self.assertTrue(mapeadas, "nenhuma rota legal encontrada em legal.ts")
        for chave, caminho in mapeadas:
            with self.subTest(documento=chave):
                self.assertIn(chave, self.catalogo, f"{chave} nao existe no catalogo")
                self.assertIn(
                    f'path="{caminho}"', app, f"{caminho} nao tem Route em App.tsx"
                )


class ATelaMostraOQueAPessoaAssina(unittest.TestCase):
    """Aceite de documento diferente do que a tela exibe nao vale nada.

    Ate 25/08/2026 o cadastro mostrava o contrato e, ao lado da caixa de aceite,
    um link para froid.com.br/termos.html — a pagina ESTATICA do site. Depois da
    separacao dos termos, a pessoa passou a aceitar `terms_nr1` no envio e a ler
    outro documento na tela.

    Numa tela que produz efeito juridico isso e mais grave que um link quebrado:
    e a primeira coisa que a outra parte usa para sustentar que nao leu o que
    aceitou. E o link estatico nem sequer carrega versao ou hash, que sao a
    prova de QUAL texto estava no ar naquele instante.
    """

    @classmethod
    def setUpClass(cls):
        cls.pagina = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "Nr1CompanyOnboarding.tsx"
        ).read_text(encoding="utf-8")

    def test_a_tela_nao_manda_mais_para_a_pagina_estatica_do_site(self):
        """Mira no href, e nao na string.

        O comentario que explica a correcao cita o endereco antigo — e deve
        citar, porque e o que faz a proxima pessoa entender por que o link nao
        volta. Banir a string inteira transformaria a explicacao em defeito.
        """
        hrefs = re.findall(r'href="([^"]+)"', self.pagina)
        for endereco in hrefs:
            with self.subTest(href=endereco):
                self.assertNotIn("froid.com.br/termos", endereco)
                self.assertNotIn("froid.com.br/privacidade", endereco)

    def test_a_tela_exibe_os_documentos_que_o_envio_registra(self):
        """Uma fonte so para as duas coisas: a lista da audiencia.

        Exibir de uma lista e enviar de outra e como o defeito nasceu.
        """
        self.assertIn('documentosDaAudiencia(catalogo, "nr1_company")', self.pagina)
        self.assertIn("paraAceitar", self.pagina)
        self.assertIn("legal_acceptances", self.pagina)

    def test_cada_documento_aparece_com_versao_e_impressao_digital(self):
        """E o que transforma o aceite em prova.

        Versao diz qual rotulo estava no ar; hash diz qual TEXTO. Sem os dois na
        tela, a pessoa aceita um titulo.
        """
        self.assertIn("doc.version", self.pagina)
        self.assertIn("doc.sha256.slice(0, 12)", self.pagina)
        self.assertIn("doc.sections.length", self.pagina)

    def test_a_privacidade_tem_aceite_proprio_e_nao_entra_no_bolo(self):
        """Reconhecer tratamento de dados e contratar servico sao dois atos.

        Juntar os dois num clique enfraquece os dois: o aceite do contrato fica
        contaminado por uma declaracao de ciencia, e a declaracao de ciencia
        deixa de ser um ato deliberado do controlador.
        """
        self.assertIn('([chave]) => chave !== "privacy"', self.pagina)
        self.assertIn('chave === "privacy" ? reconhece : contratoAceito', self.pagina)

    def test_o_texto_de_cada_documento_e_legivel_na_propria_tela(self):
        """Sem depender de abrir outra aba, que e onde a leitura se perde."""
        self.assertIn("documentoAberto === chave", self.pagina)
        self.assertIn("secao.heading", self.pagina)
        self.assertIn("secao.body", self.pagina)


class OAprovadorAlcancaOAdministrativo(unittest.TestCase):
    """A trava que prendia justamente quem destrava os outros.

    /admin estava atras de `clinicalElement`, que devolve para a escolha de
    produto quando `onboarding_required` e verdadeiro. E `access_ready` do lado
    clinico exige plano selecionado, pagamento e saldo de sessoes — coisas que o
    operador da plataforma nunca comprou para si mesmo.

    O resultado era circular e sem saida: ele caia na tela de escolha, onde a
    opcao de empresa aparece indisponivel porque a conta ja tem cadastro
    clinico, e a opcao clinica o levaria a comprar um plano que nao quer. Nao
    conseguia aprovar ninguem — e aprovacao e o passo que libera todo cadastro
    de empresa.

    Aprovar cadastro e funcao de operador da plataforma. Nao tem relacao com ter
    credito de sessao, e amarrar as duas coisas travou o unico que podia
    destravar.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = (
            SERVER_DIR.parent / "froid-dashboard" / "src" / "App.tsx"
        ).read_text(encoding="utf-8")

    def test_as_telas_de_admin_nao_dependem_do_onboarding_clinico(self):
        for tela in ("AdminDashboard", "AdminProfessionalDetail", "AdminPatientDetail"):
            with self.subTest(tela=tela):
                self.assertIn(f"adminElement(<{tela} user={{user}} />)", self.app)
                self.assertNotIn(f"clinicalElement(<{tela} user={{user}} />)", self.app)

    def test_o_guarda_novo_exige_a_marca_de_admin(self):
        """Mais restritivo que antes para quem NAO e admin.

        clinicalElement deixava passar qualquer conta com onboarding concluido,
        e a propria tela decidia o que mostrar. Agora a rota so abre com a marca
        explicita.
        """
        guarda = self.app[self.app.index("const adminElement ="):]
        guarda = guarda[: guarda.index("return (")]
        self.assertIn("user?.access_status?.admin", guarda)
        self.assertIn("Navigate", guarda)

    def test_quem_decide_de_verdade_continua_sendo_o_servidor(self):
        """Guarda de rota e navegacao, nao autorizacao.

        Se fosse so o front, bastaria editar o localStorage para virar admin.
        O backend confere o e-mail contra FROID_ADMIN_EMAILS em cada requisicao.
        """
        self.assertIn("_is_admin_email", MAIN)
        self.assertIn("FROID_ADMIN_EMAILS", MAIN)
        trecho = MAIN[MAIN.index("def _is_admin_email"):]
        trecho = trecho[: trecho.index("\n\n\n")] if "\n\n\n" in trecho else trecho[:400]
        self.assertIn("FROID_ADMIN_EMAILS", trecho)
