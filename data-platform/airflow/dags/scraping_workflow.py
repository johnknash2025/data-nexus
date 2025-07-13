"""
スクレイピングワークフロー DAG
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
import sys
import os

# スクレイピングモジュールのパス追加
sys.path.append('/opt/airflow/scraping')

from image_scraper import ImageScraper

# デフォルト引数
default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG定義
dag = DAG(
    'scraping_workflow',
    default_args=default_args,
    description='画像スクレイピングとデータ保存のワークフロー',
    schedule_interval=timedelta(hours=6),  # 6時間ごとに実行
    catchup=False,
    tags=['scraping', 'data-collection'],
)

def create_tables_if_not_exists():
    """必要なテーブルを作成"""
    from sqlalchemy import create_engine, text
    
    engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
    
    # 画像テーブル作成
    create_images_table = """
    CREATE TABLE IF NOT EXISTS scraped_images (
        id SERIAL PRIMARY KEY,
        source_url TEXT NOT NULL,
        image_url TEXT NOT NULL UNIQUE,
        alt_text TEXT,
        page_title TEXT,
        file_extension VARCHAR(10),
        has_local_copy BOOLEAN DEFAULT FALSE,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_scraped_images_source_url ON scraped_images(source_url);
    CREATE INDEX IF NOT EXISTS idx_scraped_images_scraped_at ON scraped_images(scraped_at);
    """
    
    with engine.connect() as conn:
        conn.execute(text(create_images_table))
        conn.commit()

def run_image_scraping(**context):
    """画像スクレイピング実行"""
    # 設定
    config = {
        'base_url': 'https://search.nifty.com/imagesearch/search?select=1&q=猫&ss=up',
        'target_extensions': ['.jpg', '.jpeg', '.png', '.gif'],
        'download_images': False,  # TrueNAS環境では容量に注意
        'storage_path': '/tmp/scraped_images'
    }
    
    # スクレイピング実行
    scraper = ImageScraper(config)
    result = scraper.run()
    
    # 結果をXComに保存
    context['task_instance'].xcom_push(key='scraping_result', value=result)
    
    return result

def run_multiple_sources_scraping(**context):
    """複数ソースからのスクレイピング"""
    sources = [
        {
            'name': 'nifty_cats',
            'base_url': 'https://search.nifty.com/imagesearch/search?select=1&q=猫&ss=up',
        },
        {
            'name': 'nifty_dogs', 
            'base_url': 'https://search.nifty.com/imagesearch/search?select=1&q=犬&ss=up',
        }
    ]
    
    results = []
    for source in sources:
        try:
            config = {
                'base_url': source['base_url'],
                'target_extensions': ['.jpg', '.jpeg', '.png', '.gif'],
                'download_images': False,
                'storage_path': f'/tmp/scraped_images/{source["name"]}'
            }
            
            scraper = ImageScraper(config)
            result = scraper.run()
            result['source_name'] = source['name']
            results.append(result)
            
        except Exception as e:
            print(f"Error scraping {source['name']}: {e}")
            results.append({
                'source_name': source['name'],
                'status': 'failed',
                'error': str(e)
            })
    
    context['task_instance'].xcom_push(key='multi_scraping_results', value=results)
    return results

def cleanup_old_data(**context):
    """古いデータのクリーンアップ"""
    from sqlalchemy import create_engine, text
    from pymongo import MongoClient
    from datetime import datetime, timedelta
    
    # 30日以上古いデータを削除
    cutoff_date = datetime.now() - timedelta(days=30)
    
    # PostgreSQL クリーンアップ
    engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM scraped_images WHERE scraped_at < :cutoff_date"),
            {"cutoff_date": cutoff_date}
        )
        conn.commit()
        print(f"Deleted {result.rowcount} old records from PostgreSQL")
    
    # MongoDB クリーンアップ
    mongo_client = MongoClient(os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/'))
    db = mongo_client.data_platform
    result = db.images_raw.delete_many({"scraped_at": {"$lt": cutoff_date}})
    print(f"Deleted {result.deleted_count} old documents from MongoDB")

# タスク定義
create_tables_task = PythonOperator(
    task_id='create_tables',
    python_callable=create_tables_if_not_exists,
    dag=dag,
)

scrape_images_task = PythonOperator(
    task_id='scrape_images',
    python_callable=run_image_scraping,
    dag=dag,
)

scrape_multiple_sources_task = PythonOperator(
    task_id='scrape_multiple_sources',
    python_callable=run_multiple_sources_scraping,
    dag=dag,
)

cleanup_task = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag,
)

# データ品質チェック
data_quality_check = BashOperator(
    task_id='data_quality_check',
    bash_command="""
    python -c "
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM scraped_images WHERE scraped_at >= CURRENT_DATE'))
    count = result.scalar()
    print(f'Images scraped today: {count}')
    
    if count == 0:
        print('WARNING: No images scraped today!')
        exit(1)
    else:
        print('Data quality check passed')
"
    """,
    dag=dag,
)

# タスク依存関係
create_tables_task >> [scrape_images_task, scrape_multiple_sources_task]
[scrape_images_task, scrape_multiple_sources_task] >> data_quality_check >> cleanup_task