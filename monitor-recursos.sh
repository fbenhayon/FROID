#!/bin/bash
echo "╔════════════════════════════════════════════╗"
echo "║   FROID - MONITOR TEMPO REAL              ║"
echo "╚════════════════════════════════════════════╝"
echo ""

while true; do
    clear
    echo "🕐 $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "=== RAM ==="
    free -h | grep "Mem:" | awk '{print "Total: "$2" | Usado: "$3" | Livre: "$4" | Uso%: "int($3/$2*100)"%"}'
    echo ""
    echo "=== CPU ==="
    top -bn1 | grep "Cpu(s)" | awk '{print "Uso: "$2" | Idle: "$8}'
    echo ""
    echo "=== DOCKER CONTAINERS ==="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    echo ""
    echo "=== CONEXÕES ATIVAS (porta 3001) ==="
    netstat -an | grep ":3001" | grep ESTABLISHED | wc -l
    echo ""
    echo "Pressione Ctrl+C para sair"
    sleep 3
done
