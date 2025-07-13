"""
高度なデータパイプライン - リアルタイム処理、品質管理、ML統合
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.sensors.filesystem import FileSensor
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.sensors.http import HttpSensor
import pandas as pd
import numpy as np
from typing import Dict, List, Any
import json
import logging

# デフォルト引数
default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG定義
dag = DAG(
    'advanced_data_pipeline',
    default_args=default_args,
    description='高度なデータパイプライン - リアルタイム処理とML統合',
    schedule_interval=timedelta(hours=1),  # 1時間ごと実行
    catchup=False,
    tags=['data-processing', 'ml', 'quality-control']
)

def data_quality_validation(**context):
    """データ品質検証"""
    logging.info("Starting data quality validation...")
    
    # PostgreSQLからデータ取得
    postgres_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # 重複チェック
    duplicate_query = """
    SELECT image_url, COUNT(*) as count 
    FROM scraped_images 
    GROUP BY image_url 
    HAVING COUNT(*) > 1
    """
    duplicates = postgres_hook.get_records(duplicate_query)
    
    # NULL値チェック
    null_check_query = """
    SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN image_url IS NULL THEN 1 END) as null_urls,
        COUNT(CASE WHEN source_url IS NULL THEN 1 END) as null_sources,
        COUNT(CASE WHEN scraped_at IS NULL THEN 1 END) as null_timestamps
    FROM scraped_images
    WHERE scraped_at >= NOW() - INTERVAL '1 hour'
    """
    quality_stats = postgres_hook.get_first(null_check_query)
    
    # 品質スコア計算
    total_records = quality_stats[0] if quality_stats[0] else 0
    if total_records > 0:
        null_rate = (quality_stats[1] + quality_stats[2]) / (total_records * 2)
        duplicate_rate = len(duplicates) / total_records
        quality_score = max(0, 100 - (null_rate * 50) - (duplicate_rate * 30))
    else:
        quality_score = 0
    
    # 結果をXComに保存
    context['task_instance'].xcom_push(key='quality_score', value=quality_score)
    context['task_instance'].xcom_push(key='duplicate_count', value=len(duplicates))
    context['task_instance'].xcom_push(key='total_records', value=total_records)
    
    logging.info(f"Quality Score: {quality_score:.2f}")
    logging.info(f"Duplicates found: {len(duplicates)}")
    
    return {
        'quality_score': quality_score,
        'duplicate_count': len(duplicates),
        'total_records': total_records
    }

def anomaly_detection(**context):
    """異常検知"""
    logging.info("Starting anomaly detection...")
    
    postgres_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # 時系列データ取得（過去24時間）
    query = """
    SELECT 
        DATE_TRUNC('hour', scraped_at) as hour,
        COUNT(*) as record_count,
        COUNT(DISTINCT source_url) as unique_sources
    FROM scraped_images 
    WHERE scraped_at >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', scraped_at)
    ORDER BY hour
    """
    
    data = postgres_hook.get_pandas_df(query)
    
    if len(data) > 3:  # 最低3時間分のデータが必要
        # 簡単な異常検知（Z-score）
        data['record_count_zscore'] = np.abs(
            (data['record_count'] - data['record_count'].mean()) / data['record_count'].std()
        )
        
        # 異常値検出（Z-score > 2）
        anomalies = data[data['record_count_zscore'] > 2]
        
        if len(anomalies) > 0:
            logging.warning(f"Anomalies detected: {len(anomalies)} hours")
            context['task_instance'].xcom_push(key='anomalies_detected', value=True)
            context['task_instance'].xcom_push(key='anomaly_count', value=len(anomalies))
        else:
            context['task_instance'].xcom_push(key='anomalies_detected', value=False)
            context['task_instance'].xcom_push(key='anomaly_count', value=0)
    
    return {'anomalies_detected': len(anomalies) if 'anomalies' in locals() else 0}

def feature_engineering(**context):
    """特徴量エンジニアリング"""
    logging.info("Starting feature engineering...")
    
    postgres_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # 最新データ取得
    query = """
    SELECT 
        id, source_url, image_url, alt_text, page_title, 
        file_extension, scraped_at
    FROM scraped_images 
    WHERE scraped_at >= NOW() - INTERVAL '1 hour'
    """
    
    df = postgres_hook.get_pandas_df(query)
    
    if len(df) > 0:
        # 特徴量生成
        df['url_length'] = df['image_url'].str.len()
        df['alt_text_length'] = df['alt_text'].fillna('').str.len()
        df['title_length'] = df['page_title'].fillna('').str.len()
        df['hour_of_day'] = pd.to_datetime(df['scraped_at']).dt.hour
        df['day_of_week'] = pd.to_datetime(df['scraped_at']).dt.dayofweek
        
        # ドメイン抽出
        df['domain'] = df['source_url'].str.extract(r'https?://([^/]+)')
        
        # 特徴量をMongoDBに保存
        from pymongo import MongoClient
        import os
        
        mongo_url = os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/')
        client = MongoClient(mongo_url)
        db = client.data_platform
        
        features_data = df.to_dict('records')
        db.features.insert_many(features_data)
        
        logging.info(f"Generated features for {len(df)} records")
        
        return {'features_generated': len(df)}
    
    return {'features_generated': 0}

def ml_model_training(**context):
    """機械学習モデル訓練"""
    logging.info("Starting ML model training...")
    
    try:
        import wandb
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        import joblib
        import os
        
        # wandb初期化
        if os.getenv('WANDB_API_KEY'):
            wandb.init(project="data-platform-ml", name=f"anomaly_detection_{datetime.now().strftime('%Y%m%d_%H%M')}")
        
        # MongoDBから特徴量データ取得
        from pymongo import MongoClient
        mongo_url = os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/')
        client = MongoClient(mongo_url)
        db = client.data_platform
        
        # 過去7日間のデータ
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        
        cursor = db.features.find({
            'scraped_at': {'$gte': week_ago}
        })
        
        data = list(cursor)
        
        if len(data) > 100:  # 最低100件のデータが必要
            df = pd.DataFrame(data)
            
            # 数値特徴量選択
            numeric_features = ['url_length', 'alt_text_length', 'title_length', 'hour_of_day', 'day_of_week']
            X = df[numeric_features].fillna(0)
            
            # 標準化
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # 異常検知モデル訓練
            model = IsolationForest(contamination=0.1, random_state=42)
            model.fit(X_scaled)
            
            # モデル保存
            model_path = '/tmp/anomaly_detection_model.joblib'
            scaler_path = '/tmp/feature_scaler.joblib'
            
            joblib.dump(model, model_path)
            joblib.dump(scaler, scaler_path)
            
            # wandbにモデル記録
            if os.getenv('WANDB_API_KEY'):
                wandb.log({
                    'training_samples': len(data),
                    'features_count': len(numeric_features),
                    'contamination_rate': 0.1
                })
                
                # モデルアーティファクト保存
                artifact = wandb.Artifact('anomaly_detection_model', type='model')
                artifact.add_file(model_path)
                artifact.add_file(scaler_path)
                wandb.log_artifact(artifact)
            
            logging.info(f"Model trained with {len(data)} samples")
            return {'model_trained': True, 'training_samples': len(data)}
        else:
            logging.warning("Insufficient data for model training")
            return {'model_trained': False, 'training_samples': len(data)}
            
    except Exception as e:
        logging.error(f"ML training failed: {e}")
        return {'model_trained': False, 'error': str(e)}

def generate_insights_report(**context):
    """インサイトレポート生成"""
    logging.info("Generating insights report...")
    
    # XComから結果取得
    quality_score = context['task_instance'].xcom_pull(task_ids='data_quality_validation', key='quality_score')
    anomaly_count = context['task_instance'].xcom_pull(task_ids='anomaly_detection', key='anomaly_count')
    
    postgres_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # 統計情報取得
    stats_query = """
    SELECT 
        COUNT(*) as total_images,
        COUNT(DISTINCT source_url) as unique_sources,
        COUNT(DISTINCT file_extension) as file_types,
        AVG(CASE WHEN alt_text IS NOT NULL AND alt_text != '' THEN 1 ELSE 0 END) * 100 as alt_text_coverage
    FROM scraped_images
    WHERE scraped_at >= NOW() - INTERVAL '24 hours'
    """
    
    stats = postgres_hook.get_first(stats_query)
    
    # レポート生成
    report = {
        'generated_at': datetime.now().isoformat(),
        'period': '24 hours',
        'data_quality': {
            'score': quality_score,
            'grade': 'A' if quality_score >= 90 else 'B' if quality_score >= 70 else 'C'
        },
        'statistics': {
            'total_images': stats[0],
            'unique_sources': stats[1],
            'file_types': stats[2],
            'alt_text_coverage': round(stats[3], 2) if stats[3] else 0
        },
        'anomalies': {
            'detected': anomaly_count > 0,
            'count': anomaly_count
        },
        'recommendations': []
    }
    
    # 推奨事項生成
    if quality_score < 70:
        report['recommendations'].append("データ品質が低下しています。重複除去とNULL値対応を検討してください。")
    
    if stats[3] and stats[3] < 50:
        report['recommendations'].append("alt_textの付与率が低いです。アクセシビリティ向上のため改善を推奨します。")
    
    if anomaly_count > 0:
        report['recommendations'].append(f"{anomaly_count}件の異常が検出されました。データ収集プロセスを確認してください。")
    
    # MongoDBにレポート保存
    from pymongo import MongoClient
    import os
    
    mongo_url = os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/')
    client = MongoClient(mongo_url)
    db = client.data_platform
    
    db.insights_reports.insert_one(report)
    
    logging.info("Insights report generated and saved")
    return report

# タスク定義
data_quality_task = PythonOperator(
    task_id='data_quality_validation',
    python_callable=data_quality_validation,
    dag=dag
)

anomaly_detection_task = PythonOperator(
    task_id='anomaly_detection',
    python_callable=anomaly_detection,
    dag=dag
)

feature_engineering_task = PythonOperator(
    task_id='feature_engineering',
    python_callable=feature_engineering,
    dag=dag
)

ml_training_task = PythonOperator(
    task_id='ml_model_training',
    python_callable=ml_model_training,
    dag=dag
)

insights_report_task = PythonOperator(
    task_id='generate_insights_report',
    python_callable=generate_insights_report,
    dag=dag
)

# データベース最適化タスク
db_optimization_task = PostgresOperator(
    task_id='database_optimization',
    postgres_conn_id='postgres_default',
    sql="""
    -- インデックス最適化
    REINDEX INDEX CONCURRENTLY idx_scraped_images_source_scraped;
    
    -- 統計情報更新
    ANALYZE scraped_images;
    
    -- 古いデータのアーカイブ（30日以上前）
    UPDATE scraped_images 
    SET archived = true 
    WHERE scraped_at < NOW() - INTERVAL '30 days' 
    AND archived IS NOT true;
    """,
    dag=dag
)

# タスク依存関係
[data_quality_task, anomaly_detection_task] >> feature_engineering_task
feature_engineering_task >> ml_training_task
[data_quality_task, anomaly_detection_task, ml_training_task] >> insights_report_task
insights_report_task >> db_optimization_task