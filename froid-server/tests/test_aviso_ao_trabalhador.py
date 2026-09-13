"""O que o trabalhador le antes de decidir se responde a verdade.

O CASO, 12/09/2026. A frase pedida para o cabecalho do convite era:

    "Esta avaliacao e voluntaria absolutamente confidencial. Ninguem consegue
     saber quem respondeu e o que; respostas individuais nao sao exibidas, e os
     resultados aparecem apenas de forma coletiva."

Eu objetei lendo "quem respondeu E o que" como DUAS afirmacoes, e apontei que a
primeira era falsa: quem opera o RH tem o pareamento matricula-link no CSV que
baixou para distribuir os convites, e o docstring de `reissue_nr1_invitations`
ja registrava que da para descobrir quem respondeu abrindo cada link.

O DONO ESTAVA CERTO, E EU ERRADO, sobre a leitura: "quem respondeu o que" e uma
afirmacao unica, sobre o PAREAMENTO pessoa-resposta. O RH saber quem participou
nao a contradiz.

Restava uma palavra: "ninguem". O desenho separava o conhecimento em duas maos —
o FROID com resposta <-> pseudonimo, a empresa com pseudonimo <-> matricula —, e
sozinha nenhuma das duas conseguia o pareamento. Juntas conseguiriam, porque
`assessment_responses.invitation_id` guardava o elo: sob ordem judicial, por
conluio, ou num vazamento que alcancasse os dois lados.

DECISAO DO DONO: em vez de afrouxar a frase, CONSTRUIR a impossibilidade. A
migration 034 rompe esse elo no mesmo commit que fecha a coleta. O dado deixa de
existir, e a frase passa a ser verdade de arquitetura em vez de conduta — nem
uma ordem judicial o recupera, porque nao ha o que entregar.

O que permanece dito e a participacao: a empresa distribui os links e sabe QUEM
respondeu. Admitir isso sustenta a promessa em vez de enfraquece-la.
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
STORE = (SERVER_DIR / "tenant_store.py").read_text(encoding="utf-8")
MIGRACAO = (
    SERVER_DIR / "migrations" / "034_anonimato_apos_o_fechamento.sql"
).read_text(encoding="utf-8")


def _sem_quebra(texto: str) -> str:
    """O JSX quebra frases entre linhas; o leitor ve uma frase so."""
    return " ".join(texto.split())


PAGINA_CORRIDA = _sem_quebra(PAGINA)


class OCabecalhoDoConviteDizAVerdade(unittest.TestCase):
    """As quatro afirmacoes da tela, cada uma verificavel."""

    def test_declara_que_a_participacao_e_voluntaria(self):
        self.assertIn("Esta avaliação é voluntária e confidencial.", PAGINA_CORRIDA)

    def test_afirma_a_impossibilidade_do_pareamento(self):
        """A frase do dono, e agora ela e verdade de arquitetura.

        Ela so pode estar na tela porque a migration 034 construiu a
        impossibilidade. Antes dela esta assercao seria uma promessa que o
        proprio banco desmentia.
        """
        self.assertIn("Ninguém consegue saber quem respondeu o quê.", PAGINA_CORRIDA)

    def test_declara_que_o_CONTEUDO_nao_e_exibido_a_ninguem(self):
        self.assertIn("não são exibidas individualmente a ninguém", PAGINA_CORRIDA)
        self.assertIn("nem à sua empresa", PAGINA_CORRIDA)

    def test_declara_a_agregacao_e_o_bloqueio_de_recorte_pequeno(self):
        self.assertIn("somados aos de outras pessoas", PAGINA_CORRIDA)
        self.assertIn("recortes pequenos demais são bloqueados", PAGINA_CORRIDA)

    def test_explica_o_MECANISMO_e_nao_so_a_promessa(self):
        """Quem le tem direito de saber POR QUE a promessa se sustenta."""
        self.assertIn("apagado do banco de dados", PAGINA_CORRIDA)
        self.assertIn("nem o FROID consegue refazê-lo", PAGINA_CORRIDA)

    def test_declara_que_a_empresa_pode_saber_SE_a_pessoa_respondeu(self):
        """Fica de proposito: admitir isso sustenta o resto.

        Quem desconfia que o RH sabe que respondeu, e nos ve admitir, acredita
        na parte que protege. Prometer tambem anonimato de PARTICIPACAO seria o
        unico exagero capaz de derrubar tudo o que a frase afirma de verdade.
        """
        self.assertIn("ela pode saber se você respondeu", PAGINA_CORRIDA)
        self.assertIn("nunca o que você respondeu", PAGINA_CORRIDA)

    def test_a_palavra_que_nao_descreve_o_desenho_continua_fora(self):
        """"Anonimas" diria que a resposta nasce sem vinculo. Ela nasce COM.

        O vinculo existe durante a coleta — e a guarda contra envio duplo — e e
        rompido no fechamento. Chamar de anonima desde o inicio descreveria
        outro sistema, e quem descobrisse o vinculo aberto concluiria, com
        razao, que fomos imprecisos tambem no resto.
        """
        self.assertNotIn("As respostas são anônimas", PAGINA_CORRIDA)


class OEloERompidoNoFechamento(unittest.TestCase):
    """O mecanismo que torna a frase verdadeira, preso onde ele mora."""

    def test_a_coluna_aceita_nulo(self):
        self.assertIn(
            "ALTER TABLE assessment_responses ALTER COLUMN invitation_id DROP NOT NULL",
            MIGRACAO,
        )

    def test_a_funcao_recusa_campanha_aberta(self):
        """A condicao mora no SQL para sobreviver a erro na camada de cima.

        Romper com a coleta aberta destruiria a guarda contra envio duplo.
        """
        self.assertIn("SECURITY DEFINER", MIGRACAO)
        self.assertIn("AND status = 'closed'", MIGRACAO)
        self.assertIn("RAISE EXCEPTION 'campanha % nao esta fechada'", MIGRACAO)

    def test_as_campanhas_ja_fechadas_tambem_foram_rompidas(self):
        """Sem o backfill a garantia valeria so para o futuro — e e no passado
        que o elo ficou parado por mais tempo, sem finalidade nenhuma."""
        self.assertIn("UPDATE assessment_responses AS resposta", MIGRACAO)
        self.assertIn("campanha.status = 'closed'", MIGRACAO)

    def test_o_fechamento_rompe_no_MESMO_commit(self):
        """Passo separado abriria uma janela com a coleta fechada e o elo de pe."""
        corpo = STORE[STORE.index("def nr1_close_campaign"):][:4200]
        self.assertIn("froid_nr1_sever_response_links", corpo)
        # Dentro do mesmo `with connection.transaction():` do UPDATE.
        posicao_update = corpo.index("UPDATE assessment_campaigns")
        posicao_rompe = corpo.index("froid_nr1_sever_response_links(%s)")
        posicao_saida = corpo.index("if not row:")
        self.assertLess(posicao_update, posicao_rompe)
        self.assertLess(posicao_rompe, posicao_saida)

    def test_a_trilha_registra_quantos_elos_foram_rompidos(self):
        """"Executou" nao prova nada; "rompeu 152" e conferivel."""
        self.assertIn('metadata={"links_severed": closed.get("links_severed", 0)}', MAIN)

    def test_a_coluna_continua_sem_nenhum_leitor(self):
        """Se alguem passar a LER invitation_id, romper o elo quebra algo.

        Hoje ela e escrita uma vez e nunca lida: nenhum SELECT, nenhum JOIN,
        nenhum agregado. E por isso que romper e gratuito.
        """
        import re

        sql = " ".join(
            caminho.read_text(encoding="utf-8")
            for caminho in sorted((SERVER_DIR / "migrations").glob("*.sql"))
        )
        leituras = re.findall(r"SELECT[^;]{0,400}?invitation_id", sql, re.IGNORECASE)
        self.assertEqual([], leituras, f"alguem passou a ler o elo: {leituras}")


class OQueSustentaCadaAfirmacao(unittest.TestCase):
    """Cada frase da tela amarrada ao mecanismo que a torna verdadeira.

    Sem isto a tela viraria prosa: alguem removeria o piso de coorte e ela
    continuaria prometendo que recortes pequenos sao bloqueados.
    """

    def test_o_conteudo_nao_tem_rota_que_o_devolva_individualmente(self):
        """Nao existe endpoint que entregue a resposta de um convite."""
        import re

        rotas = re.findall(r'@app\.(?:get|post|put|patch)\("([^"]+)"', MAIN)
        # So as rotas do NR-1: `/api/organization-invitations/accept` e convite
        # de MEMBRO da organizacao, e nao de trabalhador.
        suspeitas = [
            r for r in rotas
            if "/nr1/" in r and "invitation" in r
            and not r.endswith("/invitations")
            and "reissue" not in r
        ]
        self.assertEqual([], suspeitas, f"rota por convite apareceu: {suspeitas}")

    def test_o_papel_da_aplicacao_nao_le_uma_resposta(self):
        """A garantia mais forte do modulo, e a que sobrevive a bug na aplicacao."""
        hardening = (
            SERVER_DIR / "migrations" / "014_nr1_audit_hardening.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("REVOKE ALL ON assessment_responses FROM froid_runtime", hardening)
        self.assertIn(
            "REVOKE ALL ON assessment_response_items FROM froid_runtime", hardening
        )

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
        self.assertIn(
            'raise RuntimeError("FROID_DATAMART_PSEUDONYM_KEY is required")', trecho
        )


class OTrabalhadorNaoAssinaTCLE(unittest.TestCase):
    """Correcao juridica do dono em 12/09/2026.

    O trabalhador NAO precisa de TCLE para participar da avaliacao psicossocial.
    A avaliacao integra o GRO/PGR da organizacao e decorre de obrigacao
    regulatoria da empregadora — o documento adequado e aviso de privacidade e
    ciencia, e nao consentimento livre e esclarecido, que pressuporia que a
    pessoa pudesse simplesmente nao ser avaliada.

    Tratar como TCLE seria, alem de errado, pior para o trabalhador: poria o
    consentimento dele como base legal de um tratamento que a empresa e obrigada
    a fazer, e consentimento que nao pode ser livremente recusado nao e
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


class OSiteExplicaOProcedimentoNosQuatroIdiomas(unittest.TestCase):
    """A promessa publicada e a mesma que o codigo executa.

    Determinacao do dono: detalhar no site o procedimento que garante o
    anonimato. Isso cria um espelho — a afirmacao passa a viver em cinco
    lugares (quatro paginas e o codigo) — e espelho que ninguem confere diverge
    em silencio, que e o §2.7 desta casa. Esta classe e o conferidor.
    """

    PAGINAS = {
        "": "Por que ninguém consegue saber quem respondeu o quê",
        "en/": "Why nobody can know who answered what",
        "es/": "Por qué nadie puede saber quién respondió qué",
        "fr/": "Pourquoi personne ne peut savoir qui a répondu quoi",
    }

    def _texto(self, prefixo):
        return (
            ROOT / "froid-site" / prefixo / "como-funciona-nr1.html"
        ).read_text(encoding="utf-8")

    def test_a_secao_existe_nos_quatro_idiomas(self):
        for prefixo, titulo in self.PAGINAS.items():
            with self.subTest(idioma=prefixo or "pt"):
                texto = self._texto(prefixo)
                self.assertIn(titulo, texto)
                self.assertIn('id="anonimato-das-respostas"', texto)

    def test_os_quatro_fatos_estao_em_todas_as_versoes(self):
        """Se um idioma perder um passo, a promessa fica menor naquele mercado."""
        marcas = {
            "": ("HMAC-SHA256", "piso de coorte", "no mesmo commit", "ordem judicial"),
            "en/": ("HMAC-SHA256", "cohort floor", "in the same commit", "court order"),
            "es/": ("HMAC-SHA256", "piso de cohorte", "en el mismo commit", "orden judicial"),
            "fr/": ("HMAC-SHA256", "seuil de cohorte", "dans le même commit", "décision de justice"),
        }
        for prefixo, esperadas in marcas.items():
            texto = self._texto(prefixo)
            for marca in esperadas:
                with self.subTest(idioma=prefixo or "pt", marca=marca):
                    self.assertIn(marca, texto)

    def test_o_site_tambem_admite_o_que_nao_promete(self):
        """A ressalva viaja junto com a promessa, ou a promessa vira exagero."""
        admissoes = {
            "": "sabe <strong>se</strong> você respondeu",
            "en/": "knows <strong>whether</strong> you answered",
            "es/": "sabe <strong>si</strong> usted respondió",
            "fr/": "sait donc <strong>si</strong> vous avez répondu",
        }
        for prefixo, frase in admissoes.items():
            with self.subTest(idioma=prefixo or "pt"):
                self.assertIn(frase, self._texto(prefixo))

    def test_o_que_o_site_afirma_o_codigo_executa(self):
        """Cada fato publicado amarrado ao mecanismo, e nao a prosa."""
        # 1. HMAC com chave de servidor
        self.assertIn("hmac.new(", MAIN)
        # 2. o papel da aplicacao nao le resposta
        hardening = (
            SERVER_DIR / "migrations" / "014_nr1_audit_hardening.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("REVOKE ALL ON assessment_responses FROM froid_runtime", hardening)
        # 3. o elo e rompido no fechamento
        self.assertIn("froid_nr1_sever_response_links", STORE)
        # 4. o piso de coorte mora no SQL
        dez = (
            SERVER_DIR / "migrations" / "010_nr1_psychosocial_compliance.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("clamps the cohort floor in SQL", dez)


if __name__ == "__main__":
    unittest.main()
