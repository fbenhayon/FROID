"""O preco publicado do FROID Psique confere com o que o servidor cobra.

SAO DOIS PRODUTOS, COM PRECOS QUE NAO SE MISTURAM
-------------------------------------------------
`test_precos_nr1_espelhados` guarda o FROID Psicossocial (NR-1): base por
estabelecimento mais faixas por trabalhador, vendido a empresa. Este arquivo
guarda o outro: FROID Psique, pacotes de sessao vendidos ao profissional.

Os dois nunca compartilham numero, e a separacao nao e por convencao — e por
construcao. A varredura do NR-1 so olha valores seguidos de "por trabalhador";
esta so olha pacotes de sessao. `precos.html` aponta para a pagina do NR-1 com
um link, sem copiar valor nenhum, que e o unico jeito de duas tabelas de preco
coexistirem sem divergir.

A FONTE AQUI E O SERVIDOR, NAO UMA TABELA DECLARADA
---------------------------------------------------
No NR-1 a fonte tinha de ser declarada no teste, porque preco de NR-1 nao existe
em codigo — vive so em paginas e documentos. Aqui existe: `SESSION_PACKAGES` em
`subscriptions.py` e o que de fato vira cobranca. Entao o teste compara o site
CONTRA o servidor, e nao contra uma copia minha do servidor.

O QUE ESTE TESTE ACHOU EM 05/09/2026
------------------------------------
O site anuncia FROID MASTER com 200 sessoes por R$ 4.888,00. O servidor tem
`master_25`: 25 sessoes por R$ 20,00. Nao existe pacote de 200 em
`subscriptions.py`, nem variavel `STRIPE_PRICE_*` correspondente no
docker-compose.

Nao houve cobranca errada: o botao do MASTER e "Falar com a equipe", nao um
checkout. O risco e o dia em que alguem ligar o checkout do MASTER — ele cai no
unico pacote `master` que existe e cobra R$ 20,00 por 25 sessoes no lugar de
R$ 4.888,00 por 200. Um duzentos e quarenta e quatro avos do preco, em silencio.

O dono confirmou em 05/09/2026 que 200 sessoes por R$ 4.888,00 e a oferta real,
e que vai cadastrar o pacote no Stripe. Ate la a lacuna fica DECLARADA abaixo,
com data e motivo, em vez de deixar a bateria vermelha ou — pior — o teste
passar fingindo que nao ha nada a fazer. Quando o pacote entrar em
`SESSION_PACKAGES`, apague a entrada de PENDENTES e o teste fecha sozinho.
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _catalogo_do_servidor() -> dict:
    """Le `SESSION_PACKAGES` sem importar o modulo inteiro."""
    origem = (SERVER_DIR / "subscriptions.py").read_text(encoding="utf-8")
    import ast

    arvore = ast.parse(origem)
    for no in arvore.body:
        alvo = None
        if isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvo = no.target.id
        elif isinstance(no, ast.Assign) and isinstance(no.targets[0], ast.Name):
            alvo = no.targets[0].id
        if alvo == "SESSION_PACKAGES":
            return ast.literal_eval(no.value)
    raise AssertionError("nao achei SESSION_PACKAGES em subscriptions.py")


CATALOGO = _catalogo_do_servidor()

# Pacote anunciado no site que AINDA nao existe no servidor. Cada entrada e uma
# divida com data e dono, nao uma permissao permanente.
PENDENTES = {
    # (sessoes, total em centavos): motivo
    (200, 488800): "MASTER 200 sessoes — oferta real confirmada em 05/09/2026; "
                   "aguarda cadastro no Stripe e entrada em SESSION_PACKAGES",
}

PACOTE = re.compile(
    r'<span class="qtd">(\d+)\s*sess[^<]*</span>\s*'
    r'<span class="valor">R\$\s*([\d.,]+)',
    re.IGNORECASE,
)


def _centavos(texto: str) -> int:
    return int(round(float(texto.replace(".", "").replace(",", ".")) * 100))


def _pacotes_publicados():
    pagina = (REPO / "froid-site" / "precos.html").read_text(encoding="utf-8")
    return [(int(s), _centavos(v)) for s, v in PACOTE.findall(pagina)]


class OSitePublicaOQueOServidorCobra(unittest.TestCase):
    def test_a_varredura_encontra_os_pacotes(self):
        """Varredura vazia e indistinguivel de varredura limpa."""
        self.assertGreaterEqual(len(_pacotes_publicados()), 4, "nenhum pacote lido de precos.html")

    def test_todo_pacote_publicado_existe_no_servidor_com_o_mesmo_preco(self):
        do_servidor = {
            (int(p["sessions"]), int(p["prices"]["brl"]["total_amount_minor"]))
            for p in CATALOGO.values()
        }
        divergentes = []
        for sessoes, total in _pacotes_publicados():
            if (sessoes, total) in do_servidor:
                continue
            if (sessoes, total) in PENDENTES:
                continue
            divergentes.append(
                "site anuncia %d sessoes por R$ %s e o servidor nao tem esse pacote"
                % (sessoes, ("%.2f" % (total / 100)).replace(".", ","))
            )
        self.assertEqual(
            [],
            divergentes,
            "preco publicado sem cobranca correspondente:\n  " + "\n  ".join(divergentes),
        )

    def test_cada_pendencia_ainda_e_uma_pendencia(self):
        """Quando o pacote entrar no servidor, esta entrada tem de sair daqui.

        Sem isto, a excecao viraria permanente: o pacote passaria a existir e o
        teste continuaria aceitando qualquer preco para ele, que e como uma
        ressalva temporaria vira um buraco definitivo.
        """
        do_servidor = {
            (int(p["sessions"]), int(p["prices"]["brl"]["total_amount_minor"]))
            for p in CATALOGO.values()
        }
        resolvidas = [p for p in PENDENTES if p in do_servidor]
        self.assertEqual(
            [],
            resolvidas,
            "pacote ja existe no servidor — remova de PENDENTES: %s" % (resolvidas,),
        )

    def test_o_plano_master_do_servidor_nao_e_a_oferta_publicada(self):
        """A lapide do defeito, travada.

        Enquanto `master_25` for o unico pacote `master`, ligar o checkout do
        MASTER cobra R$ 20,00 por 25 sessoes. Este teste existe para que a
        proxima pessoa encontre o aviso antes de ligar.
        """
        masters = {k: v for k, v in CATALOGO.items() if v.get("plan_code") == "master"}
        self.assertTrue(masters, "nenhum pacote master no catalogo")
        if set(masters) == {"master_25"}:
            self.assertEqual(2000, masters["master_25"]["prices"]["brl"]["total_amount_minor"])
            self.assertEqual(25, masters["master_25"]["sessions"])

    def test_os_dois_produtos_nao_compartilham_tabela(self):
        """`precos.html` aponta para o NR-1 por LINK, sem copiar valor.

        Copiar seria criar o quinto espelho de um preco que ja tem quatro, e
        entre produtos diferentes — a divergencia mais dificil de perceber.
        """
        pagina = (REPO / "froid-site" / "precos.html").read_text(encoding="utf-8")
        self.assertIn("empresas.html", pagina, "a pagina nao aponta para o produto NR-1")
        self.assertNotIn("por trabalhador", pagina)
        self.assertNotIn("Faixa 1", pagina)


if __name__ == "__main__":
    unittest.main()
