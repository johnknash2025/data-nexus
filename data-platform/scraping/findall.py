import re
import urllib3
from bs4 import BeautifulSoup

url = 'https://nhentai.to/g/304138/1'
http = urllib3.PoolManager()
response = http.request('get', url)
soup = BeautifulSoup(response.data, 'html.parser')


for i in soup.find_all(re.compile("^h")):
    print(i.text)