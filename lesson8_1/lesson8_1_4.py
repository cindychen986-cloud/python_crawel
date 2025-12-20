"""
簡易股票即時監控範例（lesson8_1_4.py）

功能概要：
- 提供一個最小可運作的 Tkinter GUI 範本
- 左側為股票代碼清單（範例），可加入觀察清單
- 右側顯示已加入觀察股票的簡易資訊卡片
- 背景執行緒使用 asyncio 模擬非同步抓取（stub），透過 queue 回傳結果
- 提供手動更新與自動更新開關（每 60 秒）

此檔為範例骨架，實際爬蟲請以 `lesson8_1_3.py` 與 `crawl4ai` 實作取代 stub。
"""

import asyncio
import threading
import time
import queue
from tkinter import Tk, Frame, Button, Label, Entry, VERTICAL, RIGHT, Y, BOTH, LEFT, StringVar, END
from tkinter import font as tkfont
from tkinter import ttk


class StockMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("股票監控 - lesson8_1_4")
        self.update_interval = 60_000  # ms, tkinter.after 使用

        # Data structures
        # 優先嘗試從 twstock 套件載入完整證券代碼清單，若失敗則使用範例硬編碼清單
        try:
            import twstock

            # twstock.codes is a dict of code -> StockCodeInfo
            self.available_stocks = [(code, info.name) for code, info in twstock.codes.items()]
            # sort by code for stable ordering
            self.available_stocks.sort(key=lambda x: x[0])
        except Exception:
            self.available_stocks = [
                ("2330", "TSMC"),
                ("2317", "Hon Hai"),
                ("2412", "Chunghwa"),
                ("0050", "ETF0050"),
            ]

        self.watchlist = []  # list of codes
        # command queue -> background worker, result_queue -> main UI
        self.cmd_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.bg_thread = None
        self.bg_stop_event = threading.Event()

        # 優先設定一個支援中文的預設字型，減少亂碼問題
        try:
            for fam in ("Microsoft JhengHei", "Segoe UI", "Noto Sans CJK TC", "Arial Unicode MS"):
                try:
                    tkfont.nametofont("TkDefaultFont").configure(family=fam, size=10)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # build a quick lookup map for names
        self.code_name_map = {code: name for code, name in self.available_stocks}

        # Build UI
        self._build_ui()

        # Start polling queue
        self._poll_queue()

        # Auto-update flag
        self.auto_update = False

    def _build_ui(self):
        main_frame = Frame(self.root)
        main_frame.pack(fill=BOTH, expand=True)

        left_frame = Frame(main_frame, width=200)
        left_frame.pack(side=LEFT, fill=Y)

        right_frame = Frame(main_frame)
        right_frame.pack(side=LEFT, fill=BOTH, expand=True)

        # Left: stock list + search + add
        Label(left_frame, text="股票列表").pack(pady=4)
        self.search_var = Entry(left_frame)
        self.search_var.pack(fill='x', padx=4)
        self.search_var.bind("<KeyRelease>", lambda e: self._filter_list())

        # 使用 Treeview 顯示可選股票（模擬 Listbox，較好支援大量項目）
        listbox_frame = Frame(left_frame)
        listbox_frame.pack(fill='both', expand=False, padx=4, pady=4)
        self.list_font = tkfont.nametofont("TkFixedFont").copy()
        self.list_font.configure(size=10)
        self.listbox = ttk.Treeview(listbox_frame, columns=("name",), show='tree', height=8)
        for code, name in self.available_stocks:
            self.listbox.insert('', 'end', iid=code, text=f"{code} - {name}")
        self.listbox.pack(fill='both', expand=True, side=LEFT)

        Button(left_frame, text="加入觀察", command=self._add_selected).pack(pady=4)

        # 手動輸入股票代碼加入觀察清單
        Label(left_frame, text="以代碼加入").pack(pady=(8, 0))
        self.code_entry = Entry(left_frame)
        self.code_entry.pack(fill='x', padx=4, pady=(0, 4))
        Button(left_frame, text="加入", command=self._add_by_code).pack(pady=4)

        # Right: controls + cards
        ctrl_frame = Frame(right_frame)
        ctrl_frame.pack(fill='x')
        Button(ctrl_frame, text="手動更新", command=self.manual_update).pack(side=LEFT, padx=4, pady=4)
        self.auto_btn = Button(ctrl_frame, text="啟動自動", command=self.toggle_auto)
        self.auto_btn.pack(side=LEFT, padx=4)

        self.cards_frame = Frame(right_frame)
        self.cards_frame.pack(fill=BOTH, expand=True, padx=6, pady=6)

    def _filter_list(self):
        q = self.search_var.get().strip().lower()
        # filter treeview contents
        for code, name in self.available_stocks:
            item_text = f"{code} - {name}"
            visible = (not q) or (q in code) or (q in name.lower())
            if visible:
                if not self.listbox.exists(code):
                    self.listbox.insert('', 'end', iid=code, text=item_text)
                else:
                    self.listbox.item(code, text=item_text)
            else:
                if self.listbox.exists(code):
                    self.listbox.delete(code)

    def _add_selected(self):
        sel = self.listbox.selection()
        if not sel:
            return
        code = sel[0]
        if code in self.watchlist:
            return
        self.watchlist.append(code)
        self._create_card(code)
        # immediately request an update for the newly added code
        self._ensure_bg_thread()
        self.cmd_queue.put({"_cmd": "update_now", "symbols": [code]})

    def _add_by_code(self):
        text = getattr(self, 'code_entry', None)
        if text is None:
            return
        code = text.get().strip()
        if not code:
            return
        # 標準化：僅取前段（若使用者輸入含名稱）
        if " - " in code:
            code = code.split(" - ")[0].strip()
        # 若已在 watchlist 則不重複加入
        if code in self.watchlist:
            return
        # 若 available_stocks 有名稱，則可使用，但不強制存在
        self.watchlist.append(code)
        self._create_card(code)
        # 立即抓取新加入股票的價格
        self._ensure_bg_thread()
        self.cmd_queue.put({"_cmd": "update_now", "symbols": [code]})

    def _create_card(self, code):
        frame = Frame(self.cards_frame, bd=1, relief='solid', padx=8, pady=8, bg='#ffffff')
        frame.pack(fill='x', pady=6)
        name = self.code_name_map.get(code, '')
        title = Label(frame, text=f"{code}{(' - ' + name) if name else ''}", font=(None, 12, 'bold'), bg='#ffffff')
        title.pack(anchor='w')
        price_label = Label(frame, text="價格: -", fg='#1a73e8', bg='#ffffff')
        price_label.pack(anchor='w')
        change_label = Label(frame, text="漲跌: -", bg='#ffffff')
        change_label.pack(anchor='w')
        percent_label = Label(frame, text="漲幅: -", bg='#ffffff')
        percent_label.pack(anchor='w')

        detail_label = Label(frame, text="開: -  最高: -  最低: -", bg='#ffffff')
        detail_label.pack(anchor='w')
        extra_label = Label(frame, text="成交量: -  前收: -", bg='#ffffff')
        extra_label.pack(anchor='w')

        info_label = Label(frame, text="更新時間: -", bg='#ffffff')
        info_label.pack(anchor='w')
        remove_btn = Button(frame, text="移除", command=lambda: self._remove_card(code, frame))
        remove_btn.pack(anchor='e')

        # store reference
        frame._meta = {
            "code": code,
            "price_label": price_label,
            "change_label": change_label,
            "percent_label": percent_label,
            "detail_label": detail_label,
            "extra_label": extra_label,
            "info_label": info_label,
        }

    def _remove_card(self, code, frame):
        if code in self.watchlist:
            self.watchlist.remove(code)
        frame.destroy()

    def manual_update(self):
        if not self.watchlist:
            return
        self._ensure_bg_thread()
        # enqueue a single-run update request
        self.cmd_queue.put({"_cmd": "update_now", "symbols": list(self.watchlist)})

    def toggle_auto(self):
        self.auto_update = not self.auto_update
        self.auto_btn.config(text="Stop Auto" if self.auto_update else "Start Auto")
        if self.auto_update:
            self._ensure_bg_thread()
            # schedule periodic trigger
            self._schedule_auto()

    def _schedule_auto(self):
        if not self.auto_update:
            return
        # instruct bg thread to run an update
        if self.watchlist:
            self.cmd_queue.put({"_cmd": "update_now", "symbols": list(self.watchlist)})
        # schedule next
        self.root.after(self.update_interval, self._schedule_auto)

    def _ensure_bg_thread(self):
        if self.bg_thread and self.bg_thread.is_alive():
            return
        self.bg_stop_event.clear()
        self.bg_thread = threading.Thread(target=self._bg_worker, daemon=True)
        self.bg_thread.start()

    # ---------- formatting helpers ----------
    def _fmt_number(self, val, ndigits=2):
        try:
            f = float(val)
        except Exception:
            return str(val)
        if ndigits == 0:
            return f"{int(round(f)):,}"
        fmt = f"{{:,.{ndigits}f}}"
        return fmt.format(f)

    def _fmt_volume(self, val):
        try:
            v = int(float(val))
        except Exception:
            return str(val)
        return f"{v:,}"

    def _color_for_change(self, change_val):
        try:
            c = float(change_val)
        except Exception:
            return 'black'
        if c > 0:
            return 'red'
        if c < 0:
            return 'green'
        return 'black'

    def _bg_worker(self):
        # background thread runs an asyncio loop and listens to the queue for update commands
        asyncio.run(self._bg_async_main())

    async def _bg_async_main(self):
        while not self.bg_stop_event.is_set():
            try:
                # non-blocking get: if no command, sleep briefly
                try:
                    cmd = self.cmd_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue

                if isinstance(cmd, dict) and cmd.get("_cmd") == "update_now":
                    symbols = cmd.get("symbols", [])
                    results = await self.fetch_multiple_stocks(symbols)
                    # put results back for main thread to process
                    self.result_queue.put({"_cmd": "results", "data": results})
                else:
                    await asyncio.sleep(0.1)
            except Exception:
                await asyncio.sleep(0.5)

    async def fetch_stock_info(self, symbol: str):
        """
        Stub: 模擬非同步抓取單支股票資料。
        實作時請以 crawl4ai / twstock / 真實網路請求替換。
        """
        await asyncio.sleep(0.2)  # simulate network latency
        now = time.strftime("%H:%M:%S")
        # generate plausible stub numbers for demo
        base = 100 + (hash(symbol) % 100)
        frac = round(time.time() % 1, 2)
        price = round(base + frac, 2)
        change = round(((hash(symbol) % 5) - 2) + (0 if frac < 0.5 else 0.1), 2)
        prev_close = round(price - change, 2)
        percent = round((change / prev_close) * 100 if prev_close else 0, 2)
        open_p = round(prev_close + ((hash(symbol + 'o') % 3) - 1), 2)
        high = round(max(price, open_p) + (hash(symbol + 'h') % 3), 2)
        low = round(min(price, open_p) - (hash(symbol + 'l') % 3), 2)
        volume = (hash(symbol) % 1000) * 100
        return {
            "code": symbol,
            "price": f"{price}",
            "change": f"{change}",
            "percent": f"{percent}%",
            "open": f"{open_p}",
            "high": f"{high}",
            "low": f"{low}",
            "volume": f"{volume}",
            "prev_close": f"{prev_close}",
            "time": now,
        }

    async def fetch_multiple_stocks(self, symbols):
        """並行抓取多支股票（使用 asyncio.gather）"""
        if not symbols:
            return {}
        tasks = [self.fetch_stock_info(s) for s in symbols]
        res = await asyncio.gather(*tasks, return_exceptions=True)
        out = {}
        for item in res:
            if isinstance(item, Exception):
                continue
            out[item["code"]] = item
        return out

    def _poll_queue(self):
        # poll for results placed into queue by background worker
        try:
            while True:
                item = self.result_queue.get_nowait()
                if isinstance(item, dict) and item.get("_cmd") == "results":
                    self._apply_results(item.get("data", {}))
                # ignore other internal messages
        except queue.Empty:
            pass
        finally:
            self.root.after(200, self._poll_queue)

    def _apply_results(self, data: dict):
        # Update UI cards with new data
        for child in list(self.cards_frame.winfo_children()):
            meta = getattr(child, "_meta", None)
            if not meta:
                continue
            code = meta["code"]
            info = data.get(code)
            if not info:
                continue
            # price / change / percent with formatting and color
            price_text = self._fmt_number(info.get('price', ''), ndigits=2)
            meta["price_label"].config(text=f"價格: {price_text}")
            # change color
            change_val = info.get('change', '')
            change_text = self._fmt_number(change_val, ndigits=2)
            change_color = self._color_for_change(change_val)
            if meta.get("change_label"):
                meta["change_label"].config(text=f"漲跌: {change_text}", fg=change_color)
            # percent (may be like '1.23%')
            pct = info.get('percent', '')
            try:
                if isinstance(pct, str) and pct.endswith('%'):
                    pct_num = float(pct.rstrip('%'))
                    pct_text = f"{pct_num:.2f}%"
                else:
                    pct_text = str(pct)
            except Exception:
                pct_text = str(pct)
            if meta.get("percent_label"):
                meta["percent_label"].config(text=f"漲幅: {pct_text}", fg=change_color)
            # details: open, high, low
            o = self._fmt_number(info.get('open', ''), ndigits=2)
            h = self._fmt_number(info.get('high', ''), ndigits=2)
            l = self._fmt_number(info.get('low', ''), ndigits=2)
            if meta.get("detail_label"):
                meta["detail_label"].config(text=f"開: {o}  最高: {h}  最低: {l}")
            # extra: volume, prev_close
            vol = self._fmt_volume(info.get('volume', ''))
            prev = self._fmt_number(info.get('prev_close', ''), ndigits=2)
            if meta.get("extra_label"):
                meta["extra_label"].config(text=f"成交量: {vol}  前收: {prev}")
            if meta.get("info_label"):
                meta["info_label"].config(text=f"更新時間: {info.get('time')}")

    def stop(self):
        self.bg_stop_event.set()


def main():
    root = Tk()
    app = StockMonitorApp(root)
    try:
        root.mainloop()
    finally:
        app.stop()


if __name__ == '__main__':
    main()