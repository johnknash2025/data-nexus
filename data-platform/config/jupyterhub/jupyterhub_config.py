# JupyterHub設定ファイル

import os

# 基本設定
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = 8000

# 認証設定（開発環境用）
c.JupyterHub.authenticator_class = 'jupyterhub.auth.DummyAuthenticator'
c.DummyAuthenticator.password = "admin123"

# スポーナー設定
c.JupyterHub.spawner_class = 'jupyterhub.spawner.LocalProcessSpawner'

# データディレクトリ
c.JupyterHub.data_files_path = '/srv/jupyterhub/data'

# ログ設定
c.JupyterHub.log_level = 'INFO'

# 管理者ユーザー
c.Authenticator.admin_users = {'admin'}

# 自動起動設定
c.JupyterHub.cleanup_servers = False