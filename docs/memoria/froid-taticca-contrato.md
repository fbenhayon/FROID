---
name: froid-taticca-contrato
description: "A negociação com a TATICCA — porte, datas e o número que decide o que pode ser prometido"
metadata: 
  node_type: memory
  type: project
  originSessionId: 859c6a95-1d7f-4250-b82d-325c6509e3de
  modified: 2026-08-26T02:30:33.716Z
---

Primeiro cliente NR-1 do FROID. Conta `froidtaticca@gmail.com`, organização derivada do CNPJ da TATICCA.

**Apresentação em 28/08/2026 (sexta), 9h.** Objetivo do Fábio: sair da reunião com contrato assinado e com a relação nominal dos trabalhadores para carregar.

**Porte: 250+ trabalhadores em 11 endereços.** Daí saem os dois números que mandam na conversa, e eles não são intuitivos:

- **A campanha da organização inteira precisa de 152 respostas substantivas** (250 pessoas, 95%/±5pp, correção de população finita). Conferido em `nr1_compliance.required_sample(250)`, não estimado.
- **Nenhum dos 11 endereços publica recorte próprio.** Com ~23 pessoas cada, a amostra exigida alcança o quadro inteiro — cada endereço só publicaria em censo. Isso não é falha: desde a migration 028 cada recorte reprovado vira **linha declarada insuficiente no mesmo inventário**, com o portão que falhou e o caminho de remédio. É entregável, e é a porta natural da AEP.

**Why:** prometer "relatório por filial" numa empresa com esse desenho é a promessa que quebra no fim da coleta, com o dinheiro já pago. O que se vende aqui é o retrato da organização mais a declaração honesta do que não pôde ser avaliado por endereço — que é justamente o que a fiscalização aceita e o concorrente não entrega.

**How to apply:** antes de qualquer proposta comercial, rodar `required_sample` com o efetivo real em vez de citar número de memória — foi o defeito que a migration 027 quase pôs numa planilha. Ver [[froid-nr1-corporate-module]] para a diferença entre os dois pisos e [[froid-aceite-juridico-precondicoes]] para o que precisa estar configurado antes de aceitar contrato na frente do cliente.
