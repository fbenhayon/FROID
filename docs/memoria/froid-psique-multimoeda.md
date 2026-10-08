---
name: froid-psique-multimoeda
description: Multimoeda do Psique (07/10/2026) — mesmo numero em BRL/USD/EUR; site pelo idioma, painel pelo mercado do cadastro (legal_jurisdiction); uma tabela por moeda com versao sufixada, migration 051 gerada; codigo pronto e testado, janela pendente
metadata:
  type: project
---

Decisoes do Fabio (06 e 07/10/2026): 1 real = 1 dolar = 1 euro, sem conversao;
moeda pelo idioma da pagina (pt brl, en usd, es/fr eur); conta Stripe live;
**NR-1 adiado** (segue em reais em todos os idiomas); **direto no live** (sem
provar em modo teste antes).

Como ficou (desenho + execucao + roteiro em docs/multimoeda-psique-nr1-desenho.md):
uma tabela de precos POR MOEDA, derivada da BRL por codigo
(`psique_pricing.config_for_currency`), versao sufixada `2.1` / `2.1-usd` /
`2.1-eur` porque a 035 tem UNIQUE(code, version); migration
`051_psique_multimoeda` GERADA por `tools/psique_multimoeda_sync.py` a partir
da 046 (mesmo pacto da 046, teste de espelho byte a byte) — amplia os 3 CHECK
de moeda e faz a licenca gravar a moeda do preview. O navegador manda so o
IDIOMA (`language`), nunca moeda; a confirmacao da licenca le a moeda DO
PREVIEW no banco (`psique_v2_seat_preview_catalog`). Site: o JS formata com a
moeda que a API declarou; ate o backend novo subir, en/es/fr mostram R$.

**Painel (resolvido em 07/10/2026, depois do Fabio dizer "ja esta tudo
acertado"):** o painel e so pt-BR, mas o CADASTRO ja pergunta o mercado
(BR/US/ES/FR em `legal_jurisdiction`, a chave dos documentos juridicos).
`main.py._psique_moeda_do_profissional` resolve a moeda da sessao por ela e
o router passa `currency=` ao checkout/preview; o corpo segue so
`product_code`. `/pricing` com sessao devolve essa moeda; o painel chama com
a sessao e formata pela moeda da API. Achado lateral: "Outros paises da UE"
e "China" do cadastro viram BR no backend (pre-existente, com o dono).

**Why:** a 2.7 (espelhos de numero) exige UMA fonte: o JSON BRL; as moedas
sao derivadas, nunca digitadas. E a 2.4 (rotulo que promete o que nao
entrega) e o motivo de o ponto aberto ser dito em voz alta, nao resolvido por
mim com `navigator.language` (brasileiro com Windows em ingles pagaria 5x).

**How to apply:** testes PostgreSQL locais = Docker `postgres:16` em
`localhost:5433`, role `froid_runtime` NOLOGIN + banco `psique_v2_test_base`,
`FROID_PSIQUE_TEST_DATABASE_URL=postgresql://postgres:froid@localhost:5433/psique_v2_test_base`,
`pip install "psycopg[binary]"` no .venv (faltava). A janela (ele cola):
backup, build, `migrate_schema.py --through 051_psique_multimoeda`,
`psique_pricing_catalog.py --install-draft --producao --moeda usd|eur`,
`psique_live_stripe.py --create-objects --homolog --moeda usd|eur` e
`--register --moeda ...`, `up -d`, sondas `/pricing?language=en`. Ver
[[froid-psique-v2-estado-execucao]], [[froid-espelhos-de-numero]].
