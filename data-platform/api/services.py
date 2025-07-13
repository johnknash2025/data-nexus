"""
ビジネスロジック・サービス層
"""
import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text, func, desc
from sqlalchemy.orm import Session
import pandas as pd
import wandb

from database import get_db_connection, get_mongo_client, get_redis_client, ScrapedImage
from models import ImageData, DataSummary, TrainingDataset

class DataService:
    """データアクセスサービス"""
    
    def __init__(self):
        self.redis_client = get_redis_client()
        self.mongo_db = get_mongo_client()
    
    async def check_database_connection(self) -> str:
        """PostgreSQL接続チェック"""
        try:
            with get_db_connection() as conn:
                result = conn.execute(text("SELECT 1"))
                return "healthy"
        except Exception as e:
            return f"unhealthy: {str(e)}"
    
    async def check_mongodb_connection(self) -> str:
        """MongoDB接続チェック"""
        try:
            self.mongo_db.command('ping')
            return "healthy"
        except Exception as e:
            return f"unhealthy: {str(e)}"
    
    async def get_images(
        self, 
        limit: int = 100, 
        offset: int = 0, 
        filters: Dict[str, Any] = None
    ) -> List[ImageData]:
        """画像データ取得"""
        cache_key = f"images:{limit}:{offset}:{hash(str(filters))}"
        
        # Redis キャッシュチェック
        cached = self.redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [ImageData(**item) for item in data]
        
        # データベースクエリ
        with get_db_connection() as conn:
            query = """
            SELECT id, source_url, image_url, alt_text, page_title, 
                   file_extension, has_local_copy, scraped_at, created_at
            FROM scraped_images
            WHERE 1=1
            """
            params = {}
            
            if filters:
                if filters.get('source_url'):
                    query += " AND source_url = :source_url"
                    params['source_url'] = filters['source_url']
                
                if filters.get('file_extension'):
                    query += " AND file_extension = :file_extension"
                    params['file_extension'] = filters['file_extension']
                
                if filters.get('date_from'):
                    query += " AND scraped_at >= :date_from"
                    params['date_from'] = filters['date_from']
                
                if filters.get('date_to'):
                    query += " AND scraped_at <= :date_to"
                    params['date_to'] = filters['date_to']
            
            query += " ORDER BY scraped_at DESC LIMIT :limit OFFSET :offset"
            params.update({'limit': limit, 'offset': offset})
            
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            
            images = []
            for row in rows:
                images.append(ImageData(
                    id=row.id,
                    source_url=row.source_url,
                    image_url=row.image_url,
                    alt_text=row.alt_text,
                    page_title=row.page_title,
                    file_extension=row.file_extension,
                    has_local_copy=row.has_local_copy,
                    scraped_at=row.scraped_at,
                    created_at=row.created_at
                ))
            
            # キャッシュに保存（5分間）
            cache_data = [img.dict() for img in images]
            self.redis_client.setex(cache_key, 300, json.dumps(cache_data, default=str))
            
            return images
    
    async def get_image_by_id(self, image_id: int) -> Optional[ImageData]:
        """ID指定で画像データ取得"""
        with get_db_connection() as conn:
            query = """
            SELECT id, source_url, image_url, alt_text, page_title, 
                   file_extension, has_local_copy, scraped_at, created_at
            FROM scraped_images WHERE id = :image_id
            """
            result = conn.execute(text(query), {'image_id': image_id})
            row = result.fetchone()
            
            if row:
                return ImageData(
                    id=row.id,
                    source_url=row.source_url,
                    image_url=row.image_url,
                    alt_text=row.alt_text,
                    page_title=row.page_title,
                    file_extension=row.file_extension,
                    has_local_copy=row.has_local_copy,
                    scraped_at=row.scraped_at,
                    created_at=row.created_at
                )
            return None
    
    async def search_images(self, query: str, limit: int = 50) -> List[ImageData]:
        """画像検索"""
        with get_db_connection() as conn:
            search_query = """
            SELECT id, source_url, image_url, alt_text, page_title, 
                   file_extension, has_local_copy, scraped_at, created_at
            FROM scraped_images
            WHERE (alt_text ILIKE :query OR page_title ILIKE :query)
            ORDER BY scraped_at DESC
            LIMIT :limit
            """
            result = conn.execute(text(search_query), {
                'query': f'%{query}%',
                'limit': limit
            })
            rows = result.fetchall()
            
            images = []
            for row in rows:
                images.append(ImageData(
                    id=row.id,
                    source_url=row.source_url,
                    image_url=row.image_url,
                    alt_text=row.alt_text,
                    page_title=row.page_title,
                    file_extension=row.file_extension,
                    has_local_copy=row.has_local_copy,
                    scraped_at=row.scraped_at,
                    created_at=row.created_at
                ))
            
            return images
    
    async def get_training_dataset(
        self, 
        limit: int = 1000, 
        include_raw: bool = True,
        min_alt_text_length: int = 5
    ) -> TrainingDataset:
        """AI学習用データセット取得"""
        # 構造化データ取得
        with get_db_connection() as conn:
            query = """
            SELECT image_url, alt_text, page_title, file_extension, scraped_at
            FROM scraped_images
            WHERE alt_text IS NOT NULL 
            AND LENGTH(alt_text) >= :min_length
            ORDER BY scraped_at DESC
            LIMIT :limit
            """
            result = conn.execute(text(query), {
                'min_length': min_alt_text_length,
                'limit': limit
            })
            structured_data = [dict(row._mapping) for row in result.fetchall()]
        
        # 非構造化データ取得（MongoDB）
        raw_data = None
        if include_raw:
            raw_data = list(self.mongo_db.images_raw.find(
                {},
                limit=limit
            ).sort("scraped_at", -1))
        
        metadata = {
            'created_at': datetime.now(),
            'total_structured_records': len(structured_data),
            'total_raw_records': len(raw_data) if raw_data else 0,
            'min_alt_text_length': min_alt_text_length,
            'include_raw': include_raw
        }
        
        return TrainingDataset(
            structured_data=structured_data,
            raw_data=raw_data,
            metadata=metadata,
            total_records=len(structured_data),
            created_at=datetime.now()
        )
    
    async def get_embeddings_data(self, limit: int = 500) -> List[Dict[str, Any]]:
        """埋め込み学習用データ取得"""
        with get_db_connection() as conn:
            query = """
            SELECT image_url, alt_text, page_title
            FROM scraped_images
            WHERE alt_text IS NOT NULL AND alt_text != ''
            AND page_title IS NOT NULL AND page_title != ''
            ORDER BY scraped_at DESC
            LIMIT :limit
            """
            result = conn.execute(text(query), {'limit': limit})
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, Any]:
        """古いデータのクリーンアップ"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # PostgreSQL クリーンアップ
        with get_db_connection() as conn:
            result = conn.execute(
                text("DELETE FROM scraped_images WHERE scraped_at < :cutoff_date"),
                {"cutoff_date": cutoff_date}
            )
            conn.commit()
            postgres_deleted = result.rowcount
        
        # MongoDB クリーンアップ
        mongo_result = self.mongo_db.images_raw.delete_many(
            {"scraped_at": {"$lt": cutoff_date}}
        )
        mongo_deleted = mongo_result.deleted_count
        
        return {
            'postgres_records_deleted': postgres_deleted,
            'mongodb_documents_deleted': mongo_deleted,
            'cutoff_date': cutoff_date.isoformat(),
            'cleanup_completed_at': datetime.now().isoformat()
        }
    
    async def deduplicate_data(self) -> Dict[str, Any]:
        """重複データの削除"""
        with get_db_connection() as conn:
            # 重複削除クエリ
            query = """
            DELETE FROM scraped_images 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM scraped_images 
                GROUP BY image_url
            )
            """
            result = conn.execute(text(query))
            conn.commit()
            
            return {
                'duplicates_removed': result.rowcount,
                'cleanup_completed_at': datetime.now().isoformat()
            }
    
    async def get_latest_data(self) -> Dict[str, Any]:
        """最新データ取得（WebSocket用）"""
        with get_db_connection() as conn:
            # 最新10件取得
            query = """
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '1 hour' THEN 1 END) as last_hour,
                   COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h
            FROM scraped_images
            """
            result = conn.execute(text(query))
            stats = dict(result.fetchone()._mapping)
            
            return {
                'timestamp': datetime.now().isoformat(),
                'stats': stats
            }

class AnalyticsService:
    """分析・統計サービス"""
    
    def __init__(self):
        self.redis_client = get_redis_client()
    
    async def get_data_summary(self) -> DataSummary:
        """データサマリー取得"""
        cache_key = "analytics:summary"
        cached = self.redis_client.get(cache_key)
        
        if cached:
            data = json.loads(cached)
            return DataSummary(**data)
        
        with get_db_connection() as conn:
            # 基本統計
            basic_stats = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_images,
                    COUNT(DISTINCT source_url) as unique_sources,
                    COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h_count,
                    COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '7 days' THEN 1 END) as last_7d_count,
                    COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '30 days' THEN 1 END) as last_30d_count
                FROM scraped_images
            """)).fetchone()
            
            # トップソース
            top_sources = conn.execute(text("""
                SELECT source_url, COUNT(*) as count
                FROM scraped_images
                WHERE scraped_at >= NOW() - INTERVAL '7 days'
                GROUP BY source_url
                ORDER BY count DESC
                LIMIT 5
            """)).fetchall()
            
            # ファイル拡張子統計
            extensions = conn.execute(text("""
                SELECT file_extension, COUNT(*) as count
                FROM scraped_images
                WHERE file_extension IS NOT NULL
                GROUP BY file_extension
                ORDER BY count DESC
            """)).fetchall()
            
            # データ品質スコア計算
            quality_stats = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN alt_text IS NOT NULL AND alt_text != '' THEN 1 END) as with_alt,
                    COUNT(CASE WHEN page_title IS NOT NULL AND page_title != '' THEN 1 END) as with_title
                FROM scraped_images
            """)).fetchone()
            
            quality_score = (
                (quality_stats.with_alt / quality_stats.total * 0.5) +
                (quality_stats.with_title / quality_stats.total * 0.5)
            ) * 100 if quality_stats.total > 0 else 0
            
            summary = DataSummary(
                total_images=basic_stats.total_images,
                unique_sources=basic_stats.unique_sources,
                last_24h_count=basic_stats.last_24h_count,
                last_7d_count=basic_stats.last_7d_count,
                last_30d_count=basic_stats.last_30d_count,
                top_sources=[dict(row._mapping) for row in top_sources],
                file_extensions={row.file_extension: row.count for row in extensions},
                data_quality_score=round(quality_score, 2)
            )
            
            # キャッシュに保存（10分間）
            self.redis_client.setex(cache_key, 600, json.dumps(summary.dict(), default=str))
            
            return summary
    
    async def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """日別統計取得"""
        with get_db_connection() as conn:
            query = """
            SELECT 
                DATE(scraped_at) as date,
                COUNT(*) as count,
                COUNT(DISTINCT source_url) as unique_sources
            FROM scraped_images
            WHERE scraped_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(scraped_at)
            ORDER BY date DESC
            """ % days
            
            result = conn.execute(text(query))
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def get_source_stats(self) -> List[Dict[str, Any]]:
        """ソース別統計取得"""
        with get_db_connection() as conn:
            query = """
            SELECT 
                source_url,
                COUNT(*) as total_count,
                COUNT(CASE WHEN scraped_at >= NOW() - INTERVAL '7 days' THEN 1 END) as last_7d_count,
                MAX(scraped_at) as last_scraped,
                AVG(CASE WHEN alt_text IS NOT NULL AND alt_text != '' THEN 1.0 ELSE 0.0 END) as alt_text_ratio
            FROM scraped_images
            GROUP BY source_url
            ORDER BY total_count DESC
            LIMIT 20
            """
            
            result = conn.execute(text(query))
            return [dict(row._mapping) for row in result.fetchall()]
    
    async def log_to_wandb(self, metrics: Dict[str, Any]) -> Dict[str, str]:
        """wandbにメトリクスをログ"""
        if not os.getenv('WANDB_API_KEY'):
            return {'status': 'skipped', 'reason': 'wandb API key not configured'}
        
        try:
            wandb.init(
                project="data-platform-metrics",
                name=f"api_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            wandb.log(metrics)
            wandb.finish()
            
            return {'status': 'success', 'logged_at': datetime.now().isoformat()}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}