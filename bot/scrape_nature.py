import urllib.request
import re
import json

url = "https://www.nature.com/nature/current-issue"
req = urllib.request.Request(
    url, 
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
)

try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
except Exception as e:
    print(json.dumps([{"error": str(e)}]))
    exit()

# Extract links inside h3 or h4 tags to capture main articles and news
regex_pattern = r"""<h[34][^>]*>.*?<a[^>]*href=["'](/articles/[^"']+)["'][^>]*>(.*?)</a>.*?</h[34]>"""
matches = re.findall(regex_pattern, html, re.DOTALL | re.IGNORECASE)

results = []
seen_links = set()

for link, title in matches:
    # clean title
    title = re.sub(r'<[^>]+>', '', title) # remove inner tags like <i>
    title = title.strip()
    title = title.replace('\n', ' ').replace('\r', '')
    title = re.sub(r'\s+', ' ', title)
    
    # decode html entities
    import html as html_lib
    title = html_lib.unescape(title)
    
    full_link = f"https://www.nature.com{link}"
    
    if full_link not in seen_links and title:
        seen_links.add(full_link)
        results.append({
            "title": title,
            "link": full_link
        })
        
    if len(results) >= 30:
        break

print(json.dumps(results, indent=4, ensure_ascii=False))