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
   métodos de evidência. O piloto contém quatro métodos por unidade, todos
   identificados como simulação.
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

## Estado esperado do piloto

Ao executar `python tools/nr1_pilot_dryrun.py --create`, o comando é idempotente
e completa duas campanhas encerradas, quatro AEPs concluídas, dezesseis
evidências metodológicas, os inventários dos dois ciclos, os respectivos planos
de ação e uma revisão de eficácia para cada par comparável. O próprio relatório
confere as contagens e encerra com erro se alguma camada estiver incompleta ou
se algum risco do inventário não estiver vinculado a uma AEP.

Para a apresentação de 11/09/2026, o acesso demonstrativo foi solicitado para
`fbenhayon@gmail.com`, `froid@froid.com.br` e `froidtaticca@gmail.com.br`. O
roteiro concede a cada conta o papel `compliance_manager`, restrito ao contexto
da empresa piloto e sem leitura de prontuários ou respostas individuais.

O fechamento da reavaliação não significa que todos os riscos foram resolvidos.
As medidas cuja eficácia não foi demonstrada ficam abertas para correção no
próximo giro. Essa é a continuidade do processo prevista na NR-1, e evita usar
ausência de nova medição como prova de sucesso.

## Referências internas usadas pelo produto

- `docs/normas/primarias/guia-MTE-2025-fatores-risco-psicossociais.md`,
  especialmente o fluxo AEP, inventário, plano de ação e revisão após medidas.
- `docs/normas/primarias/manual-MTE-2026-interpretacao-cap-1.5.md`, seções de
  AEP/AET, integração com o GRO, inventário, plano de ação e eficácia.
- `.claude/skills/skill-froid-master/SKILL.md`, para os limites de privacidade,
  ausência de apuração e conteúdo que pode ser apresentado como verdade.
