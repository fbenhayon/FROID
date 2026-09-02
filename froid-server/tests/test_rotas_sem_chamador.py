"""Rota exposta e nunca chamada e funcionalidade que nao existe.

A GENERALIZACAO DO DEFEITO DE 26/08/2026.

Naquele dia tres defeitos diferentes tinham a mesma forma: um sinal existia,
completo e correto, e nada do outro lado o consumia.

  - o servidor emitia `peer-waiting` desde 22/07 e nenhum cliente lia
  - o servidor registrava `patient_joined` e publicava em /api/session-events,
    e a tela da sessao ao vivo — o unico lugar onde isso decide algo — nao lia
  - tres endpoints do NR-1 (criar campanha, abrir coleta, emitir convites)
    existiam desde a migration 010 sem nenhuma tela chamando, e a coleta so
    comecava com alguem operando o banco a mao

Nenhum deles da erro. Nenhum aparece em log. Nenhum quebra build. O codigo esta
la, bem escrito e testado; ele so nao e alcancado. O sintoma nasce longe: numa
consulta que nao conecta, ou numa venda que precisa de "configuracao conduzida
pela equipe".

`test_contrato_da_sinalizacao` faz essa pergunta para o canal de WebSocket.
Este arquivo faz para o HTTP: toda rota exposta precisa de um chamador no
frontend, ou de uma linha aqui dizendo por que nao tem.

O VALOR DA LISTA EXPLICITA

A lista abaixo nao e uma supressao — e o inventario do que e alcancado por
fora do painel. Webhook do Stripe, callback do Google e endpoint de
desenvolvimento sao chamados por terceiros e nunca terao chamador aqui.
`/session/create` e outra coisa: e codigo morto, e esta declarado como tal para
que a proxima pessoa que o encontre nao gaste o tempo que eu gastei.
"""

import re
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO = SERVER_DIR.parent
MAIN = (SERVER_DIR / "main.py").read_text(encoding="utf-8")

# Rotas legitimamente sem chamador no frontend. Cada uma com o motivo, porque
# lista de excecao sem motivo vira lixeira.
SEM_CHAMADOR_POR_DESENHO = {
    # Chamadas por terceiros, nunca pelo painel.
    "/api/stripe/webhook": "webhook do Stripe, servidor-a-servidor",
    "/api/google-calendar/callback": "callback OAuth do Google",
    "/api/auth/google-dev": "atalho de desenvolvimento local",
    "/api/organization-invitations/accept": "aberto por link de e-mail",
    # Consumidas por outra rota do proprio servidor.
    "/api/insights": "proxy interno de IA, chamado pelo backend",
    "/api/knowledge": "ingestao operada por ferramenta em tools/",
    "/api/copilot/query": "assistente operado por ferramenta interna",
    # Chamadas por caminho MONTADO, que a varredura nao enxerga.
    #
    # ControleDeAcesso.tsx faz `apiUrl(`/api/admin/access/${rota}`)`, com
    # `rota` em {membership, organization, user}. As tres sao chamadas de
    # verdade — o controle foi testado em producao em 02/09/2026 — mas o
    # detector procura o caminho literal e um template nao produz literal.
    #
    # Sao declaradas aqui e nao na divida conhecida porque nao falta tela:
    # a tela existe e funciona. O que falta e o detector saber ler template,
    # e ensina-lo a isso deixaria a varredura frouxa para os casos reais.
    "/api/admin/access/membership": "chamada por caminho montado em ControleDeAcesso.tsx",
    "/api/admin/access/organization": "chamada por caminho montado em ControleDeAcesso.tsx",
    "/api/admin/access/user": "chamada por caminho montado em ControleDeAcesso.tsx",
    # CODIGO MORTO, declarado. A sessao nasce de POST /api/session-invites,
    # que e quem grava SESSION_OWNERS. /session/create faz a mesma coisa e
    # ninguem o chama desde que o painel passou a gerar o id no cliente.
    "/session/create": "codigo morto — ver POST /api/session-invites",
}

# Rotas cuja ausencia de chamador e DIVIDA CONHECIDA, com data. Diferente da
# lista acima: estas deveriam ter tela e nao tem. Ficam aqui para que o numero
# nao cresca em silencio — acrescentar uma linha e uma decisao visivel.
DIVIDA_CONHECIDA = {
    "/api/access/plans": "26/08/2026 — catalogo de planos sem tela propria",
    "/api/billing/checkout": "26/08/2026 — fluxo de compra passa por outra rota",
    "/api/billing/confirm-checkout": "26/08/2026 — idem",
    "/api/subscriptions/current": "26/08/2026 — assinatura lida por outro caminho",
    "/api/organizations/{organization_id}/wallet": "26/08/2026 — carteira sem tela",
    "/api/organizations/{organization_id}/wallet/activate": "26/08/2026 — idem",
    "/api/organizations/{organization_id}/audit-events": (
        "26/08/2026 — auditoria por organizacao sem tela; existe painel de "
        "privacidade, nao de auditoria"
    ),
    "/api/organizations/{organization_id}/members/{membership_id}": (
        "26/08/2026 — edicao de membro sem tela"
    ),
    "/api/organizations/{organization_id}/privacy-requests/{request_id}": (
        "26/08/2026 — detalhe de pedido sem tela"
    ),
}


def _rotas_expostas() -> set:
    return {
        achado.group(2)
        for achado in re.finditer(
            r'@app\.(get|post|patch|put|delete)\("([^"]+)"', MAIN
        )
    }


def _fonte_do_frontend() -> str:
    partes = []
    for raiz in (REPO / "froid-dashboard" / "src", REPO / "froid-site"):
        if not raiz.exists():
            continue
        for caminho in raiz.rglob("*"):
            if not caminho.is_file():
                continue
            # Arquivo de teste NAO e chamador. Sem esta linha a varredura se
            # contradiz: `expect(CODIGO).not.toContain("/api/copilot/query")` —
            # uma assercao de que a rota nao e chamada — contava como prova de
            # que ela e chamada, e a rota orfa desaparecia da lista por causa
            # do teste que denuncia a orfandade.
            if caminho.name.endswith((".test.ts", ".test.tsx")):
                continue
            if caminho.suffix not in {".ts", ".tsx", ".html"}:
                continue
            if "node_modules" in caminho.parts:
                continue
            partes.append(caminho.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(partes)


FRONTEND = _fonte_do_frontend()


def _tem_chamador(rota: str) -> bool:
    """Procura o sufixo estavel da rota no fonte do frontend.

    O caminho e montado com template no cliente
    (`/api/organizations/${id}/nr1/units`), entao a rota inteira nunca aparece
    literalmente. O que aparece e o trecho depois do ultimo parametro.
    """
    cauda = rota.split("}")[-1] if "}" in rota else rota
    alvo = cauda.strip("/")
    if len(alvo) < 4:
        partes = [p for p in rota.split("/") if p and not p.startswith("{")]
        alvo = "/".join(partes[-2:])
    return alvo in FRONTEND


class TodaRotaTemChamador(unittest.TestCase):
    def test_a_varredura_enxerga_o_servidor_e_o_painel(self):
        """Varredura que nao le nada nunca e varredura que funciona."""
        self.assertGreater(len(_rotas_expostas()), 80)
        self.assertGreater(len(FRONTEND), 100_000)

    def test_a_varredura_confirma_uma_rota_que_sabidamente_tem_chamador(self):
        # Controle positivo: se este parar de passar, a heuristica quebrou e as
        # ausencias abaixo viram falso positivo.
        self.assertTrue(_tem_chamador("/api/organizations/{organization_id}/nr1/units"))
        self.assertTrue(_tem_chamador("/api/session-events"))

    def test_nenhuma_rota_orfa_fora_das_listas(self):
        orfas = {
            rota for rota in _rotas_expostas() if not _tem_chamador(rota)
        }
        nao_declaradas = sorted(
            orfas - set(SEM_CHAMADOR_POR_DESENHO) - set(DIVIDA_CONHECIDA)
        )
        self.assertEqual(
            nao_declaradas,
            [],
            "rota exposta sem chamador e sem declaracao: "
            f"{nao_declaradas}. Ou existe uma tela que a chama, ou ela e "
            "funcionalidade que nao existe. Acrescente a SEM_CHAMADOR_POR_DESENHO "
            "com o motivo, ou a DIVIDA_CONHECIDA com a data — nunca em silencio.",
        )

    def test_as_listas_nao_guardam_rota_que_ja_tem_chamador(self):
        """Excecao que deixou de ser necessaria precisa sair da lista.

        Lista de excecao que envelhece perde o poder de acusar: quem a le passa
        a assumir que tudo ali e intencional.
        """
        obsoletas = sorted(
            rota
            for rota in set(SEM_CHAMADOR_POR_DESENHO) | set(DIVIDA_CONHECIDA)
            if rota in _rotas_expostas() and _tem_chamador(rota)
        )
        self.assertEqual(
            obsoletas,
            [],
            f"rota declarada como sem chamador que hoje tem um: {obsoletas}",
        )

    def test_as_listas_nao_guardam_rota_que_deixou_de_existir(self):
        fantasmas = sorted(
            rota
            for rota in set(SEM_CHAMADOR_POR_DESENHO) | set(DIVIDA_CONHECIDA)
            if rota not in _rotas_expostas()
        )
        self.assertEqual(fantasmas, [], f"rota declarada que nao existe mais: {fantasmas}")

    def test_a_divida_conhecida_nao_cresce_sozinha(self):
        """Um numero, para que aumenta-lo seja um ato e nao um acidente."""
        self.assertLessEqual(
            len(DIVIDA_CONHECIDA),
            9,
            "a divida de rotas sem tela aumentou. Isso pode ser correto — mas "
            "precisa ser uma decisao, e nao o resultado de um endpoint escrito "
            "sem a tela que o usa.",
        )


if __name__ == "__main__":
    unittest.main()
