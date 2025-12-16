#!/bin/bash

# Script de Validação de Ambiente (Refatorado)
# Verifica dependências, recursos do Docker e disco com robustez

# Não usamos set -e para permitir que o script reporte todos os erros encontrados
# set -e 

echo "🔍 Validando ambiente de desenvolvimento..."
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variável de contagem de erros
errors=0

# Função genérica de verificação de comando
check_command() {
    local cmd=$1
    local version_flag=$2
    
    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $cmd está instalado"
        if [ ! -z "$version_flag" ]; then
            # Tenta pegar a versão e limpar a saída
            version=$($cmd $version_flag 2>&1 | head -n 1)
            echo -e "  ${BLUE}→${NC} $version"
        fi
        return 0
    else
        echo -e "${RED}✗${NC} $cmd NÃO está instalado"
        return 1
    fi
}

echo "📦 Verificando dependências básicas..."
check_command "git" "--version" || ((errors++))
check_command "python3" "--version" || ((errors++))
check_command "pip3" "--version" || ((errors++))

echo ""
echo "🐳 Verificando Docker..."

# 1. Verifica Docker Engine
if check_command "docker" "--version"; then
    # 2. Verifica se o Daemon está rodando
    if ! docker info &> /dev/null; then
        echo -e "${RED}✗${NC} Docker está instalado, mas NÃO está rodando!"
        ((errors++))
    else
        echo -e "${GREEN}✓${NC} Docker Daemon está rodando"
        
        # 3. Verifica Recursos (Memória e CPU) de forma robusta via Go template
        # Obtém memória em Bytes
        mem_bytes=$(docker info --format '{{.MemTotal}}')
        cpus=$(docker info --format '{{.NCPU}}')
        
        # Converte para GB (Bytes / 1024^3)
        mem_gb=$((mem_bytes / 1024 / 1024 / 1024))
        
        echo -e "  ${BLUE}→${NC} Memória Alocada: ${mem_gb}GB"
        echo -e "  ${BLUE}→${NC} CPUs Alocados: ${cpus}"
        
        # Validação de requisitos mínimos (4GB RAM)
        if [ "$mem_gb" -lt 4 ]; then
            echo -e "${YELLOW}⚠  Atenção: Memória Docker (${mem_gb}GB) é menor que o recomendado (4GB).${NC}"
            echo -e "   Isso pode causar erros de 'OOM Killed' em grafos grandes."
        fi
    fi
else
    ((errors++))
fi

echo ""
echo "🐙 Verificando Docker Compose..."
# Tenta primeiro o plugin novo (v2), depois o legado (v1)
if docker compose version &> /dev/null; then
    v=$(docker compose version)
    echo -e "${GREEN}✓${NC} Docker Compose (Plugin v2) detectado"
    echo -e "  ${BLUE}→${NC} $v"
elif command -v docker-compose &> /dev/null; then
    v=$(docker-compose --version)
    echo -e "${GREEN}✓${NC} Docker Compose (Standalone v1) detectado"
    echo -e "  ${BLUE}→${NC} $v"
else
    echo -e "${RED}✗${NC} Docker Compose NÃO encontrado"
    ((errors++))
fi

echo ""
echo "💾 Verificando espaço em disco..."
# df -P garante portabilidade POSIX (evita quebra de linha)
available_space=$(df -Ph . | awk 'NR==2 {print $4}')
echo -e "  ${BLUE}→${NC} Espaço disponível no diretório atual: $available_space"

echo ""
echo "-----------------------------------------------------"
if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✅ Ambiente validado com sucesso! Você está pronto.${NC}"
    exit 0
else
    echo -e "${RED}❌ Foram encontrados $errors erro(s) crítico(s).${NC}"
    echo "Corrija os itens marcados com ✗ acima antes de prosseguir."
    exit 1
fi