# Divulgação do FROID Psique — escopo aberto em 31/08/2026

Pedido do Fábio: divulgar, em `profissionais.html`, os **relatórios do
profissional**, a funcionalidade de **criar relatórios customizados**
diferenciando os itens de composição, e a **área do paciente** — com imagens
dos procedimentos no descritivo.

**Nada aqui foi executado.** Esta nota existe para a próxima sessão começar por
um plano em vez de uma descoberta.

---

## Por que não executei na hora

Duas razões, e a segunda é um bloqueio real.

**O estado das telas nunca foi levantado.** Três sessões seguidas foram inteiras
no módulo de conformidade. São 4.863 linhas em quatro telas que ninguém abriu
para este fim:

| Arquivo | Linhas |
|---|---:|
| `froid-dashboard/src/pages/SessionReport.tsx` | 1.550 |
| `froid-dashboard/src/pages/PatientPortalPage.tsx` | 1.218 |
| `froid-dashboard/src/pages/Dashboard.tsx` | 1.081 |
| `froid-dashboard/src/pages/PatientDetail.tsx` | 1.014 |

Mais `lib/report-intro.ts`, `lib/report-epigraph.ts`, `lib/patient-dashboard.ts`
e `lib/ordem-dos-cortes.ts`, que parecem carregar a lógica de composição.

**As imagens pedidas não existem.** É o bloqueio. Ver a seção seguinte.

---

## O bloqueio: capturas de tela

`site-assets/img/` tem exatamente **duas** imagens do lado profissional, e as
duas já estão em uso em `profissionais.html`:

- `prof-financeiro-creditos.png`
- `prof-relatorio-metricas.png`

Não há nenhuma da área do paciente nem da composição de relatório. Sem elas, a
parte de "imagens dos procedimentos" não sai.

### As capturas que o Fábio precisa tirar

Salvar em `site-assets/img/`, PNG, largura mínima 1400 px, com dados de
demonstração e **sem nome real de paciente na tela**:

| Arquivo sugerido | O que mostrar |
|---|---|
| `prof-relatorio-composicao.png` | A tela de montagem do relatório, com os itens de composição visíveis e alguns marcados |
| `prof-relatorio-pronto.png` | Um relatório gerado, mostrando a diferença entre um item incluído e um omitido |
| `paciente-portal-sessoes.png` | O Portal do Paciente com a lista de sessões |
| `paciente-portal-dados.png` | A tela de gestão dos próprios dados (exportar, apagar) — é o argumento de LGPD |

Convenção do repositório: prefixo por área (`prof-`, `paciente-`, `tec-`,
`cap-`, `home-`), nome descritivo em minúsculas com hífen.

---

## O que a página tem hoje

`profissionais.html`, 6 seções:

1. Uma sessão com o FROID: antes, durante e depois
2. Controle financeiro da prática
3. Análise de relatórios de pacientes
4. Compartilhamento entre profissionais
5. O que o FROID é e o que não é
6. Avalie o FROID do seu jeito

A seção 3 é o lugar natural do conteúdo de relatórios. A área do paciente não
tem seção própria — hoje aparece só em `index.html`, na seção `#paciente`.

---

## Ordem sugerida para a próxima sessão

1. **Abrir as quatro telas antes de escrever qualquer linha de copy.** O padrão
   deste repositório é que a peça já exista e ninguém a esteja chamando — isso
   se repetiu cinco vezes só no módulo NR-1. Presumir custa mais caro que grepar.
2. **Descobrir se a composição customizada de relatório realmente existe** ou se
   é desejo de produto. A diferença muda tudo: divulgar funcionalidade que não
   existe é o erro mais caro que este site pode cometer.
3. **Só então** escrever a copy, e encaixar as capturas que o Fábio tiver tirado.
4. Se as capturas não estiverem prontas, escrever a copy mesmo assim e deixar os
   `<img>` marcados — a página melhora sem elas, e elas entram depois.

---

## Convenções que valem para este trabalho

- **`froid-site` é bind mount**: entra com `git pull`, sem rebuild. O painel
  (`froid-dashboard`) exige `docker compose build froid-frontend`.
- **O menu suspenso vem de `NAV_SECOES`**, em `site-assets/script.js`. Seção
  nova em `profissionais.html` exige entrada nova lá, ou o menu aponta para o
  lugar errado — defeito que só aparece cruzando o mapa com os ids reais, nunca
  em validação de HTML.
- **Siglas**: expansão na primeira aparição, glossário ao pé.
- **Encoding**: editar por script Python com `io.open(..., encoding="utf-8")`;
  heredoc de bash quebra com conteúdo grande. Conferir mojibake e balanceamento
  depois de cada alteração.
- **Nomenclatura vigente**: FROID Psique (clínico) e FROID Psicossocial
  (corporativo). "FROID Compliance" e "FROID NR-1" foram aposentados como nome
  de produto em 31/08.
