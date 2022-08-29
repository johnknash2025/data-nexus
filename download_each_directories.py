import requests
from bs4 import BeautifulSoup

url = 'https://nhentai.to/g/304138/'
images = []
soup = BeautifulSoup(requests.get(url).content,'lxml')

print(soup.find("div",id="info").h1)