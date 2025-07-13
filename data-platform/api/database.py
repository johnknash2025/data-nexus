"""
データベース接続設定
"""
import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient
import redis
from contextlib import contextmanager

# 環境変数からDB接続情報取得
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://admin:admin123@postgres/data_platform')
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://admin:admin123@mongodb:27017/')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')

# PostgreSQL設定
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MongoDB設定
mongo_client = MongoClient(MONGODB_URL)
mongo_db = mongo_client.data_platform

# Redis設定
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def get_db_session():
    """PostgreSQLセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_mongo_client():
    """MongoDBクライアント取得"""
    return mongo_db

def get_redis_client():
    """Redisクライアント取得"""
    return redis_client

@contextmanager
def get_db_connection():
    """PostgreSQL接続コンテキストマネージャー"""
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()

# データベーステーブル定義
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from sqlalchemy.sql import func

class ScrapedImage(Base):
    """スクレイピング画像テーブル"""
    __tablename__ = 'scraped_images'
    
    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(Text, nullable=False, index=True)
    image_url = Column(Text, nullable=False, unique=True)
    alt_text = Column(Text)
    page_title = Column(Text)
    file_extension = Column(String(10))
    has_local_copy = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=func.now(), index=True)
    created_at = Column(DateTime, default=func.now())

# インデックス定義
Index('idx_scraped_images_source_scraped', ScrapedImage.source_url, ScrapedImage.scraped_at)
Index('idx_scraped_images_extension', ScrapedImage.file_extension)

def create_tables():
    """テーブル作成"""
    Base.metadata.create_all(bind=engine)