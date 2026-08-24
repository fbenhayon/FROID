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
        # Termos e privacidade valem para qualquer um; o terceiro documento e o
        # contrato DELA, criado em 22/08/2026. O que nao pode aparecer aqui e
        # contrato de profissional ou de clinica.
        self.assertIn("terms", chaves)
        self.assertIn("privacy", chaves)
        self.assertIn("nr1_company_contract", chaves)
        self.assertNotIn("professional_contract", chaves)
        self.assertNotIn("organization_contract", chaves)
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
        fronteira = secoes["O que a contratante NÃO recebe, e não pode obter por outro caminho"]
        for proibido in ("resposta individual", "prontuário", "dado clínico"):
            with self.subTest(item=proibido):
                self.assertIn(proibido, fronteira)
        self.assertIn("não é uma configuração que se possa desligar", fronteira)

    def test_o_contrato_do_nr1_declara_a_base_legal_correta(self):
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        base = secoes["Base legal e papéis no tratamento de dados"]
        self.assertIn("art. 7º, II", base)
        self.assertIn("art. 11, II", base)
        # E nao o consentimento do trabalhador, que a hierarquia comprometeria.
        self.assertIn("não o consentimento do trabalhador", base)

    def test_o_contrato_admite_que_os_pisos_sao_escolha_nossa(self):
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        pisos = secoes["Pisos de coorte e supressão de resultado"]
        self.assertIn("não exigência da NR-1", pisos)
        self.assertIn("não prescreve taxa de resposta", pisos)

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
