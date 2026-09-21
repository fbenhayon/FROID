"""A sessao seguinte nao repete as autorizacoes — mas tambem nao as presume.

DECISAO DO DONO, 21/09/2026.

O paciente preenche as autorizacoes uma vez, no cadastro. Nas sessoes seguintes,
diarias ou semanais conforme a contratacao, ele confirma num clique que as que ja
deu seguem valendo. O que este arquivo garante e que essa simplificacao continue
sendo uma REAFIRMACAO, e nao uma autorizacao generica — que a LGPD anula (art. 8o
par. 4o) e que, para dado sensivel de saude, exige destaque proprio (art. 11, I).

A diferenca entre as duas coisas esta em quatro pontos, e cada um tem teste:

1. A tela NOMEIA o que esta sendo reafirmado. Confirmar o que nao se ve nao e
   confirmar, e um "de acordo" sobre lista invisivel e exatamente a autorizacao
   generica que a lei recusa.
2. A confirmacao e EXIGIDA pelo servidor. Caixa que a tela mostra e o servidor
   ignora e teatro — e teatro num registro de consentimento e pior do que nao ter
   caixa nenhuma.
3. Reafirmar NAO substitui ter a autorizacao em ficha, nem revalida documento de
   versao vencida. As duas guardas que ja existiam continuam ANTES desta.
4. A trilha distingue o aceite original da reafirmacao, para poder responder
   "quando ela consentiu?" separado de "quando ela confirmou que seguia valendo?".

Os testes afirmam sobre o texto-fonte porque main.py depende de fastapi e a
suite estatica vizinha faz o mesmo. Onde a garantia mora na tela, o alvo e o
fonte da tela.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
TELA = (
    REPO / "froid-dashboard" / "src" / "pages" / "PatientInvitePage.tsx"
).read_text(encoding="utf-8")
TEXTOS = (
    REPO / "froid-dashboard" / "src" / "lib" / "localization.ts"
).read_text(encoding="utf-8")


def _corpo(nome: str) -> str:
    padrao = rf"\n(?:async )?def {re.escape(nome)}\(.*?(?=\n(?:async )?def |\n@app\.|\Z)"
    achado = re.search(padrao, MAIN, re.DOTALL)
    assert achado, f"funcao {nome} nao encontrada"
    return achado.group(0)


class AReafirmacaoNaoEGenericaTests(unittest.TestCase):
    # ---------- 1. a tela nomeia o que esta sendo reafirmado ----------

    def test_o_servidor_envia_as_autorizacoes_em_ficha(self):
        corpo = _corpo("get_session_invite")
        self.assertIn("consent_on_file", corpo)
        self.assertIn("_patient_consent_preferences(patient)", corpo)

    def test_so_o_paciente_recorrente_recebe_a_lista(self):
        # Convite de cadastro novo nao tem autorizacao anterior para mostrar, e
        # a lista nao pode sair para quem ainda nao e paciente.
        corpo = _corpo("get_session_invite")
        self.assertIn("if password_only and isinstance(patient, dict):", corpo)

    def test_a_tela_lista_cada_autorizacao_pelo_nome(self):
        self.assertIn("autorizacoesEmVigor", TELA)
        self.assertIn("copy.consentLabels[", TELA)
        # Chave que a tela nao sabe nomear e descartada, e nao exibida crua:
        # "sensitive_data_processing" na tela nao informa ninguem.
        self.assertIn("Boolean(item.label)", TELA)

    def test_a_tela_oferece_os_documentos_para_leitura(self):
        for destino in ("#/tcle-paciente", "#/privacidade", "#/termos"):
            self.assertIn(destino, TELA)

    # ---------- 2. a confirmacao e exigida, nao decorativa ----------

    def test_o_servidor_recusa_sem_a_reafirmacao(self):
        corpo = _corpo("accept_session_invite")
        self.assertIn('body.get("consent_reaffirmed") is not True', corpo)
        self.assertIn("status_code=400", corpo)

    def test_a_tela_envia_a_reafirmacao(self):
        self.assertIn("consent_reaffirmed: consentReaffirmed", TELA)

    def test_a_caixa_nasce_desmarcada(self):
        # Reafirmar e ato do paciente, e ato nao se pratica por omissao.
        self.assertIn("useState(false)", TELA)
        achado = re.search(
            r"const \[consentReaffirmed, setConsentReaffirmed\] = useState\((\w+)\)",
            TELA,
        )
        self.assertIsNotNone(achado, "estado da reafirmacao nao encontrado")
        self.assertEqual(achado.group(1), "false")

    # ---------- 3. reafirmar nao substitui as guardas anteriores ----------

    def test_reafirmar_nao_dispensa_a_autorizacao_em_ficha(self):
        corpo = _corpo("accept_session_invite")
        posicao_guarda = corpo.index("if missing or legal_version_outdated:")
        posicao_reafirmacao = corpo.index('body.get("consent_reaffirmed")')
        self.assertLess(
            posicao_guarda,
            posicao_reafirmacao,
            "a reafirmacao passou a rodar ANTES da checagem de autorizacao em "
            "ficha — um clique voltaria a valer por uma autorizacao que nao existe",
        )

    def test_versao_vencida_continua_bloqueando(self):
        corpo = _corpo("accept_session_invite")
        self.assertIn("legal_version_outdated", corpo)
        self.assertIn("LEGAL_DOCUMENT_VERSION", corpo)
        self.assertIn("status_code=403", corpo)

    # ---------- 4. a trilha distingue aceite de reafirmacao ----------

    def test_a_trilha_registra_que_foi_reafirmacao(self):
        corpo = _corpo("accept_session_invite")
        self.assertIn('"reaffirmed": consent_reaffirmed', corpo)
        self.assertIn("consent_reaffirmed = True", corpo)
        self.assertIn("consent_reaffirmed = False", corpo)

    # ---------- o texto existe nos quatro idiomas ----------

    def test_os_textos_existem_em_todos_os_idiomas(self):
        # O paciente le a confirmacao no idioma que o profissional escolheu para
        # a interface dele. Faltar num idioma faria a tela pedir consentimento
        # em lingua que ele nao fala — ou quebrar o build.
        for chave in (
            "authorizationsInForce",
            "authorizationsInForceBody",
            "authorizationsGivenAt",
            "reaffirmAuthorizations",
            "readDocuments",
        ):
            # 1 declaracao no tipo + 4 idiomas.
            self.assertEqual(
                TEXTOS.count(f"{chave}:"),
                5,
                f"{chave} nao esta nos quatro idiomas (e no tipo)",
            )


if __name__ == "__main__":
    unittest.main()
