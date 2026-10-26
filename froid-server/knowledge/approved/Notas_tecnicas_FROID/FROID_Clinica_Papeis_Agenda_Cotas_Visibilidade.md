# Clinica no FROID Psique: papeis, agenda, cotas, visibilidade e o carimbo Solo ou Clinica

Nota de procedimento. Descreve o que o painel faz HOJE para uma clinica com
mais de um profissional, como esta no codigo publicado em outubro de 2026.
Cada afirmacao aqui corresponde a uma tela ou a uma regra do servidor; o que
nao esta aqui, o painel nao faz. Quando o profissional perguntar "como eu
faco", a resposta e o passo desta nota, nao uma suposicao.

## Autonomo e clinica: a organizacao ativa

Todo profissional tem uma organizacao propria, do tipo "solo", criada a partir
do e-mail dele. Ele pode, alem disso, ser membro de uma ou mais clinicas. A
cada momento UMA organizacao esta ativa na sessao de trabalho, e e ela que
carimba o convite de sessao e o relatorio arquivado. Por isso:

- Pacientes atendidos com a organizacao solo ativa sao pacientes proprios do
  profissional; pacientes atendidos com a clinica ativa pertencem ao acervo da
  clinica.
- A autoria vence: o profissional ve o que ele mesmo escreveu em qualquer
  organizacao ativa. A clinica so ve o que foi carimbado com a organizacao
  dela.
- No painel, cada paciente traz um carimbo por organizacao em que teve sessao:
  "Solo", o nome da clinica, ou "Clinica 2" quando a clinica nao tem nome.
  Relatorio anterior a esse registro mostra "Sem carimbo (sessao anterior ao
  registro)"; a ausencia e declarada, nunca vira "Solo" por suposicao.
- Atencao do profissional: a separacao depende de a organizacao certa estar
  ativa quando o convite e criado. Atender um paciente da clinica com a
  organizacao solo ativa deixa a sessao no acervo pessoal, e a clinica nao a ve.

## Papeis da clinica (versao 1, a que todo painel usa)

| Papel | Pacientes e relatorios | Atribuicoes | Cotas e visibilidade | Membros |
|---|---|---|---|---|
| owner e administrator | todos da clinica | gerencia | gerencia | gerencia |
| supervisor | todos da clinica | gerencia | nao | nao |
| professional | os proprios e os atribuidos a ele | nao | le a propria cota | nao |
| auditor | nenhum clinico; auditoria e privacidade | nao | nao | nao |

Nao existe "grupo" de profissionais. O compartilhamento e por paciente: cada
paciente pode ter um profissional primario, membros de equipe (care team), um
supervisor e leitores. Owner, administrator e supervisor gerenciam essas
atribuicoes.

## Visibilidade dos relatorios

A clinica tem uma chave unica, "restrita" ou "toda a clinica", mudada por
owner ou administrator em Gestao da clinica. O padrao e "restrita".

- Restrita: o profissional ve os relatorios proprios e os dos pacientes
  atribuidos a ele.
- Toda a clinica: todo profissional ve todos os relatorios da organizacao.

## Cotas de sessao por profissional

A clinica compra creditos num saldo unico (carteira compartilhada). O
responsavel (owner ou administrator) pode atribuir a um profissional um limite
de sessoes, em Gestao da clinica, na tabela "Profissionais, uso e cotas". A
regra, decidida pelo dono em 18/10/2026:

- A sessao de um profissional so e recusada por DOIS motivos: o limite
  atribuido a ele foi atingido, ou os creditos da clinica se esgotaram.
- Sem limite atribuido, o profissional consome do saldo da clinica livremente.
- O limite barra no INICIO da sessao: ao criar o convite, o painel mostra "O
  limite de sessoes atribuido a voce nesta clinica foi atingido. Peca ao
  responsavel pela clinica para ampliar a sua cota." A cobranca, que acontece
  ao arquivar o relatorio, conta a sessao na cota e nunca recusa um
  atendimento ja realizado: se duas sessoes comecaram com uma vaga so, ou
  se o limite foi reduzido depois, a sessao que aconteceu conta e debita
  mesmo acima da cota (decisao do dono, 20/10/2026), e o portao de inicio
  barra a seguinte.
- Uma sessao realizada sem saldo na clinica fica pendente e e liquidada quando
  entram creditos; ela conta na cota do profissional, porque aconteceu.

## Papeis V2 e a agenda da clinica

A agenda interna da clinica funciona sobre os papeis V2. Eles existem em
paralelo aos papeis da versao 1 e governam a agenda:

| Papel V2 | O que pode na agenda |
|---|---|
| Clinico (CLINICIAN) | tem agenda propria; marca, reagenda e cancela os proprios atendimentos; define a propria disponibilidade; ve o nome dos SEUS pacientes (atribuidos a ele ou com atendimento dele) e os demais por identificador curto |
| Secretaria (SECRETARY) | marca, reagenda e cancela para qualquer clinico; ve o nome dos pacientes |
| Supervisor clinico (CLINICAL_SUPERVISOR) | ve a agenda inteira e marca, reagenda e cancela para os profissionais; NAO ve o nome dos pacientes, so um identificador curto |
| Administracao (ORG_ADMIN) | tudo da agenda; concede e revoga papeis; ve nomes |

Procedimento de ativacao, uma vez por clinica:

1. O owner da organizacao abre Gestao da clinica, secao "Papeis e agenda
   (V2)", e clica em "Ativar papeis V2 nesta clinica". A ativacao nao se
   desfaz.
2. Ao ativar, o servidor ja concede Clinico a quem e professional e
   Administracao a owner e administrator.
3. A administracao concede os demais papeis membro a membro, na mesma secao:
   Secretaria, Supervisor clinico, e Clinico ou Administracao para quem
   entrou depois.

Procedimento de agenda:

1. Cada clinico cadastra a propria disponibilidade semanal (dia da semana,
   inicio e fim), em "Minha agenda" no resumo do profissional ou na Agenda da
   clinica. Administracao e secretaria podem cadastrar a disponibilidade de
   qualquer clinico. Sem disponibilidade cadastrada, qualquer marcacao e
   recusada com "fora da disponibilidade cadastrada do clinico".
2. Quem opera a agenda geral (secretaria, administracao, supervisor) abre
   "Agenda da clinica" no painel: a semana por clinico, com os atendimentos
   de cada dia.
3. Marcar: escolher clinico, paciente, dia, hora e duracao em minutos. O
   servidor recusa dupla marcacao do mesmo clinico ("o clinico ja tem
   atendimento nesse horario") e marcacao fora da disponibilidade.
4. Reagendar: o botao "reagendar" no atendimento carrega dia, hora e
   duracao; confirmar grava a mudanca. Cancelar pede confirmacao.
5. O clinico ve e opera so a propria agenda em "Minha agenda".

A agenda interna e a fonte. O Google Calendar de cada profissional passa a ser
espelho dela; a falha do espelho nunca apaga nem bloqueia um agendamento. Os
horarios desta versao sao mostrados no fuso de Sao Paulo.

## O que NAO existe, para nao prometer

- Nao existe grupo ou equipe como entidade de cadastro.
- Nao existe excecao de disponibilidade por data (feriado, ferias) nesta
  versao: a disponibilidade e semanal.
- O supervisor nao ve nomes de pacientes na agenda; se precisar do nome,
  pede a secretaria ou a administracao.
- Agenda da clinica para uma clinica que nao ativou os papeis V2 mostra a
  frase "Esta clinica ainda nao ativou os papeis V2" e nada mais.
