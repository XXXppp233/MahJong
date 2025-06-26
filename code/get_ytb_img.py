import requests
from bs4 import BeautifulSoup

def get_ytb_img(url):
# 目标网页 URL
    element_prop = {"as": "image", "rel": "preload"}
    img_format = None
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
    }

    try:
        # 发送 GET 请求
        response = requests.get(url, headers=headers, timeout=10) # 设置超时以避免程序卡死
        # 检查请求是否成功 (状态码 200 表示成功)
        response.raise_for_status() 
        # 获取网页的 HTML 内容
        html_content = response.text
        print("成功获取网页内容！")

        soup = BeautifulSoup(html_content, 'html.parser')
        element = soup.find('link', attrs=element_prop)
        rtitle = soup.find('title')
        title = rtitle.text.split(' - YouTube')[0]
        print(f"网页标题: {title if title else '未找到标题'}")

        if element:
            img_url = element['href']
            img_url = img_url.replace('hqdefault', 'maxresdefault')
            print(f"图片 URL: {img_url}")
            img = requests.get(img_url, headers=headers, timeout=10)
            img_format = img_url.split('.')[-1]
            print(f"图片格式: {img_format}")
            if img.status_code == 200:
                with open(f'{title}.{img_format}', 'wb') as f:
                    f.write(img.content)
                print(f"图片已保存为 {title}.{img_format}")
            else:
                print(f"下载图片失败，状态码: {img.status_code}")
        else:
            print(f"未找到元素: {element_prop}")

    except requests.exceptions.RequestException as e:
        print(f"请求网页时出错: {e}")
        html_content = None

    return f"{title}.{img_format}" if img_format else None

# url = 'https://www.youtube.com/watch?v=Y16_rDXcfcA'
# print(get_ytb_img(url))
