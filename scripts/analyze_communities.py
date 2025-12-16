#!/usr/bin/env python3
"""
GraphX Community Detection Engine - Analysis & Visualization
Gera insights e visualizações dos resultados do processamento
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import glob
import logging
import sys
from datetime import datetime

# Configuração
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['figure.figsize'] = (14, 7)
plt.rcParams['font.size'] = 10

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_PATH = Path('./data/output')
OUTPUT_GRAPHS = Path('./analysis/graphs')
OUTPUT_METRICS = Path('./analysis/metrics')


def read_parquet_folder(folder_path: Path) -> pd.DataFrame:
    """
    Lê todos arquivos Parquet de uma pasta (incluindo partições)
    
    Args:
        folder_path: Caminho da pasta
    
    Returns:
        DataFrame consolidado
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {folder_path}")
    
    parquet_files = list(folder_path.rglob("*.parquet"))
    
    if not parquet_files:
        raise FileNotFoundError(f"Nenhum arquivo .parquet encontrado em {folder_path}")
    
    logger.info(f"📂 Lendo {len(parquet_files)} arquivo(s) de {folder_path.name}")
    return pd.read_parquet(folder_path)


def analyze_pagerank(save_plots: bool = True) -> dict:
    """Analisa resultados do PageRank"""
    logger.info("📈 Analisando PageRank...")
    
    try:
        df = read_parquet_folder(INPUT_PATH / 'pagerank')
    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
        return {}
    
    # Estatísticas básicas
    stats = {
        'total_nodes': len(df),
        'avg_pagerank': df['pagerank'].mean(),
        'median_pagerank': df['pagerank'].median(),
        'std_pagerank': df['pagerank'].std(),
        'max_pagerank': df['pagerank'].max(),
        'min_pagerank': df['pagerank'].min()
    }
    
    logger.info(f"  • Total de nós: {stats['total_nodes']:,}")
    logger.info(f"  • PageRank médio: {stats['avg_pagerank']:.6f}")
    logger.info(f"  • PageRank máximo: {stats['max_pagerank']:.6f}")
    
    # Top Influenciadores
    top_n = 20
    top_influencers = df.nlargest(top_n, 'pagerank')
    
    print("\n" + "="*70)
    print(f"🏆 TOP {top_n} INFLUENCIADORES")
    print("="*70)
    print(top_influencers[['name', 'pagerank', 'country', 'user_type']].to_string(index=False))
    print("="*70 + "\n")
    
    # Análise por tipo de usuário
    if 'user_type' in df.columns:
        type_stats = df.groupby('user_type')['pagerank'].agg(['mean', 'median', 'count'])
        logger.info("\n📊 PageRank médio por tipo de usuário:")
        print(type_stats.to_string())
    
    if save_plots:
        OUTPUT_GRAPHS.mkdir(parents=True, exist_ok=True)
        
        # 1. Distribuição Log-Log
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Histograma normal
        axes[0].hist(df['pagerank'], bins=50, edgecolor='black', alpha=0.7)
        axes[0].set_xlabel('PageRank Score')
        axes[0].set_ylabel('Frequência')
        axes[0].set_title('Distribuição de PageRank')
        axes[0].grid(True, alpha=0.3)
        
        # Histograma log-log
        axes[1].hist(df['pagerank'], bins=50, edgecolor='black', alpha=0.7)
        axes[1].set_xscale('log')
        axes[1].set_yscale('log')
        axes[1].set_xlabel('PageRank Score (log)')
        axes[1].set_ylabel('Frequência (log)')
        axes[1].set_title('Distribuição de PageRank (Log-Log) - Lei de Potência')
        axes[1].grid(True, alpha=0.3, which='both')
        
        plt.tight_layout()
        plt.savefig(OUTPUT_GRAPHS / 'pagerank_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Top Influenciadores
        fig, ax = plt.subplots(figsize=(12, 8))
        top_20 = df.nlargest(20, 'pagerank')
        
        colors = plt.cm.viridis(np.linspace(0.3, 0.9, 20))
        bars = ax.barh(range(20), top_20['pagerank'].values, color=colors)
        ax.set_yticks(range(20))
        ax.set_yticklabels(top_20['name'].values)
        ax.set_xlabel('PageRank Score')
        ax.set_title('Top 20 Influenciadores', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3, axis='x')
        
        # Adicionar valores nas barras
        for i, (idx, row) in enumerate(top_20.iterrows()):
            ax.text(row['pagerank'], i, f" {row['pagerank']:.6f}", 
                   va='center', fontsize=8)
        
        plt.tight_layout()
        plt.savefig(OUTPUT_GRAPHS / 'top_influencers.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Distribuição por país
        if 'country' in df.columns:
            fig, ax = plt.subplots(figsize=(12, 6))
            country_dist = df.groupby('country')['pagerank'].mean().sort_values(ascending=False)
            
            country_dist.plot(kind='bar', ax=ax, color='steelblue', edgecolor='black')
            ax.set_xlabel('País')
            ax.set_ylabel('PageRank Médio')
            ax.set_title('PageRank Médio por País')
            ax.grid(True, alpha=0.3, axis='y')
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            plt.savefig(OUTPUT_GRAPHS / 'pagerank_by_country.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        logger.info(f"  ✓ Gráficos salvos em {OUTPUT_GRAPHS}")
    
    return stats


def analyze_communities(save_plots: bool = True) -> dict:
    """Analisa comunidades detectadas"""
    logger.info("\n🏘️  Analisando Comunidades...")
    
    try:
        df = read_parquet_folder(INPUT_PATH / 'communities')
    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
        return {}
    
    # Estatísticas de comunidades
    community_sizes = df['label'].value_counts().sort_values(ascending=False)
    
    stats = {
        'total_nodes': len(df),
        'num_communities': len(community_sizes),
        'largest_community': int(community_sizes.iloc[0]),
        'smallest_community': int(community_sizes.iloc[-1]),
        'avg_community_size': float(community_sizes.mean()),
        'median_community_size': float(community_sizes.median())
    }
    
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS DE COMUNIDADES")
    print("="*70)
    print(f"Total de Comunidades: {stats['num_communities']:,}")
    print(f"Maior Comunidade: {stats['largest_community']:,} membros")
    print(f"Menor Comunidade: {stats['smallest_community']:,} membros")
    print(f"Tamanho Médio: {stats['avg_community_size']:.2f} membros")
    print(f"Mediana: {stats['median_community_size']:.0f} membros")
    print("="*70 + "\n")
    
    # Distribuição de tamanhos
    size_distribution = community_sizes.value_counts().sort_index()
    logger.info("Distribuição de tamanhos de comunidades:")
    for size, count in size_distribution.head(10).items():
        logger.info(f"  • {count} comunidades com {size} membros")
    
    if save_plots:
        OUTPUT_GRAPHS.mkdir(parents=True, exist_ok=True)
        
        # 1. Top 30 Comunidades
        fig, ax = plt.subplots(figsize=(14, 8))
        top_30 = community_sizes.head(30)
        
        colors = plt.cm.plasma(np.linspace(0.2, 0.9, 30))
        bars = ax.bar(range(30), top_30.values, color=colors, edgecolor='black')
        
        ax.set_xlabel('Ranking da Comunidade')
        ax.set_ylabel('Número de Membros')
        ax.set_title('Top 30 Maiores Comunidades', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Adicionar valores nas barras
        for i, v in enumerate(top_30.values):
            ax.text(i, v, f'{v:,}', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        plt.savefig(OUTPUT_GRAPHS / 'top_communities.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. Distribuição de Tamanhos (Histograma)
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Normal
        axes[0].hist(community_sizes.values, bins=50, edgecolor='black', alpha=0.7, color='coral')
        axes[0].set_xlabel('Tamanho da Comunidade')
        axes[0].set_ylabel('Frequência')
        axes[0].set_title('Distribuição de Tamanhos de Comunidades')
        axes[0].grid(True, alpha=0.3)
        
        # Log scale
        axes[1].hist(community_sizes.values, bins=50, edgecolor='black', alpha=0.7, color='coral')
        axes[1].set_xscale('log')
        axes[1].set_yscale('log')
        axes[1].set_xlabel('Tamanho da Comunidade (log)')
        axes[1].set_ylabel('Frequência (log)')
        axes[1].set_title('Distribuição Log-Log')
        axes[1].grid(True, alpha=0.3, which='both')
        
        plt.tight_layout()
        plt.savefig(OUTPUT_GRAPHS / 'community_size_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. Análise por país (se disponível)
        if 'country' in df.columns:
            fig, ax = plt.subplots(figsize=(12, 6))
            country_communities = df.groupby('country')['label'].nunique().sort_values(ascending=False)
            
            country_communities.plot(kind='bar', ax=ax, color='teal', edgecolor='black')
            ax.set_xlabel('País')
            ax.set_ylabel('Número de Comunidades')
            ax.set_title('Comunidades por País')
            ax.grid(True, alpha=0.3, axis='y')
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            plt.savefig(OUTPUT_GRAPHS / 'communities_by_country.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        logger.info(f"  ✓ Gráficos salvos em {OUTPUT_GRAPHS}")
    
    return stats


def analyze_connected_components(save_plots: bool = True) -> dict:
    """Analisa componentes conectados"""
    logger.info("\n🔗 Analisando Connected Components...")
    
    try:
        df = read_parquet_folder(INPUT_PATH / 'connected_components')
    except FileNotFoundError as e:
        logger.warning(f"⚠️  {e} (pode ter sido pulado com --skip-cc)")
        return {}
    
    component_sizes = df['component'].value_counts().sort_values(ascending=False)
    
    stats = {
        'total_components': len(component_sizes),
        'largest_component': int(component_sizes.iloc[0]),
        'largest_component_pct': float(component_sizes.iloc[0] / len(df) * 100)
    }
    
    print("\n" + "="*70)
    print("🔗 ESTATÍSTICAS DE CONECTIVIDADE")
    print("="*70)
    print(f"Total de Componentes: {stats['total_components']:,}")
    print(f"Maior Componente: {stats['largest_component']:,} nós ({stats['largest_component_pct']:.1f}%)")
    print("="*70 + "\n")
    
    if save_plots and len(component_sizes) > 1:
        OUTPUT_GRAPHS.mkdir(parents=True, exist_ok=True)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        top_10 = component_sizes.head(10)
        
        colors = plt.cm.coolwarm(np.linspace(0.2, 0.8, len(top_10)))
        bars = ax.bar(range(len(top_10)), top_10.values, color=colors, edgecolor='black')
        
        ax.set_xlabel('Componente')
        ax.set_ylabel('Tamanho')
        ax.set_title('Top 10 Componentes Conectados', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        for i, v in enumerate(top_10.values):
            ax.text(i, v, f'{v:,}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(OUTPUT_GRAPHS / 'connected_components.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"  ✓ Gráfico salvo em {OUTPUT_GRAPHS}")
    
    return stats


def save_summary_report(pr_stats: dict, comm_stats: dict, cc_stats: dict) -> None:
    """Salva relatório consolidado em CSV"""
    OUTPUT_METRICS.mkdir(parents=True, exist_ok=True)
    
    report_data = {
        'metric': [],
        'value': []
    }
    
    # PageRank
    for key, value in pr_stats.items():
        report_data['metric'].append(f'pagerank_{key}')
        report_data['value'].append(value)
    
    # Communities
    for key, value in comm_stats.items():
        report_data['metric'].append(f'communities_{key}')
        report_data['value'].append(value)
    
    # Connected Components
    for key, value in cc_stats.items():
        report_data['metric'].append(f'cc_{key}')
        report_data['value'].append(value)
    
    df_report = pd.DataFrame(report_data)
    report_path = OUTPUT_METRICS / f'summary_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    df_report.to_csv(report_path, index=False)
    
    logger.info(f"\n📄 Relatório consolidado salvo em: {report_path}")


def main():
    print("=" * 70)
    print("📊 GraphX Community Detection - Análise de Resultados")
    print("=" * 70)
    print()
    
    try:
        # Executar análises
        pr_stats = analyze_pagerank(save_plots=True)
        comm_stats = analyze_communities(save_plots=True)
        cc_stats = analyze_connected_components(save_plots=True)
        
        # Salvar relatório
        save_summary_report(pr_stats, comm_stats, cc_stats)
        
        print("\n" + "=" * 70)
        print(f"✅ Análise concluída com sucesso!")
        print(f"📊 Gráficos salvos em: {OUTPUT_GRAPHS}")
        print(f"📈 Métricas salvas em: {OUTPUT_METRICS}")
        print("=" * 70)
        
    except Exception as e:
        logger.error(f"\n❌ Erro durante análise: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()