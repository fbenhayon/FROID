# Memória — FROID

- [Deploy no Hetzner](froid-deploy-hetzner.md) — Fábio cola os comandos no console; minha chave SSH não está autorizada
- [Arquitetura site + SPA](froid-site-architecture.md) — froid-site na raiz, painel em /app/#, rotas preservadas e cache de imagens
- [Armadilha de encoding nos HTML](froid-html-encoding-pitfall.md) — edições manuais podem corromper UTF-8; verificar mojibake antes de commitar
- [Módulo NR-1 corporativo](froid-nr1-corporate-module.md) — instrumento, pisos de coorte e a fronteira que impede o empregador de ler dado clínico
- [Infra de produção](froid-infra-producao.md) — branch, banco e contêineres reais; três suposições minhas que quase viraram incidente
- [Topologia de deploy](froid-deploy-topologia.md) — site entra com git pull, painel exige rebuild, backend quase nunca; DEPLOY_LOG.md engana
- [Envio de e-mail (SMTP)](froid-smtp-envio.md) — froid@froid.com.br funciona; fbenhayon@froid.com.br não, e por quê
- [Fontes normativas da NR-1](froid-nr1-fontes-normativas.md) — o texto da lei vive em docs/normas/, e três coisas que ela não diz
- [Espelho PostgreSQL silencioso](froid-espelho-postgres-silencioso.md) — o 403 do NR-1 que não era permissão: o espelho nunca rodou
- [Contrato TATICCA](froid-taticca-contrato.md) — 250+ pessoas em 11 endereços; 152 respostas, e nenhum endereço publica sozinho
- [Pré-condições do aceite jurídico](froid-aceite-juridico-precondicoes.md) — sem chave de 32 bytes o aceite não é gravado; /ready avisa e não é público
- [Sinal sem leitor](froid-sinal-sem-leitor.md) — o padrão que custou um cliente: existe, é correto, e ninguém consome
- [Acervo do FROID Explica NR-1](froid-explica-nr1-acervo.md) — collection própria, como reindexar e o que "completo" significa (661 trechos)
- [Espelhos de número](froid-espelhos-de-numero.md) — pisos e fórmulas copiados no site e nos documentos; o piso 50 ficou publicado semanas depois de virar 15
- [Heredoc e barra invertida](froid-heredoc-barra-invertida.md) — `\` colapsa e quebra o arquivo gerado; usar chr(10)/chr(92) ou Write
- [Acervo Data-Froid](froid-data-froid-corpus.md) — preservar a substância vale mais que recusar por precaução
- [Capacidade facial afirmada](froid-facs-capacidade-afirmada.md) — 16 AUs e seis regras, sem onset/apex/offset; corrigido no site, pendente no painel
