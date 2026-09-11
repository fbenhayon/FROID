"""O defeito de 11/09/2026 que só apareceu com o produto no ar.

O site chamava uma rota que o backend não tinha. Pior: a rota EXISTIA no código.
O site entra por `git pull` e o backend é imagem que exige rebuild — então
`sobre-contato.html` subiu com o formulário e o backend ficou para trás.

Em produção, nas quatro versões de idioma, quem preenchia "Enviar mensagem"
recebia "Não foi possível enviar agora" e a mensagem se perdia.

Não houve erro de build, teste vermelho nem linha de log. A lição não é sobre a
rota, é sobre a ASSIMETRIA de implantação: site e backend sobem por caminhos
diferentes e em momentos diferentes, e nada avisava quando um passava na frente
do outro. `tools/conferir-deploy.py` passou a responder isso contra o servidor
real; este arquivo trava a parte que dá para travar no código.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
PAINEL = REPO / "froid-dashboard" / "src"
SITE = REPO / "froid-site"


def _rotas_do_backend() -> set:
    return {
        achado.group(2)
        for achado in re.finditer(
            r'@app\.(get|post|patch|put|delete|websocket)\("([^"]+)"', MAIN
        )
    }


def _rotas_que_o_site_chama() -> dict:
    """Cada `/api/...` citado pelo site público, e em que arquivos aparece."""
    chamadas: dict = {}
    if not SITE.exists():
        return chamadas
    for caminho in SITE.rglob("*"):
        if not caminho.is_file() or caminho.suffix not in {".html", ".js"}:
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for rota in re.findall(r"[\"'](/api/[A-Za-z0-9/_-]+)[\"']", texto):
            chamadas.setdefault(rota, set()).add(caminho.name)
    return chamadas


class OSiteNaoChamaRotaQueNaoExiste(unittest.TestCase):
    """O site público só pode chamar rota que o backend declara.

    Este teste não teria pego o incidente de 11/09 — lá a rota existia no código
    e faltava no SERVIDOR, que é outra camada. Ele pega o irmão mais fácil do
    mesmo defeito: alguém renomeia ou remove um endpoint e a página continua
    chamando o nome antigo. O sintoma seria idêntico para o visitante, e a
    descoberta seria igualmente cara.
    """

    def test_toda_chamada_do_site_tem_rota_no_backend(self):
        rotas = _rotas_do_backend()
        chamadas = _rotas_que_o_site_chama()
        self.assertTrue(chamadas, "nenhuma chamada de API encontrada no site")
        for rota, arquivos in sorted(chamadas.items()):
            with self.subTest(rota=rota):
                self.assertIn(
                    rota,
                    rotas,
                    f"{rota} e chamada por {sorted(arquivos)} e nao existe em main.py",
                )

    def test_as_duas_chamadas_conhecidas_continuam_declaradas(self):
        """Ancora explicita: se uma delas sumir, este teste nomeia qual.

        `/api/contato` e a do incidente. `/api/leads/nr1` alimenta a captacao do
        NR-1 e estava correta no servidor — e serviu de controle para provar que
        o problema era a rota nova, e nao a comunicacao site-backend.
        """
        rotas = _rotas_do_backend()
        for rota in ("/api/contato", "/api/leads/nr1"):
            with self.subTest(rota=rota):
                self.assertIn(rota, rotas)


class OConferidorDeDeployExiste(unittest.TestCase):
    """A ferramenta que responde "o que esta no ar e diferente do repositorio?".

    O `DEPLOY_LOG.md` respondia isso ate 03/06/2026 e depois parou — ficou
    descrevendo um `uvicorn --reload` num IP e porta que nao existem mais. Log de
    implantacao que envelhece nao e registro incompleto: e registro que MENTE,
    porque quem o le conclui que aquilo esta no ar.

    A substituicao nao e outro arquivo escrito a mao. E um comando que PERGUNTA
    ao servidor.
    """

    FERRAMENTA = REPO / "tools" / "conferir-deploy.py"

    def test_a_ferramenta_esta_versionada(self):
        self.assertTrue(
            self.FERRAMENTA.exists(),
            "tools/conferir-deploy.py sumiu — sem ele a deriva volta a ser invisivel",
        )

    def test_ela_confere_as_tres_camadas(self):
        fonte = self.FERRAMENTA.read_text(encoding="utf-8")
        for camada in ("backend", "painel", "site"):
            with self.subTest(camada=camada):
                self.assertIn(camada, fonte.lower())

    def test_ela_confere_as_rotas_que_o_site_chama(self):
        """O incidente de 11/09 em forma de checagem automatica."""
        fonte = self.FERRAMENTA.read_text(encoding="utf-8")
        self.assertIn("_rotas_que_o_site_chama", fonte)

    def test_ela_nao_precisa_de_chave_ssh(self):
        """Apurado em 04/08/2026: minha chave nao esta autorizada no servidor.

        Uma ferramenta que exigisse SSH so rodaria na maquina do dono, e por isso
        nao rodaria. Esta fala com o servico publico por HTTP.
        """
        fonte = self.FERRAMENTA.read_text(encoding="utf-8")
        self.assertNotIn("ssh ", fonte)
        self.assertIn("https://", fonte)


if __name__ == "__main__":
    unittest.main()
