"""
画像スクレイピング - 既存のfind_all_img.pyを基にした改良版
"""
import os
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .base_scraper import BaseScraper

class ImageScraper(BaseScraper):
    """画像スクレイピングクラス"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('base_url')
        self.target_extensions = config.get('target_extensions', ['.jpg', '.jpeg', '.png', '.gif'])
        self.download_images = config.get('download_images', False)
        self.storage_path = config.get('storage_path', '/tmp/scraped_images')
        
    def scrape(self) -> List[Dict[str, Any]]:
        """画像URLをスクレイピング"""
        if not self.base_url:
            raise ValueError("base_url is required in config")
            
        self.logger.info(f"Starting image scraping from: {self.base_url}")
        
        try:
            response = requests.get(self.base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # ページタイトル取得
            page_title = soup.find('title')
            title_text = page_title.text.strip() if page_title else "Unknown"
            
            # 画像URL収集
            images_data = []
            img_tags = soup.find_all('img')
            
            for img_tag in img_tags:
                src = img_tag.get('src')
                if not src:
                    continue
                    
                # 相対URLを絶対URLに変換
                full_url = urljoin(self.base_url, src)
                
                # 対象拡張子チェック
                if any(full_url.lower().endswith(ext) for ext in self.target_extensions):
                    image_data = {
                        'source_url': self.base_url,
                        'image_url': full_url,
                        'alt_text': img_tag.get('alt', ''),
                        'title': img_tag.get('title', ''),
                        'page_title': title_text,
                        'file_extension': self._get_file_extension(full_url)
                    }
                    
                    # 画像ダウンロード（オプション）
                    if self.download_images:
                        local_path = self._download_image(full_url, title_text)
                        image_data['local_path'] = local_path
                    
                    images_data.append(image_data)
            
            self.logger.info(f"Found {len(images_data)} images")
            return images_data
            
        except Exception as e:
            self.logger.error(f"Error scraping images: {e}")
            raise
    
    def _get_file_extension(self, url: str) -> str:
        """URLからファイル拡張子を取得"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in self.target_extensions:
            if path.endswith(ext):
                return ext
        return ''
    
    def _download_image(self, image_url: str, page_title: str) -> str:
        """画像をダウンロード"""
        try:
            # ディレクトリ作成
            safe_title = "".join(c for c in page_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            dir_path = os.path.join(self.storage_path, safe_title)
            os.makedirs(dir_path, exist_ok=True)
            
            # ファイル名生成
            filename = os.path.basename(urlparse(image_url).path)
            if not filename:
                filename = f"image_{hash(image_url)}.jpg"
            
            file_path = os.path.join(dir_path, filename)
            
            # 画像ダウンロード
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            self.logger.info(f"Downloaded image: {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Error downloading image {image_url}: {e}")
            return ""
    
    def extract_structured_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """PostgreSQL用の構造化データ抽出"""
        structured = []
        for item in data:
            structured.append({
                'source_url': item['source_url'],
                'image_url': item['image_url'],
                'alt_text': item['alt_text'][:500] if item['alt_text'] else '',  # 長さ制限
                'page_title': item['page_title'][:200] if item['page_title'] else '',
                'file_extension': item['file_extension'],
                'has_local_copy': bool(item.get('local_path'))
            })
        return structured
    
    def get_postgres_table(self) -> str:
        return 'scraped_images'
    
    def get_mongodb_collection(self) -> str:
        return 'images_raw'