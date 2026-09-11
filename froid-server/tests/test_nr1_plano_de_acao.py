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
        # As duas reguas eram um if/else sobre `is_nr1_company`. Desde
        # 09/09/2026 sao duas expressoes independentes, porque a mesma conta
        # pode carregar os dois produtos: uma clinica que contrata o NR-1 fica
        # pronta na conformidade antes de comprar o primeiro pacote de sessoes.
        inicio = MAIN.index("nr1_pronto = (")
        trecho = MAIN[inicio : MAIN.index("\n    )", inicio)]
        self.assertIn("organization_document", trecho)
        self.assertIn("lgpd_acknowledged", trecho)
        for clinico in ("selected_plan", "payment_status", "remaining_sessions"):
            with self.subTest(campo=clinico):
                self.assertNotIn(clinico, trecho)

    def test_o_clinico_continua_precisando_de_tudo_isso(self):
        inicio = MAIN.index("clinico_pronto = (")
        trecho = MAIN[inicio : MAIN.index("\n    )", inicio)]
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


class OBloqueioFalaComQuemLe(unittest.TestCase):
    """O 403 tem de dizer o que houve e o que fazer.

    ESTA CLASSE GUARDAVA A DECISAO CONTRARIA. Ate 09/09/2026 ela se chamava
    `LiberacaoPendenteFalaComQuemLe` e defendia a frase "cadastro da empresa
    recebido — a liberacao para operar o modulo NR-1 e feita pela equipe FROID",
    porque a liberacao previa era o caminho normal de toda empresa nova.

    A liberacao previa foi retirada pelo dono ao entrar a fase operacional. O
    403 que sobrou nao e mais "espere": e "esta conta foi cortada". Dizer
    "aguardando aprovacao" a quem foi suspenso manda a pessoa esperar uma coisa
    que nao vai chegar sozinha.

    O que continua valendo, e por isso a classe nao foi apagada: a resposta tem
    de trazer um SINAL que a tela distinga de erro de preenchimento, e um canal.
    Sem eles a pessoa rele o formulario atras de um erro que nao esta la — que
    foi o defeito original.
    """

    def _corpo_do_403(self) -> str:
        trecho = MAIN[MAIN.index('content={\n                    "detail": ('):]
        return trecho[: trecho.index("},")]

    def test_a_mensagem_diz_o_que_houve_e_para_onde_ir(self):
        trecho = self._corpo_do_403()
        self.assertIn("acesso suspenso pelo FROID", trecho)
        self.assertIn("cadastro recusado pelo FROID", trecho)
        self.assertIn("FROID_TRIAL_CONTACT_EMAIL", trecho)

    def test_ninguem_e_mandado_esperar_liberacao(self):
        trecho = self._corpo_do_403()
        self.assertNotIn("aguardando", trecho)
        self.assertNotIn("liberação", trecho)

    def test_a_resposta_traz_o_sinal_que_a_tela_distingue_de_erro_de_dado(self):
        # Sem esse sinal a tela nao consegue separar "seu acesso foi cortado" de
        # "voce preencheu errado".
        self.assertIn('"access_blocked": True', MAIN)
        self.assertIn('"access_block_status": approval.get("access_block_status")', MAIN)


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

    def test_o_objeto_diz_que_avalia_trabalho_e_nao_pessoa(self):
        """A garantia sobreviveu à troca de 11/09/2026; a constante, não.

        Até esta data as duas frases do objeto moravam em `OBJETO_NR1`. A
        constante já estava morta antes da troca — a seção "Objeto" do contrato
        trazia texto próprio e nenhum documento lia a constante; só estes testes
        liam. Retirada, com lápide em legal_documents.py.

        O que a norma exige continua dito, agora onde alguém lê: cláusulas 2.1 e
        2.2 do contrato vigente.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        natureza = secoes["2. Natureza, finalidade e limites do serviço"]
        self.assertIn("tem por objeto material as condições de trabalho", natureza)
        self.assertIn("concepção, organização, conteúdo e gestão do trabalho", natureza)
        # E a contrapartida: o objeto NAO e a pessoa.
        self.assertIn("natureza ocupacional e coletiva", natureza)
        self.assertIn(
            "não se destina à avaliação clínica ou psicológica individual", natureza
        )
        for vedado in ("diagnóstico de saúde mental", "prontuário clínico", "ranking individual"):
            with self.subTest(item=vedado):
                self.assertIn(vedado, natureza)

    def test_o_contrato_nao_promete_assumir_o_GRO_da_empresa(self):
        """O Manual do GRO e explicito: a responsabilidade final e sempre da
        organizacao. Um contrato que sugerisse o contrario venderia uma isencao
        que nao existe — e que a fiscalizacao desmonta na primeira pergunta.

        Depois de 11/09/2026 a garantia esta em tres lugares do texto novo, e
        este teste cobre os tres: 6.2 (a responsabilidade permanece dela), 6.3
        (o FORNECEDOR nao decide por ela) e 14.8 (o encerramento nao transfere).
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        contratante = secoes["6. Responsabilidades da CONTRATANTE"]
        self.assertRegex(
            contratante,
            r"CONTRATANTE permanece responsável pela implementação e manutenção de seu"
            r" gerenciamento de riscos ocupacionais",
        )
        self.assertIn("não assumirá poder de decisão sobre organização do trabalho", contratante)
        encerramento = secoes["14. Vigência, alterações e encerramento"]
        self.assertIn(
            "encerramento do Contrato não transfere ao FORNECEDOR a responsabilidade",
            encerramento,
        )

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
        """A fronteira mudou de endereço em 11/09/2026, não de conteúdo.

        Era a cláusula "Dados não disponibilizados à contratante"; agora é a 8.2
        do contrato vigente. A lista do que o empregador não recebe continua
        inteira, e é ela que este teste guarda.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        fronteira = secoes["8. Agregação, pisos de coorte e proteção das respostas"]
        for proibido in (
            "respostas individualizadas",
            "associação entre identidade e resposta",
            "escore ou ranking individual",
            "diagnóstico ou avaliação clínica individual",
        ):
            with self.subTest(item=proibido):
                self.assertIn(proibido, fronteira)
        # A vedação vale sobre a COLETA DO FROID, e nao sobre o mundo.
        self.assertIn("relacionado à coleta FROID", fronteira)
        # E a protecao do participante contra represalia continua no texto.
        self.assertIn("não poderá retaliar, discriminar", fronteira)

    def test_a_vedacao_continua_limitada_a_coleta_e_nao_ao_mundo(self):
        """"não pode obter por outro caminho" era promessa que nao nos cabia.

        O parecer de 25/08/2026 apontou que a redacao antiga contradizia outras
        obrigacoes do proprio empregador: ele PODE receber dado individual de
        trabalhador por relato espontaneo, denuncia de assedio, investigacao de
        acidente, processo trabalhista, ordem judicial ou atendimento
        ocupacional.

        O QUE MUDOU EM 11/09/2026, e precisa ficar registrado: o texto anterior
        resolvia isso com uma RESSALVA EXPRESSA, que listava "investigação de
        acidente" e "ordem de autoridade competente" como caminhos legitimos. O
        contrato novo, adotado por determinacao do dono, nao traz essa ressalva.
        A limitacao sobrevive apenas pelo ESCOPO da clausula 8.3 — a vedacao
        alcanca o que for "relacionado à coleta FROID", e nada alem disso.

        Este teste passa a guardar a limitacao por escopo, que e o que restou.
        Se um dia a ressalva expressa voltar, este docstring explica por que ela
        existia.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        fronteira = secoes["8. Agregação, pisos de coorte e proteção das respostas"]
        self.assertNotIn("não pode obter por outro caminho", fronteira)
        self.assertIn("relacionado à coleta FROID", fronteira)
        self.assertRegex(
            fronteira,
            r"não solicitar, exigir, reconstruir ou tentar obter.*relacionado à coleta FROID",
        )

    def test_o_contrato_nao_promete_arquitetura_que_nao_podemos_garantir(self):
        """"as tabelas não são legíveis pela aplicação" virava garantia de arquitetura.

        Bastaria uma rotina de manutencao, um backup, um subprocessador ou um
        console de banco alcancar o dado para a frase se revelar falsa — e uma
        afirmacao tecnica falsa num contrato e pior que nenhuma afirmacao.

        O contrato novo mantem a saida correta: o acesso tecnico excepcional
        EXISTE, e declarado, e vem com controles. O que ele nao mantem sao as
        expressoes "privilégio mínimo" e "não será interpretada como declaração
        de inexistência", retiradas em 11/09/2026 junto com o texto anterior.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        todas = " ".join(
            secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        )
        self.assertNotIn("não são legíveis pela aplicação", todas)
        dados = secoes["9. Proteção de dados pessoais e segurança da informação"]
        self.assertIn("Eventual acesso técnico do FORNECEDOR", dados)
        self.assertIn("mediante controles adequados de acesso e confidencialidade", dados)
        # E os controles declarados, que sao verificaveis um a um.
        for controle in ("segregação lógica entre clientes", "controle de acesso", "registro de eventos"):
            with self.subTest(controle=controle):
                self.assertIn(controle, dados)

    def test_o_contrato_do_nr1_declara_papeis_e_base_legal(self):
        """AQUI MORA A PERDA MAIS MATERIAL DE 11/09/2026. Leia antes de mexer.

        O texto anterior, vindo do parecer de 25/08/2026, dizia tres coisas que
        o texto novo NAO diz, e que este docstring preserva porque a razao delas
        continua valendo:

        1. Citava a base legal POR ARTIGO e de forma CONDICIONAL — "art. 7º, II"
           para dado comum e "art. 11, II, alínea a" so quando houvesse dado
           sensivel e ele fosse indispensavel. Invocar os dois em bloco afirma
           que a coleta trata dado sensivel SEMPRE, que e o oposto do que o
           produto sustenta. O texto novo (9.4) cita apenas "arts. 7º e 11".
        2. Dizia, de forma categorica, que a base "não [está] no consentimento
           do trabalhador", porque "a relação de hierarquia comprometeria" a
           liberdade da manifestacao. O texto novo (7.2) diz que a
           voluntariedade "não implica, NECESSARIAMENTE," que o consentimento
           seja a base — categorico virou condicional.
        3. Dizia que quem decide a natureza do dado e o "conteúdo real das
           perguntas". O texto novo (9.5) diz "conteúdo efetivamente tratado".

        O ponto 2 e o mais sensivel: `lgpd_registry.py` continua afirmando, no
        codigo que executa a operacao, que no fluxo NR-1 a base NAO e
        consentimento — e agora o contrato e mais fraco que o cadastro de
        operacoes. Se alguem for reconciliar os dois, o lugar certo e o contrato.

        O que este teste guarda e o que sobrou, mais a separacao de papeis, que
        veio intacta.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        base = secoes["9. Proteção de dados pessoais e segurança da informação"]
        self.assertIn("Lei nº 13.709/2018", base)
        # Papeis: a empresa controla, o FROID opera.
        self.assertIn("esta atuará como controladora e o FORNECEDOR como operador", base)
        self.assertIn("controlador independente", base)
        # Base legal: obrigacao legal ou regulatoria, com os artigos citados.
        self.assertIn("cumprimento de obrigação legal ou regulatória", base)
        self.assertIn("arts. 7º e 11 da LGPD", base)
        # A natureza do dado vem do conteudo, nao do rotulo do instrumento.
        self.assertIn("conteúdo efetivamente tratado", base)
        self.assertIn("não apenas da denominação", base)
        # Consentimento nao e afirmado como base pela mera voluntariedade.
        participacao = secoes["7. Participação dos trabalhadores e canal de apoio"]
        self.assertIn(
            "não implica, necessariamente, que o consentimento constitua a base legal",
            participacao,
        )

    def test_ausencia_de_dado_nao_vira_ausencia_de_risco(self):
        """A frase que muda o produto, e nao so o contrato.

        O painel devolve vazio quando o piso nao e atingido, e vazio se le como
        "nao ha risco aqui". O contrato proibe isso expressamente e cria a
        terceira saida: declarar o recorte insuficiente para classificacao.
        Suprimir e ocultar; declarar insuficiente e documentar.

        Sobreviveu inteira a troca de 11/09/2026, em 3.4, 8.4 e 8.5.
        """
        secoes = {
            secao["heading"]: secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        }
        pisos = secoes["8. Agregação, pisos de coorte e proteção das respostas"]
        self.assertIn("declarado insuficiente para classificação", pisos)
        self.assertIn(
            "ausência de evidência suficiente não deverá ser interpretada automaticamente"
            " como ausência de risco",
            pisos,
        )
        metodologia = secoes["3. Metodologia, questionário e avaliações complementares"]
        self.assertIn("inconclusivo, não avaliável ou sujeito a complementação", metodologia)
        # Nenhum percentual vira nivel de risco sozinho.
        self.assertIn(
            "Nenhum percentual, média, prevalência aparente ou escore", metodologia
        )
        self.assertIn("sem aplicação dos critérios técnicos", metodologia)

    def test_o_que_a_substituicao_de_11_09_2026_retirou(self):
        """O registro executável do que saiu do contrato, e por que existia.

        Em 11/09/2026 o dono determinou a substituicao integral do contrato do
        NR-1: 45 clausulas deram lugar a 16. Eu apresentei a perda antes, ele
        reafirmou a decisao, e ela foi executada. Este teste existe para que a
        perda nao vire silencio — ele AFIRMA a ausencia, e falha no dia em que
        alguem reintroduzir qualquer um destes textos sem atualizar o registro.

        O que saiu, com o motivo pelo qual tinha sido escrito:

        - "FROID Psique e serviços assistenciais": vedava ao FORNECEDOR
          favorecer o proprio servico assistencial "em detrimento de medida
          organizacional mais adequada", e fechava a porta pela qual o
          empregador poderia receber prontuario, conteudo de sessao ou
          diagnostico individual. A hierarquia de 1.5.5.1.2 manda agir sobre a
          FONTE: sobrecarga e meta impossivel nao se tratam oferecendo
          psicoterapia a quem adoeceu por causa delas, e um algoritmo que
          recomendasse o servico do proprio fornecedor seria indefensavel em
          pericia, porque a recomendacao teria motivo comercial e nao tecnico.
          A clausula tambem dizia que "a procura será ato do trabalhador" e que
          informacoes clinicas nao seriam reutilizadas para classificar
          individualmente.
        - "Acompanhamento, risco residual e eficácia": dizia que a campanha
          seguinte e "uma das evidências" de eficacia e "não constitui
          necessariamente o único ou suficiente meio", porque 1.5.5.3.2 exige
          acompanhamento PLANEJADO do desempenho. Dizia tambem que a medida
          sobre risco residual "não deverá ser automaticamente postergada" e que
          resultado ruim "não condicionará a emissão" do documento.
        - "Pisos de coorte": separava as DUAS finalidades do piso — reduzir o
          risco de reidentificacao e assegurar "suficiência metodológica
          mínima" —, obrigando a "distinguir essas finalidades". Um piso de 5,
          7 ou 10 pessoas pode proteger o anonimato sem que a amostra seja
          representativa, e apresentar os dois como a mesma coisa e o erro que
          faz um perito derrubar a defesa inteira. Dizia ainda que os pisos sao
          "critérios metodológicos e de proteção definidos pelo FORNECEDOR" e
          que "não serão apresentados como tamanho mínimo de coorte" exigido
          por norma.
        - "Canal de apoio ao trabalhador": a justificativa dizia que o canal
          existe porque o instrumento pode "revelar ou provocar relatos de
          sofrimento". A condicao metodologica do canal sobreviveu (7.3 a 7.5);
          essa justificativa, nao.
        - Citacao da Portaria MTE nº 1.419/2024, que datava a redacao do
          capitulo 1.5 da NR-1 aplicada ao contrato.
        """
        todas = " ".join(
            secao["body"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        )
        titulos = [
            secao["heading"]
            for secao in self.catalogo["documents"]["nr1_company_contract"]["sections"]
        ]
        for titulo in (
            "FROID Psique e serviços assistenciais",
            "Acompanhamento, risco residual e eficácia",
            "Canal de apoio ao trabalhador",
        ):
            with self.subTest(clausula=titulo):
                self.assertNotIn(titulo, titulos)
        for frase in (
            "não poderá favorecer serviço assistencial do próprio FORNECEDOR",
            "a procura será ato do trabalhador",
            "não constitui necessariamente o único ou suficiente meio",
            "suficiência metodológica mínima",
            "não serão apresentados como tamanho mínimo de coorte",
            "revelar ou provocar relatos de sofrimento",
            "1.419/2024",
        ):
            with self.subTest(frase=frase):
                self.assertNotIn(frase, todas)

    def test_a_versao_sobe_a_cada_mudanca_material_do_texto(self):
        """Regra do proprio arquivo: mudanca material sobe a versao.

        Sem isso, aceites antigos provariam um texto que nao e mais o vigente —
        e o sha256 existe justamente para impedir essa confusao.

        Cada versao aposentada entra na lista. Quem trocar o texto de novo e
        esquecer de subir a versao vai ver este teste falhar, que e o unico
        aviso que chega antes do aceite errado ser gravado.
        """
        aposentadas = (
            "2026-08-04.br-pf-v2",   # antes da separacao dos termos
            "2026-08-25.br-pf-v5",   # antes da troca do TCLE e do contrato NR-1
        )
        for antiga in aposentadas:
            with self.subTest(versao=antiga):
                self.assertNotEqual(self.legal.LEGAL_DOCUMENT_VERSION, antiga)

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

    def test_o_canal_de_apoio_continua_sendo_condicao_metodologica_nossa(self):
        """O canal sobreviveu a troca de 11/09/2026; a justificativa dele, nao.

        Duas coisas seguem ditas, e sao as que importam contratualmente: o canal
        e condicao METODOLOGICA do servico, e nao obrigacao que a NR-1 imponha
        por conta propria; e canal individual NAO substitui medida sobre a
        organizacao do trabalho, que e a hierarquia de 1.5.5.1.2.

        A frase "perguntar a alguém como ele está" — que descrevia outro produto
        e era a primeira coisa que a parte adversa citaria para dizer que o
        instrumento faz avaliacao clinica — continua fora, e o teste guarda isso.

        O que saiu esta registrado em
        `test_o_que_a_substituicao_de_11_09_2026_retirou`.
        """
        canal = self.nr1["7. Participação dos trabalhadores e canal de apoio"]
        self.assertNotIn("como ele está", canal)
        self.assertIn("condição metodológica", canal)
        self.assertIn("não deverá ser apresentado como obrigação autônoma", canal)
        self.assertIn(
            "canal individual de apoio não substitui medidas de prevenção", canal
        )
        self.assertIn("eliminação, redução ou controle de fatores de risco", canal)
        # A resposta do trabalhador continua voluntaria.
        self.assertIn("será voluntária", canal)

    def test_a_indicacao_de_aprofundamento_nao_pode_ter_motivo_comercial(self):
        """O que restou da regra anti-funil, depois de 11/09/2026.

        A clausula que proibia o FORNECEDOR de empurrar o proprio servico
        assistencial saiu inteira (ver
        `test_o_que_a_substituicao_de_11_09_2026_retirou`). O contrato novo
        preserva a mesma ideia num escopo menor, e so nele: a indicacao de
        aprofundamento, AET ou metodologia complementar "não poderá ser
        condicionada à aquisição de outro produto ou serviço do FORNECEDOR"
        (3.7).

        E menos do que havia — cobre a venda de metodo complementar, e nao a
        recomendacao de servico assistencial diante de um problema de
        organizacao do trabalho. Fica dito para quem for reconciliar.
        """
        metodologia = self.nr1["3. Metodologia, questionário e avaliações complementares"]
        self.assertIn("decorrer da necessidade técnica identificada", metodologia)
        self.assertIn(
            "não poderá ser condicionada à aquisição de outro produto ou serviço",
            metodologia,
        )


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
        # O componente mudou de casa em b3c66f1 (components/Sigla.tsx virou
        # lib/siglas.tsx) e este teste ficou apontando para o arquivo apagado.
        componente = self._fonte("lib/siglas.tsx")
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


class AAprovacaoSobreviveAoRestart(unittest.TestCase):
    """A aprovacao vivia so em memoria, e sumia no proximo deploy.

    admin_professional_access_approval era o UNICO endpoint administrativo que
    muta perfil, e o unico que nao chamava _save_identity_state(). O efeito e
    cruel de diagnosticar: aprovar funciona, a tela muda, o cliente entra — e no
    proximo `docker compose up` do backend a aprovacao desaparece, sem que
    ninguem tenha desfeito nada.

    Num dia de deploy, aprovar e reconstruir o container produz exatamente o
    sintoma de "o botao nao fez nada".

    E como o espelho do PostgreSQL roda DENTRO de _save_identity_state, a
    aprovacao tambem nunca chegava ao banco onde o modulo NR-1 vive — entao a
    empresa aprovada continuaria sem organizacao do lado que importa.
    """

    def test_o_endpoint_de_aprovacao_persiste(self):
        trecho = MAIN[MAIN.index("async def admin_professional_access_approval"):]
        trecho = trecho[: trecho.index("@app.")]
        self.assertIn("_save_identity_state()", trecho)

    def test_todo_endpoint_administrativo_que_muta_perfil_persiste(self):
        """A trava da classe inteira, e nao so deste endpoint."""
        import ast

        arvore = ast.parse(MAIN)
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not no.name.startswith("admin_"):
                continue
            corpo = ast.get_source_segment(MAIN, no) or ""
            muta = "PROFESSIONAL_PROFILES[" in corpo
            if not muta:
                continue
            with self.subTest(endpoint=no.name):
                self.assertIn(
                    "_save_identity_state()",
                    corpo,
                    f"{no.name} altera perfil e nao persiste: a mudanca some no "
                    "proximo restart e nunca chega ao PostgreSQL",
                )

    def test_o_admin_sem_plano_nao_cai_mais_na_escolha_de_produto(self):
        """Ele nao tem o que escolher ali, e nao pode escolher nada.

        A opcao de empresa aparece indisponivel porque a conta ja e clinica, e a
        clinica o levaria a comprar um plano de sessoes que ele nao quer. Era um
        circulo: entrar, cair na escolha, digitar /admin na barra, clicar em
        Dashboard e voltar para a escolha.
        """
        painel = SERVER_DIR.parent / "froid-dashboard" / "src"
        lib = (painel / "lib" / "product-choice.ts").read_text(encoding="utf-8")
        rota = lib[lib.index("export function defaultAuthenticatedPath"):]
        rota = rota[: rota.index("\n}")]
        self.assertIn('if (user?.access_status?.admin) return "/admin";', rota)
        # E a checagem do admin vem ANTES da escolha de produto, senao nunca roda.
        self.assertLess(
            rota.index("access_status?.admin"), rota.index("needsProductChoice")
        )

    def test_a_decisao_de_destino_mora_num_lugar_so(self):
        """Tres copias da mesma regra, e a excecao entrou so numa.

        A regra estava escrita em `defaultAuthenticatedPath` no App e mais duas
        vezes, abreviada, em LoginPage e AccountAccessPages — cada uma decidindo
        sozinha que `onboarding_required` significa "va escolher um produto".

        Quando a excecao do administrador entrou, ela entrou so na copia do App.
        O login continuou mandando o admin para a escolha de produto, e a
        correcao parecia nao ter funcionado: era a copia errada que decidia.
        """
        painel = SERVER_DIR.parent / "froid-dashboard" / "src"
        for arquivo in ("pages/LoginPage.tsx", "pages/AccountAccessPages.tsx", "App.tsx"):
            fonte = (painel / arquivo).read_text(encoding="utf-8")
            with self.subTest(arquivo=arquivo):
                self.assertIn("defaultAuthenticatedPath", fonte)
                # Nenhuma reescreve a condicao.
                self.assertNotRegex(
                    fonte, r'onboarding_required\s*\?\s*"/access/produto"'
                )


class OAdministrativoNaoEBecoSemSaida(unittest.TestCase):
    """A tela nao pode ter o "Sair" como unico caminho para fora.

    O defeito veio em duas camadas, e a correcao da primeira criou a segunda.

    PRIMEIRA. O cabecalho oferecia "Dashboard". Para o administrador da
    plataforma que nunca comprou plano de sessoes para si mesmo, /dashboard esta
    atras do onboarding clinico e devolve para /admin — o botao trocava a URL e
    a tela continuava a mesma. Quem clica duas vezes conclui que travou.

    SEGUNDA. A correcao escondeu o botao quando ele nao levaria a lugar nenhum.
    Honesto, e pior: sobrava UM botao no cabecalho, e era o "Sair". Em
    26/08/2026 o titular precisou atender um paciente, entrou como
    administrador e a unica saida oferecida encerrava a sessao.

    Botao escondido nao informa — some, e a pessoa conclui que nao ha caminho.
    A tela agora diz QUAL e a pendencia, oferece a porta que a resolve, e mantem
    aberta a porta do NR-1, que nao depende do onboarding clinico.

    Estes testes descrevem a segunda correcao. Nao restaurar a condicao
    `destinoDoDashboard !== "/admin" && (` — foi ela o beco.
    """

    @classmethod
    def setUpClass(cls):
        cls.pagina = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "AdminDashboard.tsx"
        ).read_text(encoding="utf-8")

    def test_o_botao_do_dashboard_so_leva_a_lugar_alcancavel(self):
        """A primeira correcao continua de pe: nada de botao que nao leva."""
        self.assertIn("destinoDoDashboard", self.pagina)
        self.assertIn('destinoDoDashboard !== "/admin" ?', self.pagina)

    def test_quando_nao_leva_a_tela_oferece_a_porta_que_resolve(self):
        """O lugar da segunda correcao: informar em vez de sumir."""
        self.assertIn("pendenciaDoAdministrador", self.pagina)
        self.assertIn("nav(pendencia.destino)", self.pagina)
        self.assertIn("pendencia?.rotulo", self.pagina)

    def test_a_pendencia_e_explicada_na_tela(self):
        """title de botao nao e explicacao: some junto com o botao."""
        corrida = " ".join(self.pagina.split())
        self.assertIn("O painel de atendimento", corrida)

    def test_o_nr1_fica_sempre_alcancavel_daqui(self):
        """A porta que nao depende do onboarding clinico.

        A empresa contratante do NR-1 vive fora daquele fluxo. E ela que
        impede que a unica saida da tela seja encerrar a sessao — que era o
        estado em que a tela estava num dia de atendimento.
        """
        self.assertIn('nav("/nr1")', self.pagina)

    def test_nao_oferece_porta_que_nao_resolve(self):
        """Acesso cortado nao tem botao, de proposito.

        Oferecer caminho para quem nao pode resolver dali manda a pessoa
        procurar solucao onde nao ha. Era "aprovacao pendente" ate 09/09/2026,
        quando a liberacao previa acabou; o caso que sobrou e a suspensao
        administrativa, e a regra de nao oferecer botao vale igual.
        """
        self.assertIn("access_blocked", self.pagina)
        self.assertIn('rotulo: ""', self.pagina)

    def test_o_destino_vem_da_mesma_regra_do_roteamento(self):
        """Perguntar a regra, e nao adivinhar de novo.

        Reimplementar aqui a condicao seria a QUINTA copia da mesma decisao, e
        as quatro anteriores custaram o dia inteiro.
        """
        self.assertIn(
            "defaultAuthenticatedPath(user, readProductChoice())", self.pagina
        )

    def test_existe_saida_da_tela(self):
        self.assertIn("const sair = ", self.pagina)
        self.assertIn("froid_token", self.pagina)
        self.assertIn("clearProductChoice()", self.pagina)


class ORaizDoPainelNaoServeSiteVelho(unittest.TestCase):
    """Duas paginas iniciais no mesmo dominio, e uma delas congelada.

    /app/#/ renderizava HomePage, que embute uma COPIA de froid-site/index.html
    dentro do bundle do painel. A do site foi revista em 21/08/2026; a copia era
    de 04/08 — dezessete dias de diferenca, servidas lado a lado.

    O site institucional entra com git pull e a copia so muda em rebuild do
    painel, entao a distancia entre as duas so cresce. Ninguem linkava para la:
    chegava-se por acidente — foi exatamente o que aconteceu ao sair do
    Administrativo, e podia acontecer na frente de um cliente.

    Quem abre /app/ quer o produto.
    """

    @classmethod
    def setUpClass(cls):
        painel = SERVER_DIR.parent / "froid-dashboard" / "src"
        cls.app = (painel / "App.tsx").read_text(encoding="utf-8")
        cls.admin = (painel / "pages" / "AdminDashboard.tsx").read_text(encoding="utf-8")

    def _rota_raiz(self) -> str:
        """O elemento inteiro da rota, e nao ate o primeiro `/>`.

        O primeiro `/>` de dentro pertence ao <Navigate>, entao cortar ali
        deixava metade da rota de fora e o teste passava sem ver o que
        precisava ver.
        """
        inicio = self.app.index('path="/"')
        fim = self.app.index('path="/privacidade"', inicio)
        return self.app[inicio:fim]

    def test_a_raiz_do_painel_redireciona_em_vez_de_renderizar(self):
        rota = self._rota_raiz()
        self.assertIn("Navigate", rota)
        self.assertNotIn("HomePage", rota)

    def test_a_raiz_respeita_quem_ja_esta_autenticado(self):
        """Mandar quem esta logado para /login seria expulsar da propria sessao."""
        rota = self._rota_raiz()
        self.assertIn("isAuthenticated", rota)
        self.assertIn("defaultAuthenticatedPath", rota)
        self.assertIn('to="/login"', rota)

    def test_sair_do_administrativo_vai_para_o_login(self):
        """E nao para a raiz, que era como se caia no site congelado."""
        sair = self.admin[self.admin.index("const sair = "):]
        sair = sair[: sair.index("};")]
        self.assertIn('window.location.hash = "#/login"', sair)
        self.assertNotIn('window.location.hash = "#/";', sair)


class ODocumentoJuridicoSaiDaTela(unittest.TestCase):
    """O documento so termina o trabalho quando chega ao juridico do cliente.

    E isso acontece em papel ou PDF, nao na tela. Duas coisas faltavam: uma
    saida — a pessoa abria o contrato durante o cadastro e ficava presa, porque
    o unico caminho era o logotipo, que a tirava do fluxo e fazia perder o
    formulario preenchido — e uma forma de imprimir que nao gastasse tinta com
    menu e nao devolvesse texto claro sobre fundo escuro.
    """

    @classmethod
    def setUpClass(cls):
        cls.pagina = (
            SERVER_DIR.parent
            / "froid-dashboard"
            / "src"
            / "pages"
            / "LegalPages.tsx"
        ).read_text(encoding="utf-8")

    def test_existe_saida_da_tela_do_documento(self):
        self.assertIn("← Voltar", self.pagina)
        self.assertIn("window.history.back()", self.pagina)

    def test_a_saida_respeita_de_onde_a_pessoa_veio(self):
        """Destino fixo faria quem estava no meio do cadastro perder o formulario."""
        volta = self.pagina[self.pagina.index("function voltar()"):]
        volta = volta[: volta.index("\n}")]
        self.assertIn("window.history.length > 1", volta)

    def test_a_navegacao_inclui_os_documentos_do_nr1(self):
        """Existiam desde 22/08 e a barra so listava os clinicos."""
        self.assertIn('href="#/termos-nr1"', self.pagina)
        self.assertIn('href="#/contrato-nr1"', self.pagina)

    def test_a_impressao_esconde_o_que_nao_e_documento(self):
        self.assertIn("@media print", self.pagina)
        self.assertIn("froid-nao-imprime", self.pagina)
        self.assertIn("size: A4", self.pagina)

    def test_a_clausula_nao_parte_entre_paginas(self):
        """Clausula partida e onde a citacao erra o numero."""
        self.assertIn("break-inside: avoid", self.pagina)
        self.assertIn("froid-clausula", self.pagina)

    def test_o_hash_sai_inteiro_no_papel_e_abreviado_na_tela(self):
        """Meia impressao digital nao confere nada.

        Na tela o hash e referencia visual; no documento levado ao juridico do
        cliente ele e a prova, e e la que a conferencia acontece.
        """
        self.assertIn("document.sha256.slice(0, 16)", self.pagina)
        self.assertIn("SHA-256 {document.sha256}", self.pagina)

    def test_ha_botao_de_impressao(self):
        self.assertIn("window.print()", self.pagina)
        self.assertIn("Imprimir / salvar em PDF", self.pagina)
