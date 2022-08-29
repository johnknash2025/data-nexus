import requests
import re
from bs4 import BeautifulSoup

url = "https://search.nifty.com/imagesearch/search?select=1&q=%s&ss=up"
keyword = "猫"
r = requests.get(url%(keyword))
soup = BeautifulSoup(r.text,'lxml')
imgs = soup.find_all('img',src=re.compile('^https://msp.c.yimg.jp/yjimage'))
for img in imgs:
        print(img['src'])
