import urllib3
from bs4 import BeautifulSoup

url = 'https://nhentai.to/g/304138/1'
http = urllib3.PoolManager()
response = http.request('get', url)
soup = BeautifulSoup(response.data, 'html.parser')
title = soup.find('title').text
print(title)
print(soup.find("div",id="info-block"))