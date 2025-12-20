import asyncio
import json
import sys
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "匯率資訊",
    "baseSelector": "table[title='牌告匯率'] tr",
    "fields": [
        {
            "name": "幣別",
            "selector": "td[data-table='幣別'] div.print_show",
            "type": "text"
        },
        {
            "name": "本行即期買入",
            "selector": "td[data-table='本行即期買入']",
            "type": "text"
        },
        {
            "name": "本行即期賣出",
            "selector": "td[data-table='本行即期賣出']",
            "type": "text"
        }
    ]
}

async def fetch_rates():
    """爬取台灣銀行匯率資料"""
    try:
        strategy = JsonCssExtractionStrategy(schema)
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=strategy
        )
        
        async with AsyncWebCrawler() as crawler:
            url = 'https://rate.bot.com.tw/xrt?Lang=zh-TW'
            result = await crawler.arun(url=url, config=run_config)
            
            if result.extracted_content:
                data = json.loads(result.extracted_content)
                return data
            else:
                print("錯誤: 無法提取匯率資料", file=sys.stderr)
                return []
                
    except Exception as e:
        print(f"爬蟲執行錯誤: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return []

def main():
    """主程式"""
    try:
        rates = asyncio.run(fetch_rates())
        
        if rates:
            with open("rates.json", "w", encoding="utf-8") as f:
                json.dump(rates, f, ensure_ascii=False, indent=2)
            print(f"成功寫入 {len(rates)} 筆匯率資料")
            sys.exit(0)
        else:
            print("錯誤: 沒有取得任何匯率資料", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"主程式錯誤: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

