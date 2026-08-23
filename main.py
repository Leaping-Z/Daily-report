import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ==================== 配置区 ====================
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "")

# ==================== 新闻获取（多源备用）====================

def fetch_rss_news(url, max_items=5):
    """通用RSS解析器，带错误处理"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        root = ET.fromstring(resp.content)
        
        items = []
        for item in root.iter("item"):
            title = item.find("title")
            link = item.find("link")
            
            title_text = title.text.strip() if title is not None and title.text else ""
            link_text = link.text.strip() if link is not None and link.text else ""
            
            if title_text and title_text not in [i["title"] for i in items]:
                items.append({"title": title_text, "link": link_text})
            if len(items) >= max_items:
                break
        return items
    except Exception as e:
        print(f"RSS失败 {url}: {str(e)[:60]}")
        return []

def fetch_news_multi_sources(sources, max_items=5):
    """多源聚合，自动去重，直到凑够条数"""
    all_news = []
    seen = set()
    
    for name, url in sources:
        if len(all_news) >= max_items:
            break
        news = fetch_rss_news(url, max_items=max_items - len(all_news))
        for n in news:
            if n["title"] not in seen:
                seen.add(n["title"])
                n["source"] = name
                all_news.append(n)
        if news:
            print(f"✅ {name}: 获取 {len(news)} 条")
        else:
            print(f"❌ {name}: 获取失败")
    
    return all_news

def get_international_news():
    """国际新闻 - 多源备用"""
    sources = [
        ("BBC中文", "http://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
        ("联合早报", "https://rsshub.app/zaobao/realtime/world"),
        ("路透", "https://rsshub.app/reuters/world/china"),
        ("FT中文", "https://rsshub.app/ft/chinese/hotstory"),
    ]
    return fetch_news_multi_sources(sources, max_items=5)

def get_domestic_news():
    """国内新闻 - 多源备用"""
    sources = [
        ("澎湃新闻", "https://rsshub.app/thepaper/featured"),
        ("新浪新闻", "https://rsshub.app/sina/news/china"),
        ("财新网", "https://rsshub.app/caixin/latest"),
        ("人民网", "http://www.people.com.cn/rss/politics.xml"),
        ("联合早报", "https://rsshub.app/zaobao/realtime/china"),
    ]
    return fetch_news_multi_sources(sources, max_items=5)

# ==================== 金融数据 ====================
def get_us_stock():
    """美股三大指数"""
    try:
        symbols = {
            "道琼斯": "^DJI",
            "纳斯达克": "^IXIC", 
            "标普500": "^GSPC"
        }
        result = {}
        for name, ticker in symbols.items():
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                latest = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                change = latest - prev
                change_pct = (change / prev) * 100
                result[name] = {
                    "price": round(latest, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2)
                }
        return result
    except Exception as e:
        return {"error": str(e)}

def get_gold_price():
    """黄金价格"""
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="2d")
        if len(hist) >= 2:
            latest = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            change = latest - prev
            change_pct = (change / prev) * 100
            return {
                "price": round(latest, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2)
            }
        return {"price": round(hist["Close"].iloc[-1], 2), "change": 0, "change_pct": 0}
    except Exception as e:
        return {"error": str(e)}

def get_exchange_rate():
    """美元兑人民币汇率"""
    try:
        fx = yf.Ticker("CNY=X")
        hist = fx.history(period="2d")
        if len(hist) >= 2:
            latest = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            change_pct = ((latest - prev) / prev) * 100
            return {"rate": round(latest, 4), "change_pct": round(change_pct, 3)}
        return {"rate": round(hist["Close"].iloc[-1], 4), "change_pct": 0}
    except Exception as e:
        return {"error": str(e)}

# ==================== 消息组装 ====================
def build_report():
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]
    
    print("🌍 获取国际新闻...")
    intl_news = get_international_news()
    print(f"   共 {len(intl_news)} 条")
    
    print("🇨🇳 获取国内新闻...")
    domestic_news = get_domestic_news()
    print(f"   共 {len(domestic_news)} 条")
    
    print("📈 获取金融数据...")
    us_stock = get_us_stock()
    gold = get_gold_price()
    fx = get_exchange_rate()
    
    # 组装HTML消息（PushPlus html模板支持<b>标签）
    lines = []
    lines.append(f"📰 <b>每日晨报</b> | {today} {weekday}")
    lines.append("─" * 20)
    
    # 国际新闻
    lines.append("🌍 <b>国际时事</b>")
    if intl_news:
        for i, n in enumerate(intl_news, 1):
            lines.append(f"{i}. {n['title']}")
    else:
        lines.append("暂无数据")
    lines.append("")
    
    # 国内新闻
    lines.append("🇨🇳 <b>国内热点</b>")
    if domestic_news:
        for i, n in enumerate(domestic_news, 1):
            lines.append(f"{i}. {n['title']}")
    else:
        lines.append("暂无数据")
    lines.append("")
    
    # 美股
    lines.append("📈 <b>美股走势</b>")
    if "error" in us_stock:
        lines.append(f"获取失败: {us_stock['error']}")
    else:
        for name, data in us_stock.items():
            emoji = "📈" if data["change"] >= 0 else "📉"
            lines.append(f"{emoji} {name}: {data['price']} ({data['change']:+.2f}, {data['change_pct']:+.2f}%)")
    lines.append("")
    
    # 金价
    lines.append("🥇 <b>金价走势</b>")
    if "error" in gold:
        lines.append(f"获取失败: {gold['error']}")
    else:
        emoji = "📈" if gold["change"] >= 0 else "📉"
        lines.append(f"{emoji} 现货黄金: {gold['price']}美元/盎司 ({gold['change']:+.2f}, {gold['change_pct']:+.2f}%)")
    lines.append("")
    
    # 汇率
    lines.append("💱 <b>汇率</b>")
    if "error" in fx:
        lines.append(f"获取失败: {fx['error']}")
    else:
        lines.append(f"💵 美元兑人民币: {fx['rate']} ({fx['change_pct']:+.3f}%)")
    
    lines.append("")
    lines.append("⏰ 数据截止至北京时间08:00")
    lines.append("🤖 由 GitHub Actions 自动生成")
    
    return "\n".join(lines)

# ==================== 推送 ====================
def push_pushplus(content):
    """PushPlus推送（html模板）"""
    if not PUSHPLUS_TOKEN:
        print("❌ 未设置 PUSHPLUS_TOKEN")
        return False
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"📰 每日晨报 {datetime.now().strftime('%m/%d')}",
        "content": content,
        "template": "html"  # 关键修复：支持<b>标签渲染
    }
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        if result.get("code") == 200:
            print("✅ PushPlus 推送成功")
            return True
        else:
            print(f"❌ PushPlus 推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ PushPlus 异常: {e}")
        return False

def push_serverchan(content):
    """Server酱推送"""
    if not SERVERCHAN_KEY:
        print("❌ 未设置 SERVERCHAN_KEY")
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
        else:
            print(f"❌ Server酱 推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ Server酱 异常: {e}")
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
        print("⚠️ 未配置任何推送渠道")
