import streamlit as st
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from datetime import datetime
import time

# --- 設定頁面配置 ---
st.set_page_config(page_title="台幣匯率轉換器", layout="wide")

# --- 爬蟲功能函數 ---
async def fetch_exchange_rates():
    """
    使用 crawl4ai 爬取台灣銀行牌告匯率
    """
    url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url)
        
    if not result.success:
        return None
        
    # 使用 BeautifulSoup 解析 HTML (針對台灣銀行表格結構)
    soup = BeautifulSoup(result.html, 'html.parser')
    table_rows = soup.find('tbody').find_all('tr')
    
    data = []
    
    for row in table_rows:
        # 獲取幣別名稱 (例如: USD 美金)
        currency_cell = row.find('div', class_='visible-phone')
        if not currency_cell:
            continue
        currency_name = currency_cell.get_text(strip=True)
        
        # 獲取匯率數值 (現金買入, 現金賣出, 即期買入, 即期賣出)
        # 欄位索引: 1=現金買入, 2=現金賣出, 3=即期買入, 4=即期賣出
        cells = row.find_all('td')
        
        # 定義一個處理數值的內部函數
        def parse_rate(cell):
            val = cell.get_text(strip=True)
            if val == '-' or val == '':
                return "暫停交易"
            return val

        cash_buy = parse_rate(cells[1])
        cash_sell = parse_rate(cells[2]) # 這是銀行賣給我們的價格 (我們換外幣看這個)
        
        # 需求10: 無法交易的貨幣(完全沒有匯率)，不要顯示出來
        # 這裡的邏輯是：如果現金賣出是暫停交易，且現金買入也是暫停交易，視為該貨幣目前無法臨櫃交易
        if cash_buy == "暫停交易" and cash_sell == "暫停交易":
            continue

        data.append({
            "幣別": currency_name,
            "現金買入": cash_buy,
            "現金賣出": cash_sell, # 用於計算台幣換外幣
            "更新時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return pd.DataFrame(data)

# --- 資料載入與快取管理 ---
# 使用 Streamlit 的 session state 來儲存資料，避免每次互動都重爬
if 'exchange_data' not in st.session_state:
    st.session_state.exchange_data = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

async def update_data():
    with st.spinner('正在從台灣銀行抓取最新匯率...'):
        df = await fetch_exchange_rates()
        if df is not None:
            st.session_state.exchange_data = df
            st.session_state.last_update = datetime.now()
        else:
            st.error("爬取資料失敗，請檢查網路連線。")

# --- 主程式介面 ---
def main():
    st.title("💱 台幣匯率即時轉換 (Crawl4AI + Streamlit)")

    # 手動更新按鈕 (需求7)
    if st.button("🔄 手動更新匯率"):
        asyncio.run(update_data())

    # 檢查是否需要初次載入
    if st.session_state.exchange_data is None:
        asyncio.run(update_data())

    # --- 自動更新邏輯 (需求6) ---
    # 使用 st.fragment 讓這塊區域獨立運作，並設定 run_every 達到定時執行
    @st.fragment(run_every="10m")
    def auto_refresh_check():
        # 顯示最後更新時間
        if st.session_state.last_update:
            st.caption(f"最後更新時間: {st.session_state.last_update.strftime('%H:%M:%S')} (每 10 分鐘自動更新)")
        
        # 這裡可以加入邏輯強迫重新抓取，但因為 st.fragment 會定時重跑，
        # 我們只需確保資料是最新的。為了不頻繁打擾伺服器，
        # 這裡依賴 fragment 的計時器觸發上面的 update_data 邏輯 (如果結合全頁刷新)
        # 為了更嚴謹的後端自動化，我們在 fragment 內部執行檢查
        
        # 如果距離上次更新超過 9 分鐘 (稍微寬容一點)，則執行更新
        if st.session_state.last_update:
            delta = datetime.now() - st.session_state.last_update
            if delta.total_seconds() > 590: # 約 10 分鐘
                asyncio.run(update_data())
                st.rerun()

    auto_refresh_check()

    # 取得目前的 DataFrame
    df = st.session_state.exchange_data

    if df is not None:
        # --- 版面配置 (需求3) ---
        col1, col2 = st.columns([1, 2])

        # --- 左邊欄位：計算匯率 (需求4) ---
        with col1:
            st.header("💰 匯率試算")
            st.info("請輸入您想兌換的台幣金額")
            
            # 使用者輸入交易金額 (需求9的部分邏輯移至此以便操作)
            twd_amount = st.number_input("台幣金額 (TWD)", min_value=1.0, value=1000.0, step=100.0)
            
            # 選擇目標貨幣
            # 過濾掉「暫停交易」的貨幣選項，以免無法計算
            valid_currencies = df[df['現金賣出'] != "暫停交易"]['幣別'].tolist()
            target_currency = st.selectbox("選擇兌換貨幣", valid_currencies)
            
            if target_currency:
                # 取得該貨幣的匯率
                rate_row = df[df['幣別'] == target_currency].iloc[0]
                rate_str = rate_row['現金賣出']
                
                if rate_str != "暫停交易":
                    exchange_rate = float(rate_str)
                    converted_amount = twd_amount / exchange_rate
                    
                    st.divider()
                    st.markdown(f"### 試算結果")
                    st.markdown(f"**{twd_amount:,.0f} TWD** 可兌換約：")
                    st.markdown(f"## {converted_amount:,.2f} {target_currency.split()[-1]}")
                    st.caption(f"參考匯率 (現金賣出): {exchange_rate}")
                else:
                    st.warning("此貨幣目前暫停現金交易")

        # --- 右邊欄位：表格顯示 (需求5, 9) ---
        with col2:
            st.header("📊 即時匯率表")
            
            # 需求9: 右邊欄位顯示台幣轉換為其他貨幣 (動態計算)
            # 我們在原始 DataFrame 中增加一欄「可兌換金額」
            
            display_df = df.copy()
            
            def calculate_exchange(row):
                rate = row['現金賣出']
                if rate == "暫停交易":
                    return "無法交易"
                try:
                    # 台幣 / 匯率 = 外幣金額
                    val = twd_amount / float(rate)
                    return f"{val:,.2f}"
                except:
                    return "計算錯誤"

            display_df[f'台幣{twd_amount:,.0f}元可換'] = display_df.apply(calculate_exchange, axis=1)
            
            # 調整顯示順序
            display_df = display_df[['幣別', '現金買入', '現金賣出', f'台幣{twd_amount:,.0f}元可換']]
            
            # 使用 st.dataframe 顯示，並Highlight 暫停交易
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "幣別": st.column_config.TextColumn("幣別", help="貨幣名稱"),
                    "現金賣出": st.column_config.TextColumn("銀行賣出 (匯率)", help="銀行賣給你的價格"),
                },
                hide_index=True
            )
            st.caption("* 「現金賣出」為銀行賣給您的價格，即您用台幣換外幣的匯率。")

if __name__ == "__main__":
    main()