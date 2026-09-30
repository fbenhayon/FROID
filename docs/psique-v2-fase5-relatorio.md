# FROID Psique V2.1 — resultado da Fase 5 (app e website V2)

Data: 30/09/2026, America/Sao_Paulo. Autorização do proprietário nesta data, com a revisão pré-fase que definiu a decisão central de segurança da entrega.

**Resultado:** a experiência V2 de preços existe de ponta a ponta — backend público, site em quatro idiomas e cliente/componentes do painel — **sem um único número embutido**: tudo vem da API, e a falha vira indisponibilidade declarada, nunca preço antigo ou saldo zero. **184 testes Psique verdes (9 novos) em Windows e dentro de contêiner Linux; 812 testes do painel verdes + typecheck limpo.** A execução PARA aqui; a virada pública é a Fase 6.

## A decisão que a revisão impôs: coexistência, não substituição

A página de preços vigente é V1 e o site entra em produção com `git pull`: substituí-la agora embarcaria a V2 (com backend desligado → tudo "indisponível") na próxima atualização de rotina do site — o mesmo padrão do incidente das derivadas. Por isso a V2 nasce **coexistente**: `precos-v2.html` em PT/EN/ES/FR, fora do menu e com `noindex`, e um teste garante que a página V1 permanece intocada. A troca é um ato da virada (Fase 6), junto com FAQ/profissionais/metadados e a ativação do flag.

## Backend

`GET /api/psique/v2/pricing` (público, sob o flag): versão/moeda, regra do Trial, as seis ofertas PRO com `unit_price_display` exato, e o teto self-service da licença — via `psique_pricing.public_catalog()`, com falha de catálogo respondendo `503 PRICING_UNAVAILABLE` (nunca payload parcial). `GET /api/psique/v2/wallet` (autenticada) expõe o BALANCE do comando de crédito, com recusas mapeadas (403/409 nomeados — a revisão pegou `PSIQUE_ROLE_DENIED` caindo em 503 e corrigiu o mapa). Espelho do Trial (`TRIAL_CREDITS=10`, `TRIAL_DAYS=14`) com guarda de teste contra o texto executável da migration 037.

## Site (froid-site)

`site-assets/psique-pricing-v2.js/.css` + `precos-v2.html` ×4: cards das seis ofertas e números do Trial renderizados da API; calculadora da licença consultando a quote ao vivo (201+ → mensagem Enterprise); **indisponibilidade explícita em todos os blocos** quando a API não responde. Guardas de teste: zero preços hardcoded (regex sobre páginas e JS), contrato i18n idêntico nas quatro línguas, estrutura obrigatória presente, página V1 intocada.

## Painel (froid-dashboard)

`src/lib/psique-v2-api.ts`: cliente tipado com estados discriminados (`ok`/`indisponivel`/`negado`) — fora do "ok" **não existe campo de dados**, o que torna impossível exibir 0 no lugar de saldo; checkout envia somente `product_code` com a chave de idempotência da intenção do usuário. `portaoDeAcessoV2`: sem saldo (ou sem resposta), fecha SÓ a análise nova — login/histórico/relatórios são literais `true` travados por teste. `menuVisivelV2` deriva menus de `GET /capabilities`. `src/components/psique/PsiqueCreditsPanel.tsx`: apresentacional, saldo/trial/ofertas separados da licença, indisponibilidade declarada. 7 testes vitest novos (fetch estubado, sem DOM — `renderToStaticMarkup`, padrão da casa); `tsc --noEmit` limpo.

## Falha preexistente segregada

`retencao-da-apuracao.test.tsx` falha no `main` pristino (o gráfico IPM já declara "Sem Capacidade de Apuração" e o teste antigo espera outra frase) — pertence à frente dos gráficos/derivadas, cuja correção vive na branch `frente-derivadas-zeradas` por decisão adiada do proprietário. Não foi tocada nesta fase.

## Pendências (virada — Fase 6)

Trocar a página pública de preços e atualizar FAQ/profissionais/metadados nas quatro línguas; fiar o painel (rotas, menus, onboarding, polling de compra pós-redirect) usando os módulos desta fase; ativar `FROID_PSIQUE_V2_BILLING_ENABLED` com chave/whsec reais. Sem LIVE, sem produção, sem publicação nesta fase. **Fase 6 somente com nova aprovação explícita.**
