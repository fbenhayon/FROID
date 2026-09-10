# Road map da demonstração FROID NR-1 / ISO 45003

Este roteiro apresenta o ciclo operacional completo do produto. A organização
`FROID NR-1 Piloto 01 — DADOS SIMULADOS` e todos os seus documentos são
demonstrativos, não contêm dados de pessoas reais e não têm validade documental.

## Sequência para a apresentação

1. **Estruturar a empresa.** Conferir estabelecimentos, setores e efetivos em
   **Estrutura da empresa**. Esses dados definem os recortes e o denominador da
   representatividade.
2. **Preparar a AEP.** Em **AEP**, mostrar a descrição da atividade real, a
   caracterização da exposição, os indicadores disponíveis, o responsável e os
   métodos de evidência. Cada grupo de exposição contém questionário,
   observação da atividade, diálogo com trabalhadores, análise documental,
   oficina moderada e manifestação da representação dos trabalhadores.
3. **Executar a linha de base.** Em **Campanha e convites**, abrir a campanha,
   distribuir os convites, acompanhar adesão e encerrar a coleta. Nenhum
   resultado é liberado enquanto a campanha está aberta.
4. **Apurar os riscos.** No **Painel de conformidade**, explicar os dois portões:
   representatividade do efetivo e proteção contra recortes pequenos. A
   classificação usa somente resultados agregados.
5. **Documentar o PGR.** Gerar e abrir o **Inventário**. Cada risco do piloto
   está vinculado à AEP da mesma unidade e do mesmo ciclo. A geração também cria
   as linhas do **Plano de ação**, o segundo documento mínimo do PGR.
6. **Programar e implementar medidas.** No **Plano de ação**, apresentar a
   prioridade, o tipo da medida, o responsável, o prazo, o acompanhamento e a
   forma de aferir o resultado. No piloto, os registros da linha de base são
   explicitamente fictícios.
7. **Reavaliar após a implementação.** A segunda campanha repete os mesmos
   recortes e instrumento. Ela não substitui a linha de base: forma o par de
   comparação.
8. **Comprovar a eficácia.** Em **Eficácia das medidas**, comparar linha de base
   e reavaliação por unidade e dimensão. Mudança menor que o ruído é declarada
   sem mudança; piora ou eficácia insuficiente abre correção no plano do próximo
   giro.
9. **Consolidar o dossiê.** Em **Dossiê de evidências**, conferir a prontidão,
   registrar uma versão imutável e exportar PDF e JSON. O SHA-256 detecta
   alteração do conteúdo; cada versão guarda também o hash da anterior.

## Cenário empresarial e decisões que o piloto demonstra

O caso representa uma rede com 1.084 farmácias em São Paulo, Rio de Janeiro,
Minas Gerais, Paraná, Santa Catarina, Goiás e Bahia. A avaliação acompanha 450
participantes distribuídos em três grupos de exposição:

- atendimento e operação de lojas, com 240 participantes;
- logística e centros de distribuição, com 120 participantes;
- comércio digital e televendas, com 90 participantes.

Na operação de lojas, a linha de base localiza excesso de demandas e eventos
violentos. A reavaliação verifica fila própria para retirada digital, cobertura
regional, pausas e protocolo de segurança, mantendo a aplicação desigual em
lojas 24 horas como pendência. Na logística, prioridade conflitante, passagem
de turno e capacidade das ondas orientam as medidas; comunicação melhora e
sobrecarga permanece em acompanhamento. No comércio digital, novas alçadas
melhoram a autonomia, enquanto o ranking nominal introduz risco de assédio. O
ciclo registra simultaneamente a melhora e a piora, abre correção e impede que
a reavaliação seja apresentada como sucesso automático.

## Estado esperado do piloto

Ao executar `python tools/nr1_pilot_dryrun.py --create`, o comando recompõe de
forma idempotente os dados operacionais e completa duas campanhas encerradas,
seis AEPs concluídas, 36 evidências
metodológicas, 18 registros de participação e comunicação, os inventários dos
dois ciclos, os respectivos planos de ação e uma revisão de eficácia para cada
par comparável. Depois do commit da carga, o comando registra a versão do
dossiê com seu SHA-256. O próprio relatório confere as contagens e encerra com
erro se alguma camada estiver incompleta ou se algum risco do inventário não
estiver vinculado a uma AEP.

Para a apresentação de 11/09/2026, o acesso demonstrativo foi solicitado para
`fbenhayon@gmail.com`, `froid@froid.com.br` e `froidtaticca@gmail.com.br`. O
roteiro concede a cada conta o papel `compliance_manager`, restrito ao contexto
da empresa piloto e sem leitura de prontuários ou respostas individuais.

O fechamento da reavaliação não significa que todos os riscos foram resolvidos.
As medidas cuja eficácia não foi demonstrada ficam abertas para correção no
próximo giro. Essa é a continuidade do processo prevista na NR-1, e evita usar
ausência de nova medição como prova de sucesso.

## Como responder a uma fiscalização ou requisição

1. Registre quem solicitou, número do expediente, escopo, prazo e responsável
   interno. A fiscalização direta das normas de segurança e saúde do trabalho
   cabe à Inspeção do Trabalho, no MTE; demandas coletivas também podem chegar
   pelo Ministério Público do Trabalho. A menção genérica a “MPF” deve ser
   confirmada no documento recebido, pois MPF e MPT são ramos distintos.
2. Abra o dossiê, resolva todos os itens apontados como lacuna e registre uma
   nova versão. Não tente completar ausência com zero ou afirmação sem fonte.
3. Exporte PDF e JSON da mesma versão. Confira se o SHA-256 exibido é o mesmo
   do registro. O JSON contém os registros detalhados; o PDF serve à leitura e
   à assinatura.
4. Apresente a cadeia na ordem: estrutura e efetivos; critérios do GRO; AEP e
   evidências; participação; campanhas e proteção da coleta; inventário; plano
   com responsável e prazo; implementação; reavaliação; eficácia e correções.
5. Se a política jurídica exigir assinatura eletrônica, aplique ao PDF uma
   assinatura qualificada ICP-Brasil. O hash interno prova integridade do
   conteúdo guardado, mas não é, sozinho, assinatura digital do responsável.
6. Entregue apenas o escopo solicitado, registre o recibo ou protocolo no
   expediente da organização e preserve os arquivos enviados. Nenhuma resposta
   individual deve acompanhar a entrega.

O MTE aceita o PGR em meio físico ou digital e não estabelece um único modelo
de comprovação. Por isso o dossiê organiza a evidência existente e sua cadeia;
ele não cria uma declaração automática de conformidade nem substitui a revisão
do responsável pelo GRO, do profissional competente ou da assessoria jurídica.

## Referências internas usadas pelo produto

- `docs/normas/primarias/guia-MTE-2025-fatores-risco-psicossociais.md`,
  especialmente o fluxo AEP, inventário, plano de ação e revisão após medidas.
- `docs/normas/primarias/manual-MTE-2026-interpretacao-cap-1.5.md`, seções de
  AEP/AET, integração com o GRO, inventário, plano de ação e eficácia.
- `.claude/skills/skill-froid-master/SKILL.md`, para os limites de privacidade,
  ausência de apuração e conteúdo que pode ser apresentado como verdade.
