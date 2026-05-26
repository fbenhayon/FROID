#!/bin/bash
echo "=========================================="
echo "🚀 FROID - Atualização Git no SERVIDOR"
echo "=========================================="
echo ""
cd /root/froid
echo "📍 Branch atual:"
git branch --show-current
echo ""
echo "📋 Verificando mudanças..."
git status --short
echo ""
echo "➕ Adicionando mudanças ao stage..."
git add .
echo ""
echo "📦 Arquivos para commit:"
git diff --cached --name-status
echo ""
read -p "💬 Mensagem do commit: " commit_msg
if [ -z "$commit_msg" ]; then
  commit_msg="chore: Atualização servidor $(date +%Y-%m-%d\ %H:%M)"
fi
echo ""
echo "💾 Fazendo commit..."
git commit -m "$commit_msg"
echo ""
echo "☁️  Fazendo push para GitHub..."
git push origin main
echo ""
echo "✅ Último commit:"
git log -1 --oneline
echo ""
echo "=========================================="
echo "✅ Atualização concluída no SERVIDOR!"
echo "=========================================="
