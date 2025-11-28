from playwright.sync_api import sync_playwright
from time import sleep

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        print(type(browser))
        # 開啟新分頁
        page = browser.new_page()
        page.goto("https://www.google.com")
        print(page.title())
        sleep(5)
        browser.close()
        
    print("釋放資源檔")

if __name__ == "__main__":
    main()
