# FROID Psique — custos e créditos de atendimento

Decisão do proprietário em 24/09/2026:
- Encerrar a oferta de desconto de pioneiro nas novas ofertas.
- Usar **créditos de atendimento** como unidade comercial.
- Avaliar novos valores antes de alterar o catálogo de cobrança.

## Planilha

Arquivo: [FROID_Psique_Custos_Creditos_Atendimento.xlsx](../../FROID_Psique_Custos_Creditos_Atendimento.xlsx)

Gerador: [tools/gerar-custos-psique.py](../../tools/gerar-custos-psique.py)
Requer Python e openpyxl. Executar da raiz:
```
python tools/gerar-custos-psique.py
```

O gerador recria o modelo vazio; para preservar entradas, trabalhe numa cópia.
As referências de pacotes são lidas do catálogo do servidor e da página de preços.
A divergência MASTER fica identificada, sem alteração de preço ou de crédito.
A planilha não contém dados clínicos, credenciais ou informações de clientes.

Abas: Guia, Premissas, Referencias, IA, Fixos, Variaveis, Resultado, Pacotes e Cenarios.

## Apuração e limites

Os valores de faturas, uso de APIs, rateio entre produtos, volume de atendimentos,
câmbio, tributos e margem ainda não foram fornecidos. As entradas estão vazias.
Resultados dependentes permanecem **Sem Capacidade de Apuração**.
Tarifas públicas de OpenAI e Stripe são referências com fonte e data, não gastos medidos.

O cálculo inclui atendimentos gratuitos. A taxa fixa do pagamento é distribuída
pelos créditos do pacote. O modelo considera consumo integral dos pacotes e
equilíbrio mensal; não é um fluxo de caixa de compras antecipadas. O custo da
estrutura inclui a ociosidade. Crescimento que exige mais infraestrutura demanda
revisão do orçamento.

As fórmulas foram verificadas com casos de ausência, zero confirmado,
exclusão documentada, câmbio/rateio, gratuitos, taxa por pacote, margem inviável
e ausência de créditos pagos. Dados de teste existem apenas em memória;
não são salvos na planilha entregue. O arquivo guarda cache calculado e solicita
recálculo ao abrir no Excel.

## Oferta de pioneiro

Oferta removida da página vigente e do modelo de proposta.
O simulador NR-1 passa a iniciar sem desconto (0%).
A proposta datada de 28/08/2026 enviada à TATICCA é registro histórico:
não foi reescrita para aparentar que a condição nunca foi oferecida.
A cortesia de entrada é outra política e foi mantida.

## Publicação e cobrança

A mudança de nomenclatura é de apresentação comercial: página de preços,
pacotes, compra, cadastro e avisos de saldo. Sessão permanece o nome do evento
clínico e as chaves técnicas das APIs permanecem compatíveis.
Não foram alterados preços, quantidades, chaves Stripe, condições de contratos
já aceitos nem exigência de assinatura.
