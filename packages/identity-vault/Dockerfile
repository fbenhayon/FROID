# Etapa 1: Builder
FROM node:20-alpine AS builder

# Instala dependências de build necessárias
RUN apk add --no-cache libc6-compat

# Habilita Corepack e prepara pnpm com versão fixa + hash de integridade
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable && \
    corepack prepare pnpm@10.13.1 --activate && \
    # Garante que o PATH inclua o diretório dos shims do corepack
    export PATH="$PATH:$(corepack which pnpm | xargs dirname)"

WORKDIR /app

# Copia arquivos de dependência primeiro (cache eficiente)
COPY package.json pnpm-lock.yaml ./

# Instala dependências com lockfile congelado
RUN pnpm install --frozen-lockfile

# Copia código fonte
COPY . .

# Gera Prisma e faz build
# Usa o caminho completo do pnpm para evitar erros de PATH
RUN $(corepack which pnpm) run prisma:generate
RUN $(corepack which pnpm) run build

# Etapa 2: Runner (Produção)
FROM node:20-alpine AS runner

WORKDIR /app

# Cria usuário não-root para segurança
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nestjs -u 1001

# Copia apenas o necessário do builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/src/prisma ./src/prisma
COPY --from=builder /app/package.json ./

# Ajusta permissões
RUN chown -R nestjs:nodejs /app

USER nestjs

EXPOSE 3001

CMD ["node", "dist/main.js"]