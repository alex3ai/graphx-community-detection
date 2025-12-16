#!/usr/bin/env python3
"""
GraphX Community Detection Engine - Spark Processing Pipeline
✅ OTIMIZAÇÕES IMPLEMENTADAS:
- Checkpoint persistente
- Particionamento dinâmico baseado em recursos
- Tratamento robusto de erros
- Métricas detalhadas de performance
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *
from graphframes import GraphFrame
import argparse
import time
import os
import sys
from datetime import datetime

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


def calculate_optimal_partitions(num_cores: int, dataset_size: str = 'medium') -> int:
    """
    ✅ NOVO: Calcula número ótimo de partições baseado em recursos
    
    Referência: Spark Performance Tuning Guide
    https://spark.apache.org/docs/3.5.0/sql-performance-tuning.html
    
    Regra: 2-5x número de cores disponíveis
    """
    size_multipliers = {
        'small': 2,   # <10k nós
        'medium': 4,  # 10-50k nós
        'large': 6    # >50k nós
    }
    
    multiplier = size_multipliers.get(dataset_size, 4)
    optimal = num_cores * multiplier
    
    # Limites mínimo e máximo
    return max(8, min(optimal, 200))


def create_spark_session(
    app_name: str, 
    master: str, 
    shuffle_partitions: int = None,
    auto_tune: bool = True
) -> SparkSession:
    """
    ✅ MELHORADO: Criação de sessão com auto-tuning
    """
    print("⚡ Inicializando Spark Session com otimizações...")
    
    # Auto-detectar cores disponíveis se não especificado
    if shuffle_partitions is None and auto_tune:
        # Padrão conservador para recursos limitados
        shuffle_partitions = calculate_optimal_partitions(2, 'medium')
        print(f"  🎯 Auto-tuning: {shuffle_partitions} partições calculadas")
    elif shuffle_partitions is None:
        shuffle_partitions = 50  # Fallback conservador
    
    builder = SparkSession.builder \
        .appName(app_name) \
        .master(master) \
        .config("spark.jars.packages", "graphframes:graphframes:0.8.3-spark3.5-s_2.12")
    
    # Configurações de serialização (Kryo obrigatório para GraphFrames)
    builder = builder \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.kryo.registrationRequired", "false") \
        .config("spark.kryoserializer.buffer.max", "256m")
    
    # ✅ Particionamento otimizado
    builder = builder \
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions)) \
        .config("spark.default.parallelism", str(shuffle_partitions))
    
    # ✅ Adaptive Query Execution (crítico para grafos)
    # Referência: https://spark.apache.org/docs/3.5.0/sql-performance-tuning.html#adaptive-query-execution
    builder = builder \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.enabled", "true") \
        .config("spark.sql.adaptive.localShuffleReader.enabled", "true")
    
    # Configurações de memória
    builder = builder \
        .config("spark.memory.fraction", "0.6") \
        .config("spark.memory.storageFraction", "0.5")
    
    # ✅ Cleanup automático de checkpoints
    builder = builder \
        .config("spark.cleaner.referenceTracking.cleanCheckpoints", "true")
    
    spark = builder.getOrCreate()
    
    # ✅ CRÍTICO: Checkpoint persistente
    # Referência GraphFrames: https://graphframes.github.io/graphframes/docs/_site/user-guide.html
    checkpoint_dir = "/opt/spark-checkpoints"
    
    # Criar diretório se não existir (seguro no container)
    try:
        os.makedirs(checkpoint_dir, exist_ok=True)
        spark.sparkContext.setCheckpointDir(checkpoint_dir)
        print(f"  ✅ Checkpoint configurado: {checkpoint_dir}")
    except Exception as e:
        print(f"  ⚠️  Aviso ao configurar checkpoint: {e}")
        # Fallback para /tmp se falhar
        spark.sparkContext.setCheckpointDir("/tmp/spark-checkpoints")
    
    # Log level
    spark.sparkContext.setLogLevel("WARN")
    
    print(f"  ✅ Spark {spark.version} inicializado")
    print(f"  • Master: {master}")
    print(f"  • Shuffle Partitions: {shuffle_partitions}")
    print(f"  • AQE: Enabled")
    
    return spark


def load_graph(spark: SparkSession, input_dir: str) -> GraphFrame:
    """
    ✅ MELHORADO: Carregamento com validação robusta
    """
    print(f"\n📂 Carregando dados de: {input_dir}")
    
    vertices_path = f"{input_dir}/vertices.csv"
    edges_path = f"{input_dir}/edges.csv"
    
    try:
        # Carregar vértices
        v = spark.read.csv(vertices_path, header=True, inferSchema=True)
        
        # Validação obrigatória
        if 'id' not in v.columns:
            raise ValueError("❌ Vértices devem conter coluna 'id'")
        
        vertex_count = v.count()
        print(f"  ✓ Vértices: {vertex_count:,} registros")
        
        # Carregar arestas
        e = spark.read.csv(edges_path, header=True, inferSchema=True)
        
        if 'src' not in e.columns or 'dst' not in e.columns:
            raise ValueError("❌ Arestas devem conter 'src' e 'dst'")
        
        edge_count = e.count()
        print(f"  ✓ Arestas: {edge_count:,} registros")
        
        # ✅ Validação de integridade referencial
        print("  🔍 Validando integridade do grafo...")
        vertex_ids = v.select("id").distinct()
        
        invalid_src = e.join(vertex_ids, e.src == vertex_ids.id, "left_anti")
        invalid_dst = e.join(vertex_ids, e.dst == vertex_ids.id, "left_anti")
        
        invalid_src_count = invalid_src.count()
        invalid_dst_count = invalid_dst.count()
        
        if invalid_src_count > 0 or invalid_dst_count > 0:
            raise ValueError(
                f"❌ Grafo inválido: {invalid_src_count} arestas com src inválido, "
                f"{invalid_dst_count} com dst inválido"
            )
        
        print("  ✅ Integridade validada")
        
        # Criar GraphFrame
        print("  🔨 Construindo GraphFrame...")
        g = GraphFrame(v, e)
        
        # ✅ Cache estratégico
        # Referência: https://spark.apache.org/docs/3.5.0/rdd-programming-guide.html#rdd-persistence
        g.vertices.cache()
        g.edges.cache()
        
        # Forçar materialização
        g.vertices.count()
        g.edges.count()
        
        # Métricas do grafo
        avg_degree = (2.0 * edge_count) / vertex_count
        print(f"  📊 Métricas:")
        print(f"     • Grau médio: {avg_degree:.2f}")
        print(f"     • Densidade: {(2.0 * edge_count) / (vertex_count * (vertex_count - 1)):.6f}")
        
        print("  ✅ GraphFrame criado e cacheado")
        return g
        
    except Exception as e:
        print(f"\n❌ ERRO ao carregar grafo: {e}")
        raise


def run_pagerank(g: GraphFrame, output_dir: str, max_iter: int = 10) -> dict:
    """
    ✅ MELHORADO: PageRank com métricas detalhadas
    
    Referência: https://graphframes.github.io/graphframes/docs/_site/api/python/graphframes.html#graphframes.GraphFrame.pageRank
    """
    print(f"\n🚀 Executando PageRank (maxIter={max_iter})...")
    start_time = time.time()
    
    try:
        # PageRank com checkpoint automático
        results = g.pageRank(resetProbability=0.15, maxIter=max_iter)
        
        # Selecionar e ordenar
        pr_output = results.vertices \
            .select("id", "name", "pagerank", "country", "user_type") \
            .orderBy(F.desc("pagerank"))
        
        # ✅ Salvar com particionamento por país
        output_path = f"{output_dir}/pagerank"
        pr_output.write \
            .mode("overwrite") \
            .partitionBy("country") \
            .parquet(output_path)
        
        elapsed = time.time() - start_time
        
        # Estatísticas detalhadas
        stats = pr_output.select(
            F.count("*").alias("total"),
            F.max("pagerank").alias("max_pr"),
            F.mean("pagerank").alias("avg_pr"),
            F.stddev("pagerank").alias("std_pr")
        ).collect()[0]
        
        metrics = {
            'duration': elapsed,
            'total_nodes': stats['total'],
            'max_pagerank': stats['max_pr'],
            'avg_pagerank': stats['avg_pr'],
            'std_pagerank': stats['std_pr']
        }
        
        print(f"  ✅ PageRank concluído em {elapsed:.2f}s")
        print(f"     • Nós processados: {metrics['total_nodes']:,}")
        print(f"     • PageRank máximo: {metrics['max_pagerank']:.6f}")
        print(f"     • PageRank médio: {metrics['avg_pagerank']:.6f}")
        print(f"     • Desvio padrão: {metrics['std_pagerank']:.6f}")
        print(f"     • Salvo em: {output_path}")
        
        return metrics
        
    except Exception as e:
        print(f"  ❌ Erro no PageRank: {e}")
        raise


def run_label_propagation(g: GraphFrame, output_dir: str, max_iter: int = 5) -> dict:
    """
    ✅ MELHORADO: LPA com análise de qualidade
    
    Nota: LPA pode ser instável em grafos scale-free (documentado em análise)
    Referência: https://graphframes.github.io/graphframes/docs/_site/user-guide.html#label-propagation-algorithm-lpa
    """
    print(f"\n🏘️  Executando Label Propagation (maxIter={max_iter})...")
    start_time = time.time()
    
    try:
        results = g.labelPropagation(maxIter=max_iter)
        
        # Calcular tamanhos de comunidades
        community_sizes = results.groupBy("label") \
            .count() \
            .withColumnRenamed("count", "community_size")
        
        results_enriched = results.join(community_sizes, "label")
        
        # Salvar
        output_path = f"{output_dir}/communities"
        results_enriched.write \
            .mode("overwrite") \
            .partitionBy("label") \
            .parquet(output_path)
        
        elapsed = time.time() - start_time
        
        # Estatísticas
        comm_stats = community_sizes.select(
            F.count("*").alias("num_communities"),
            F.max("community_size").alias("largest"),
            F.mean("community_size").alias("avg_size"),
            F.stddev("community_size").alias("std_size")
        ).collect()[0]
        
        metrics = {
            'duration': elapsed,
            'num_communities': comm_stats['num_communities'],
            'largest_community': comm_stats['largest'],
            'avg_size': comm_stats['avg_size'],
            'std_size': comm_stats['std_size'] if comm_stats['std_size'] else 0
        }
        
        print(f"  ✅ Label Propagation concluído em {elapsed:.2f}s")
        print(f"     • Comunidades: {metrics['num_communities']:,}")
        print(f"     • Maior: {metrics['largest_community']:,} membros")
        print(f"     • Tamanho médio: {metrics['avg_size']:.1f}")
        print(f"     • Salvo em: {output_path}")
        
        # ⚠️ Aviso para grafos scale-free
        if metrics['largest_community'] > metrics['avg_size'] * 10:
            print(f"     ⚠️  Comunidade dominante detectada (scale-free trait)")
        
        return metrics
        
    except Exception as e:
        print(f"  ❌ Erro no Label Propagation: {e}")
        raise


def run_connected_components(g: GraphFrame, output_dir: str) -> dict:
    """
    ✅ MELHORADO: SCC com análise de conectividade
    """
    print(f"\n🔗 Executando Connected Components...")
    start_time = time.time()
    
    try:
        results = g.connectedComponents()
        
        component_sizes = results.groupBy("component") \
            .count() \
            .withColumnRenamed("count", "component_size")
        
        results_enriched = results.join(component_sizes, "component")
        
        output_path = f"{output_dir}/connected_components"
        results_enriched.write \
            .mode("overwrite") \
            .parquet(output_path)
        
        elapsed = time.time() - start_time
        
        # Estatísticas
        total_nodes = results.count()
        comp_stats = component_sizes.select(
            F.count("*").alias("num_components"),
            F.max("component_size").alias("largest")
        ).collect()[0]
        
        metrics = {
            'duration': elapsed,
            'num_components': comp_stats['num_components'],
            'largest_component': comp_stats['largest'],
            'largest_pct': (comp_stats['largest'] / total_nodes) * 100
        }
        
        print(f"  ✅ Connected Components concluído em {elapsed:.2f}s")
        print(f"     • Componentes: {metrics['num_components']:,}")
        print(f"     • Maior: {metrics['largest_component']:,} nós ({metrics['largest_pct']:.1f}%)")
        print(f"     • Salvo em: {output_path}")
        
        return metrics
        
    except Exception as e:
        print(f"  ❌ Erro no Connected Components: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="GraphX Community Detection Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--input', default='/opt/spark-data/input')
    parser.add_argument('--output', default='/opt/spark-data/output')
    parser.add_argument('--master', default='spark://spark-master:7077')
    parser.add_argument('--shuffle-partitions', type=int, default=None, 
                       help='Se não especificado, usa auto-tuning')
    parser.add_argument('--pagerank-iter', type=int, default=10)
    parser.add_argument('--lpa-iter', type=int, default=5)
    parser.add_argument('--skip-cc', action='store_true')
    parser.add_argument('--no-auto-tune', action='store_true',
                       help='Desabilita auto-tuning de partições')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🕸️  GraphX Community Detection Engine")
    print("=" * 70)
    print(f"Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    spark = None
    metrics_summary = {}
    
    try:
        # Criar sessão
        spark = create_spark_session(
            "GraphX Community Detection",
            args.master,
            args.shuffle_partitions,
            auto_tune=not args.no_auto_tune
        )
        
        # Carregar grafo
        g = load_graph(spark, args.input)
        
        # Executar algoritmos
        total_start = time.time()
        
        metrics_summary['pagerank'] = run_pagerank(g, args.output, args.pagerank_iter)
        metrics_summary['lpa'] = run_label_propagation(g, args.output, args.lpa_iter)
        
        if not args.skip_cc:
            metrics_summary['cc'] = run_connected_components(g, args.output)
        else:
            print("\n⏭️  Connected Components pulado (--skip-cc)")
        
        total_elapsed = time.time() - total_start
        
        print("\n" + "=" * 70)
        print(f"✨ Pipeline finalizado com sucesso!")
        print(f"⏱️  Tempo total: {total_elapsed:.2f}s")
        print(f"📁 Resultados: {args.output}")
        
        # Resumo de métricas
        print("\n📊 RESUMO DE MÉTRICAS:")
        for algo, metrics in metrics_summary.items():
            print(f"\n  {algo.upper()}:")
            for key, value in metrics.items():
                if isinstance(value, float):
                    print(f"    • {key}: {value:.2f}")
                else:
                    print(f"    • {key}: {value:,}")
        
        print("=" * 70)
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ Erro fatal no pipeline: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        if spark:
            print("\n🛑 Finalizando Spark Session...")
            spark.stop()


if __name__ == "__main__":
    main()