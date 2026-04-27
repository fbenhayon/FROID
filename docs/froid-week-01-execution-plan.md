# FROID - Week 01 Execution Plan (Operacional)

## Objetivo da semana
Entregar base estável de desenvolvimento global com deploy previsível e UX foundation.

## Priorização (P0/P1/P2)

### P0 (bloqueantes)
1) CI/CD mínimo do identity-vault
- Escopo: build + up + smoke login
- Esforço: 1 dia
- Dependências: Dockerfile estável, compose funcional
- Dono: Backend/DevOps

2) Observabilidade mínima
- Escopo: health endpoint + logs estruturados
- Esforço: 0.5 dia
- Dependências: app rodando
- Dono: Backend

3) Contrato de API v1
- Escopo: convenção de rotas/erros/status code
- Esforço: 0.5 dia
- Dependências: Auth endpoints definidos
- Dono: Backend Lead

### P1 (alto impacto)
4) Base de Design System
- Escopo: cores, tipografia, spacing, botões, inputs
- Esforço: 1 dia
- Dependências: decisão de branding
- Dono: UI/UX (Antigravity)

5) i18n base (pt-BR/en-US/es-ES)
- Escopo: estrutura de traduções + fallback
- Esforço: 1 dia
- Dependências: layout base
- Dono: Frontend

6) Acessibilidade AA (MVP)
- Escopo: contraste, foco teclado, labels
- Esforço: 0.5 dia
- Dependências: componentes base
- Dono: Frontend/UI

### P2 (preparação escala)
7) Timezone/locale por usuário
- Escopo: normalização UTC + render local
- Esforço: 0.5 dia
- Dependências: i18n base
- Dono: Fullstack

8) Documento de compliance por região
- Escopo: matriz LGPD/GDPR inicial
- Esforço: 0.5 dia
- Dependências: jurídico/produto
- Dono: Produto + Compliance

## Critérios de aceite da semana
- [ ] Build e restart sem intervenção manual extensa
- [ ] /auth/register e /auth/login passando
- [ ] Logs sem erro crítico por 24h
- [ ] Design tokens aplicados em pelo menos 1 tela
- [ ] i18n funcional em 3 idiomas (mínimo 1 fluxo)

## Riscos
- Divergência entre schema Prisma e serviços
- Falta de versionamento de API
- Mudanças de layout sem design system

## Mitigações
- PR checklist obrigatório (build+smoke)
- Congelamento de contrato v1 por sprint
- Revisão técnica diária de 15 minutos
