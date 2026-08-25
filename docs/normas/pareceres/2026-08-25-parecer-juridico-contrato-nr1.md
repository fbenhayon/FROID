# Parecer jurídico sobre o contrato do FROID NR-1

**Origem:** assessoria jurídica do FROID, entregue por Fábio em 25/08/2026.
**Objeto:** revisão do contrato de prestação de serviços do FROID NR-1 à luz da
NR-1 com a redação da Portaria MTE nº 1.419/2024 e das orientações oficiais do
MTE disponíveis em 2026.

> **Isto não é fonte normativa.** É parecer de advogado sobre um contrato nosso.
> Não citar a cliente ou a auditor como se fosse norma. As fontes citáveis estão
> em `../primarias/`. Guardado aqui porque várias recomendações viraram exigência
> de produto, e a rastreabilidade de *por que* o algoritmo faz o que faz importa
> tanto quanto o que ele faz.

## Conclusão do parecer

A arquitetura jurídica é boa e em vários pontos está acima da média do mercado,
**mas o contrato não deveria ir a produção como estava**. O ponto central:

> o contrato pode sustentar legitimamente que o FROID é uma ferramenta utilizada
> pela organização dentro do GRO/PGR, mas **não deve transmitir a ideia de que a
> aplicação do questionário e a geração automática dos documentos, por si sós,
> "cumprirão a NR-1 e a NR-17"** em qualquer empresa e em qualquer situação.

Recomendação estrutural: posicionar o FROID como *instrumento técnico documentado
de identificação, avaliação, classificação, integração à AEP e apoio ao PGR*,
**com critérios de escalonamento para investigação adicional** — e não como
substituto universal da análise técnica da organização.

## O que o parecer considerou correto

Foco na condição de trabalho e não na pessoa; inserção no GRO/PGR; preservação da
responsabilidade da empregadora; classificação dos riscos; documento de critérios
(apontado como um dos pontos mais fortes); inventário; plano de ação; proteção
contra individualização; revisão periódica; guarda do histórico.

Sobre os pisos de coorte: *"juridicamente uma boa solução"* — a afirmação de que
a NR-1 não prescreve taxa de resposta nem tamanho mínimo de coorte está correta
em essência, e os pisos podem ser regra metodológica do FROID.

## Prioridade alta — cinco pontos

| # | ponto | o que muda |
|---|---|---|
| 1 | "não pode obter por outro caminho" | redação absoluta demais; restringir ao ambiente e aos dados provenientes do FROID. A empresa **pode** legitimamente receber dado individual por relato espontâneo, denúncia, investigação de acidente, processo, ordem judicial ou atendimento ocupacional |
| 2 | "eficácia aferida pela campanha seguinte" | categórico demais; a campanha subsequente é **uma** das evidências, não a única. 1.5.5.3.2 exige acompanhamento planejado com verificação de execução, monitoramento e participação dos trabalhadores |
| 3 | limites do questionário | explicitar gatilho de complementação/AET; questionário não equivale à AEP inteira |
| 4 | responsabilidade | a permanência da responsabilidade regulatória da contratante **não exclui** a responsabilidade contratual e civil do fornecedor por erro técnico, cálculo errado, setor omitido, documento perdido ou resposta individual revelada |
| 5 | LGPD | uma cláusula só é insuficiente; falta Anexo de Tratamento de Dados (DPA) completo |

## Prioridade média

Canal de apoio como requisito **metodológico do FROID**, não regulatório;
distinguir retenção do inventário (20 anos) da retenção de resposta bruta;
distinguir medida *sugerida* de medida *adotada*; propriedade intelectual dos
documentos (licença perpétua em vez de "são dela"); versão de metodologia por
ciclo; baixa adesão; responsabilidade por cadastro errado de setor/efetivo.

## Observações que viraram requisito de produto

**Sobre os pisos (item 11).** *"Um piso de 5, 7 ou 10 indivíduos pode reduzir
risco de identificação, mas isso não significa automaticamente que determinada
amostra seja estatisticamente representativa. São problemas diferentes. O
documento metodológico deveria dizer qual piso serve a qual finalidade."* —
Já implementado: `cohort_floors` separa anonimato de representatividade.

**Sobre afirmações técnicas absolutas (item 13).** *"as tabelas de resposta não
são legíveis pela aplicação"* vira garantia contratual de arquitetura. Se
qualquer rotina de manutenção, backup, subprocessador ou console de banco puder
acessar, a frase se revela falsa. Preferir obrigações verificáveis. — Ver
cláusula 19.3 do contrato novo, que faz exatamente essa ressalva.

**Sobre o algoritmo (item 5).** *"um algoritmo que transforme exclusivamente
percentual de respostas em 'baixo/médio/alto', sem demonstrar como isso se
relaciona com aquelas variáveis normativas, seria vulnerável."* — O FROID não
faz isso: severidade vem da magnitude da consequência (1.5.4.4.4.1) e
probabilidade das exigências da atividade mais a eficácia das medidas
(1.5.4.4.5.3). Continua sendo o ponto a defender em qualquer perícia.

**Sobre o dossiê de evidências (item 25).** Não basta "resultado = risco médio".
O sistema deve demonstrar depois: *o que foi identificado → como → quem estava
potencialmente exposto → qual metodologia → quais critérios levaram à
classificação → quais medidas foram decididas → quando foram implementadas →
como foram acompanhadas → qual foi o risco residual.* É esse encadeamento que
torna o PGR defensável numa perícia anos depois.

## Item 15 — FROID Psique e indução comercial

O parecer recomenda regra expressa de que o diagnóstico de risco psicossocial e a
recomendação de medidas organizacionais **não poderão favorecer indevidamente a
contratação do FROID Psique quando medidas de prevenção na fonte forem mais
apropriadas**, porque a hierarquia preventiva privilegia atuação sobre o risco:
sobrecarga, metas impossíveis, subdimensionamento e jornada excessiva não se
"tratam" oferecendo psicoterapia.

Também corrige a justificativa do canal de apoio. A frase antiga — *"perguntar a
alguém como ele está sem ter para onde encaminhá-lo"* — **contradiz o fundamento
do produto**, que é não perguntar como o trabalhador está, e sim sobre condições
de trabalho. Substituída por: *"considerando que a avaliação pode revelar ou
provocar relatos de sofrimento, violência, assédio ou outras circunstâncias que
demandem acolhimento"*.

Decisão do FROID em 25/08/2026: **acatada integralmente.** Ver a análise em
[[froid-nr1-posicionamento-escalonado]] — a regra não fecha o funil do Psique, ela
o move de empurrão algorítmico para escolha declarada da contratante (o canal de
apoio é requisito de abertura de campanha, e o Psique pode ser escolhido para
esse papel). O que ela protege é a independência técnica, que é o ativo do
produto.
