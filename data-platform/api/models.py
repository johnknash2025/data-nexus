"""
データモデル定義
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ImageData(BaseModel):
    """画像データモデル"""
    id: int
    source_url: str
    image_url: str
    alt_text: Optional[str] = None
    page_title: Optional[str] = None
    file_extension: Optional[str] = None
    has_local_copy: bool = False
    scraped_at: datetime
    created_at: datetime

class DataSummary(BaseModel):
    """データサマリーモデル"""
    total_images: int
    unique_sources: int
    last_24h_count: int
    last_7d_count: int
    last_30d_count: int
    top_sources: List[Dict[str, Any]]
    file_extensions: Dict[str, int]
    data_quality_score: float

class TrainingDataset(BaseModel):
    """学習データセットモデル"""
    structured_data: List[Dict[str, Any]]
    raw_data: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]
    total_records: int
    created_at: datetime

class AnalyticsMetrics(BaseModel):
    """分析メトリクスモデル"""
    metric_name: str
    value: float
    timestamp: datetime
    tags: Optional[Dict[str, str]] = None

class ScrapingJob(BaseModel):
    """スクレイピングジョブモデル"""
    job_id: str
    source_url: str
    status: str  # pending, running, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    records_scraped: Optional[int] = None
    error_message: Optional[str] = None

class DataQualityReport(BaseModel):
    """データ品質レポートモデル"""
    total_records: int
    duplicate_count: int
    null_url_count: int
    invalid_extension_count: int
    quality_score: float
    recommendations: List[str]
    generated_at: datetime