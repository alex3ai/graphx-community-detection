# íµ¸ï¸ GraphX Community Detection Engine

Motor de inteligÃªncia para detecÃ§Ã£o de comunidades e anÃ¡lise de influÃªncia em redes sociais usando Apache Spark e GraphFrames.

## í¾¯ Objetivo
Validar eficiÃªncia e escalabilidade de algoritmos de grafos distribuÃ­dos (PageRank, Label Propagation) em topologias Scale-Free com recursos limitados.

## í¿—ï¸ Arquitetura
- **Engine**: Apache Spark 3.5 + GraphFrames
- **Infraestrutura**: Docker Compose (2GB RAM, 2 Cores)
- **SerializaÃ§Ã£o**: Kryo
- **Storage**: Parquet particionado

## íº€ Quick Start
```bash
# 1. Validar ambiente
bash validate_environment.sh

# 2. Instalar dependÃªncias
make setup

# 3. Iniciar cluster
make start

# 4. Executar pipeline completo
make all
```

## í³Š Resultados
- DetecÃ§Ã£o de comunidades (Label Propagation)
- IdentificaÃ§Ã£o de influenciadores (PageRank)
- AnÃ¡lise de conectividade (Connected Components)

## í³– DocumentaÃ§Ã£o Completa
Consulte `/docs` para guias detalhados.
