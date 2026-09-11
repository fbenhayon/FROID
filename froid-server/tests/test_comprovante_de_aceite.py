"""O comprovante de aceite, e o defeito que o teria feito nascer vazio.

Tres coisas sao verificadas aqui, e as tres sao invisiveis em producao ate
alguem PEDIR o comprovante — que e sempre do lado errado de uma discussao.

1. **A aceitacao era arquivada na organizacao errada.** O cadastro gravava
   `stable_uuid("organization", owner_email)`, que e a regra do profissional
   autonomo. Clinica e empresa NR-1 derivam do CNPJ, porque varias pessoas do
   mesmo CNPJ compartilham a organizacao. O aceite da empresa ficava sob um id
   que nao corresponde a organizacao nenhuma dela.

2. **Aceite que nao pode ser gravado precisa falhar alto.** `_legal_hmac`
   devolve string vazia quando FROID_LEGAL_AUDIT_HMAC_KEY tem menos de 32
   bytes, e `_record_legal_documents` saia em silencio: o cadastro respondia
   sucesso e a prova do aceite nao existia em lugar nenhum. E o mesmo padrao
   de "except Exception que so loga" que ja custou seis dias neste servidor.

3. **A leitura procura pelo SUJEITO, nao pela organizacao.** Nao e preferencia
   de estilo: `legal_acceptance_events` e append-only por gatilho, entao as
   linhas gravadas com o id errado nao podem ser corrigidas. Procurar pelo
   sujeito e o que as mantem alcancaveis.
"""

import ast
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MIGRACAO_009 = (
    SERVER_DIR / "migrations" / "009_legal_acceptance_ledger.sql"
).read_text(encoding="utf-8")


def _corpo_da_funcao(fonte: str, nome: str) -> str:
    """O texto de uma funcao, isolado — para nao acusar match de outro trecho."""
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"funcao {nome} nao encontrada")


class AOrganizacaoDoAceite(unittest.TestCase):
    """A empresa NR-1 vive na organizacao do CNPJ, e o aceite tem de ir junto."""

    def test_o_cadastro_deriva_a_organizacao_pela_mesma_regra_do_resto(self):
        # A regra mora em organization_id_for_profile e ja e importada no main
        # como tenant_organization_id_for_profile. Recalcular por fora seria
        # duas verdades sobre a mesma coisa — e foi assim que esta divergiu.
        trecho = MAIN[MAIN.index("context=\"professional_onboarding\"") - 1200 :]
        trecho = trecho[: trecho.index("context=\"professional_onboarding\"") + 60]
        self.assertIn("tenant_organization_id_for_profile(", trecho)

    def test_nao_volta_a_derivar_a_organizacao_do_email_no_aceite(self):
        # A linha exata do defeito. Se ela reaparecer, o aceite da empresa
        # volta a ser arquivado onde nenhuma leitura por organizacao alcanca.
        self.assertNotIn(
            'organization_id=str(stable_uuid("organization", owner_email)),',
            MAIN,
        )

    def test_a_leitura_procura_pelo_sujeito(self):
        # legal_acceptance_events e append-only: as linhas com o id velho nao
        # podem ser corrigidas. Filtrar por organizacao devolveria vazio
        # justamente para o caso que motivou a funcao.
        corpo = _corpo_da_funcao(STORE, "list_legal_acceptances")
        self.assertIn("subject_reference_hash = %s", corpo)
        self.assertIn("if not alvo:", corpo)

    def test_a_organizacao_continua_sendo_filtro_opcional(self):
        corpo = _corpo_da_funcao(STORE, "list_legal_acceptances")
        self.assertIn("if organization_id:", corpo)


class ProvaQueNaoEGravadaPrecisaFalharAlto(unittest.TestCase):
    """Cadastro com sucesso e aceite em lugar nenhum e o pior dos dois mundos."""

    def test_o_registro_recusa_em_vez_de_sair_em_silencio(self):
        corpo = _corpo_da_funcao(MAIN, "_record_legal_documents")
        self.assertIn("subject_hash = _legal_hmac(subject_reference)", corpo)
        self.assertIn("raise HTTPException(", corpo)
        self.assertIn("503", corpo)
        # O `return` mudo era o defeito inteiro.
        self.assertNotIn("if not subject_hash:\n        return\n", corpo)

    def test_a_mensagem_nomeia_a_variavel_que_precisa_ser_configurada(self):
        # Erro de configuracao que nao diz QUAL configuracao manda quem o le
        # procurar no lugar errado — foi o que aconteceu com o 403 do NR-1.
        corpo = _corpo_da_funcao(MAIN, "_record_legal_documents")
        self.assertIn("FROID_LEGAL_AUDIT_HMAC_KEY", corpo)

    def test_a_prontidao_continua_publicando_a_checagem(self):
        # /ready ja avisava; o que faltava era a gravacao recusar.
        self.assertIn('"legal_audit_hmac_configured"', MAIN)


class OLivroContinuaImutavel(unittest.TestCase):
    """Ler o comprovante nao pode ter afrouxado a garantia de quem grava."""

    def test_a_tabela_recusa_alteracao_e_exclusao(self):
        self.assertIn("legal_acceptance_events is append-only", MIGRACAO_009)
        self.assertIn("BEFORE UPDATE OR DELETE ON legal_acceptance_events", MIGRACAO_009)

    def test_o_papel_de_runtime_continua_sem_acesso_ao_livro(self):
        # Prova juridica nao passa pelo papel que atende requisicao. Por isso a
        # leitura usa a conexao do dono, e nao runtime=True.
        self.assertIn("REVOKE ALL ON legal_acceptance_events FROM froid_runtime", MIGRACAO_009)
        corpo = _corpo_da_funcao(STORE, "list_legal_acceptances")
        self.assertNotIn("runtime=True", corpo)

    def test_o_endpoint_devolve_so_os_aceites_de_quem_pediu(self):
        corpo = _corpo_da_funcao(MAIN, "list_organization_legal_acceptances")
        self.assertIn("_require_current_user(request)", corpo)
        self.assertIn("_legal_hmac(email)", corpo)
        # Listar os de terceiros exporia quem mais da empresa se cadastrou.
        self.assertNotIn("organization_id=organization_id", corpo)

    def test_o_endpoint_distingue_ausencia_de_impossibilidade_de_verificar(self):
        corpo = _corpo_da_funcao(MAIN, "list_organization_legal_acceptances")
        self.assertIn('"ledger_configured": False', corpo)
        self.assertIn('"ledger_configured": True', corpo)


class OCatalogoDeInstrumentos(unittest.TestCase):
    """O id do instrumento era a unica coisa que a campanha exigia e ninguem dava."""

    def test_existe_rota_que_lista_os_publicados(self):
        self.assertIn(
            '@app.get("/api/organizations/{organization_id}/nr1/instruments")',
            MAIN,
        )

    def test_so_devolve_instrumento_publicado(self):
        corpo = _corpo_da_funcao(STORE, "nr1_list_instruments")
        self.assertIn("status = 'published'", corpo)

    def test_a_tela_nao_fixa_o_uuid_do_instrumento(self):
        # Seria a quinta copia espelhada de algo que so o banco decide. Ja
        # houve uma que sobreviveu a uma migration em silencio e poria o numero
        # velho numa planilha de proposta comercial.
        tela = (
            SERVER_DIR.parent / "froid-dashboard" / "src" / "pages" / "Nr1Campaign.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("/nr1/instruments", tela)
        self.assertNotIn("155b04c0", tela)


class AEmpresaConsegueReaceitar(unittest.TestCase):
    """O contrato muda, a versao sobe, e a empresa precisa de um caminho.

    Ate 11/09/2026 so o profissional tinha: `/api/professional/legal-acceptances`
    com tela em Settings. A empresa contratante do NR-1 nao tinha nenhum. No dia
    em que o texto do contrato foi substituido, o aceite dela passaria a provar
    um texto superado, o comprovante diria isso em voz alta — corretamente — e
    nao existiria botao para aceitar o novo. O unico caminho seria refazer o
    cadastro, que e o pior conserto possivel para um problema de prova.
    """

    def test_a_rota_da_organizacao_aceita_o_reaceite(self):
        self.assertIn(
            '@app.post("/api/organizations/{organization_id}/legal-acceptances")',
            MAIN,
        )

    def test_so_quem_contrata_pode_aceitar(self):
        """Compliance manager conduz o programa e nao assina pela empresa.

        Aceite valido na aparencia e questionavel na origem e pior que aceite
        nenhum: o primeiro parece prova e nao e.
        """
        corpo = _corpo_da_funcao(MAIN, "renew_organization_legal_acceptances")
        self.assertIn('{"owner", "administrator"}', corpo)
        self.assertIn("403", corpo)

    def test_os_dois_caminhos_compartilham_a_gravacao(self):
        """Duas copias da mesma regra divergem, e aqui a divergencia e cara.

        A que divergisse gravaria o aceite com o hash de um catalogo e deixaria
        o perfil apontando para outro — comprovante certo e acesso errado, ou o
        contrario, e nenhum dos dois aparece ate alguem conferir.
        """
        for rota in (
            "renew_organization_legal_acceptances",
            "renew_professional_legal_acceptances",
        ):
            with self.subTest(rota=rota):
                self.assertIn("_record_legal_renewal(", _corpo_da_funcao(MAIN, rota))
        corpo = _corpo_da_funcao(MAIN, "_record_legal_renewal")
        self.assertIn("required=True", corpo)
        self.assertIn("_record_legal_documents(", corpo)

    def test_o_reaceite_exige_o_hash_do_texto_vigente(self):
        """`required=True` faz `_validated_legal_acceptances` conferir versao E
        sha256 contra o catalogo. Sem isso, a tela poderia gravar aceite de um
        texto que nao e o exibido, e o comprovante imprimiria a divergencia
        como se fosse historico."""
        validacao = _corpo_da_funcao(MAIN, "_validated_legal_acceptances")
        self.assertIn('candidate.get("version") == document["version"]', validacao)
        self.assertIn('candidate.get("sha256") == document["sha256"]', validacao)

    def test_o_contexto_do_ato_diz_a_verdade(self):
        """O comprovante imprime `acceptance_context`.

        Gravar `professional_legal_renewal` num aceite de EMPREGADOR descreve um
        ato que nao aconteceu — e num documento de prova isso e o defeito.
        """
        corpo = _corpo_da_funcao(MAIN, "_legal_renewal_context")
        self.assertIn('"nr1_company_legal_renewal"', corpo)
        self.assertIn('account_type == "nr1_company"', corpo)

    def test_a_natureza_do_sujeito_tem_uma_fonte_so(self):
        """O ternario existia em tres copias.

        O rotulo da empresa ali e errado — a CHECK da migration 009 so admite
        professional, organization e patient, e a empresa entra como
        'professional'. Corrigi-lo exige ALTER numa tabela append-only com
        aceites reais, decisao do dono. O que da para fazer sem essa decisao e
        impedir que o rotulo errado vire tres rotulos errados diferentes.
        """
        self.assertIn("def _legal_subject_kind(", MAIN)
        fora = MAIN.replace(_corpo_da_funcao(MAIN, "_legal_subject_kind"), "")
        self.assertNotIn(
            '"organization" if account_type == "organization" else "professional"',
            fora,
        )

    def test_o_livro_continua_append_only(self):
        """O reaceite ACRESCENTA. Nao existe caminho que altere o anterior."""
        self.assertIn("legal_acceptance_events is append-only", MIGRACAO_009)
        corpo = _corpo_da_funcao(MAIN, "_record_legal_renewal")
        for verbo in ("UPDATE", "DELETE", "delete_legal"):
            with self.subTest(verbo=verbo):
                self.assertNotIn(verbo, corpo)


if __name__ == "__main__":
    unittest.main()
