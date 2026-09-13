"""O que o trabalhador le antes de decidir se responde a verdade.

O CASO, 12/09/2026. A frase pedida para o cabecalho do convite era:

    "Esta avaliacao e voluntaria absolutamente confidencial. Ninguem consegue
     saber quem respondeu e o que; respostas individuais nao sao exibidas, e os
     resultados aparecem apenas de forma coletiva."

Tres quartos dela sao verdade apurada. A metade "ninguem consegue saber QUEM
respondeu" nao e — e o proprio codigo ja registrava isso, no docstring de
`reissue_nr1_invitations`:

    "Quem opera o RH ja tem o pareamento matricula-link no CSV que baixou, e ja
     podia descobrir quem respondeu abrindo cada link e vendo qual recusa."

O empregador RECEBE {matricula, token, pseudonimo} para despachar os convites —
precisa disso para entrega-los. O FROID nao guarda o pareamento, mas quem o
recebeu guarda.

POR QUE ISSO NAO E PREGUICA DE REDACAO. Quem vai relatar assedio decide com base
nesta frase. Se prometermos anonimato de PARTICIPACAO e a pessoa depois descobrir
que o RH sabia que ela respondeu, ela deixa de acreditar tambem na parte que a
protege de verdade — a de que o CONTEUDO nunca e exibido. O exagero custa
exatamente a confianca que ele tentava comprar.

A redacao publicada separa as duas coisas de proposito, e e a mesma recusa que
os contratos ja fazem: Psique 16.4 e NR-1 9.8 nao vendem impossibilidade
arquitetural.
"""

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
ROOT = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

PAGINA = (
    ROOT / "froid-dashboard" / "src" / "pages" / "Nr1QuestionnairePage.tsx"
).read_text(encoding="utf-8")
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")


class OCabecalhoDoConviteDizAVerdade(unittest.TestCase):
    """As tres afirmacoes verdadeiras estao la, e a falsa nao."""

    def test_declara_que_a_participacao_e_voluntaria(self):
        self.assertIn("Esta avaliação é voluntária.", PAGINA)

    def test_declara_que_o_CONTEUDO_nao_e_exibido_a_ninguem(self):
        self.assertIn("O que você respondeu não é exibido a ninguém", PAGINA)
        self.assertIn("nem à sua\n            empresa", PAGINA)

    def test_declara_a_agregacao_e_o_bloqueio_de_recorte_pequeno(self):
        self.assertIn("somados aos de outras pessoas", PAGINA)
        self.assertIn("recortes pequenos demais são bloqueados", PAGINA)

    def test_declara_que_a_empresa_pode_saber_SE_a_pessoa_respondeu(self):
        """A metade desconfortavel, e a que sustenta a credibilidade da outra."""
        self.assertIn("ela pode saber se você\n            respondeu", PAGINA)
        self.assertIn("nunca o que você respondeu", PAGINA)

    def test_a_promessa_forte_demais_nao_esta_na_tela(self):
        for exagero in (
            "absolutamente confidencial",
            "Ninguém consegue saber quem respondeu",
            "As respostas são anônimas",
            "respostas são anônimas",
        ):
            with self.subTest(exagero=exagero):
                self.assertNotIn(exagero, PAGINA)


class OQueSustentaCadaAfirmacao(unittest.TestCase):
    """Cada frase da tela amarrada ao mecanismo que a torna verdadeira.

    Sem isto a tela viraria prosa: alguem removeria o piso de coorte e a frase
    continuaria prometendo que recortes pequenos sao bloqueados.
    """

    def test_o_conteudo_nao_tem_rota_que_o_devolva_individualmente(self):
        """Nao existe endpoint que entregue resposta de um convite."""
        import re

        rotas = re.findall(r'@app\.(?:get|post|put|patch)\("([^"]+)"', MAIN)
        # So as rotas do NR-1: `/api/organization-invitations/accept` e convite
        # de MEMBRO da organizacao (um profissional entrando na clinica), e nao
        # convite de trabalhador. A primeira versao deste filtro as confundiu.
        suspeitas = [
            r for r in rotas
            if "/nr1/" in r and "invitation" in r
            and not r.endswith("/invitations")
            and "reissue" not in r
        ]
        self.assertEqual([], suspeitas, f"rota por convite apareceu: {suspeitas}")

    def test_o_pareamento_matricula_pseudonimo_nao_e_guardado_por_nos(self):
        """A tela diz 'nem a sua empresa' porque NOS nao temos como contar a ela."""
        self.assertIn("FROID never stores the pairing", MAIN)

    def test_a_reemissao_continua_contida_e_auditada(self):
        """E o caminho barato para saber QUEM respondeu — por isso a tela avisa."""
        trecho = MAIN[MAIN.index("async def reissue_nr1_invitations"):][:3000]
        self.assertIn("limite de 50 matrículas", trecho)
        self.assertIn("Sem convite pendente", trecho)

    def test_o_pseudonimo_e_HMAC_com_chave_do_servidor(self):
        """Sem a chave, ninguem reconstroi a tabela a partir de uma folha."""
        trecho = MAIN[MAIN.index("def _nr1_subject_pseudonym"):][:900]
        self.assertIn("hmac.new(", trecho)
        self.assertIn("FROID_DATAMART_PSEUDONYM_KEY", trecho)
        self.assertIn('raise RuntimeError("FROID_DATAMART_PSEUDONYM_KEY is required")', trecho)


class OTrabalhadorNaoAssinaTCLE(unittest.TestCase):
    """Correcao juridica do dono em 12/09/2026.

    O trabalhador NAO precisa de TCLE para participar da avaliacao psicossocial.
    A avaliacao integra o GRO/PGR da organizacao e decorre de obrigacao
    regulatoria da empregadora — o documento adequado e aviso de privacidade e
    ciencia, e nao consentimento livre e esclarecido, que pressuporia que a
    pessoa pudesse simplesmente nao ser avaliada.

    Tratar como TCLE seria, alem de errado, pior para o trabalhador: colocaria o
    consentimento dele como base legal de um tratamento que a empresa e obrigada
    a fazer, e um consentimento que nao pode ser livremente recusado nao e
    consentimento — e a primeira coisa que uma fiscalizacao desmonta.
    """

    def test_nao_existe_documento_de_consentimento_para_o_trabalhador(self):
        import legal_documents

        audiencias = set()
        for doc in legal_documents.DOCUMENT_TEMPLATES.values():
            audiencias |= set(doc["audiences"])
        self.assertNotIn("worker", audiencias)
        self.assertNotIn("trabalhador", audiencias)

    def test_a_base_legal_continua_declarada_no_aviso_da_campanha(self):
        """O aviso por campanha carrega a base legal de forma estrutural."""
        import lgpd_registry

        self.assertTrue(lgpd_registry.AVISO_BASE_LEGAL_NR1.strip())
        self.assertIn("compose_purpose_notice", MAIN)

    def test_os_termos_do_NR1_nao_prometem_consentimento_do_trabalhador(self):
        import legal_documents

        corpo = " ".join(
            b for _, b in legal_documents.DOCUMENT_TEMPLATES["terms_nr1"]["sections"]
        )
        self.assertIn(
            "a voluntariedade não significa, por si só, que consentimento seja a base "
            "jurídica utilizada para todo tratamento",
            corpo,
        )


if __name__ == "__main__":
    unittest.main()
