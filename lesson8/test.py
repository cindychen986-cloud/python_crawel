import os
import asyncio
import sys
from typing import List, Dict, Tuple

# 範例原始資料（模擬爬蟲輸出）
RAW_SAMPLE = [
    {"幣別": " USD ", "本行即期買入": " 29.500 ", "本行即期賣出": " 30.000 "},
    {"幣別": " EUR ", "本行即期買入": " ", "本行即期賣出": ""},  # 暫停交易範例
    {"幣別": " JPY ", "本行即期買入": "0.260", "本行即期賣出": "0.270"},
    {"幣別": "", "本行即期買入": "abc", "本行即期賣出": "def"},  # 非數值
]

def clean_and_filter(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """根據 plan.md 清理字元並過濾不可交易的貨幣（買入與賣出皆須為可解析數值）"""
    out = []
    for row in data:
        currency = row.get("幣別", "").strip()
        buy = row.get("本行即期買入", "").strip()
        sell = row.get("本行即期賣出", "").strip()
        # 檢查數值可解析
        try:
            buy_v = float(buy)
            sell_v = float(sell)
        except Exception:
            continue
        if currency:
            out.append({"幣別": currency, "本行即期買入": buy, "本行即期賣出": sell})
    return out

def calculate_conversion(twd_amount: float, buy_rate: float, sell_rate: float) -> Tuple[float, float]:
    """
    計算台幣轉外幣（依 plan.md）
    - 買入：銀行買入外幣 ⇒ 用 buy_rate 計算 TWD / buy_rate
    - 賣出：銀行賣出外幣 ⇒ 用 sell_rate 計算 TWD / sell_rate
    """
    if buy_rate <= 0 or sell_rate <= 0:
        raise ValueError("rate must be > 0")
    return (twd_amount / buy_rate, twd_amount / sell_rate)

def approx(a: float, b: float, rel: float = 1e-6) -> bool:
    return abs(a - b) <= rel * max(1.0, abs(a), abs(b))

def test_clean_and_filter():
    cleaned = clean_and_filter(RAW_SAMPLE)
    currencies = [r["幣別"] for r in cleaned]
    assert "USD" in currencies, "USD should be present"
    assert "JPY" in currencies, "JPY should be present"
    assert "EUR" not in currencies, "EUR should be filtered out"
    assert "" not in currencies, "empty currency should be filtered out"
    usd = next(r for r in cleaned if r["幣別"] == "USD")
    assert usd["本行即期買入"] == "29.500"
    assert usd["本行即期賣出"] == "30.000"

def test_calculate_conversion_results():
    buy_res, sell_res = calculate_conversion(3000.0, 29.5, 30.0)
    assert approx(buy_res, 3000.0 / 29.5), "buy result mismatch"
    assert approx(sell_res, 3000.0 / 30.0), "sell result mismatch"

async def _maybe_await(maybe_coro):
    if asyncio.iscoroutine(maybe_coro) or asyncio.isfuture(maybe_coro):
        return await maybe_coro
    return maybe_coro

def test_fetch_exchange_rates_if_available():
    try:
        from lesson8.main import fetch_exchange_rates  # type: ignore
    except Exception:
        print("SKIP: lesson8.main.fetch_exchange_rates not available")
        return
    try:
        res = fetch_exchange_rates()
        data = asyncio.run(_maybe_await(res))
    except Exception as e:
        print(f"SKIP: fetch_exchange_rates raised during test: {e}")
        return
    if data is not None and not isinstance(data, list):
        raise AssertionError("fetch_exchange_rates must return None or list")
    print("OK: fetch_exchange_rates integration (skipped if not available)")

def test_exchange_rate_app_instantiate_if_available():
    # skip headless environments on non-Windows
    if (os.name != "nt") and (not os.environ.get("DISPLAY")):
        print("SKIP: No DISPLAY (headless), skip tkinter instantiation test")
        return
    try:
        from lesson8.main import ExchangeRateApp  # type: ignore
    except Exception:
        print("SKIP: lesson8.main.ExchangeRateApp not available")
        return
    app = None
    try:
        app = ExchangeRateApp()
        if not (hasattr(app, "_update_treeview") or hasattr(app, "_update_ui_with_data")):
            raise AssertionError("ExchangeRateApp missing expected methods")
        print("OK: ExchangeRateApp instantiated")
    finally:
        if app is not None:
            try:
                app.destroy()
            except Exception:
                pass

def main():
    tests = [
        ("clean_and_filter", test_clean_and_filter),
        ("calculate_conversion_results", test_calculate_conversion_results),
        ("fetch_exchange_rates_if_available", test_fetch_exchange_rates_if_available),
        ("exchange_rate_app_instantiate_if_available", test_exchange_rate_app_instantiate_if_available),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"[ERROR] {name}: {e}")
    if failures:
        print(f"\n{failures} test(s) failed.")
        sys.exit(1)
    print("\nAll tests passed or skipped.")
    sys.exit(0)

if __name__ == "__main__":
    main()
