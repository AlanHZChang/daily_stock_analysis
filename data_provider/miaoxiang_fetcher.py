"""
妙想(MiaoXiang)金融數據源 — 東方財富妙想 Skills MX_API 封裝

定位：
    補齊公開行情接口不穩定時的垂直數據塊（個股資金流 / 籌碼分佈），
    不參與日線 K 線主鏈路（`_DAILY_MARKET_FETCHER_SUPPORT` 中支持市場為空集）。

數據來源：
    妙想量化 API（MX_API），自然語言查詢返回結構化表格：
    POST https://mkapi2.dfcfs.com/finskillshub/api/claw/query
    Header: apikey: <MX_APIKEY>
    Body:   {"toolQuery": "<自然語言查詢>"}

啟用條件：
    配置 MX_APIKEY 後由 DataFetcherManager 自動實例化。
"""

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from .base import (
    BaseFetcher,
    DataFetchError,
    _is_etf_code,
    _is_non_cn_request,
    normalize_stock_code,
)
from .realtime_types import ChipDistribution

logger = logging.getLogger(__name__)

# 妙想 API 基礎地址（國內直連）
MX_API_BASE_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"

# 查詢結果緩存 TTL（秒）：同一股票的資金流/籌碼短期內複用，降低配額消耗
MX_CACHE_TTL_SECONDS = 300.0
# 相鄰請求最小間隔（秒）：對自然語言接口保持禮貌
MX_MIN_REQUEST_INTERVAL_SECONDS = 0.3





def _parse_number(text: Any) -> Optional[float]:
    """從 '13.91' / '13.91元' / '-1.5' 等文本中提取數值。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def _parse_money_yuan(text: Any) -> Optional[float]:
    """把 '-93.64萬元' / '1.2億' / '-493.5萬' 解析為元的浮點數。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if "%" in s or "％" in s:
        return None
    val = _parse_number(s)
    if val is None:
        return None
    if "亿" in s:
        val *= 1e8
    elif "万" in s:
        val *= 1e4
    return val


def _parse_ratio(text: Any) -> Optional[float]:
    """把 '83.24%' 解析為 0.8324；'0.83' 視為已是小數。"""
    val = _parse_number(text)
    if val is None:
        return None
    if "%" in str(text or ""):
        val = val / 100.0
    if val > 1.0:
        # 兜底：個別查詢可能返回 83.24 但不帶 % 號
        val = val / 100.0
    return val


class MiaoxiangFetcher(BaseFetcher):
    """妙想金融數據源（資金流 / 籌碼分佈補充源）"""

    name = "MiaoxiangFetcher"
    # 聲明該補充源可服務的資金流市場；探測與預算分配據此判斷,
    # 避免把僅支持其他市場的同名方法實現(如 FutuFetcher 僅港股)誤判為本市場補充源
    capital_flow_markets = {"cn"}
    # Admission is shared by chip/flow queries and by fresh manager instances.
    # Never queue another quota-consuming request behind an abandoned worker.
    _request_lock = threading.Lock()

    def __init__(
        self,
        api_key: str = "",
        priority: int = 6,
        timeout: int = 10,
        base_url: str = MX_API_BASE_URL,
        cache_ttl: float = MX_CACHE_TTL_SECONDS,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.priority = int(priority)
        self.timeout = int(timeout)
        self.base_url = base_url.rstrip("/")
        self._cache_ttl = float(cache_ttl)
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._last_request_ts = 0.0

    def is_available_for_request(self, capability: str = "") -> bool:
        """Keep this supplement-only provider out of every daily-data route."""
        return capability != "daily_data"

    # ------------------------------------------------------------------
    # MX_API 客戶端
    # ------------------------------------------------------------------

    def _query_tables(self, cache_key: str, tool_query: str) -> List[Dict[str, Any]]:
        """執行一次自然語言查詢，返回 dataTableDTOList（帶 TTL 緩存）。"""
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                return cached[1]

        if not self._request_lock.acquire(blocking=False):
            raise DataFetchError("妙想 API 請求仍在執行，跳過本次補充查詢")
        try:
            wait = MX_MIN_REQUEST_INTERVAL_SECONDS - (time.time() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            try:
                response = requests.post(
                    self.base_url,
                    headers={"apikey": self.api_key, "Content-Type": "application/json"},
                    json={"toolQuery": tool_query},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                raise DataFetchError(f"妙想 API 請求失敗: {exc}") from exc
            finally:
                self._last_request_ts = time.time()
        finally:
            self._request_lock.release()

        if payload.get("status") != 0:
            message = str(payload.get("message", ""))[:120]
            raise DataFetchError(f"妙想 API 返回錯誤: status={payload.get('status')} {message}")

        # 兼容兩種官方返回形態（有限的顯式候選路徑，不做遞歸兜底）：
        #   A. 實測形態:  data.data.searchDataResultDTO.dataTableDTOList
        #   B. 公開文檔:  data.dataTableDTOList
        tables: list = []
        data_node = payload.get("data")
        if isinstance(data_node, dict):
            candidate_a = (
                data_node.get("data", {})
                if isinstance(data_node.get("data"), dict) else {}
            ).get("searchDataResultDTO", {})
            candidate_a = candidate_a.get("dataTableDTOList") if isinstance(candidate_a, dict) else None
            candidate_b = data_node.get("dataTableDTOList")
            for candidate in (candidate_a, candidate_b):
                if isinstance(candidate, list) and candidate:
                    tables = [t for t in candidate if isinstance(t, dict)]
                    break
        if not tables:
            raise DataFetchError("妙想 API 未返回數據表格")

        with self._cache_lock:
            self._cache[cache_key] = (time.time(), tables)
        return tables

    @staticmethod
    def _table_name_map(table_dto: Dict[str, Any]) -> Dict[str, Any]:
        """Use the same numeric-key/list mapping for selection and row parsing."""
        name_map = table_dto.get("nameMap") or {}
        if isinstance(name_map, list):
            name_map = {str(i): v for i, v in enumerate(name_map)}
        return name_map

    @staticmethod
    def _table_rows(table_dto: Dict[str, Any]) -> List[Dict[str, str]]:
        """把 MX 表格（headName 為行軸 + 指標列數組）轉為 [{label: value}] 行列表。"""
        table = table_dto.get("table") or {}
        name_map = MiaoxiangFetcher._table_name_map(table_dto)
        heads = table.get("headName") or []
        rows: List[Dict[str, str]] = []
        for key, values in table.items():
            if key == "headName" or not isinstance(values, list):
                continue
            label = str(name_map.get(key, name_map.get(str(key), key)))
            for idx, value in enumerate(values):
                while len(rows) <= idx:
                    rows.append({})
                rows[idx][label] = "" if value is None else str(value)
        # 保留每行對應日期（headName），便於資金流按日聚合
        for idx, head in enumerate(heads):
            while len(rows) <= idx:
                rows.append({})
            rows[idx]["_date"] = str(head)
        return rows

    def _table_labels(self, table_dto: Dict[str, Any]) -> List[str]:
        """返回表格包含的全部指標名（經 nameMap 映射）。"""
        table = table_dto.get("table") or {}
        name_map = self._table_name_map(table_dto)
        labels: List[str] = []
        for key in table:
            if key == "headName":
                continue
            labels.append(str(name_map.get(key, name_map.get(str(key), key))))
        return labels

    def _find_table_by_label(self, tables: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
        """返回包含指定指標名的表格；命中多張時優先行數最多的（時間序列優先於當前快照）。"""
        best: Optional[Dict[str, Any]] = None
        best_rows = -1
        for table_dto in tables:
            if not any(keyword in label for label in self._table_labels(table_dto)):
                continue
            rows = len((table_dto.get("table") or {}).get("headName") or [])
            if rows > best_rows:
                best = table_dto
                best_rows = rows
        return best

    def _find_table_by_label_score(
        self,
        tables: List[Dict[str, Any]],
        required_keyword: str,
        wanted_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        """自然語言返回的表格組合不穩定：按"目標字段命中數"評分選表，行數少者優先（快照優於序列）。"""
        best: Optional[Dict[str, Any]] = None
        best_key = (-1, 10**9)
        for table_dto in tables:
            labels = self._table_labels(table_dto)
            if not any(required_keyword in label for label in labels):
                continue
            score = sum(1 for kw in wanted_keywords if any(kw in label for label in labels))
            rows = len((table_dto.get("table") or {}).get("headName") or [])
            if (score, -rows) > best_key:
                best = table_dto
                best_key = (score, -rows)
        return best

    # ------------------------------------------------------------------
    # 籌碼分佈
    # ------------------------------------------------------------------

    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        通過妙想 API 獲取籌碼分佈核心指標：
        獲利比例 / 平均成本 / 90%集中度 / 70%集中度。

        Returns:
            ChipDistribution（source=miaoxiang），失敗拋 DataFetchError。
        """
        stock_code = normalize_stock_code(stock_code)
        if _is_non_cn_request(stock_code) or _is_etf_code(stock_code):
            logger.debug(f"[API跳過] {stock_code} 非A股个股，無筹码分佈數據")
            return None

        tables = self._query_tables(
            f"chip:{stock_code}",
            f"{stock_code} 獲利比例 平均成本 90%筹码集中度 70%筹码集中度",
        )
        target = self._find_table_by_label_score(
            tables,
            required_keyword="平均成本",
            wanted_keywords=["获利比例", "90%筹码集中度", "70%筹码集中度"],
        )
        if target is None:
            target = self._find_table_by_label(tables, "筹码")
        if target is None:
            raise DataFetchError("妙想 API 筹码分佈返回缺少可用表格")

        rows = self._table_rows(target)
        if not rows:
            raise DataFetchError("妙想 API 筹码分佈表格為空")
        row = rows[0]

        avg_cost = _parse_number(row.get("平均成本"))
        profit_ratio = _parse_ratio(row.get("获利比例"))
        concentration_90 = _parse_ratio(row.get("90%筹码集中度"))
        concentration_70 = _parse_ratio(row.get("70%筹码集中度"))

        if avg_cost is None or avg_cost <= 0:
            raise DataFetchError(f"妙想 API 筹码分佈平均成本無效: {row}")

        chip = ChipDistribution(
            code=stock_code,
            date=str(row.get("_date", "")).split(" ")[0],
            source="miaoxiang",
        )
        chip.avg_cost = float(avg_cost)
        if profit_ratio is not None:
            chip.profit_ratio = float(profit_ratio)
        if concentration_90 is not None:
            chip.concentration_90 = float(concentration_90)
        if concentration_70 is not None:
            chip.concentration_70 = float(concentration_70)
        return chip

    # ------------------------------------------------------------------
    # 個股資金流
    # ------------------------------------------------------------------

    def get_capital_flow(self, stock_code: str, top_n: int = 5) -> Dict[str, Any]:
        """
        通過妙想 API 獲取個股主力資金流：
        今日主力淨流入 + 近5日/近10日主力淨流入合計。

        Returns:
            與 AkshareFundamentalAdapter.get_capital_flow 同構的 payload。
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "stock_flow": {},
            "sector_rankings": {"top": [], "bottom": []},
            "source_chain": [],
            "errors": [],
        }
        stock_code = normalize_stock_code(stock_code)
        if _is_non_cn_request(stock_code) or _is_etf_code(stock_code):
            return result

        try:
            tables = self._query_tables(
                f"flow:{stock_code}",
                f"{stock_code} 近10日每日主力淨流入资金",
            )
        except DataFetchError as exc:
            result["errors"].append(f"miaoxiang: {exc}")
            return result
        # Natural-language responses may include prices or ratios before the amount.
        # Only explicit monetary metrics may feed currency-valued stock_flow fields.
        amount_labels = {"主力净流入", "主力净流入资金", "主力净流入金额"}
        amount_tables = [
            table for table in tables
            if any(label in amount_labels for label in self._table_labels(table))
        ]
        target = self._find_table_by_label(amount_tables, "主力净流入")
        if target is None:
            result["errors"].append("miaoxiang: no capital flow table")
            return result

        rows = self._table_rows(target)
        series: List[Tuple[str, Optional[float]]] = []
        for row in rows:
            label = next((k for k in row if k in amount_labels), None)
            value = _parse_money_yuan(row.get(label)) if label is not None else None
            # Keep missing observations in their original trading window; dropping
            # them would backfill today's value or compress a 5/10-day aggregate.
            series.append((str(row.get("_date", "")), value))

        if not series or all(value is None for _, value in series):
            result["errors"].append("miaoxiang: empty capital flow series")
            return result

        # headName 通常按日期倒序（最新在前），這裡顯式按日期排序保證聚合正確
        series.sort(key=lambda item: item[0], reverse=True)
        latest = series[0][1]
        # 窗口字段必須拿到完整交易日數據才輸出,避免把部分歷史合計
        # 誤標為 5日/10日淨流入(稀疏歷史的次新股會注入錯誤中期信號)
        def window_sum(size: int) -> Optional[float]:
            values = [value for _, value in series[:size]]
            if len(values) < size or any(value is None for value in values):
                return None
            return sum(values)

        inflow_5d = window_sum(5)
        inflow_10d = window_sum(10)

        result["stock_flow"] = {
            "main_net_inflow": latest,
            "inflow_5d": inflow_5d,
            "inflow_10d": inflow_10d,
        }
        result["status"] = "partial"
        result["source_chain"].append("miaoxiang:capital_flow")
        return result

    # ------------------------------------------------------------------
    # 日線主鏈路：顯式不支持（快速失敗，避免佔用降級鏈時間）
    # ------------------------------------------------------------------

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise DataFetchError("MiaoxiangFetcher 不提供日線行情數據（專用補充數據源）")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise DataFetchError("MiaoxiangFetcher 不提供日線行情數據（專用補充數據源）")
