"""Leitura de Governança: quem pode contratar, numa fonte só.

Leitura de Governança é o nome comercial (adotado pelo dono em 26/11/2026) da
avaliação NR-1 por FUNÇÃO: a liderança lida como um grupo de exposição similar
que atravessa os estabelecimentos ("Gerentes de loja" das 40 lojas), com o
resultado lançado no inventário de cada estabelecimento coberto (migration 059).

POR QUE ESTES DOIS NÚMEROS
--------------------------
Nenhum dos dois é palpite; cada um sai de uma regra que já existe:

* PESSOAS_NA_FUNCAO_MINIMAS = 40. Abaixo disso a função não deve ser lida
  sozinha. O piso de anonimato (10 por recorte) até seria atingido, mas a regra
  de representatividade do FROID (margem de 5 pontos, censo acima de 80% do
  grupo) exige censo em todo grupo de até 97 pessoas. Com menos de 40, uma ou
  duas ausências já impedem a publicação, e o ruído que protegeria o indivíduo
  apagaria o resultado. Decisão registrada no documento aos sócios de
  26/11/2026 ("a leitura horizontal só é oferecida para camadas com 40 pessoas
  ou mais").

* ESTABELECIMENTOS_MINIMOS = 20. É o menor número de unidades em que uma
  camada de liderança de loja chega a 40 pessoas: gerente e subgerente juntos,
  dois por unidade. Com menos endereços, nenhuma função típica de rede chega ao
  mínimo acima.

O que NÃO existe aqui: mínimo de trabalhadores totais. O efetivo total não diz
se uma função de liderança chega a 40 pessoas — uma empresa de 5.000 pessoas
num único endereço não tem camada nenhuma para atravessar. A condição real é a
das 40 pessoas na mesma função, e ela só se confirma com o cadastro, na
ativação (simulação antes de abrir a campanha).

Toda cópia destes números (site em quatro idiomas, proposta, kit) é conferida
contra este módulo em tests/test_leitura_governanca_espelhos.py.
"""

from __future__ import annotations

NOME = "Leitura de Governança"
ESTABELECIMENTOS_MINIMOS = 20
PESSOAS_NA_FUNCAO_MINIMAS = 40


def pode_oferecer(estabelecimentos: int | None) -> bool:
    """A proposta pode apresentar o adicional a esta empresa?

    Só o número de estabelecimentos é conhecido no pedido do kit. Ele é
    condição necessária, não suficiente: as 40 pessoas na mesma função se
    confirmam na ativação, e a proposta diz isso.
    """
    try:
        return int(estabelecimentos or 0) >= ESTABELECIMENTOS_MINIMOS
    except (TypeError, ValueError):
        return False
