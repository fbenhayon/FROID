# === BUILDER ===
FROM node:20-bookworm AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/shared/package.json ./packages/shared/
COPY packages/identity-vault/package.json ./packages/identity-vault/

RUN pnpm install --frozen-lockfile
COPY . .

RUN cd packages/identity-vault && pnpm exec prisma generate --schema src/prisma/schema.prisma
RUN cd packages/shared && (pnpm run build 2>/dev/null || true)
RUN mkdir -p packages/shared/dist
RUN cd packages/identity-vault && pnpm exec tsc

# === RUNNER ===
FROM node:20-bookworm AS runner
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate
RUN addgroup --system nodejs && adduser --system --ingroup nodejs nestjs

COPY --from=builder /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=builder /app/packages/shared/package.json ./packages/shared/
COPY --from=builder /app/packages/identity-vault/package.json ./packages/identity-vault/

RUN pnpm install --prod --frozen-lockfile

COPY --from=builder /app/packages/shared/dist ./packages/shared/dist
COPY --from=builder /app/packages/identity-vault/dist ./packages/identity-vault/dist
COPY --from=builder /app/packages/identity-vault/src/prisma ./packages/identity-vault/src/prisma
COPY --from=builder /app/node_modules ./node_modules

RUN cd packages/identity-vault && pnpm dlx prisma@5.22.0 generate --schema ./src/prisma/schema.prisma

RUN chown -R nestjs:nodejs /app
USER nestjs
WORKDIR /app/packages/identity-vault
EXPOSE 3001
# CMD ["node", "dist/main.js"]

