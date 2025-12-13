import asyncio,json
from crawl4ai import AsyncWebCrawler,CrawlerRunConfig,CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def main():
    html = """
<div class="item">
    <h2>項目1</h2>
    <a href="https://example.com/item1">連結1</a>
</div>"""

    schema ={
        "name":"項目名稱",
        "baseSelector":"div.item",
        "fields":[
            {
                "name":"標題",
                "selector":"h2",
                "type":"text"
            },
            {
                "name":"連結名稱",
                "selector":"a",
                "type":"text"
            },
            {
                "name":"連結網址",
                "selector":"a",
                "type":"attribute",
                "attribute":"href"
            }
        ]
    }
#JsonCssExtractionStrategy套件中的一個資料擷取策略類別。它允許你根據 JSON 格式的 schema，利用 CSS Selector 從 HTML 內容中擷取結構化資料。
# 會根據你定義的 schema，自動解析 HTML，並依據 selector 與 type 取得對應欄位的資料。這讓你可以用簡單的 JSON 描述擷取規則，而不用手動寫解析邏輯。
#簡單來說，它是用來「根據 CSS 選擇器與欄位設定，從 HTML 擷取資料」的工具。
    strategy = JsonCssExtractionStrategy(schema)

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=strategy
        )
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url=f"raw://{html}",
            config=run_config)
        data = json.loads(result.extracted_content)
        for item in data:
            print(f"標題: {item['標題']}")
            print(f"連結名稱: {item['連結名稱']}")
            print(f"連結網址: {item['連結網址']}")

if __name__ == "__main__":
    asyncio.run(main())