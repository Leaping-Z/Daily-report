import os
import re
import requests
import yfinance as yf
from datetime import datetime
import xml.etree.ElementTree as ET

# ==================== 配置区 ====================
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")

# ==================== 工具函数 ====================

def clean_html(raw):
    """清洗HTML标签，保留纯文本"""
    if not raw:
        return ""
    # 去掉HTML标签
    clean = re.sub(r'<[^>]+>', '', raw)
    # 去掉多余空白
    clean = re.sub(r'\s+', ' ', clean).strip()
    # 去掉常见RSS垃圾前缀
    clean = re.sub(r'^(图片来源|图|原标题|原标题：|原题|导语|导语：)\s*', '', clean)
    return clean

def fetch_rss_news(url, max_items=6):
    """通用RSS解析器，提取标题+摘要"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.encoding = 'utf-8'
        root = ET.fromstring(resp.content)
        
        # 注册命名空间（有些RSS用content:encoded）
        namespaces = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }
        
        items = []
        for item in root.iter("item"):
            title = item.find("title")
            link = item.find("link")
            
            # 优先取 description，其次取 content:encoded
            desc = item.find("description")
            content = item.find("content:encoded", namespaces)
            
            title_text = clean_html(title.text) if title is not None and title.text else ""
            link_text = link.text.strip() if link is not None and link.text else ""
            
            # 提取摘要
            desc_text = ""
            if content is not None and content.text:
                desc_text = clean_html(content.text)
            elif desc is not None and desc.text:
                desc_text = clean_html(desc.text)
            
            # 截断摘要到合适长度
            if desc_text:
                if len(desc_text) > 180:
                    desc_text = desc_text[:180] + "..."
                elif len(desc_text) < 20:
                    desc_text = ""  # 太短的摘要不要
            
            if title_text and title_text not in [i["title"] for i in items]:
                items.append({
                    "title": title_text,
                    "desc": desc_text,
                    "link": link_text
                })
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"RSS失败: {str(e)[:80]}")
        return []

def fetch_news_multi_sources(sources, max_items=6):
    """多源聚合，自动去重，凑够条数"""
    all_news = []
    seen = set()
    
    for name, url in sources:
        if len(all_news) >= max_items:
            break
        news = fetch_rss_news(url, max_items=max_items - len(all_news) + 1)
        for n in news:
            if n["title"] not in seen:
                seen.add(n["title"])
                n["source"] = name
                all_news.append(n)
        print(f"{'✅' if news else '❌'} {name}: {len(news)}条")
    
    return all_news[:max_items]

# ==================== 新闻获取 ====================

def get_international_news():
    """国际时政 - 聚焦冲突、外交、地缘"""
    sources = [
        ("BBC中文", "http://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
        ("联合早报", "https://rsshub.app/zaobao/realtime/world"),
        ("路透", "https://rsshub.app/reuters/world/china"),
        ("德国之声", "https://rsshub.app/dw/news"),
    ]
    return fetch_news_multi_sources(sources, max_items=6)

def get_domestic_news():
    """国内热点 - 社会、商业、民生，减少政治口号"""
    sources = [
        ("澎湃新闻", "https://rsshub.app/thepaper/featured"),
        ("界面新闻", "https://rsshub.app/jiemian/lists/71.html"),
        ("36氪", "https://rsshub.app/36kr/newsflashes"),
        ("虎嗅", "https://rsshub.app/huxiu/article"),
        ("网易", "https://rsshub.app/netease/news/rank/whole/click/10"),
    ]
    return fetch_news_multi_sources(sources, max_items=6)

# ==================== 金融数据 ====================

def get_us_stock():
    """美股三大指数 + 热门个股"""
    try:
        # 三大指数
        indices = {
            "道琼斯": "^DJI",
            "纳斯达克": "^IXIC",
            "标普500": "^GSPC"
        }
        result = {"indices": {}, "stocks": {}}
        
        for name, ticker in indices.items():
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                latest = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                change = latest - prev
                change_pct = (change / prev) * 100
                result["indices"][name] = {
                    "price": round(latest, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2)
                }
        
        # 热门个股
        hot_stocks = {
            "苹果": "AAPL", "微软": "MSFT", "英伟达": "NVDA",
            "特斯拉": "TSLA", "Meta": "META", "谷歌": "GOOGL",
            "亚马逊": "AMZN", "台积电": "TSM"
        }
        
        for name, ticker in hot_stocks.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                if len(hist) >= 2:
                    latest = hist["Close"].iloc[-1]
                    prev = hist["Close"].iloc[-2]
                    change_pct = ((latest - prev) / prev) * 100
                    result["stocks"][name] = round(change_pct, 2)
            except:
                continue
                
        return result
    except Exception as e:
        return {"error": str(e)}

def get_commodities():
    """大宗商品"""
    try:
        result = {}
        
        # 黄金
        gold = yf.Ticker("GC=F")
        g_hist = gold.history(period="2d")
        if len(g_hist) >= 2:
            g_latest = g_hist["Close"].iloc[-1]
            g_prev = g_hist["Close"].iloc[-2]
            result["gold"] = {
                "price": round(g_latest, 2),
                "change_pct": round(((g_latest - g_prev) / g_prev) * 100, 2)
            }
        
        # 原油 WTI
        oil = yf.Ticker("CL=F")
        o_hist = oil.history(period="2d")
        if len(o_hist) >= 2:
            o_latest = o_hist["Close"].iloc[-1]
            o_prev = o_hist["Close"].iloc[-2]
            result["oil"] = {
                "price": round(o_latest, 2),
                "change_pct": round(((o_latest - o_prev) / o_prev) * 100, 2)
            }
        
        # 10年期美债收益率
        tnx = yf.Ticker("^TNX")
        t_hist = tnx.history(period="2d")
        if len(t_hist) >= 2:
            t_latest = t_hist["Close"].iloc[-1]
            t_prev = t_hist["Close"].iloc[-2]
            result["tnx"] = {
                "rate": round(t_latest, 2),
                "change": round(t_latest - t_prev, 2)
            }
        
        # 汇率
        fx = yf.Ticker("CNY=X")
        f_hist = fx.history(period="2d")
        if len(f_hist) >= 2:
            f_latest = f_hist["Close"].iloc[-1]
            f_prev = f_hist["Close"].iloc[-2]
            result["usd_cny"] = {
                "rate": round(f_latest, 4),
                "change_pct": round(((f_latest - f_prev) / f_prev) * 100, 3)
            }
        
        return result
    except Exception as e:
        return {"error": str(e)}

# ==================== 消息组装 ====================

def build_report():
    today = datetime.now().strftime("%Y年%m月%d日")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]
    
    print("🌍 获取国际时政...")
    intl_news = get_international_news()
    
    print("🇨🇳 获取国内热点...")
    domestic_news = get_domestic_news()
    
    print("📈 获取金融数据...")
    us_stock = get_us_stock()
    comm = get_commodities()
    
    lines = []
    lines.append(f"📰 <b>每日晨报</b> | {today} {weekday}")
    lines.append("─" * 22)
    lines.append("")
    
    # ===== 国际时事 =====
    lines.append("🌍 <b>国际时事</b>")
    if intl_news:
        for i, n in enumerate(intl_news, 1):
            lines.append(f"<b>{i}. {n['title']}</b>")
            if n['desc']:
                lines.append(f"   {n['desc']}")
            lines.append("")
    else:
        lines.append("暂无数据")
        lines.append("")
    
    # ===== 国内热点 =====
    lines.append("🇨🇳 <b>国内热点</b>")
    if domestic_news:
        for i, n in enumerate(domestic_news, 1):
            lines.append(f"<b>{i}. {n['title']}</b>")
            if n['desc']:
                lines.append(f"   {n['desc']}")
            lines.append("")
    else:
        lines.append("暂无数据")
        lines.append("")
    
    # ===== 美股市场 =====
    lines.append("📈 <b>美股市场</b>")
    if "error" in us_stock:
        lines.append(f"获取失败: {us_stock['error']}")
    else:
        # 三大指数
        for name, data in us_stock.get("indices", {}).items():
            emoji = "📈" if data["change"] >= 0 else "📉"
            lines.append(f"{emoji} <b>{name}</b>: {data['price']} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)")
        lines.append("")
        
        # 热门个股
        stocks = us_stock.get("stocks", {})
        if stocks:
            lines.append("<b>热门个股涨跌：</b>")
            up = [(k, v) for k, v in stocks.items() if v >= 0]
            down = [(k, v) for k, v in stocks.items() if v < 0]
            
            if up:
                up_str = " | ".join([f"{n} +{v}%" for n, v in sorted(up, key=lambda x: -x[1])])
                lines.append(f"🟢 {up_str}")
            if down:
                down_str = " | ".join([f"{n} {v}%" for n, v in sorted(down, key=lambda x: x[1])])
                lines.append(f"🔴 {down_str}")
            lines.append("")
    
    # ===== 大宗商品 & 汇率 =====
    lines.append("🥇 <b>大宗商品 & 汇率</b>")
    if "error" not in comm:
        if "gold" in comm:
            g = comm["gold"]
            emoji = "📈" if g["change_pct"] >= 0 else "📉"
            lines.append(f"{emoji} 黄金: {g['price']}美元/盎司 ({g['change_pct']:+.2f}%)")
        
        if "oil" in comm:
            o = comm["oil"]
            emoji = "📈" if o["change_pct"] >= 0 else "📉"
            lines.append(f"{emoji} 原油(WTI): {o['price']}美元/桶 ({o['change_pct']:+.2f}%)")
        
        if "tnx" in comm:
            t = comm["tnx"]
            lines.append(f"📊 10年期美债: {t['rate']}% ({t['change']:+.2f}bp)")
        
        if "usd_cny" in comm:
            f = comm["usd_cny"]
            lines.append(f"💵 美元兑人民币: {f['rate']} ({f['change_pct']:+.3f}%)")
    else:
        lines.append("获取失败")
    
    lines.append("")
    lines.append("⏰ 数据截止至北京时间08:00")
    lines.append("🤖 由 GitHub Actions 自动生成")
    
    return "\n".join(lines)

# ==================== 推送 ====================

def push_pushplus(content):
    if not PUSHPLUS_TOKEN:
        print("❌ 未设置 PUSHPLUS_TOKEN")
        return False
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"📰 每日晨报 {datetime.now().strftime('%m/%d')}",
        "content": content,
        "template": "html"
    }
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        if result.get("code") == 200:
            print("✅ PushPlus 推送成功")
            return True
        else:
            print(f"❌ PushPlus 失败: {result}")
            return False
    except Exception as e:
        print(f"❌ PushPlus 异常: {e}")
        return False

def push_serverchan(content):
    if not SERVERCHAN_KEY:
        return False
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    data = {
        "title": f"📰 每日晨报 {datetime.now().strftime('%m/%d')}",
        "desp": content.replace("<b>", "**").replace("</b>", "**")
    }
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            print("✅ Server酱 推送成功")
            return True
        return False
    except:
        return False

# ==================== 主程序 ====================

if __name__ == "__main__":
    print("🚀 开始生成每日晨报...")
    report = build_report()
    print("\n" + "="*40)
    print(report)
    print("="*40 + "\n")
    
    pushed = False
    if PUSHPLUS_TOKEN:
        pushed = push_pushplus(report)
    if not pushed and SERVERCHAN_KEY:
        pushed = push_serverchan(report)
    
    if not pushed:
        print("⚠️ 未配置推送渠道")

