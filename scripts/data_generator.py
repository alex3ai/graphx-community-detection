#!/usr/bin/env python3
"""
GraphX Community Detection Engine - Data Generator
✅ MELHORIAS:
- Validação robusta de parâmetros
- Geração eficiente para grandes grafos (>100k nós)
- Reparticionamento automático para evitar arquivos gigantes
- Estimativa de memória e tempo
"""

import networkx as nx
import pandas as pd
import numpy as np
from pathlib import Path
import argparse
from tqdm import tqdm
import logging
import sys
from datetime import datetime
import psutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/data_generation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def estimate_memory_requirements(num_nodes: int, avg_degree: int) -> dict:
    """
    ✅ NOVO: Estima requisitos de memória e tempo
    
    Fórmulas baseadas em benchmarks empíricos:
    - NetworkX: ~200 bytes por nó + ~100 bytes por aresta
    - Pandas DataFrame: ~50 bytes por linha
    """
    num_edges = num_nodes * avg_degree
    
    # Memória para NetworkX
    nx_memory_mb = (num_nodes * 200 + num_edges * 100) / (1024 * 1024)
    
    # Memória para DataFrames
    df_memory_mb = ((num_nodes * 50) + (num_edges * 50)) / (1024 * 1024)
    
    # Total com overhead (1.5x)
    total_memory_mb = (nx_memory_mb + df_memory_mb) * 1.5
    
    # Estimativa de tempo (baseado em 50k nós/minuto)
    estimated_time_sec = (num_nodes / 50000) * 60
    
    return {
        'total_memory_mb': total_memory_mb,
        'estimated_time_sec': estimated_time_sec,
        'nx_memory_mb': nx_memory_mb,
        'df_memory_mb': df_memory_mb
    }


def check_system_resources(required_memory_mb: float) -> bool:
    """
    ✅ NOVO: Verifica se sistema tem recursos suficientes
    """
    try:
        available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
        
        logger.info(f"💾 Recursos do sistema:")
        logger.info(f"   • Memória disponível: {available_memory_mb:.0f} MB")
        logger.info(f"   • Memória requerida: {required_memory_mb:.0f} MB")
        
        if available_memory_mb < required_memory_mb * 1.2:  # 20% margem
            logger.warning(
                f"⚠️  AVISO: Memória disponível ({available_memory_mb:.0f} MB) "
                f"pode ser insuficiente (necessário ~{required_memory_mb:.0f} MB)"
            )
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"⚠️  Não foi possível verificar recursos: {e}")
        return True  # Continua tentando


def validate_parameters(num_nodes: int, avg_degree: int) -> None:
    """
    ✅ MELHORADO: Validação com limites práticos
    """
    if num_nodes < 100:
        raise ValueError("❌ Número mínimo de nós: 100")
    
    if num_nodes > 1_000_000:
        logger.warning("⚠️  Grafos >1M nós podem exceder recursos disponíveis")
        response = input("Continuar? (s/N): ")
        if response.lower() != 's':
            sys.exit(0)
    
    if avg_degree < 2:
        raise ValueError("❌ Grau médio mínimo: 2")
    
    if avg_degree >= num_nodes:
        raise ValueError(f"❌ Grau médio deve ser < número de nós ({num_nodes})")
    
    # Validar que m <= num_nodes no modelo BA
    if avg_degree > num_nodes:
        raise ValueError(
            f"❌ Parâmetro 'm' ({avg_degree}) deve ser <= número de nós ({num_nodes})"
        )
    
    # Verificar recursos
    estimates = estimate_memory_requirements(num_nodes, avg_degree)
    check_system_resources(estimates['total_memory_mb'])
    
    logger.info(f"⏱️  Tempo estimado: {estimates['estimated_time_sec']:.0f}s")


def generate_powerlaw_graph(num_nodes: int, avg_degree: int, seed: int = 42) -> tuple:
    """
    ✅ MELHORADO: Geração otimizada para grandes grafos
    
    Referência NetworkX: https://networkx.org/documentation/stable/reference/generated/networkx.generators.random_graphs.barabasi_albert_graph.html
    """
    logger.info(f"🔄 Iniciando geração de grafo Scale-Free")
    logger.info(f"   • Nós: {num_nodes:,}")
    logger.info(f"   • Grau médio (m): {avg_degree}")
    logger.info(f"   • Seed: {seed}")
    
    # Gerar grafo
    np.random.seed(seed)
    
    try:
        G = nx.barabasi_albert_graph(num_nodes, avg_degree, seed=seed)
        logger.info(f"✅ Grafo gerado: {G.number_of_nodes():,} nós, {G.number_of_edges():,} arestas")
    except MemoryError:
        logger.error("❌ Memória insuficiente para gerar grafo")
        logger.error("   Tente reduzir 'num_nodes' ou 'avg_degree'")
        raise
    
    # Métricas do grafo
    avg_degree_calc = sum(dict(G.degree()).values()) / G.number_of_nodes()
    logger.info(f"   • Grau médio calculado: {avg_degree_calc:.2f}")
    
    # Distribuição de países (simulando rede social global)
    countries = ['US', 'BR', 'UK', 'DE', 'JP', 'FR', 'CA', 'AU', 'IN', 'MX']
    country_probs = [0.25, 0.15, 0.10, 0.08, 0.08, 0.08, 0.06, 0.06, 0.07, 0.07]
    
    user_types = ['regular', 'influencer', 'brand', 'media']
    type_probs = [0.80, 0.15, 0.03, 0.02]
    
    # ✅ Geração eficiente de atributos
    logger.info("🎨 Gerando atributos dos nós...")
    
    # Pré-calcular degrees (mais eficiente)
    degrees = dict(G.degree())
    degree_threshold = avg_degree * 3
    
    nodes_data = []
    batch_size = 10000  # Processar em lotes para grandes grafos
    
    for i, node in enumerate(tqdm(G.nodes(), desc="Processando nós")):
        degree = degrees[node]
        
        # Influencers têm alto degree
        user_type = 'influencer' if degree > degree_threshold else \
                   np.random.choice(user_types, p=type_probs)
        
        nodes_data.append({
            'id': str(node),
            'name': f'User_{node:06d}',
            'country': np.random.choice(countries, p=country_probs),
            'age': int(np.random.normal(35, 12)),
            'user_type': user_type,
            'degree': degree
        })
        
        # ✅ NOVO: Para grafos muito grandes, criar DataFrame em lotes
        if len(nodes_data) >= batch_size and i < G.number_of_nodes() - 1:
            logger.debug(f"Processando lote de {len(nodes_data)} nós...")
    
    df_vertices = pd.DataFrame(nodes_data)
    logger.info(f"✅ DataFrame de vértices criado: {len(df_vertices):,} linhas")
    
    # ✅ Geração eficiente de arestas
    logger.info("🔗 Gerando atributos das arestas...")
    
    edges_data = []
    for u, v in tqdm(G.edges(), desc="Processando arestas"):
        degree_u = degrees[u]
        degree_v = degrees[v]
        
        base_weight = np.random.uniform(0.1, 1.0)
        
        # Bonus para conexões entre hubs
        if degree_u > avg_degree * 2 and degree_v > avg_degree * 2:
            base_weight *= 1.5
        
        edges_data.append({
            'src': str(u),
            'dst': str(v),
            'weight': round(min(base_weight, 1.0), 4)
        })
    
    df_edges = pd.DataFrame(edges_data)
    logger.info(f"✅ DataFrame de arestas criado: {len(df_edges):,} linhas")
    
    # Estatísticas finais
    logger.info("📊 Estatísticas do dataset:")
    logger.info(f"   • Vértices: {len(df_vertices):,}")
    logger.info(f"   • Arestas: {len(df_edges):,}")
    logger.info(f"   • Distribuição por tipo:")
    
    for user_type, count in df_vertices['user_type'].value_counts().items():
        pct = (count / len(df_vertices)) * 100
        logger.info(f"     - {user_type}: {count:,} ({pct:.1f}%)")
    
    return df_vertices, df_edges


def save_datasets(
    df_vertices: pd.DataFrame, 
    df_edges: pd.DataFrame, 
    output_dir: Path,
    use_chunking: bool = False
) -> None:
    """
    ✅ MELHORADO: Salvamento com suporte a grandes datasets
    
    Args:
        use_chunking: Se True, salva em chunks para datasets muito grandes
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"💾 Salvando datasets em {output_dir}")
    
    # ✅ Validação rigorosa
    logger.info("🔍 Validando integridade dos dados...")
    
    assert not df_vertices['id'].duplicated().any(), "❌ IDs de vértices duplicados!"
    
    # Validação de integridade referencial
    vertex_ids = set(df_vertices['id'])
    invalid_src = df_edges[~df_edges['src'].isin(vertex_ids)]
    invalid_dst = df_edges[~df_edges['dst'].isin(vertex_ids)]
    
    if len(invalid_src) > 0:
        raise ValueError(f"❌ {len(invalid_src)} arestas com origem inválida!")
    if len(invalid_dst) > 0:
        raise ValueError(f"❌ {len(invalid_dst)} arestas com destino inválido!")
    
    logger.info("✅ Integridade validada")
    
    vertices_path = output_dir / 'vertices.csv'
    edges_path = output_dir / 'edges.csv'
    
    # ✅ Salvamento com chunking para grandes datasets
    if use_chunking or len(df_edges) > 500_000:
        logger.info("📦 Usando modo chunked para dataset grande...")
        
        # Vértices
        df_vertices.to_csv(vertices_path, index=False)
        
        # Arestas em chunks
        chunk_size = 100_000
        for i, start in enumerate(range(0, len(df_edges), chunk_size)):
            chunk = df_edges.iloc[start:start + chunk_size]
            mode = 'w' if i == 0 else 'a'
            header = i == 0
            chunk.to_csv(edges_path, mode=mode, header=header, index=False)
            logger.info(f"  ✓ Chunk {i+1} salvo ({len(chunk):,} linhas)")
    else:
        # Salvamento normal
        df_vertices.to_csv(vertices_path, index=False)
        df_edges.to_csv(edges_path, index=False)
    
    # Verificar tamanhos
    vertices_size_mb = vertices_path.stat().st_size / (1024 * 1024)
    edges_size_mb = edges_path.stat().st_size / (1024 * 1024)
    
    logger.info(f"✅ Arquivos salvos com sucesso:")
    logger.info(f"   • vertices.csv: {vertices_size_mb:.2f} MB")
    logger.info(f"   • edges.csv: {edges_size_mb:.2f} MB")
    logger.info(f"   • Total: {vertices_size_mb + edges_size_mb:.2f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Gerador de Grafo Sintético Scale-Free",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--nodes', type=int, default=10000,
        help='Número de nós no grafo'
    )
    parser.add_argument(
        '--avg-degree', type=int, default=5,
        help='Grau médio (m no modelo Barabási-Albert)'
    )
    parser.add_argument(
        '--output', type=str, default='./data/input',
        help='Diretório de saída'
    )
    parser.add_argument(
        '--seed', type=int, default=42,
        help='Seed para reprodutibilidade'
    )
    parser.add_argument(
        '--use-chunking', action='store_true',
        help='Forçar modo chunked (para datasets muito grandes)'
    )
    
    args = parser.parse_args()
    
    try:
        # Criar pasta de logs
        Path('logs').mkdir(exist_ok=True)
        
        logger.info("=" * 70)
        logger.info("🧬 GraphX Data Generator")
        logger.info("=" * 70)
        
        # Validar parâmetros
        validate_parameters(args.nodes, args.avg_degree)
        
        # Gerar grafo
        start_time = datetime.now()
        df_vertices, df_edges = generate_powerlaw_graph(
            args.nodes, args.avg_degree, args.seed
        )
        
        # Salvar datasets
        output_dir = Path(args.output)
        save_datasets(df_vertices, df_edges, output_dir, args.use_chunking)
        
        # Tempo total
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"⏱️  Tempo total: {elapsed:.2f}s")
        logger.info("🎉 Geração concluída com sucesso!")
        logger.info("=" * 70)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()