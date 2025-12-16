# 🔧 Guia de Troubleshooting - GraphX Community Detection Engine

## 📋 Índice Rápido

1. [Problemas de Infraestrutura](#infraestrutura)
2. [Erros de Memória](#memória)
3. [Erros do Spark](#spark)
4. [Problemas com GraphFrames](#graphframes)
5. [Erros de Checkpoint](#checkpoint)
6. [Performance Issues](#performance)
7. [Validação de Dados](#dados)

---

## 🐳 Problemas de Infraestrutura

### ❌ Erro: "Container spark_master não está rodando"

**Sintomas:**
```bash
Error: No such container: spark_master
```

**Diagnóstico:**
```bash
make status
docker ps -a | grep spark
```

**Soluções:**

1. **Iniciar cluster:**
   ```bash
   make start
   ```

2. **Se container existir mas estar parado:**
   ```bash
   docker start spark_master spark_worker_1
   ```

3. **Se houver erro de porta em uso:**
   ```bash
   # Identificar processo usando porta 8080
   lsof -i :8080  # macOS/Linux
   netstat -ano | findstr :8080  # Windows
   
   # Matar processo ou mudar porta no docker-compose.yml
   ```

4. **Rebuild completo:**
   ```bash
   make stop
   docker-compose down -v
   make start
   ```

---

### ❌ Erro: "Health check failed"

**Sintomas:**
```
⚠️  Master: Não respondendo
```

**Diagnóstico:**
```bash
docker logs spark_master
docker exec spark_master curl http://localhost:8080
```

**Causas Comuns:**
- Container iniciando (aguarde 30s)
- Memória Docker insuficiente
- Conflito de portas

**Solução:**
```bash
# Verificar recursos Docker
docker info | grep -E "(Memory|CPUs)"

# Se memória < 4GB, aumentar em Docker Settings
# macOS: Docker Desktop → Preferences → Resources
# Linux: /etc/docker/daemon.json
{
  "resources": {
    "memory": "6G"
  }
}

# Reiniciar Docker
sudo systemctl restart docker  # Linux
# Ou reiniciar Docker Desktop
```

---

## 💾 Erros de Memória

### ❌ Erro: "Java Heap Space" ou "OutOfMemoryError"

**Sintomas:**
```
java.lang.OutOfMemoryError: Java heap space
Exception in thread "main" java.lang.OutOfMemoryError: GC overhead limit exceeded
```

**Diagnóstico:**
```bash
# Verificar recursos
make check-resources

# Verificar tamanho do dataset
make check-data
```

**Soluções por Ordem de Prioridade:**

1. **Usar dataset menor:**
   ```bash
   make clean
   make generate-small  # 5k nós ao invés de 10k
   make process
   ```

2. **Aumentar memória do Executor (docker-compose.yml):**
   ```yaml
   spark-worker:
     environment:
       - SPARK_WORKER_MEMORY=3G  # Era 2G
   ```

3. **Reduzir partições (community_detection.py):**
   ```python
   # Linha ~50
   shuffle_partitions = 50  # Era 100
   ```

4. **Desabilitar cache agressivo:**
   ```bash
   # Editar community_detection.py
   # Comentar linhas de cache:
   # g.vertices.cache()
   # g.edges.cache()
   ```

5. **Aumentar memória Docker:**
   ```bash
   # Linux: editar /etc/docker/daemon.json
   {
     "default-runtime": "runc",
     "data-root": "/var/lib/docker",
     "storage-driver": "overlay2",
     "memory": "6442450944"  # 6GB em bytes
   }
   ```

---

### ❌ Erro: "Container exited with code 137" (OOM Killed)

**Causa:** Linux OOM Killer matou o processo.

**Solução:**
```bash
# 1. Verificar logs do sistema
dmesg | grep -i "killed process"

# 2. Aumentar swap (temporário)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 3. Usar dataset menor ou reduzir recursos
make clean
make generate-small
```

---

## ⚡ Erros do Spark

### ❌ Erro: "graphframes package not found"

**Sintomas:**
```
java.lang.ClassNotFoundException: org.graphframes.GraphFrame
```

**Causa:** Maven package não foi baixado.

**Soluções:**

1. **Verificar conexão internet:**
   ```bash
   docker exec spark_master ping -c 3 repo1.maven.org
   ```

2. **Download manual:**
   ```bash
   docker exec spark_master spark-shell \
     --packages graphframes:graphframes:0.8.3-spark3.5-s_2.12
   # Aguardar download, depois Ctrl+D
   ```

3. **Limpar cache Maven:**
   ```bash
   docker exec spark_master rm -rf /root/.ivy2/cache
   ```

4. **Especificar repositório:**
   ```bash
   # Editar Makefile, adicionar:
   --repositories https://repo1.maven.org/maven2/
   ```

---

### ❌ Erro: Job "fica travado" em uma stage

**Sintomas:**
- UI mostra tasks pendentes por muito tempo
- Stage não progride após 5+ minutos

**Diagnóstico:**
```bash
# Acessar Spark UI
open http://localhost:4040

# Verificar:
# - Stages → Tasks: quantas estão running vs pending?
# - Executors: todos workers conectados?
# - Storage: cache excessivo?
```

**Causas e Soluções:**

1. **Worker não conectado:**
   ```bash
   make status
   # Se worker não aparecer:
   docker restart spark_worker_1
   ```

2. **Data skew (partições desbalanceadas):**
   ```bash
   # Editar community_detection.py, adicionar:
   .config("spark.sql.adaptive.skewJoin.enabled", "true")
   .config("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
   ```

3. **Muitas partições pequenas:**
   ```bash
   # Reduzir shuffle.partitions para 50
   # Ver seção "Otimizações"
   ```

4. **Checkpoint muito grande:**
   ```bash
   make clean-checkpoints
   ```

---

### ❌ Erro: "Checkpoint directory not set"

**Sintomas:**
```
java.lang.IllegalStateException: Checkpoint directory has not been set
```

**Causa:** GraphFrames EXIGE checkpoint para algoritmos iterativos.

**Solução Definitiva:**
```bash
# 1. Verificar se volume está montado
docker exec spark_master ls -la /opt/spark-checkpoints

# 2. Se não existir, criar manualmente:
docker exec spark_master mkdir -p /opt/spark-checkpoints
docker exec spark_master chmod 777 /opt/spark-checkpoints

# 3. Verificar código (community_detection.py linha ~70):
spark.sparkContext.setCheckpointDir("/opt/spark-checkpoints")
```

**Referência:** [GraphFrames User Guide - Checkpointing](https://graphframes.github.io/graphframes/docs/_site/user-guide.html#algorithms)

---

## 📊 Problemas com GraphFrames

### ❌ Erro: "Label Propagation returned empty results"

**Causa:** Grafo desconectado ou configuração incorreta.

**Diagnóstico:**
```python
# Verificar conectividade do grafo
results = g.connectedComponents()
num_components = results.select("component").distinct().count()
print(f"Componentes: {num_components}")

# Se > 1, grafo tem ilhas desconectadas
```

**Solução:**
```python
# Trabalhar apenas com maior componente
from pyspark.sql import Window

# Identificar maior componente
component_sizes = results.groupBy("component").count()
largest = component_sizes.orderBy(F.desc("count")).first()["component"]

# Filtrar grafo
vertices_filtered = results.filter(F.col("component") == largest)
edges_filtered = g.edges.join(
    vertices_filtered.select("id"),
    g.edges.src == vertices_filtered.id
)

g_filtered = GraphFrame(vertices_filtered, edges_filtered)
```

---

### ❌ Aviso: "LPA detectou comunidade dominante em scale-free"

**Sintoma:**
```
⚠️  Comunidade dominante detectada (scale-free trait)
```

**Explicação:** 
Label Propagation síncrono é conhecido por convergir para comunidades gigantes em redes power-law devido à influência de hubs.

**Isso é um bug?** 
Não! É comportamento esperado documentado na literatura.

**Alternativas:**

1. **Usar algoritmo Louvain (mais robusto para scale-free):**
   ```bash
   # Atualmente não implementado
   # Sugestão: contribuir com implementação!
   ```

2. **Usar Strongly Connected Components:**
   ```bash
   # Já implementado no pipeline
   make process  # Não usar --skip-cc
   ```

3. **Ajustar maxIter do LPA:**
   ```bash
   # Menos iterações podem evitar convergência prematura
   docker exec spark_master spark-submit ... \
     --lpa-iter 3  # Ao invés de 5
   ```

**Referência:** [Near linear time algorithm to detect community structures in large-scale networks](https://arxiv.org/abs/0709.2938)

---

## 🔍 Validação de Dados

### ❌ Erro: "Arestas com origem/destino inválido"

**Sintomas:**
```
ValueError: ❌ Grafo inválido: X arestas com src inválido
```

**Diagnóstico:**
```bash
# Verificar integridade dos CSVs
head -20 data/input/vertices.csv
head -20 data/input/edges.csv

# Verificar IDs únicos
cut -d',' -f1 data/input/vertices.csv | sort | uniq -d
```

**Causas:**
- Arquivo corrompido
- Encoding errado (UTF-8 esperado)
- Vírgulas dentro de valores

**Solução:**
```bash
# Regerar dados
make clean
make generate

# Se usando dados próprios:
# 1. Verificar formato CSV
# 2. Garantir colunas: id, src, dst
# 3. IDs devem ser strings únicas
```

---

### ❌ Erro: "CSV parsing failed"

**Sintomas:**
```
pyspark.sql.utils.AnalysisException: CSV format error
```

**Solução:**
```bash
# 1. Verificar delimitador
file data/input/vertices.csv

# 2. Verificar encoding
file -i data/input/vertices.csv

# 3. Se necessário, converter:
iconv -f ISO-8859-1 -t UTF-8 vertices.csv > vertices_utf8.csv

# 4. Remover caracteres especiais:
sed 's/[^a-zA-Z0-9,._-]//g' vertices.csv > vertices_clean.csv
```

---

## 🚀 Performance Issues

### 🐢 Job muito lento (>10min para 10k nós)

**Benchmarks Esperados:**
- 5k nós: ~2-3 minutos
- 10k nós: ~5-7 minutos
- 50k nós: ~15-25 minutos

**Diagnóstico:**
```bash
# 1. Acessar Spark UI
open http://localhost:4040/stages/

# 2. Identificar stage mais lenta
# 3. Verificar métricas:
#    - Shuffle Read/Write
#    - GC Time
#    - Task distribution
```

**Otimizações:**

1. **Reduzir partições:**
   ```python
   # community_detection.py
   shuffle_partitions = 50  # Para 2 cores
   ```

2. **Habilitar AQE:**
   ```python
   .config("spark.sql.adaptive.enabled", "true")
   .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
   ```

3. **Ajustar cache:**
   ```python
   # Apenas para datasets pequenos
   g.vertices.cache().count()
   g.edges.cache().count()
   ```

4. **Desabilitar checkpoints desnecessários:**
   ```python
   # Se LPA convergir rápido, reduzir checkpointInterval
   # Nota: NÃO remover checkpoint completamente!
   ```

5. **Usar SSD para checkpoint:**
   ```bash
   # Mudar volume no docker-compose.yml
   volumes:
     - /path/to/ssd/checkpoints:/opt/spark-checkpoints
   ```

---

### 📊 Shuffle excessivo (>10GB para dataset pequeno)

**Diagnóstico:**
```bash
# Spark UI → Stages → Shuffle Read
# Se shuffle > 10x tamanho do dataset = problema
```

**Causas:**
- Muitas partições
- Joins sem broadcast
- Cache não utilizado

**Soluções:**
```python
# 1. Usar broadcast para joins pequenos
from pyspark.sql.functions import broadcast
df.join(broadcast(small_df), "key")

# 2. Repartir antes de joins
df = df.repartition(50, "join_key")

# 3. Persistir DataFrames reutilizados
df.persist(StorageLevel.MEMORY_AND_DISK)
```

---

## 🆘 Comandos de Emergência

### 🔴 Sistema completamente travado

```bash
# 1. Forçar parada de tudo
docker kill $(docker ps -q)

# 2. Limpar recursos
make clean-all

# 3. Reiniciar Docker
sudo systemctl restart docker

# 4. Recomeçar do zero
make setup-dev
make start
make generate-small
make process-fast
```

---

### 🔴 Erro desconhecido - coletar logs

```bash
# Coletar informações para debug
mkdir -p debug-logs

# Logs do Spark
docker logs spark_master > debug-logs/master.log 2>&1
docker logs spark_worker_1 > debug-logs/worker.log 2>&1

# Configurações
docker exec spark_master env > debug-logs/env.txt
docker info > debug-logs/docker-info.txt
docker-compose config > debug-logs/compose-config.yml

# Compactar
tar -czf debug-$(date +%Y%m%d-%H%M%S).tar.gz debug-logs/

# Incluir em issue no GitHub
```

---

## 📚 Recursos Adicionais

### Documentação Oficial

1. **Apache Spark:**
   - [Performance Tuning](https://spark.apache.org/docs/3.5.0/sql-performance-tuning.html)
   - [Configuration](https://spark.apache.org/docs/3.5.0/configuration.html)
   - [Monitoring](https://spark.apache.org/docs/3.5.0/monitoring.html)

2. **GraphFrames:**
   - [User Guide](https://graphframes.github.io/graphframes/docs/_site/user-guide.html)
   - [API Docs](https://graphframes.github.io/graphframes/docs/_site/api/python/index.html)

3. **Docker:**
   - [Resource Constraints](https://docs.docker.com/config/containers/resource_constraints/)

### Debugging Avançado

```bash
# Modo debug verboso
docker exec spark_master spark-submit \
  --conf spark.log.level=DEBUG \
  --conf spark.eventLog.enabled=true \
  --conf spark.eventLog.dir=/opt/spark/logs \
  /opt/spark-apps/community_detection.py

# Analisar event logs
docker exec spark_master ls -lh /opt/spark/logs/
```

---

## ✅ Checklist de Diagnóstico

Antes de reportar bug, verifique:

- [ ] `make validate` passa sem erros
- [ ] Docker tem ≥4GB RAM configurado
- [ ] Cluster está saudável (`make health-check`)
- [ ] Dataset foi gerado corretamente (`make check-data`)
- [ ] Versões corretas (Spark 3.5.0, GraphFrames 0.8.3)
- [ ] Logs coletados (`docker logs spark_master`)
- [ ] Tentou `make clean && make start`

---

**💡 Dica:** A maioria dos problemas se resolve com:
```bash
make clean-all && make setup-dev && make quick-test
```