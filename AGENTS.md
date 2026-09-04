# Regras para qualquer agente que edite este repositório

Este arquivo existe para que a conduta não dependa de qual ferramenta está
sendo usada. Vale para Claude Code, Codex, Cline, Cursor, Copilot ou qualquer
outro — humano inclusive.

## A fonte

**Leia `.claude/skills/skill-froid-master/SKILL.md` antes de mexer em qualquer
caminho que produza número, texto ou decisão que alguém vá ler como verdade.**

Esse arquivo é a única fonte. Este aqui não repete o conteúdo dele de
propósito: duas cópias da mesma regra divergem em silêncio, e neste repositório
isso já aconteceu com números publicados no site e com o procedimento de revisão
dos serviços. Se você precisa da regra, abra a fonte.

## O mínimo, para quem vai fazer só uma edição pequena

1. **Onde não há apuração, declare a ausência.** Nunca preencha com zero, com
   média, com último valor conhecido, nem com um padrão qualquer. Índice em
   branco significa "não medido", nunca "zero". Isto é determinação do dono, de
   03/09/2026, e não tem exceção.

2. **Não invente número, nome de produto, prazo ou capacidade.** Se um número
   aparece em mais de um lugar, todos têm de bater com a fonte — que é o código
   ou um documento em `docs/normas/`, nunca o valor mais bonito.

3. **A fronteira clínica é inviolável.** Nenhum texto, tela, relatório ou
   consulta pode sugerir que o empregador lê resposta individual de trabalhador.

4. **Falhe fechado.** Problema de infraestrutura nunca amplia acesso. E diga que
   fechou: degradação silenciosa é pior que erro visível.

5. **Não remova nem enfraqueça um teste para fazer o seu código passar** —
   principalmente teste de segurança. Se a garantia precisa mudar, isso é
   decisão do dono, não da tarefa.

6. **Não faça `commit` nem `push` sem pedir**, e nunca em cima de trabalho de
   outra sessão. Este repositório costuma ter mais de um agente trabalhando ao
   mesmo tempo, em territórios separados.

## Territórios

Quando há trabalho em paralelo, cada frente fica numa área e não entra na outra:

| Área | Pastas |
|---|---|
| Motor e API | `froid-server/` |
| Painel e relatório | `froid-dashboard/` |
| Site institucional | `froid-site/` |
| Documentação e normas | `docs/` |

`froid-site` entra em produção com `git pull`, sem build. `froid-dashboard` e
`froid-server` são imagens e exigem `docker compose build`. Rebuild do backend
derruba sessão clínica em andamento.

## Estratégia de modelo e trabalho de conteúdo

*(Herdado da versão anterior deste arquivo, e mantido: continua valendo.)*

- Claude para planejamento, revisão de arquitetura e raciocínio longo.
- Gemini para pesquisa, reescrita multilíngue e ideação rápida.
- Para vídeo, os três agentes em `.claude/agents/`: o de *brief* define objetivo,
  público, tom e distribuição; o de roteiro monta script, lista de planos,
  locução e legendas; o de *prompt ops* gera os prompts das ferramentas de
  imagem, vídeo e edição.
- Trabalho de conteúdo sai em português, salvo pedido explícito de outro idioma.
- Ao editar código, prefira mudanças pequenas e focadas, e preserve as
  convenções existentes do arquivo.

## Armadilhas que já custaram caro

- Heredoc de bash com `\` corrompe o arquivo gerado. Use escrita de arquivo.
- Os HTML são UTF-8: depois de editar, procure mojibake (`Ã§`, `Ã£`, `â€"`).
- Variável de ambiente nova exige linha em `docker-compose.yml`; só no `.env`
  ela não chega ao contêiner, e a falha é silenciosa.
