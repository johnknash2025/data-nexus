-- PostgreSQL初期化スクリプト

-- Airflow用データベース作成
CREATE DATABASE airflow;

-- データ基盤用のスキーマ作成
CREATE SCHEMA IF NOT EXISTS data_platform;

-- 基本的な権限設定
GRANT ALL PRIVILEGES ON DATABASE data_platform TO admin;
GRANT ALL PRIVILEGES ON DATABASE airflow TO admin;
GRANT ALL PRIVILEGES ON SCHEMA data_platform TO admin;

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- インデックス用の設定
SET shared_preload_libraries = 'pg_stat_statements';