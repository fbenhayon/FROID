"""Leitura de Governança: quem pode contratar e quanto custa, numa fonte só.

Regra 2.7: o número tem uma fonte. Os limites (estabelecimentos, pessoas na
mesma função) vivem em leitura_governanca.py; o percentual do adicional, em
pricing_nr1.py (decisão do dono, 27/11/2026: 30% para quem optar pela
avaliação horizontal). Site em quatro idiomas, proposta e kit são cópias, e
este arquivo as confere — o glob alcança a próxima página que mencionar o
adicional sem ninguém precisar lembrar.
"""

import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import leitura_governanca  # noqa: E402
import pricing_nr1  # noqa: E402
import proposta_nr1  # noqa: E402

SITE = REPO / "froid-site-dev"
NOMES = ("Leitura de Governança", "Governance Reading", "Lectura de Gobernanza",
         "Lecture de Gouvernance")
PERCENTUAL = pricing_nr1.ADICIONAL_LEITURA_GOVERNANCA_PERCENTUAL


def paginas_que_citam_o_adicional():
    for pagina in sorted(SITE.rglob("*.html")):
        texto = pagina.read_text(encoding="utf-8")
        if any(nome in texto for nome in NOMES):
            yield pagina, texto


class OSiteCopiaAsFontes(unittest.TestCase):
    def test_a_secao_existe_nos_quatro_idiomas(self):
        for idioma in ("", "en/", "es/", "fr/"):
            with self.subTest(idioma=idioma or "pt"):
                texto = (SITE / f"{idioma}nr1/apresentacao-nr1.html").read_text(encoding="utf-8")
                self.assertIn('id="leitura-de-governanca"', texto)
                self.assertIn('id="adicional-leitura-de-governanca"', texto)

    def test_toda_pagina_que_cita_o_adicional_usa_o_percentual_do_motor(self):
        paginas = list(paginas_que_citam_o_adicional())
        self.assertGreaterEqual(len(paginas), 5)
        for pagina, texto in paginas:
            with self.subTest(pagina=str(pagina.relative_to(SITE))):
                citados = {int(n) for n in re.findall(r"(\d+)\s?%\s+(?:sobre|on|sur)", texto)}
                self.assertEqual(citados, {PERCENTUAL})

    def test_os_limites_sao_os_do_modulo(self):
        for pagina, texto in paginas_que_citam_o_adicional():
            if 'id="leitura-de-governanca"' not in texto and "precos-nr1" not in pagina.name:
                continue
            with self.subTest(pagina=str(pagina.relative_to(SITE))):
                self.assertIn(str(leitura_governanca.ESTABELECIMENTOS_MINIMOS), texto)
                self.assertIn(str(leitura_governanca.PESSOAS_NA_FUNCAO_MINIMAS), texto)

    def test_o_modelo_de_proposta_do_canal_copia_as_fontes(self):
        modelo = (REPO / "docs" / "comercial" / "modelo-proposta-cliente-final.md").read_text(
            encoding="utf-8")
        trecho = modelo[modelo.index("Leitura de Governança"):]
        trecho = trecho[: trecho.index("## 7.")]
        self.assertEqual({int(n) for n in re.findall(r"(\d+)%", trecho)}, {PERCENTUAL})
        self.assertIn(f"a partir de {leitura_governanca.ESTABELECIMENTOS_MINIMOS} estabelecimentos", trecho)
        self.assertIn(f"ao menos {leitura_governanca.PESSOAS_NA_FUNCAO_MINIMAS} pessoas", trecho)

    def test_o_site_nao_promete_resolucao_reduzida_que_nao_existe(self):
        """A leitura só em nível de risco para a liderança foi aprovada em
        26/11/2026 e ainda não foi construída: o inventário mostra a média de
        todo grupo, inclusive dos gerentes. Prometê-la seria rótulo que não
        entrega. Quando existir, este teste vira o contrário."""
        for pagina, texto in paginas_que_citam_o_adicional():
            with self.subTest(pagina=str(pagina.relative_to(SITE))):
                for promessa in ("sem média", "no average", "sin promedio", "sans moyenne"):
                    self.assertNotIn(promessa, texto)

    def test_nada_promete_o_nivel_de_decisao_que_ainda_nao_existe(self):
        """O campo "corporativa, regional ou local" no plano de ação foi
        aprovado e não foi construído. Nem o site nem a proposta o prometem."""
        promessas = ("corporativa, regional ou local", "corporate, regional or local",
                     "corporativa, regional o local", "corporative, régionale ou locale",
                     "nível de decisão")
        textos = [(str(p.relative_to(SITE)), t) for p, t in paginas_que_citam_o_adicional()]
        textos.append(("proposta_nr1.py",
                       (SERVER_DIR / "proposta_nr1.py").read_text(encoding="utf-8")))
        for nome, texto in textos:
            with self.subTest(pagina=nome):
                for promessa in promessas:
                    self.assertNotIn(promessa, texto)

    def test_o_site_explica_como_funciona(self):
        for idioma, marca in (("", "COMO FUNCIONA NA PRÁTICA"), ("en/", "HOW IT WORKS IN PRACTICE"),
                              ("es/", "CÓMO FUNCIONA EN LA PRÁCTICA"),
                              ("fr/", "COMMENT CELA FONCTIONNE EN PRATIQUE")):
            with self.subTest(idioma=idioma or "pt"):
                texto = (SITE / f"{idioma}nr1/apresentacao-nr1.html").read_text(encoding="utf-8")
                secao = texto[texto.index('id="leitura-de-governanca"'):]
                secao = secao[: secao.index("</section>")]
                self.assertIn(marca, secao)
                self.assertEqual(secao.count("<li>"), 4)

    def test_o_site_nao_apresenta_o_adicional_como_obrigatorio(self):
        frases = {
            "": "Não é necessária para cumprir a NR-1",
            "en/": "It is not required to comply with NR-1",
            "es/": "No es necesaria para cumplir la NR-1",
            "fr/": "Elle n’est pas nécessaire pour respecter la NR-1",
        }
        for idioma, frase in frases.items():
            with self.subTest(idioma=idioma or "pt"):
                texto = (SITE / f"{idioma}nr1/apresentacao-nr1.html").read_text(encoding="utf-8")
                self.assertIn(frase, texto)


class APropostaCopiaAsFontes(unittest.TestCase):
    LEAD = dict(empresa="Rede Exemplo S.A.", cnpj="00000000000191", nome="Responsável",
                cargo="RH", email="rh@exemplo.com.br", trabalhadores=600)

    def retrato(self, estabelecimentos):
        return proposta_nr1.montar_retrato(
            lead=dict(self.LEAD, estabelecimentos=estabelecimentos), lead_id="ab",
            tabela=pricing_nr1.TABELA_VIGENTE, procedencia="modulo",
            emitida_em=datetime(2026, 11, 27, tzinfo=timezone.utc),
        )

    def test_o_bloco_so_aparece_a_partir_do_limite(self):
        limite = leitura_governanca.ESTABELECIMENTOS_MINIMOS
        self.assertIsNone(self.retrato(limite - 1)["leitura_governanca"])
        self.assertNotIn("Adicional opcional", proposta_nr1.renderizar(self.retrato(limite - 1)))
        self.assertIn("Adicional opcional", proposta_nr1.renderizar(self.retrato(limite)))

    def test_o_valor_e_o_do_motor_de_preco(self):
        r = self.retrato(40)
        calculo = pricing_nr1.simular(600, 40, pricing_nr1.TABELA_VIGENTE)
        mensal = calculo["monthlyTotalCents"]
        adicional = pricing_nr1.adicional_leitura_governanca(mensal)
        self.assertEqual(r["leitura_governanca"]["percentual"], PERCENTUAL)
        self.assertEqual(r["leitura_governanca"]["mensal"], pricing_nr1.formatar_brl(adicional))
        self.assertEqual(
            r["leitura_governanca"]["total_com_adicional"],
            pricing_nr1.formatar_brl(mensal + adicional),
        )

    def test_retrato_antigo_nao_ganha_o_bloco(self):
        """A proposta já enviada continua dizendo o que foi proposto."""
        r = self.retrato(40)
        r.pop("leitura_governanca")
        self.assertNotIn("Adicional opcional", proposta_nr1.renderizar(r))

    def test_nenhum_percentual_escrito_no_texto_da_proposta(self):
        # Percentual de preço ("30% sobre ..."); o "100%" de largura no CSS
        # não é preço.
        fonte = (SERVER_DIR / "proposta_nr1.py").read_text(encoding="utf-8")
        self.assertNotRegex(fonte, r"\b\d+\s?%\s+sobre")


class OPrecoEArredondadoComoAFatura(unittest.TestCase):
    def test_metade_arredonda_para_cima_em_inteiros(self):
        # 2105 centavos x 30% = 631,5 centavos: a fatura cobra 632.
        self.assertEqual(pricing_nr1.adicional_leitura_governanca(2105), 632)
        self.assertEqual(pricing_nr1.adicional_leitura_governanca(2102), 631)
        self.assertEqual(pricing_nr1.adicional_leitura_governanca(0), 0)

    def test_o_adicional_nao_mexe_na_digital_da_tabela(self):
        # A tabela é cópia do motor em TypeScript; o adicional fica fora dela.
        self.assertNotIn("adicional", str(pricing_nr1.canonical_pricing_payload(
            pricing_nr1.TABELA_VIGENTE)).lower())


class OKitCopiaAsFontes(unittest.TestCase):
    def test_o_kit_le_os_limites_e_o_percentual_dos_modulos(self):
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        pagina = gerador[gerador.index("def documento_governanca("):gerador.index("def encerramento(")]
        self.assertIn("leitura_governanca.ESTABELECIMENTOS_MINIMOS", pagina)
        self.assertIn("leitura_governanca.PESSOAS_NA_FUNCAO_MINIMAS", pagina)
        self.assertIn("pricing_nr1.ADICIONAL_LEITURA_GOVERNANCA_PERCENTUAL", pagina)
        self.assertNotRegex(pagina, r"\b\d+\s?%")
        self.assertIn("documento_governanca(p)", gerador)

    def test_a_capa_nao_soma_estabelecimento_como_participante(self):
        gerador = (REPO / "tools" / "gerar-kit-demonstracao-nr1.py").read_text(encoding="utf-8")
        capa = gerador[gerador.index("def capa("):gerador.index("def sumario(")]
        self.assertIn('u["unit_type"] != "site"', capa)
        self.assertNotIn("três grupos", capa)


class QuemPodeContratar(unittest.TestCase):
    def test_limite_de_estabelecimentos(self):
        limite = leitura_governanca.ESTABELECIMENTOS_MINIMOS
        self.assertFalse(leitura_governanca.pode_oferecer(limite - 1))
        self.assertTrue(leitura_governanca.pode_oferecer(limite))
        self.assertFalse(leitura_governanca.pode_oferecer(None))
        self.assertFalse(leitura_governanca.pode_oferecer("x"))

    def test_o_limite_de_enderecos_decorre_de_dois_lideres_por_unidade(self):
        # 20 unidades com gerente e subgerente = 40 pessoas na mesma camada.
        self.assertEqual(
            leitura_governanca.ESTABELECIMENTOS_MINIMOS * 2,
            leitura_governanca.PESSOAS_NA_FUNCAO_MINIMAS,
        )


if __name__ == "__main__":
    unittest.main()
