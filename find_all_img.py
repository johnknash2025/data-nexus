import requests
import os
from bs4 import BeautifulSoup

url = 'https://nhentai.to/g/341118' #"input()"
#https://nhentai.to/g/304138/
#https://nhentai.to/g/271739/
images = []
soup = BeautifulSoup(requests.get(url).content,'lxml')

new_dir_path= "/home/keigo/git/python_beautifulsoup/img/"+soup.find("div",id="info").h1.text
print(new_dir_path)
if os.path.exists(new_dir_path) == False :
    os.mkdir(new_dir_path)

for link in soup.find_all("img"):
    print(link.get("src"))
    if not link.get("src") == None:
        if link.get("src").endswith(".jpg"):
            images.append(link.get("src"))

for target in images:
    resp = requests.get(target)
    with open(new_dir_path + '/' + target.split('/')[-1], 'wb') as f:
        f.write(resp.content)# 重要！.contentを入れないと画像データではなくtextデータになってしまう。
