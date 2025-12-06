import asyncio
import nest_asyncio
from crawl4ai import AsyncWebCrawler

nest_asyncio.apply()

async def main():
    #建立一個AsyncWebCrawler的實體
    async with AsyncWebCrawler() as crawler:
        #Run the crawler on a URL
        result = await crawler.arun(url='https://www.bnext.com.tw/')

        #列印取出的結果
        print(result.markdown)

#py檔執行
asyncio.run(main())