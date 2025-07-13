"""
ベーススクレイピングクラス - 既存コードの統合とデータベース連携
"""
import os
import requests
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from pymongo import MongoClient
import wandb

class BaseScraper(ABC):
    """スクレイピングの基底クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = self._setup_logger()
        self.db_engine = self._setup_postgres()
        self.mongo_client = self._setup_mongodb()
        self.wandb_run = self._setup_wandb()
        
    def _setup_logger(self) -> logging.Logger:
        """ログ設定"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def _setup_postgres(self):
        """PostgreSQL接続設定"""
        db_url = os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform')
        return create_engine(db_url)
    
    def _setup_mongodb(self):
        """MongoDB接続設定"""
        mongo_url = os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/')
        return MongoClient(mongo_url)
    
    def _setup_wandb(self):
        """wandb設定"""
        if os.getenv('WANDB_API_KEY'):
            return wandb.init(
                project="data-platform-scraping",
                name=f"{self.__class__.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
        return None
    
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """スクレイピング実行（サブクラスで実装）"""
        pass
    
    def save_to_postgres(self, data: List[Dict[str, Any]], table_name: str):
        """PostgreSQLにデータ保存"""
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            df['scraped_at'] = datetime.now()
            df.to_sql(table_name, self.db_engine, if_exists='append', index=False)
            self.logger.info(f"Saved {len(data)} records to PostgreSQL table: {table_name}")
        except Exception as e:
            self.logger.error(f"Error saving to PostgreSQL: {e}")
            raise
    
    def save_to_mongodb(self, data: List[Dict[str, Any]], collection_name: str):
        """MongoDBにデータ保存"""
        try:
            db = self.mongo_client.data_platform
            collection = db[collection_name]
            
            # タイムスタンプ追加
            for item in data:
                item['scraped_at'] = datetime.now()
            
            result = collection.insert_many(data)
            self.logger.info(f"Saved {len(result.inserted_ids)} records to MongoDB collection: {collection_name}")
        except Exception as e:
            self.logger.error(f"Error saving to MongoDB: {e}")
            raise
    
    def log_metrics(self, metrics: Dict[str, Any]):
        """wandbにメトリクス記録"""
        if self.wandb_run:
            wandb.log(metrics)
        self.logger.info(f"Metrics: {metrics}")
    
    def run(self) -> Dict[str, Any]:
        """スクレイピング実行とデータ保存"""
        start_time = datetime.now()
        
        try:
            # スクレイピング実行
            data = self.scrape()
            
            # データ保存
            if data:
                # PostgreSQLに構造化データ保存
                structured_data = self.extract_structured_data(data)
                if structured_data:
                    self.save_to_postgres(structured_data, self.get_postgres_table())
                
                # MongoDBに生データ保存
                self.save_to_mongodb(data, self.get_mongodb_collection())
            
            # メトリクス記録
            end_time = datetime.now()
            metrics = {
                'records_scraped': len(data),
                'execution_time_seconds': (end_time - start_time).total_seconds(),
                'success': True
            }
            self.log_metrics(metrics)
            
            return {
                'status': 'success',
                'records_count': len(data),
                'execution_time': (end_time - start_time).total_seconds()
            }
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {e}")
            self.log_metrics({
                'success': False,
                'error': str(e),
                'execution_time_seconds': (datetime.now() - start_time).total_seconds()
            })
            raise
    
    def extract_structured_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """構造化データの抽出（サブクラスでオーバーライド可能）"""
        return data
    
    @abstractmethod
    def get_postgres_table(self) -> str:
        """PostgreSQLテーブル名を返す"""
        pass
    
    @abstractmethod
    def get_mongodb_collection(self) -> str:
        """MongoDBコレクション名を返す"""
        pass