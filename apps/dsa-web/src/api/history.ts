import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  HistoryListResponse,
  HistoryItem,
  HistoryFilters,
  AnalysisReport,
  NewsIntelResponse,
  NewsIntelItem,
  RunDiagnosticSummary,
  StockBarResponse,
} from '../types/analysis';
import type { RunFlowSnapshot } from '../types/runFlow';

// ============ API 接口 ============

export interface GetHistoryListParams extends HistoryFilters {
  page?: number;
  limit?: number;
}

export interface GetHistoryListOptions {
  signal?: AbortSignal;
}

export const historyApi = {
  /**
   * 獲取歷史分析列表
   * @param params 篩選和分頁參數
   */
  getList: async (
    params: GetHistoryListParams = {},
    options: GetHistoryListOptions = {},
  ): Promise<HistoryListResponse> => {
    const { stockCode, reportType, startDate, endDate, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (stockCode) queryParams.stock_code = stockCode;
    if (reportType) queryParams.report_type = reportType;
    if (startDate) queryParams.start_date = startDate;
    if (endDate) queryParams.end_date = endDate;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history', {
      params: queryParams,
      signal: options.signal,
    });

    const data = toCamelCase<{ total: number; page: number; limit: number; items: HistoryItem[] }>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: data.items.map(item => toCamelCase<HistoryItem>(item)),
    };
  },

  /**
   * 獲取歷史報告詳情
   * @param recordId 分析歷史記錄主鍵 ID（使用 ID 而非 query_id，因為 query_id 在批量分析時可能重複）
   */
  getDetail: async (recordId: number): Promise<AnalysisReport> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}`);
    return toCamelCase<AnalysisReport>(response.data);
  },

  /**
   * 獲取歷史報告關聯新聞
   * @param recordId 分析歷史記錄主鍵 ID
   * @param limit 返回數量限制
   */
  getNews: async (recordId: number, limit = 20): Promise<NewsIntelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/news`, {
      params: { limit },
    });

    const data = toCamelCase<NewsIntelResponse>(response.data);
    return {
      total: data.total,
      items: (data.items || []).map(item => toCamelCase<NewsIntelItem>(item)),
    };
  },

  /**
   * 獲取歷史報告的 Markdown 格式內容
   * @param recordId 分析歷史記錄主鍵 ID
   * @returns Markdown 格式的完整報告內容
   */
  getMarkdown: async (recordId: number): Promise<string> => {
    const response = await apiClient.get<{ content: string }>(`/api/v1/history/${recordId}/markdown`);
    return response.data.content;
  },

  /**
   * 生成歷史報告分享圖片
   * @param recordId 分析歷史記錄主鍵 ID
   */
  getShareImage: async (recordId: number): Promise<Blob> => {
    const response = await apiClient.get<Blob>(`/api/v1/history/${recordId}/share-image`, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * 獲取歷史報告運行診斷摘要
   * @param recordId 分析歷史記錄主鍵 ID
   */
  getDiagnostics: async (recordId: number): Promise<RunDiagnosticSummary> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/diagnostics`);
    return toCamelCase<RunDiagnosticSummary>(response.data);
  },

  /**
   * 獲取歷史報告運行流快照
   * @param recordId 分析歷史記錄主鍵 ID
   */
  getRecordFlow: async (recordId: number): Promise<RunFlowSnapshot> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/history/${recordId}/flow`);
    return toCamelCase<RunFlowSnapshot>(response.data);
  },

  /**
   * 批量刪除歷史記錄
   * @param recordIds 分析歷史記錄主鍵 ID 列表
   */
  deleteRecords: async (recordIds: number[]): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>('/api/v1/history', {
      data: { record_ids: recordIds },
    });

    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * 按股票代碼刪除所有歷史記錄
   * @param stockCode 股票代碼
   */
  deleteByCode: async (stockCode: string): Promise<{ deleted: number }> => {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/history/by-code/${encodeURIComponent(stockCode)}`);
    return toCamelCase<{ deleted: number }>(response.data);
  },

  /**
   * 獲取個股欄列表（不重複個股，不包含大盤覆盤）
   */
  getStockBarList: async (params: {
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<StockBarResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.startDate) queryParams.start_date = params.startDate;
    if (params.endDate) queryParams.end_date = params.endDate;
    if (params.limit) queryParams.limit = params.limit;

    const response = await apiClient.get<Record<string, unknown>>('/api/v1/history/stocks', {
      params: queryParams,
    });

    const data = toCamelCase<{ total: number; items: unknown[] }>(response.data);
    return {
      total: data.total,
      items: data.items.map(item => toCamelCase<Record<string, unknown>>(item) as unknown as typeof data.items[0]),
    } as StockBarResponse;
  },
};
