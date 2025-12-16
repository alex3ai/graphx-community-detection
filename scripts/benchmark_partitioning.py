#!/usr/bin/env python3
"""
GraphX Community Detection Engine - Benchmarking & Tuning
Testa diferentes configurações de particionamento e mede performance
"""

import subprocess
import time
import pandas as pd
from pathlib import Path
import logging
import sys
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_docker_running() -> bool:
    """Verifica se containers Docker estão rodando"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=spark_master', '--format', '{{.Names}}'],
            capture_output=True,
            text=True,
            check=True
        )
        return 'spark_master' in result.stdout
    except subprocess.CalledProcessError:
        return False


def run_spark_job(partitions: int, memory: str = "2G", pagerank_iter: int = 10, 
                  lpa_iter: int = 5) -> tuple:
    """
    Executa job Spark com configurações específicas
    
    Args:
        partitions: Número de partições de shuffle
        memory: Memória do executor
        pagerank_iter: Iterações do PageRank
        lpa_iter: Iterações do Label Propagation
    
    Returns:
        tuple: (duration, success, error_msg)
    """
    logger.info(f"🔄 Executando teste: partitions={partitions}, memory={memory}")
    
    cmd = [
        "docker", "exec", "spark_master",
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--executor-memory", memory,
        "--driver-memory", "1G",
        "--packages", "graphframes:graphframes:0.8.3-spark3.5-s_2.12",
        "--conf", f"spark.sql.shuffle.partitions={partitions}",
        "--conf", f"spark.default.parallelism={partitions}",
        "--conf", "spark.serializer=org.apache.spark.serializer.KryoSerializer",
        "/opt/spark-apps/community_detection.py",
        "--pagerank-iter", str(pagerank_iter),
        "--lpa-iter", str(lpa_iter)
    ]
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 min timeout
        )
        
        duration = time.time() - start_time
        success = result.returncode == 0
        
        if not success:
            error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
            logger.error(f"  ❌ Job falhou: {error_msg}")
            return duration, False, error_msg
        
        logger.info(f"  ✅ Job concluído em {duration:.2f}s")
        return duration, True, None
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f"  ⏰ Timeout após {duration:.2f}s")
        return duration, False, "Timeout"
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"  ❌ Erro: {e}")
        return duration, False, str(e)


def run_benchmark_suite(test_configs: list) -> pd.DataFrame:
    """
    Executa suite completa de benchmarks
    
    Args:
        test_configs: Lista de dicionários com configurações de teste
    
    Returns:
        DataFrame com resultados
    """
    results = []
    
    print("\n" + "=" * 70)
    print("🧪 INICIANDO BENCHMARK SUITE")
    print("=" * 70)
    print(f"Total de testes: {len(test_configs)}")
    print()
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n[{i}/{len(test_configs)}] Teste: {config}")
        
        duration, success, error = run_spark_job(
            partitions=config['partitions'],
            memory=config.get('memory', '2G'),
            pagerank_iter=config.get('pagerank_iter', 10),
            lpa_iter=config.get('lpa_iter', 5)
        )
        
        results.append({
            'test_id': i,
            'partitions': config['partitions'],
            'memory': config.get('memory', '2G'),
            'pagerank_iter': config.get('pagerank_iter', 10),
            'lpa_iter': config.get('lpa_iter', 5),
            'duration_sec': round(duration, 2),
            'success': success,
            'error': error if error else ''
        })
        
        # Pequena pausa entre testes para cleanup
        time.sleep(5)
    
    return pd.DataFrame(results)


def analyze_benchmark_results(df: pd.DataFrame) -> None:
    """Analisa e exibe resultados do benchmark"""
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DO BENCHMARK")
    print("=" * 70)
    
    # Filtrar apenas sucessos
    df_success = df[df['success'] == True].copy()
    
    if len(df_success) == 0:
        logger.error("❌ Nenhum teste foi bem-sucedido!")
        return
    
    print("\n✅ Testes bem-sucedidos:")
    print(df_success[['partitions', 'memory', 'duration_sec']].to_string(index=False))
    
    # Encontrar configuração ótima
    best = df_success.loc[df_success['duration_sec'].idxmin()]
    
    print("\n" + "=" * 70)
    print("🏆 CONFIGURAÇÃO ÓTIMA")
    print("=" * 70)
    print(f"Partições: {best['partitions']}")
    print(f"Memória: {best['memory']}")
    print(f"Tempo: {best['duration_sec']:.2f}s")
    print("=" * 70)
    
    # Análise de falhas
    df_failed = df[df['success'] == False]
    if len(df_failed) > 0:
        print(f"\n⚠️  {len(df_failed)} teste(s) falharam:")
        print(df_failed[['partitions', 'error']].to_string(index=False))


def save_results(df: pd.DataFrame, output_dir: Path) -> None:
    """Salva resultados em CSV e JSON"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV
    csv_path = output_dir / f'benchmark_results_{timestamp}.csv'
    df.to_csv(csv_path, index=False)
    logger.info(f"📊 CSV salvo: {csv_path}")
    
    # JSON com metadados
    json_path = output_dir / f'benchmark_results_{timestamp}.json'
    results_dict = {
        'timestamp': timestamp,
        'total_tests': len(df),
        'successful_tests': int(df['success'].sum()),
        'failed_tests': int((~df['success']).sum()),
        'results': df.to_dict('records')
    }
    
    with open(json_path, 'w') as f:
        json.dump(results_dict, f, indent=2)
    
    logger.info(f"📄 JSON salvo: {json_path}")


def main():
    # Verificar se Docker está rodando
    if not check_docker_running():
        logger.error("❌ Container spark_master não está rodando!")
        logger.error("   Execute: make start")
        sys.exit(1)
    
    # Configurações de teste
    # Testamos diferentes números de partições mantendo memória constante
    test_configs = [
        {'partitions': 50},
        {'partitions': 100},
        {'partitions': 200},
        {'partitions': 300},
    ]
    
    # Teste adicional com diferentes configurações de memória (se tiver recursos)
    # test_configs.extend([
    #     {'partitions': 100, 'memory': '1G'},
    #     {'partitions': 100, 'memory': '3G'},
    # ])
    
    try:
        # Executar benchmark
        df_results = run_benchmark_suite(test_configs)
        
        # Analisar resultados
        analyze_benchmark_results(df_results)
        
        # Salvar resultados
        output_dir = Path('./analysis/metrics')
        save_results(df_results, output_dir)
        
        print("\n✨ Benchmark concluído!")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Benchmark interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Erro fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()