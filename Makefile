# GraphX Community Detection Engine - Makefile
# ✅ MELHORIAS: Comandos otimizados, validações, documentação inline

.PHONY: help setup validate start stop status logs \
        generate generate-small generate-medium generate-large \
        process analyze benchmark clean clean-all \
        all test install-hooks health-check

# Variáveis
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose
SPARK_MASTER := spark_master

# ✅ Detectar número de cores disponíveis
CPU_CORES := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)

# Cores para output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
CYAN := \033[0;36m
NC := \033[0m

##@ Ajuda

help: ## Exibe esta mensagem de ajuda
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║  🕸️  GraphX Community Detection Engine - Comandos Disponíveis        ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════════╝$(NC)"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(CYAN)ℹ️  Dica: Execute 'make quick-test' para validação rápida$(NC)"
	@echo ""

##@ Setup e Configuração

validate: ## Valida ambiente de desenvolvimento
	@echo "$(BLUE)🔍 Validando ambiente...$(NC)"
	@bash validate_environment.sh || (echo "$(RED)❌ Validação falhou!$(NC)" && exit 1)
	@echo "$(GREEN)✅ Ambiente validado com sucesso!$(NC)"

setup: validate ## Instala dependências Python locais
	@echo "$(BLUE)📦 Instalando dependências...$(NC)"
	$(PIP) install -r requirements.txt --quiet
	@echo "$(GREEN)✅ Dependências instaladas!$(NC)"

setup-dev: setup ## Setup completo para desenvolvimento
	@echo "$(BLUE)🔧 Configurando ambiente de desenvolvimento...$(NC)"
	@mkdir -p data/{input,output,temp} analysis/{graphs,metrics} logs checkpoints
	@chmod -R 777 data analysis logs checkpoints 2>/dev/null || true
	@echo "$(GREEN)✅ Estrutura de diretórios criada!$(NC)"

install-hooks: ## Instala git hooks para validação
	@echo "$(BLUE)🪝 Configurando git hooks...$(NC)"
	@mkdir -p .git/hooks
	@echo '#!/bin/bash\nmake validate' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "$(GREEN)✅ Git hooks instalados!$(NC)"

##@ Infraestrutura Docker

start: ## Inicia cluster Spark
	@echo "$(BLUE)🚀 Iniciando cluster Spark...$(NC)"
	@$(DOCKER_COMPOSE) up -d
	@echo "$(YELLOW)⏳ Aguardando inicialização (20s)...$(NC)"
	@sleep 20
	@$(MAKE) health-check
	@echo ""
	@echo "$(GREEN)✅ Cluster Spark iniciado!$(NC)"
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  📊 Spark Master UI: $(YELLOW)http://localhost:8080$(BLUE)                              ║$(NC)"
	@echo "$(BLUE)║  📈 Application UI:  $(YELLOW)http://localhost:4040$(BLUE) (quando job rodar)           ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════════╝$(NC)"

stop: ## Para cluster Spark
	@echo "$(YELLOW)🛑 Parando cluster Spark...$(NC)"
	@$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Cluster parado!$(NC)"

restart: stop start ## Reinicia cluster Spark

status: ## Mostra status dos containers
	@echo "$(BLUE)📊 Status dos containers:$(NC)"
	@$(DOCKER_COMPOSE) ps

health-check: ## ✅ NOVO: Verifica saúde do cluster
	@echo "$(BLUE)🏥 Verificando saúde do cluster...$(NC)"
	@if docker exec $(SPARK_MASTER) curl -sf http://localhost:8080 > /dev/null 2>&1; then \
		echo "$(GREEN)✅ Master: Saudável$(NC)"; \
	else \
		echo "$(RED)❌ Master: Não respondendo$(NC)"; \
		exit 1; \
	fi
	@if docker ps --filter "name=spark_worker" --format "{{.Names}}" | grep -q worker; then \
		echo "$(GREEN)✅ Worker: Rodando$(NC)"; \
	else \
		echo "$(RED)❌ Worker: Não encontrado$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Cluster saudável!$(NC)"

logs: ## Exibe logs do Spark Master
	@$(DOCKER_COMPOSE) logs -f spark-master

logs-worker: ## Exibe logs do Spark Worker
	@$(DOCKER_COMPOSE) logs -f spark-worker

##@ Geração de Dados

generate-small: ## Gera dataset pequeno (5k nós) - ~30s
	@echo "$(BLUE)🧬 Gerando dataset PEQUENO (5,000 nós)...$(NC)"
	@$(PYTHON) scripts/data_generator.py --nodes 5000 --avg-degree 4
	@echo "$(GREEN)✅ Dataset gerado em data/input/$(NC)"

generate: generate-medium ## Alias para generate-medium

generate-medium: ## Gera dataset médio (10k nós) - ~1min
	@echo "$(BLUE)🧬 Gerando dataset MÉDIO (10,000 nós)...$(NC)"
	@$(PYTHON) scripts/data_generator.py --nodes 10000 --avg-degree 5
	@echo "$(GREEN)✅ Dataset gerado em data/input/$(NC)"

generate-large: ## Gera dataset grande (50k nós) - ~5min
	@echo "$(YELLOW)⚠️  Gerando dataset GRANDE (50,000 nós)...$(NC)"
	@$(PYTHON) scripts/data_generator.py --nodes 50000 --avg-degree 6
	@echo "$(GREEN)✅ Dataset gerado em data/input/$(NC)"

generate-xlarge: ## ⚠️  Dataset muito grande (100k nós) - requer 6GB+ RAM
	@echo "$(RED)⚠️  AVISO: Dataset MUITO GRANDE (100,000 nós)$(NC)"
	@echo "$(YELLOW)   Requer pelo menos 6GB RAM disponível$(NC)"
	@read -p "Continuar? (s/N): " confirm && [ "$$confirm" = "s" ] || exit 1
	@$(PYTHON) scripts/data_generator.py --nodes 100000 --avg-degree 8 --use-chunking
	@echo "$(GREEN)✅ Dataset gerado em data/input/$(NC)"

generate-custom: ## Gera dataset customizado (use: make generate-custom NODES=20000 DEGREE=6)
	@echo "$(BLUE)🧬 Gerando dataset CUSTOMIZADO...$(NC)"
	@$(PYTHON) scripts/data_generator.py --nodes $(NODES) --avg-degree $(DEGREE)

##@ Processamento

process: ## Executa pipeline Spark completo (~5min para dataset médio)
	@echo "$(BLUE)⚙️  Executando pipeline Spark...$(NC)"
	@echo "$(YELLOW)⏳ Isso pode levar alguns minutos...$(NC)"
	@docker exec $(SPARK_MASTER) /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 \
		--executor-memory 2G \
		--driver-memory 1G \
		--packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
		--conf spark.serializer=org.apache.spark.serializer.KryoSerializer \
		--conf spark.sql.adaptive.enabled=true \
		/opt/spark-apps/community_detection.py
	@echo "$(GREEN)✅ Pipeline concluído! Resultados em data/output/$(NC)"

process-fast: ## Executa pipeline rápido (menos iterações) ~2min
	@echo "$(BLUE)⚡ Executando pipeline RÁPIDO...$(NC)"
	@docker exec $(SPARK_MASTER) /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 \
		--executor-memory 2G \
		--driver-memory 1G \
		--packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
		/opt/spark-apps/community_detection.py \
		--pagerank-iter 5 \
		--lpa-iter 3 \
		--skip-cc
	@echo "$(GREEN)✅ Pipeline rápido concluído!$(NC)"

process-optimized: ## ✅ NOVO: Pipeline com auto-tuning ativo
	@echo "$(BLUE)🎯 Executando pipeline OTIMIZADO (auto-tuning)...$(NC)"
	@docker exec $(SPARK_MASTER) /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 \
		--executor-memory 2G \
		--driver-memory 1G \
		--packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
		--conf spark.sql.adaptive.enabled=true \
		--conf spark.sql.adaptive.skewJoin.enabled=true \
		/opt/spark-apps/community_detection.py
	@echo "$(GREEN)✅ Pipeline otimizado concluído!$(NC)"

##@ Análise

analyze: ## Gera gráficos e métricas (~30s)
	@echo "$(BLUE)📊 Gerando análises e visualizações...$(NC)"
	@$(PYTHON) scripts/analyze_communities.py
	@echo "$(GREEN)✅ Análises concluídas!$(NC)"
	@echo "$(BLUE)╔═══════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  📊 Gráficos: $(YELLOW)analysis/graphs/$(BLUE)                                        ║$(NC)"
	@echo "$(BLUE)║  📈 Métricas: $(YELLOW)analysis/metrics/$(BLUE)                                       ║$(NC)"
	@echo "$(BLUE)╚═══════════════════════════════════════════════════════════════════════╝$(NC)"

##@ Benchmarking

benchmark: ## Executa testes de performance (~15-20min)
	@echo "$(BLUE)🧪 Iniciando benchmark...$(NC)"
	@echo "$(YELLOW)⚠️  Isso executará múltiplos jobs Spark (15-20 minutos)$(NC)"
	@$(PYTHON) scripts/benchmark_partitioning.py
	@echo "$(GREEN)✅ Benchmark concluído! Resultados em analysis/metrics/$(NC)"

benchmark-quick: ## ✅ NOVO: Benchmark rápido (3 configurações) ~5min
	@echo "$(BLUE)🧪 Executando benchmark RÁPIDO...$(NC)"
	@echo "Testando apenas 3 configurações críticas..."
	@# Implementar versão reduzida do benchmark
	@echo "$(YELLOW)⚠️  Recurso em desenvolvimento$(NC)"

##@ Limpeza

clean: ## Remove dados gerados (mantém código)
	@echo "$(YELLOW)🧹 Limpando dados gerados...$(NC)"
	@rm -rf data/input/*.csv
	@rm -rf data/output/*
	@rm -rf data/temp/*
	@rm -rf analysis/graphs/*.png
	@rm -rf logs/*.log
	@echo "$(GREEN)✅ Dados limpos!$(NC)"

clean-checkpoints: ## ✅ NOVO: Limpa apenas checkpoints
	@echo "$(YELLOW)🧹 Limpando checkpoints...$(NC)"
	@rm -rf checkpoints/*
	@docker exec $(SPARK_MASTER) rm -rf /opt/spark-checkpoints/* 2>/dev/null || true
	@echo "$(GREEN)✅ Checkpoints limpos!$(NC)"

clean-all: clean clean-checkpoints ## Limpeza TOTAL (incluindo Docker cache)
	@echo "$(RED)🗑️  Limpeza TOTAL...$(NC)"
	@$(DOCKER_COMPOSE) down -v
	@rm -rf analysis/metrics/*.csv analysis/metrics/*.json
	@docker system prune -f
	@echo "$(GREEN)✅ Limpeza total concluída!$(NC)"

##@ Fluxos Completos

all: setup-dev start generate process analyze ## Pipeline COMPLETO (~10min)
	@echo ""
	@echo "$(GREEN)╔═══════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║  🎉 Pipeline completo executado com sucesso!                          ║$(NC)"
	@echo "$(GREEN)╚═══════════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(BLUE)📊 Próximos passos:$(NC)"
	@echo "  • Visualize gráficos em: $(YELLOW)analysis/graphs/$(NC)"
	@echo "  • Acesse Spark UI: $(YELLOW)http://localhost:8080$(NC)"
	@echo "  • Execute benchmark: $(YELLOW)make benchmark$(NC)"
	@echo ""

quick-test: setup-dev start generate-small process-fast analyze ## ✅ Teste rápido (~3min)
	@echo "$(GREEN)✅ Teste rápido concluído!$(NC)"

full-benchmark: setup-dev start generate benchmark ## Pipeline com benchmark (~20min)
	@echo "$(GREEN)✅ Benchmark completo concluído!$(NC)"

##@ Utilitários

shell-master: ## Abre shell no Spark Master
	@docker exec -it $(SPARK_MASTER) /bin/bash

shell-worker: ## Abre shell no Spark Worker
	@docker exec -it spark_worker_1 /bin/bash

check-data: ## ✅ MELHORADO: Verifica dados com estatísticas
	@echo "$(BLUE)🔍 Verificando dados...$(NC)"
	@if [ -f "data/input/vertices.csv" ] && [ -f "data/input/edges.csv" ]; then \
		echo "$(GREEN)✅ Dados de entrada encontrados$(NC)"; \
		echo "$(CYAN)Linhas:$(NC)"; \
		wc -l data/input/*.csv; \
		echo "$(CYAN)Tamanhos:$(NC)"; \
		du -sh data/input/*.csv; \
	else \
		echo "$(YELLOW)⚠️  Dados não encontrados. Execute: make generate$(NC)"; \
	fi
	@if [ -d "data/output/pagerank" ]; then \
		echo "$(GREEN)✅ Resultados encontrados$(NC)"; \
		du -sh data/output/* 2>/dev/null; \
	else \
		echo "$(YELLOW)⚠️  Resultados não encontrados. Execute: make process$(NC)"; \
	fi

check-resources: ## ✅ NOVO: Verifica recursos do sistema
	@echo "$(BLUE)💻 Recursos do Sistema:$(NC)"
	@echo "  • CPU Cores: $(CPU_CORES)"
	@echo "  • Memória Total:" $$(free -h 2>/dev/null | awk '/^Mem:/{print $$2}' || echo "N/A")
	@echo "  • Memória Disponível:" $$(free -h 2>/dev/null | awk '/^Mem:/{print $$7}' || echo "N/A")
	@echo "  • Espaço em Disco:" $$(df -h . | awk 'NR==2{print $$4}')
	@echo ""
	@echo "$(BLUE)🐳 Recursos Docker:$(NC)"
	@docker info 2>/dev/null | grep -E "(Total Memory|CPUs)" || echo "$(YELLOW)Docker não está rodando$(NC)"

version: ## Exibe versões das ferramentas
	@echo "$(BLUE)📋 Versões:$(NC)"
	@echo "  • Docker: $$(docker --version)"
	@echo "  • Docker Compose: $$(docker-compose --version)"
	@echo "  • Python: $$(python3 --version)"
	@echo "  • Pip: $$(pip3 --version)"
	@echo "  • CPU Cores: $(CPU_CORES)"

monitor: ## ✅ NOVO: Monitora recursos em tempo real
	@echo "$(BLUE)📡 Monitorando recursos (Ctrl+C para sair)...$(NC)"
	@watch -n 2 'docker stats --no-stream'

##@ Desenvolvimento

test: validate check-data health-check ## Executa testes de validação
	@echo "$(GREEN)✅ Todos os testes passaram!$(NC)"

watch-logs: ## Monitora logs em tempo real
	@$(DOCKER_COMPOSE) logs -f

debug: ## ✅ NOVO: Modo debug com logs verbosos
	@echo "$(BLUE)🐛 Modo Debug$(NC)"
	@echo "Executando pipeline com logs verbosos..."
	@docker exec $(SPARK_MASTER) /opt/spark/bin/spark-submit \
		--master spark://spark-master:7077 \
		--packages graphframes:graphframes:0.8.3-spark3.5-s_2.12 \
		--conf spark.log.level=INFO \
		/opt/spark-apps/community_detection.py

ci: validate test ## ✅ NOVO: Simulação de CI/CD
	@echo "$(GREEN)✅ Checks de CI passaram!$(NC)"

.DEFAULT_GOAL := help