"""O formulario de contato do site: o que precisa ser verdade para ele servir.

A mensagem escrita pelo visitante nao e gravada em lugar nenhum — vira e-mail
e acabou. A escolha foi deliberada: `marketing_leads` grava e nenhuma tela le,
entao mandar a mensagem para la seria escreve-la onde ninguem a encontraria.
A consequencia e que a caixa de entrada e o unico leitor, e por isso os testes
daqui giram em torno de duas garantias: a mensagem chega a um endereco que a
propria pagina publica, e quando nao chega o visitante fica sabendo.
"""

import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
SITE_DIR = SERVER_DIR.parent / "froid-site"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# Glob, e nao lista de quatro caminhos: quando entrar um quinto idioma ele cai
# nestes testes sem ninguem precisar lembrar de acrescenta-lo (regra 2.8).
PAGINAS = sorted(SITE_DIR.glob("**/sobre-contato.html"))

TEL_CANONICO = "tel:+5511945856941"


def _destino_publicado_no_backend() -> str:
    """O endereco padrao de `CONTATO_DESTINO`, lido pelo parser.

    Pelo parser e nao por regex de linha porque a constante esta quebrada em
    varias linhas, e recorte por linha ja quebrou testes desta casa duas vezes.
    """
    arvore = ast.parse((SERVER_DIR / "main.py").read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == "CONTATO_DESTINO"
            for alvo in no.targets
        ):
            textos = [
                filho.value
                for filho in ast.walk(no.value)
                if isinstance(filho, ast.Constant) and isinstance(filho.value, str)
            ]
            enderecos = [t for t in textos if "@" in t]
            if enderecos:
                return enderecos[-1]
    raise AssertionError("CONTATO_DESTINO nao encontrado em main.py")


class PaginasEncontradasTests(unittest.TestCase):
    def test_o_glob_acha_as_paginas(self):
        # Sem esta assercao, um glob que deixasse de casar faria toda a classe
        # abaixo passar varrendo lista vazia — verde sem ter verificado nada.
        self.assertGreaterEqual(len(PAGINAS), 4, f"achei {len(PAGINAS)}: {PAGINAS}")


class EnderecoPublicadoTests(unittest.TestCase):
    """Espelho de endereco (regra 2.7 aplicada a contato, nao a numero).

    Se a pagina publicar um endereco e o backend mandar para outro, o visitante
    le um e escreve para outro, e a mensagem que ele digitou no formulario cai
    numa caixa que ninguem abre. Os dois lados sao conferidos contra a mesma
    fonte.
    """

    def setUp(self):
        self.destino = _destino_publicado_no_backend()

    def test_o_backend_manda_para_o_endereco_que_o_site_publica(self):
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                self.assertIn(f"mailto:{self.destino}", html)

    def test_nenhuma_pagina_publica_outro_endereco_de_contato(self):
        # contato@, vendas@ e suporte@ estavam nas versoes traduzidas e nao
        # respondem por este formulario. Um endereco morto ao lado do vivo faz
        # o visitante escolher errado.
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                outros = set(re.findall(r"mailto:([^\"'>\s]+@froid\.com\.br)", html))
                self.assertEqual(outros, {self.destino}, f"tambem publica {outros}")

    def test_o_padrao_do_compose_e_o_mesmo_do_backend(self):
        # Terceira copia do endereco (main.py, docker-compose.yml e as
        # paginas). Um padrao divergente no compose venceria o do codigo, e a
        # mensagem passaria a ir para outro lugar sem erro nenhum.
        compose = (SERVER_DIR.parent / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        achado = re.search(
            r"FROID_CONTATO_DESTINO=\$\{FROID_CONTATO_DESTINO:-([^}]*)\}", compose
        )
        self.assertIsNotNone(
            achado,
            "FROID_CONTATO_DESTINO precisa de linha no docker-compose.yml: o "
            "froid-backend recebe lista explicita, nao env_file",
        )
        self.assertEqual(achado.group(1), self.destino)

    def test_o_telefone_e_o_mesmo_em_todo_lugar(self):
        # O texto visivel muda por idioma ("(11) 94585-6941" em portugues,
        # "+55 11 94585-6941" nas outras) — o que nao pode variar e o href,
        # que e o que disca.
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                telefones = set(re.findall(r'href="(tel:[^"]+)"', html))
                self.assertEqual(telefones, {TEL_CANONICO})


class FormularioNaPaginaTests(unittest.TestCase):
    def test_toda_pagina_tem_o_formulario_apontando_para_o_endpoint(self):
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                self.assertIn('action="/api/contato"', html)
                for campo in ("nome", "email", "telefone", "mensagem"):
                    self.assertIn(f'name="{campo}"', html)

    def test_a_secao_quem_faz_o_froid_saiu_das_quatro(self):
        removidos = ("Quem faz o FROID", "Who makes FROID", "Quién hace FROID",
                     "Qui fait FROID")
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                for titulo in removidos:
                    self.assertNotIn(titulo, html)

    def test_o_visitante_fica_sabendo_quando_o_envio_falha(self):
        # Padrao 2.2: degradacao silenciosa e indistinguivel de sucesso. Se o
        # POST falhar, a pagina precisa dizer, e precisa oferecer a saida que
        # nao depende do backend — o telefone e o e-mail.
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                html = pagina.read_text(encoding="utf-8")
                self.assertIn("function falhou(", html)
                self.assertIn("form-status erro", html)
                self.assertIn(".catch(function () { falhou(0); })", html)


class ScriptEmbutidoTests(unittest.TestCase):
    """O script inline precisa existir como JavaScript valido.

    Nasceu de um defeito real: as tres frases francesas com apostrofo —
    "L'envoi", "d'au moins", "l'adresse" — foram interpoladas dentro de aspas
    simples e quebraram o arquivo inteiro. O sintoma nao seria um formulario
    meio funcionando: `enviarContato` nunca chegaria a ser definido, o
    `onsubmit` falharia e o navegador faria o POST nativo, entregando ao
    visitante a resposta JSON crua da API.
    """

    def _script_de(self, pagina: Path) -> str:
        html = pagina.read_text(encoding="utf-8")
        achado = re.search(r"<script>\n(.*?)</script>", html, re.S)
        self.assertIsNotNone(achado, f"{pagina} nao tem script inline")
        return achado.group(1)

    @staticmethod
    def _defeitos_de_string(linha: str):
        """Problemas de string na linha, como lista de descricoes.

        Contar aspas nao serve, e acompanhar so o estado tambem nao. A linha
        que de fato quebrou o arquivo frances era
        `return 'L'envoi n'a pas pu aboutir...';` — quatro apostrofos, numero
        par, nenhuma string aberta no fim. O JavaScript a recusa por outro
        motivo: `'L'` termina a string e o `envoi` logo em seguida vira um
        identificador solto, dois valores colados sem operador.

        Entao sao duas as coisas verificadas: string aberta ao fim da linha
        (uma string nao atravessa a quebra de linha em JS) e string fechada
        colada num identificador, que e a assinatura do apostrofo perdido.
        """
        problemas = []
        aberta = None
        i = 0
        while i < len(linha):
            c = linha[i]
            if aberta:
                if c == "\\":
                    i += 2
                    continue
                if c == aberta:
                    aberta = None
                    seguinte = linha[i + 1 : i + 2]
                    if seguinte and (seguinte.isalnum() or seguinte in "_$'\""):
                        problemas.append(
                            f"string fechada colada em {seguinte!r} na coluna {i + 2}"
                        )
            elif c in ("'", '"'):
                aberta = c
            elif c == "/" and linha[i : i + 2] == "//":
                break  # comentario: o resto da linha nao e codigo
            i += 1
        if aberta:
            problemas.append(f"string aberta com {aberta} ate o fim da linha")
        return problemas

    def test_nenhuma_linha_tem_string_malformada(self):
        # Substituto estatico do parser, que roda sempre — inclusive onde nao
        # houver node.
        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                for numero, linha in enumerate(self._script_de(pagina).splitlines(), 1):
                    self.assertEqual(
                        self._defeitos_de_string(linha),
                        [],
                        f"{pagina.parent.name}/{pagina.name} linha {numero}: "
                        f"{linha.strip()}",
                    )

    def test_o_verificador_reprova_o_defeito_que_de_fato_existiu(self):
        """O teste acima precisa falhar onde deve — senao nao defende nada.

        As duas primeiras linhas sao as versoes reais do arquivo frances,
        antes e depois da correcao. A primeira versao deste verificador
        contava aspas, dava par nas duas, e aprovava a quebrada.
        """
        quebrada = "    return 'L'envoi n'a pas pu aboutir pour le moment.';"
        correta = '    return "L\'envoi n\'a pas pu aboutir pour le moment.";'
        self.assertTrue(self._defeitos_de_string(quebrada))
        self.assertEqual(self._defeitos_de_string(correta), [])

        # Um apostrofo dentro de aspas duplas nao pode ser acusado.
        self.assertEqual(
            self._defeitos_de_string('  var a = "d\'au moins 10 caracteres";'), []
        )
        # Nem as formas comuns do proprio script.
        for legitima in (
            "  var dados = { origem: \"sobre-contato-en\" };",
            "  ['nome', 'email', 'telefone', 'mensagem'].forEach(function (campo) {",
            "    var el = document.getElementById('contato-' + campo);",
            '    status.innerHTML = t + " veja <a href=\\"mailto:a@b.c\\">a@b.c</a>.";',
        ):
            self.assertEqual(self._defeitos_de_string(legitima), [], legitima)

        # E a string aberta ate o fim da linha continua sendo pega.
        self.assertTrue(self._defeitos_de_string("  var a = 'sem fechar;"))

    def test_o_parser_de_javascript_aceita(self):
        try:
            subprocess.run(
                ["node", "--version"], capture_output=True, check=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError):
            self.skipTest("node ausente; o teste estatico acima cobre o caso")
        import tempfile

        for pagina in PAGINAS:
            with self.subTest(pagina=pagina.name, idioma=pagina.parent.name):
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".js", encoding="utf-8", delete=False
                ) as arquivo:
                    arquivo.write(self._script_de(pagina))
                    caminho = arquivo.name
                try:
                    resultado = subprocess.run(
                        ["node", "--check", caminho],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                finally:
                    Path(caminho).unlink(missing_ok=True)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)


class EndpointPublicoTests(unittest.TestCase):
    def setUp(self):
        fonte = (SERVER_DIR / "main.py").read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        # Recorte pelo parser, nao por janela de caracteres: crescimento de
        # comentario ja quebrou testes desta casa que fatiavam por tamanho.
        for no in ast.walk(arvore):
            if isinstance(no, ast.AsyncFunctionDef) and no.name == (
                "receber_mensagem_de_contato"
            ):
                self.funcao = no
                self.trecho = ast.unparse(no)
                break
        else:
            raise AssertionError("endpoint de contato nao encontrado em main.py")

    def test_tem_limite_de_taxa_por_ip(self):
        # Formulario aberto na internet e alvo de robo antes de ser alvo de
        # cliente — e aqui cada envio custa um e-mail saindo pelo SMTP do FROID.
        self.assertIn("_rate_limit_guard", self.trecho)
        self.assertIn("_client_ip(request)", self.trecho)

    def test_limita_o_tamanho_de_cada_campo(self):
        self.assertIn("def _texto(", self.trecho)
        self.assertIn("[:limite]", self.trecho)

    def test_nao_finge_ter_enviado_quando_nao_enviou(self):
        # Regra 1.3: falhe fechado, e diga que fechou. Um 200 sem envio deixa
        # o visitante esperando resposta a um e-mail que nunca saiu.
        self.assertIn("503", self.trecho)
        self.assertIn("mailer_enabled()", self.trecho)
        self.assertIn("MailerError", self.trecho)

    def test_o_sucesso_so_existe_depois_do_envio(self):
        """Nenhum `return` de sucesso antes da chamada que envia o e-mail.

        Os `return` de funcoes aninhadas ficam de fora: o ajudante `_texto`
        tem o seu, e conta-lo faria o teste reprovar codigo correto.
        """
        envio = [
            no.lineno
            for no in ast.walk(self.funcao)
            if isinstance(no, ast.Attribute) and no.attr == "send_email"
        ]
        self.assertTrue(envio, "o endpoint nao chama send_email")

        aninhadas = {
            id(filho)
            for no in ast.walk(self.funcao)
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
            and no is not self.funcao
            for filho in ast.walk(no)
        }
        sucessos = [
            no.lineno
            for no in ast.walk(self.funcao)
            if isinstance(no, ast.Return)
            and no.value is not None
            and id(no) not in aninhadas
        ]
        self.assertTrue(sucessos, "o endpoint nao devolve nada")
        self.assertGreater(min(sucessos), max(envio))

    def test_nao_grava_a_mensagem_onde_ninguem_le(self):
        # `marketing_leads` nao tem leitor. Escrever a mensagem la seria
        # perde-la de um jeito que ninguem reclamaria (padrao 2.1).
        self.assertNotIn("register_marketing_lead", self.trecho)
        self.assertNotIn("INSERT", self.trecho)

    def test_o_log_da_falha_nao_leva_a_mensagem_nem_o_remetente(self):
        # A excecao do smtplib pode carregar o destinatario; a mensagem e de um
        # visitante. Nem uma nem outra tem por que ficar no arquivo de log.
        #
        # Pelo parser, e nao por regex sobre o texto: `ast.unparse` normaliza a
        # formatacao, e uma regex ancorada em quebra de linha nunca casaria —
        # passaria a vida sem poder falhar.
        registros = [
            ast.unparse(no)
            for no in ast.walk(self.funcao)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and isinstance(no.func.value, ast.Name)
            and no.func.value.id == "LOGGER"
        ]
        self.assertTrue(registros, "a falha de envio precisa ser registrada")
        for registro in registros:
            for proibido in ("mensagem", "email", "nome", "telefone", "corpo"):
                self.assertNotIn(proibido, registro, f"log leva {proibido}")


class CabecalhoDeEmailTests(unittest.TestCase):
    """Nome e e-mail de visitante anonimo entram em Subject e Reply-To.

    Um CRLF no meio de um cabecalho e o que permite anexar outro cabecalho —
    um `Bcc:` para uma lista qualquer, com o SMTP autenticado do FROID
    assinando o envio.
    """

    def setUp(self):
        self.fonte = (SERVER_DIR / "froid_mailer.py").read_text(encoding="utf-8")
        self.arvore = ast.parse(self.fonte)

    def test_todo_cabecalho_passa_pelo_saneamento(self):
        """Subject e Reply-To saem de `_header_safe`, direto ou por variavel.

        A garantia e "o texto do visitante foi achatado antes de virar
        cabecalho", nao "a chamada esta escrita na mesma linha": `Reply-To`
        recebe uma variavel que `_header_safe` produziu duas linhas acima, e
        exigir a forma literal reprovaria codigo correto.
        """
        for no in ast.walk(self.arvore):
            if isinstance(no, ast.FunctionDef) and no.name == "send_email":
                funcao = no
                break
        else:
            raise AssertionError("send_email nao encontrado")

        saneadas = {
            alvo.id
            for no in ast.walk(funcao)
            if isinstance(no, ast.Assign)
            for alvo in no.targets
            if isinstance(alvo, ast.Name) and "_header_safe" in ast.unparse(no.value)
        }

        vistos = set()
        for no in ast.walk(funcao):
            if not (isinstance(no, ast.Assign) and len(no.targets) == 1):
                continue
            alvo = no.targets[0]
            if not (
                isinstance(alvo, ast.Subscript)
                and isinstance(alvo.value, ast.Name)
                and alvo.value.id == "message"
                and isinstance(alvo.slice, ast.Constant)
            ):
                continue
            cabecalho = alvo.slice.value
            vistos.add(cabecalho)
            if cabecalho not in ("Subject", "Reply-To"):
                continue  # From, To, Message-ID e Auto-Submitted sao do backend
            origem = ast.unparse(no.value)
            self.assertTrue(
                "_header_safe" in origem or origem in saneadas,
                f"{cabecalho} recebe {origem} sem passar por _header_safe",
            )
        for obrigatorio in ("Subject", "Reply-To"):
            self.assertIn(obrigatorio, vistos)

    def test_o_saneamento_remove_quebra_de_linha(self):
        espaco = {}
        exec(  # noqa: S102 - a funcao e pequena e nao toca em nada externo
            ast.unparse(
                next(
                    no
                    for no in ast.walk(self.arvore)
                    if isinstance(no, ast.FunctionDef) and no.name == "_header_safe"
                )
            ),
            espaco,
        )
        _header_safe = espaco["_header_safe"]
        self.assertEqual(
            _header_safe("Fabio\r\nBcc: lista@exemplo.com"),
            "Fabio Bcc: lista@exemplo.com",
        )
        self.assertEqual(_header_safe("linha\nquebrada"), "linha quebrada")
        self.assertEqual(_header_safe(""), "")


if __name__ == "__main__":
    unittest.main()
