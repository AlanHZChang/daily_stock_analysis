import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AlertsPage from '../AlertsPage';

const {
  listRules,
  createRule,
  deleteRule,
  enableRule,
  disableRule,
  testRule,
  listTriggers,
  listNotifications,
} = vi.hoisted(() => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  deleteRule: vi.fn(),
  enableRule: vi.fn(),
  disableRule: vi.fn(),
  testRule: vi.fn(),
  listTriggers: vi.fn(),
  listNotifications: vi.fn(),
}));

vi.mock('../../api/alerts', () => ({
  alertsApi: {
    listRules,
    createRule,
    deleteRule,
    enableRule,
    disableRule,
    testRule,
    listTriggers,
    listNotifications,
  },
}));

vi.mock('../../api/portfolio', () => ({
  portfolioApi: {
    getAccounts: vi.fn().mockResolvedValue({ accounts: [] }),
  },
}));

const parsedError = {
  title: '加載失敗',
  message: '告警 API 不可用',
  rawMessage: '告警 API 不可用',
  category: 'http_error' as const,
  status: 500,
};

const rule = {
  id: 1,
  name: '茅台價格突破',
  targetScope: 'single_symbol' as const,
  target: '600519',
  alertType: 'price_cross' as const,
  parameters: { direction: 'above' as const, price: 1800 },
  severity: 'warning' as const,
  enabled: true,
  source: 'api',
  createdAt: '2026-05-18T09:00:00',
  updatedAt: '2026-05-18T09:30:00',
};

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.clearAllMocks();
  listRules.mockResolvedValue({ items: [rule], total: 1, page: 1, pageSize: 20 });
  listTriggers.mockResolvedValue({
    items: [
      {
        id: 10,
        ruleId: 1,
        target: '600519',
        observedValue: 1801,
        threshold: 1800,
        reason: '600519 price above 1800',
        dataSource: 'realtime_quote',
        dataTimestamp: '2026-05-18T09:30:00',
        triggeredAt: '2026-05-18T09:30:01',
        status: 'triggered',
      },
    ],
    total: 1,
    page: 1,
    pageSize: 20,
  });
  listNotifications.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 });
  testRule.mockResolvedValue({
    ruleId: 1,
    status: 'triggered',
    triggered: true,
    observedValue: 1801,
    message: '600519 price above 1800',
  });
  createRule.mockResolvedValue(rule);
  disableRule.mockResolvedValue({ ...rule, enabled: false });
  enableRule.mockResolvedValue(rule);
  deleteRule.mockResolvedValue({ deleted: 1 });
});

describe('AlertsPage', () => {
  it('discloses environment rules even when the database rule list is empty', async () => {
    listRules.mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 20,
      ruleSources: { legacyConfigured: 2, legacyEffective: 1 },
    });
    render(<AlertsPage />);
    expect(await screen.findByText('存在環境變量告警規則')).toBeInTheDocument();
    expect(screen.getByText(/配置了 2 條有效規則.*去重後有 1 條/)).toBeInTheDocument();
    expect(screen.getByText(/刪除或禁用頁面規則不會停用環境規則/)).toBeInTheDocument();
  });

  it('keeps the warning when enabled database rules currently cover all environment rules', async () => {
    listRules.mockResolvedValue({
      items: [rule], total: 1, page: 1, pageSize: 20,
      ruleSources: { legacyConfigured: 1, legacyEffective: 0 },
    });
    render(<AlertsPage />);
    expect(await screen.findByText('存在環境變量告警規則')).toBeInTheDocument();
    expect(screen.getByText(/去重後有 0 條/)).toBeInTheDocument();
  });

  it('does not warn when no valid environment rules are configured', async () => {
    listRules.mockResolvedValue({
      items: [rule], total: 1, page: 1, pageSize: 20,
      ruleSources: { legacyConfigured: 0, legacyEffective: 0 },
    });
    render(<AlertsPage />);
    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
    expect(screen.queryByText('存在環境變量告警規則')).not.toBeInTheDocument();
  });

  it('loads rules, trigger history, and notification empty state', async () => {
    render(<AlertsPage />);

    expect(screen.getByText('管理事件告警、日線技術指标、自選股、持倉/賬戶聯動和大盘紅綠燈規則，執行一次性测试，並查看後臺評估任務記錄的觸發歷史。')).toBeInTheDocument();
    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
    expect(await screen.findByText('600519 price above 1800')).toBeInTheDocument();
    expect(await screen.findByText('暫無通知嘗試記錄')).toBeInTheDocument();
    expect(listRules).toHaveBeenCalledWith({
      enabled: undefined,
      alertType: undefined,
      page: 1,
      pageSize: 20,
    });
    expect(listTriggers).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    expect(listNotifications).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
  });

  it('runs a dry-run test and renders only declared response fields', async () => {
    listTriggers.mockResolvedValueOnce({ items: [], total: 0, page: 1, pageSize: 20 });
    render(<AlertsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '测试' }));

    await waitFor(() => expect(testRule).toHaveBeenCalledWith(1));
    expect(await screen.findByText('测试結果')).toBeInTheDocument();
    expect(screen.getByText(/600519 price above 1800/)).toBeInTheDocument();
    expect(screen.getByText(/观察值：1801/)).toBeInTheDocument();
    expect(screen.queryByText(/realtime_quote/)).not.toBeInTheDocument();
  });

  it('renders batch dry-run summary and target results', async () => {
    testRule.mockResolvedValueOnce({
      ruleId: 1,
      targetScope: 'watchlist',
      status: 'triggered',
      triggered: true,
      observedValue: 11,
      message: 'Evaluated 2 targets',
      evaluatedCount: 2,
      triggeredCount: 1,
      degradedCount: 1,
      skippedCount: 0,
      targetResults: [
        {
          target: '600519',
          displayTarget: '自選股 - 600519',
          status: 'triggered',
          recordStatus: 'triggered',
          triggered: true,
          observedValue: 11,
          message: 'triggered',
        },
        {
          target: '000001',
          displayTarget: '自選股 - 000001',
          status: 'not_triggered',
          recordStatus: 'degraded',
          triggered: false,
          observedValue: null,
          message: 'degraded',
        },
      ],
    });
    render(<AlertsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '测试' }));

    expect(await screen.findByText(/評估 2 · 觸發 1 · 降级 1 · 跳過 0/)).toBeInTheDocument();
    expect(screen.getByText('自選股 - 600519')).toBeInTheDocument();
    expect(screen.getByText(/not_triggered \/ degraded/)).toBeInTheDocument();
  });

  it('creates a rule through the page form and reloads rules', async () => {
    render(<AlertsPage />);

    await screen.findByText('茅台價格突破');
    fireEvent.change(screen.getByLabelText('標的代碼'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('價格閾值'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '創建規則' }));

    await waitFor(() => {
      expect(createRule).toHaveBeenCalledWith(expect.objectContaining({
        target: 'AAPL',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 200 },
      }));
    });
    expect(await screen.findByText(/已創建告警規則/)).toBeInTheDocument();
  });

  it('keeps create form values when create API fails', async () => {
    createRule.mockRejectedValueOnce({ parsedError });
    render(<AlertsPage />);

    await screen.findByText('茅台價格突破');
    fireEvent.change(screen.getByLabelText('標的代碼'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('價格閾值'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '創建規則' }));

    expect(await screen.findByText('加載失敗')).toBeInTheDocument();
    expect(screen.getByLabelText('標的代碼')).toHaveValue('aapl');
    expect(screen.getByLabelText('價格閾值')).toHaveValue(200);
  });

  it('clamps rules pagination when a mutation leaves the current page empty', async () => {
    const page2Rule = { ...rule, id: 2, name: '第二頁規則', target: 'AAPL' };
    listRules
      .mockResolvedValueOnce({ items: [rule], total: 21, page: 1, pageSize: 20 })
      .mockResolvedValueOnce({ items: [page2Rule], total: 21, page: 2, pageSize: 20 })
      .mockResolvedValueOnce({ items: [], total: 20, page: 2, pageSize: 20 })
      .mockResolvedValue({ items: [rule], total: 20, page: 1, pageSize: 20 });

    render(<AlertsPage />);

    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    expect(await screen.findByText('第二頁規則')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('刪除 第二頁規則'));
    fireEvent.click(await screen.findByRole('button', { name: '刪除' }));

    await waitFor(() => expect(deleteRule).toHaveBeenCalledWith(2));
    await waitFor(() => {
      expect(listRules).toHaveBeenCalledWith({
        enabled: undefined,
        alertType: undefined,
        page: 1,
        pageSize: 20,
      });
    });
    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
  });

  it('keeps the latest rules response when filter requests resolve out of order', async () => {
    const initialRequest = createDeferred<{ items: Array<typeof rule>; total: number; page: number; pageSize: number }>();
    const filteredRequest = createDeferred<{ items: Array<typeof rule>; total: number; page: number; pageSize: number }>();
    const staleRule = { ...rule, id: 3, name: '舊筛选規則', enabled: true };
    const filteredRule = { ...rule, id: 4, name: '停用規則', enabled: false };
    listRules
      .mockReset()
      .mockReturnValueOnce(initialRequest.promise)
      .mockReturnValueOnce(filteredRequest.promise);

    render(<AlertsPage />);

    fireEvent.change(screen.getByLabelText('啟停状态'), { target: { value: 'disabled' } });
    await waitFor(() => expect(listRules).toHaveBeenCalledTimes(2));

    filteredRequest.resolve({ items: [filteredRule], total: 1, page: 1, pageSize: 20 });
    expect(await screen.findByText('停用規則')).toBeInTheDocument();

    initialRequest.resolve({ items: [staleRule], total: 1, page: 1, pageSize: 20 });
    await waitFor(() => expect(screen.queryByText('舊筛选規則')).not.toBeInTheDocument());
    expect(screen.getByText('停用規則')).toBeInTheDocument();
  });

  it('refreshes toggle results with the latest enabled filter after a pending mutation', async () => {
    const enabledRule = { ...rule, name: '可停用規則', enabled: true };
    const disabledRule = { ...rule, id: 2, name: '已停用規則', enabled: false };
    const otherEnabledRule = { ...rule, id: 3, name: '其他啟用規則', enabled: true };
    const disableRequest = createDeferred<typeof disabledRule>();
    let mutationApplied = false;

    disableRule.mockReturnValueOnce(disableRequest.promise);
    listRules.mockImplementation(async (query: { enabled?: boolean }) => {
      if (query.enabled === false) {
        return {
          items: mutationApplied ? [disabledRule, { ...enabledRule, enabled: false }] : [disabledRule],
          total: mutationApplied ? 2 : 1,
          page: 1,
          pageSize: 20,
        };
      }
      return {
        items: [mutationApplied ? { ...enabledRule, enabled: false } : enabledRule, disabledRule, otherEnabledRule],
        total: 3,
        page: 1,
        pageSize: 20,
      };
    });

    render(<AlertsPage />);

    expect(await screen.findByText('其他啟用規則')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '停用' })[0]);
    fireEvent.change(screen.getByLabelText('啟停状态'), { target: { value: 'disabled' } });

    await waitFor(() => expect(screen.queryByText('其他啟用規則')).not.toBeInTheDocument());
    await act(async () => {
      mutationApplied = true;
      disableRequest.resolve({ ...enabledRule, enabled: false });
    });

    await waitFor(() => expect(listRules).toHaveBeenLastCalledWith({
      enabled: false,
      alertType: undefined,
      page: 1,
      pageSize: 20,
    }));
    expect(screen.getByLabelText('啟停状态')).toHaveValue('disabled');
    expect(screen.getByText('可停用規則')).toBeInTheDocument();
    expect(screen.queryByText('其他啟用規則')).not.toBeInTheDocument();
  });

  it('refreshes create results with the latest type filter after a pending mutation', async () => {
    const priceRule = { ...rule, name: '價格規則', alertType: 'price_cross' as const };
    const volumeRule = { ...rule, id: 2, name: '成交量規則', alertType: 'volume_spike' as const };
    const createRequest = createDeferred<typeof priceRule>();

    createRule.mockReturnValueOnce(createRequest.promise);
    listRules.mockImplementation(async (query: { alertType?: string }) => {
      if (query.alertType === 'volume_spike') {
        return { items: [volumeRule], total: 1, page: 1, pageSize: 20 };
      }
      if (query.alertType === 'price_cross') {
        return { items: [priceRule], total: 1, page: 1, pageSize: 20 };
      }
      return { items: [priceRule, volumeRule], total: 2, page: 1, pageSize: 20 };
    });

    render(<AlertsPage />);

    expect(await screen.findByText('價格規則')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('標的代碼'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('價格閾值'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '創建規則' }));
    fireEvent.change(screen.getAllByLabelText('規則類型')[1], { target: { value: 'volume_spike' } });

    await waitFor(() => expect(screen.queryByText('價格規則')).not.toBeInTheDocument());
    await act(async () => {
      createRequest.resolve(priceRule);
    });

    await waitFor(() => expect(listRules).toHaveBeenLastCalledWith({
      enabled: undefined,
      alertType: 'volume_spike',
      page: 1,
      pageSize: 20,
    }));
    expect(screen.getAllByLabelText('規則類型')[1]).toHaveValue('volume_spike');
    expect(screen.getByText('成交量規則')).toBeInTheDocument();
    expect(screen.queryByText('價格規則')).not.toBeInTheDocument();
  });

  it('refreshes delete results with the latest page after a pending mutation', async () => {
    const page2Rule = { ...rule, id: 2, name: '第二頁待刪規則', target: 'AAPL' };
    const deleteRequest = createDeferred<{ deleted: number }>();

    deleteRule.mockReturnValueOnce(deleteRequest.promise);
    listRules.mockImplementation(async (query: { page?: number }) => {
      if (query.page === 2) {
        return { items: [page2Rule], total: 21, page: 2, pageSize: 20 };
      }
      return { items: [rule], total: 21, page: 1, pageSize: 20 };
    });

    render(<AlertsPage />);

    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    expect(await screen.findByText('第二頁待刪規則')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('刪除 第二頁待刪規則'));
    fireEvent.click(await screen.findByRole('button', { name: '刪除' }));
    fireEvent.click(screen.getByRole('button', { name: '1' }));

    expect(await screen.findByText('茅台價格突破')).toBeInTheDocument();
    await act(async () => {
      deleteRequest.resolve({ deleted: 1 });
    });

    await waitFor(() => expect(listRules).toHaveBeenLastCalledWith({
      enabled: undefined,
      alertType: undefined,
      page: 1,
      pageSize: 20,
    }));
    expect(screen.getByText('茅台價格突破')).toBeInTheDocument();
    expect(screen.queryByText('第二頁待刪規則')).not.toBeInTheDocument();
  });

  it('renders API errors through ApiErrorAlert', async () => {
    listRules.mockRejectedValueOnce({ parsedError });

    render(<AlertsPage />);

    expect(await screen.findByText('加載失敗')).toBeInTheDocument();
    expect(screen.getByText('告警 API 不可用')).toBeInTheDocument();
  });
});
