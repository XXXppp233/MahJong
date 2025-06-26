import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import os
import re
import json

def get_bilibili_voice(url):
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
}
    pattern = r'(https://.*?")'
    pattern1 = r'-\d+-(\d+)'
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text
        print("成功获取网页内容！")

        soup = BeautifulSoup(html_content, 'html.parser')
        rtitle = soup.find('title')
        title = rtitle.text.split('_')[-3]
        scripts = soup.find_all('script')
  
        play_info = None
        for script in scripts:
            if 'window.__playinfo__' in script.text:
                play_info = script.text
                break
        print("成功获取播放信息！")
        links = re.findall(pattern, play_info)
        print(f"找到 {len(links)} 个 m4s 片段链接。")
        voice_links = []
        print("开始解析获取音频链接")
        for link in links:
            link = link[0:-1]  # 去掉末尾的引号
            match = re.search(pattern1, link)
            # 解析 URL 的 bw 参数
            if match:
                # 提取捕获组的内容，即分类码
                classification_code = match.group(1)
                # 检查分类码的开头来判断类型
                if classification_code.startswith('100'):
                    continue
                elif classification_code.startswith('30'):
                    voice_links.append(link)
                else:
                    # 模式匹配成功，但分类码不是1000或300开头
                    print("未知类型")
        number = len(voice_links)     
        print(f"找到 {number} 个音频片段链接。")       
        # 下载音频片段            
        for voice_link in reversed(voice_links):
            try:
                response = requests.get(voice_link, headers=headers, timeout=10)
                if response.status_code == 200:
                    with open(f'{title}_voice.m4s', 'wb') as f:
                        f.write(response.content)
                    print(f"音频片段 {title} {number}已保存。")
                    break
            except Exception as e:
                print(f"下载音频片段 {title} {number}失败: ")
                number -= 1
                continue
        return f'{title}_voice.m4s'
    except requests.exceptions.RequestException as e:
        print(f"请求网页时出错: {e}")
        return None
# Bilibili 音频为 域名/v1/resource/数字-p-1000数字，顺序靠前的质量高
# Bilibili 视频为 域名/v1/resource/数字-p-300数字，顺序越靠后的质量越高


# url = 'https://www.bilibili.com/video/BV1g4moYBE4M'
# print(get_bilibili_voice(url))
