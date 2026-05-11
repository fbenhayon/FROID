#!/bin/bash
set -e

echo "╔════════════════════════════════════════════╗"
echo "║   FROID - DEPLOY PRODUÇÃO AUTOMATIZADO    ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# 1. ATUALIZAR SISTEMA
echo "=== 1. ATUALIZANDO SISTEMA ==="
sudo apt-get update && sudo apt-get upgrade -y

# 2. INSTALAR DEPENDÊNCIAS
echo "=== 2. INSTALANDO DEPENDÊNCIAS ==="
sudo apt-get install -y git curl wget build-essential

# 3. INSTALAR DOCKER
echo "=== 3. INSTALANDO DOCKER ==="
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 4. INSTALAR DOCKER COMPOSE
echo "=== 4. INSTALANDO DOCKER COMPOSE ==="
sudo curl -L "https://github.com/docker/compose/releases/download/v2.30.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. INSTALAR NODE.JS 20 LTS
echo "=== 5. INSTALANDO NODE.JS 20 ==="
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 6. INSTALAR PNPM
echo "=== 6. INSTALANDO PNPM ==="
sudo npm install -g pnpm

# 7. CLONAR REPOSITÓRIO
echo "=== 7. CLONANDO REPOSITÓRIO ==="
cd /root
if [ -d "froid" ]; then
  cd froid
  git pull origin main
else
  git clone https://github.com/seu-usuario/froid.git
  cd froid
fi

# 8. CONFIGURAR DOCKER COMPOSE PRODUÇÃO
echo "=== 8. CONFIGURANDO DOCKER COMPOSE ==="
cat > docker-compose.prod.yml << 'EOFCOMPOSE'
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: froid
      POSTGRES_PASSWORD: froid_prod_secret_2026
      POSTGRES_DB: froid_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U froid"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass froid_redis_prod_2026
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  identity-vault:
    build:
      context: ./packages/identity-vault
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3001:3001"
    environment:
      NODE_ENV: production
      DATABASE_URL: postgresql://froid:froid_prod_secret_2026@postgres:5432/froid_db
      REDIS_URL: redis://:froid_redis_prod_2026@redis:6379
      JWT_SECRET: froid_jwt_production_secret_change_me_2026
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    mem_limit: 1g
    cpus: 2

  froid-voice:
    build:
      context: ./packages/froid-voice
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3002:3002"
    mem_limit: 2g
    cpus: 2

  froid-face:
    build:
      context: ./packages/froid-face
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3003:3003"
    mem_limit: 2g
    cpus: 2

  payment:
    build:
      context: ./packages/payment
      dockerfile: Dockerfile
    restart: always
    ports:
      - "3004:3004"
    depends_on:
      postgres:
        condition: service_healthy
    mem_limit: 512m
    cpus: 1

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: froid-production
EOFCOMPOSE

# 9. SUBIR SERVIÇOS
echo "=== 9. SUBINDO SERVIÇOS ==="
docker-compose -f docker-compose.prod.yml up -d --build

# 10. AGUARDAR SERVIÇOS
echo "=== 10. AGUARDANDO SERVIÇOS (30s) ==="
sleep 30

# 11. VERIFICAR STATUS
echo "=== 11. STATUS DOS SERVIÇOS ==="
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║   ✅ DEPLOY COMPLETO!                     ║"
echo "║                                            ║"
echo "║   Backend:  http://[IP]:3001              ║"
echo "║   Swagger:  http://[IP]:3001/api/docs     ║"
echo "╚════════════════════════════════════════════╝"
