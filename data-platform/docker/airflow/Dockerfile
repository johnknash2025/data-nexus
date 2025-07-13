FROM apache/airflow:2.7.3-python3.11

USER root

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Python依存関係のインストール
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# スクレイピング用の追加パッケージ
RUN pip install --no-cache-dir \
    beautifulsoup4 \
    lxml \
    selenium \
    requests \
    pandas \
    sqlalchemy \
    psycopg2-binary \
    pymongo \
    wandb \
    mlflow