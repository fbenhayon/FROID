# -*- coding: utf-8 -*-
"""Gera a secao "Inscricao Profissional Gratuita" em toda pagina do FROID Psique.

Pedido do dono, 10/11/2026: a inscricao gratuita deve estar presente na
pagina das 10 habilidades, na pagina inicial do Psique "e todos os outros",
para o profissional poder, a qualquer momento, se cadastrar e receber as
sessoes gratuitas.

    python tools/gerar-inscricao-psique.py            # regera
    python tools/gerar-inscricao-psique.py --conferir # so acusa divergencia

Por que um gerador: a mesma secao escrita a mao em treze paginas e treze
copias, e copia diverge em silencio (skill-froid-master, 2.7). O bloco abaixo
e a fonte; o HTML e resultado. Ele entra antes do </main> de cada pagina de
froid-site/psique/ (pt-BR), menos os redirecionamentos.

O que a secao NAO tem, e por que: ate esta data a pagina inicial tinha um
formulario (nome, e-mail, CRP/CRM, telefone, abordagem, modalidade) que
DESCARTAVA tudo e mandava para /cadastro, onde a pessoa digitava de novo; e,
abaixo dele, um "voucher" simulado ("Parabens! Suas 10 Sessoes Foram
Liberadas", codigo aleatorio, "mensagem enviada para o seu e-mail e
WhatsApp") que nada enviava. O cadastro real (ProfessionalOnboarding.tsx) e
quem pede o registro profissional e quem concede o teste. A secao leva ate
ele, sem pedir dado que nao vai a lugar nenhum.

O numero de sessoes e de dias e o do catalogo (psique_pricing.py) e e
trocado ao vivo por site-assets/inscricao-psique.js; o teste
froid-server/tests/test_inscricao_psique.py confere o texto escrito.
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PSIQUE = os.path.join(REPO, "froid-site", "psique")
STUB = "<!-- redirecionamento: pagina movida em 09/11/2026 -->"
INICIO = "<!-- inscricao gratuita: gerado por tools/gerar-inscricao-psique.py -->"
FIM = "<!-- /inscricao gratuita -->"
GERADO = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIM) + r"(?:\r?\n)?", re.S)
MAIN_FIM = re.compile(r"[ \t]*</main>")

BLOCO = INICIO + """
<section class="section-block" id="resgate-bonificacao">
  <div class="claim-form-box" style="text-align: center;">
    <span class="badge-amber-pill">Inscrição Profissional Gratuita</span>
    <h2 class="section-title-amber" style="margin-top: 0.5rem; font-size: 1.85rem;">Ative suas <span class="teste-qtd">10</span> sessões clínicas gratuitas</h2>
    <p style="color: var(--on-surface-variant); font-size: 1rem; max-width: 580px; margin: 0 auto var(--space-md);">Todo profissional cadastrado recebe <strong class="teste-condicoes">10 sessões gratuitas, válidas por 14 dias</strong>, sem cartão de crédito e sem compromisso. No cadastro você informa seus dados profissionais e o registro no conselho (CRP ou CRM).</p>
    <div style="display: flex; justify-content: center; gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-lg);">
      <a class="btn btn-amber" href="https://www.froid.com.br/cadastro" style="font-size: 1rem; padding: 0.9rem 1.4rem;">Cadastrar e ativar minhas sessões gratuitas</a>
      <a class="btn btn-secondary" href="https://www.froid.com.br/app/#/login">Já tenho conta: entrar</a>
    </div>
    <p style="font-size: 0.82rem; color: var(--on-surface-variant); margin: var(--space-lg) auto 0; max-width: 580px;">O teste vale uma vez por conta. Ferramenta de apoio à escuta clínica: não substitui avaliação, diagnóstico ou julgamento profissional.</p>
  </div>
</section>
<script src="../site-assets/inscricao-psique.js?v=1"></script>
""" + FIM + "\n"


def paginas():
    for nome in sorted(os.listdir(PSIQUE)):
        if not nome.endswith(".html"):
            continue
        caminho = os.path.join(PSIQUE, nome)
        texto = io.open(caminho, encoding="utf-8", newline="").read()
        if STUB in texto:
            continue
        yield nome, caminho, texto


def aplicar(texto):
    nl = "\r\n" if "\r\n" in texto else "\n"
    bloco = BLOCO.replace("\n", nl)
    if INICIO in texto:
        return GERADO.sub(lambda _m: bloco, texto, count=1)
    m = MAIN_FIM.search(texto)
    if not m:
        raise SystemExit("sem </main>: nao sei onde pôr a secao")
    if 'id="resgate-bonificacao"' in texto:
        raise SystemExit("ja existe outro id=resgate-bonificacao: retire a secao antiga antes")
    return texto[:m.start()] + bloco + nl + texto[m.start():]


def main():
    conferir = "--conferir" in sys.argv
    divergentes = []
    for nome, caminho, texto in paginas():
        novo = aplicar(texto)
        if novo != texto:
            divergentes.append(nome)
            if not conferir:
                io.open(caminho, "w", encoding="utf-8", newline="").write(novo)
    acao = "divergem" if conferir else "atualizadas"
    print("%s: %s" % (acao, ", ".join(divergentes) or "nenhuma"))
    return 1 if conferir and divergentes else 0


if __name__ == "__main__":
    sys.exit(main())
