"""
データ処理・分析ワークフロー DAG
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pandas as pd
import os

default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'data_processing_workflow',
    default_args=default_args,
    description='データ処理・分析・AI学習準備のワークフロー',
    schedule_interval=timedelta(hours=12),  # 12時間ごとに実行
    catchup=False,
    tags=['data-processing', 'ai-training'],
)

def analyze_scraped_data(**context):
    """スクレイピングデータの分析"""
    from sqlalchemy import create_engine
    import wandb
    
    # データベース接続
    engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
    
    # データ読み込み
    query = """
    SELECT 
        source_url,
        COUNT(*) as image_count,
        COUNT(DISTINCT file_extension) as extension_types,
        DATE(scraped_at) as scrape_date
    FROM scraped_images 
    WHERE scraped_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY source_url, DATE(scraped_at)
    ORDER BY scrape_date DESC, image_count DESC
    """
    
    df = pd.read_sql(query, engine)
    
    # 分析結果
    analysis = {
        'total_images_last_7_days': df['image_count'].sum(),
        'unique_sources': df['source_url'].nunique(),
        'avg_images_per_source': df.groupby('source_url')['image_count'].sum().mean(),
        'most_productive_source': df.groupby('source_url')['image_count'].sum().idxmax() if not df.empty else None
    }
    
    # wandbにログ
    if os.getenv('WANDB_API_KEY'):
        wandb.init(project="data-platform-analysis", name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        wandb.log(analysis)
        wandb.finish()
    
    print(f"Analysis results: {analysis}")
    context['task_instance'].xcom_push(key='analysis_results', value=analysis)
    
    return analysis

def prepare_training_data(**context):
    """AI学習用データの準備"""
    from sqlalchemy import create_engine
    from pymongo import MongoClient
    import json
    
    # データベース接続
    engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
    mongo_client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/'))
    
    # 構造化データ取得
    structured_query = """
    SELECT 
        image_url,
        alt_text,
        page_title,
        file_extension,
        scraped_at
    FROM scraped_images 
    WHERE alt_text IS NOT NULL AND alt_text != ''
    AND scraped_at >= CURRENT_DATE - INTERVAL '30 days'
    ORDER BY scraped_at DESC
    LIMIT 1000
    """
    
    df = pd.read_sql(structured_query, engine)
    
    # 非構造化データ取得
    db = mongo_client.data_platform
    raw_data = list(db.images_raw.find(
        {"scraped_at": {"$gte": datetime.now() - timedelta(days=30)}},
        limit=1000
    ).sort("scraped_at", -1))
    
    # 学習データセット作成
    training_dataset = {
        'structured_data': df.to_dict('records'),
        'raw_data': raw_data,
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'total_structured_records': len(df),
            'total_raw_records': len(raw_data),
            'date_range_days': 30
        }
    }
    
    # MinIOに保存（オプション）
    dataset_path = f'/tmp/training_dataset_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(dataset_path, 'w', encoding='utf-8') as f:
        json.dump(training_dataset, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"Training dataset prepared: {len(df)} structured + {len(raw_data)} raw records")
    context['task_instance'].xcom_push(key='training_dataset_path', value=dataset_path)
    
    return training_dataset['metadata']

def generate_data_report(**context):
    """データレポート生成"""
    from sqlalchemy import create_engine
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
    
    # 日別データ収集量
    daily_query = """
    SELECT 
        DATE(scraped_at) as date,
        COUNT(*) as count
    FROM scraped_images 
    WHERE scraped_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE(scraped_at)
    ORDER BY date
    """
    
    df_daily = pd.read_sql(daily_query, engine)
    
    # ソース別データ量
    source_query = """
    SELECT 
        source_url,
        COUNT(*) as count
    FROM scraped_images 
    WHERE scraped_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY source_url
    ORDER BY count DESC
    LIMIT 10
    """
    
    df_sources = pd.read_sql(source_query, engine)
    
    # レポート生成
    report = {
        'daily_collection': df_daily.to_dict('records'),
        'top_sources': df_sources.to_dict('records'),
        'summary': {
            'total_last_30_days': df_daily['count'].sum(),
            'avg_daily': df_daily['count'].mean(),
            'max_daily': df_daily['count'].max(),
            'active_sources': len(df_sources)
        }
    }
    
    print(f"Data report generated: {report['summary']}")
    context['task_instance'].xcom_push(key='data_report', value=report)
    
    return report

# タスク定義
analyze_data_task = PythonOperator(
    task_id='analyze_scraped_data',
    python_callable=analyze_scraped_data,
    dag=dag,
)

prepare_training_task = PythonOperator(
    task_id='prepare_training_data',
    python_callable=prepare_training_data,
    dag=dag,
)

generate_report_task = PythonOperator(
    task_id='generate_data_report',
    python_callable=generate_data_report,
    dag=dag,
)

# データ品質監視
monitor_data_quality = BashOperator(
    task_id='monitor_data_quality',
    bash_command="""
    python -c "
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))

with engine.connect() as conn:
    # 重複チェック
    dup_result = conn.execute(text('''
        SELECT COUNT(*) as duplicates 
        FROM (
            SELECT image_url, COUNT(*) 
            FROM scraped_images 
            GROUP BY image_url 
            HAVING COUNT(*) > 1
        ) t
    '''))
    duplicates = dup_result.scalar()
    
    # NULL値チェック
    null_result = conn.execute(text('''
        SELECT COUNT(*) as null_urls 
        FROM scraped_images 
        WHERE image_url IS NULL OR image_url = ''
    '''))
    null_urls = null_result.scalar()
    
    print(f'Data Quality Report:')
    print(f'- Duplicate URLs: {duplicates}')
    print(f'- NULL/Empty URLs: {null_urls}')
    
    if duplicates > 100 or null_urls > 10:
        print('WARNING: Data quality issues detected!')
        exit(1)
    else:
        print('Data quality check passed')
"
    """,
    dag=dag,
)

# タスク依存関係
[analyze_data_task, prepare_training_task, generate_report_task] >> monitor_data_quality