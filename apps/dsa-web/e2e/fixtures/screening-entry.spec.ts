import { expect, test } from '@playwright/test';

for (const state of ['disabled', 'error', 'unavailable'] as const) {
  test(`screening entry remains discoverable: ${state}`, async ({ page }, testInfo) => {
    let failed = state === 'error';
    const writes: string[] = [];
    await page.route('**/api/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (!pathname.startsWith('/api/')) return route.continue();
      if (route.request().method() !== 'GET') writes.push(pathname);
      if (pathname.endsWith('/auth/status')) {
        return route.fulfill({ json: { authEnabled: false, loggedIn: true, setupState: 'no_password' } });
      }
      if (pathname.endsWith('/screening/status')) {
        if (failed) return route.fulfill({ status: 503, json: { detail: 'Fixture status unavailable' } });
        return route.fulfill({ json: { enabled: state === 'unavailable', available: state !== 'unavailable' } });
      }
      if (pathname.endsWith('/data/overview')) {
        return route.fulfill({ json: { providers: [], datasets: [], priorities: [], warnings: [] } });
      }
      return route.fulfill({ json: { items: [], total: 0 } });
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/data');
    const nav = page.getByRole('complementary', { name: '桌面側邊導航' });
    await nav.getByRole('link', { name: '選股', exact: true }).click();
    await expect(page).toHaveURL(/\/screening$/);
    await expect(page.getByRole('button', { name: /運行選股/ })).toBeDisabled();
    if (state === 'disabled') {
      await expect(page.getByRole('button', { name: '開啟選股', exact: true })).toBeVisible();
    } else {
      await expect(page.getByRole('button', { name: '開啟選股', exact: true })).toHaveCount(0);
      await expect(page.getByText(state === 'error' ? '選股状态加載失敗' : '選股功能不可用', { exact: true }).first()).toBeVisible();
      await expect(page.getByText('選股未開啟', { exact: true })).toHaveCount(0);
    }
    for (const [name, width, height] of [['desktop', 1440, 900], ['mobile', 390, 844]] as const) {
      await page.setViewportSize({ width, height });
      const screenshot = testInfo.outputPath(`screening-entry-${state}-${name}.png`);
      await page.screenshot({ path: screenshot, animations: 'disabled' });
      await testInfo.attach(`${state}-${name}`, { path: screenshot, contentType: 'image/png' });
    }
    if (state === 'error') {
      failed = false;
      await page.getByRole('button', { name: '重试', exact: true }).click();
      await expect(page.getByRole('button', { name: '開啟選股', exact: true })).toBeVisible();
      await expect(page.getByText('選股状态加載失敗', { exact: true })).toHaveCount(0);
    }
    expect(writes).toEqual([]);
  });
}

for (const language of ['zh', 'en'] as const) {
  test(`screening settings explain the persistent entry: ${language}`, async ({ page }, testInfo) => {
    await page.addInitScript((value) => localStorage.setItem('dsa.uiLanguage', value), language);
    await page.route('**/api/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (!pathname.startsWith('/api/')) return route.continue();
      if (pathname.endsWith('/auth/status')) {
        return route.fulfill({ json: { authEnabled: false, loggedIn: true, setupState: 'no_password' } });
      }
      if (pathname === '/api/v1/system/config') {
        return route.fulfill({ json: { configVersion: 'fixture', maskToken: '******', items: [{
          key: 'SCREENING_ENABLED', value: 'false', rawValueExists: true, isMasked: false,
          schema: { key: 'SCREENING_ENABLED', title: '選股', category: 'base', dataType: 'boolean',
            uiControl: 'switch', isSensitive: false, isRequired: false, isEditable: true,
            options: [], validation: {}, displayOrder: 1 },
        }] } });
      }
      if (pathname.endsWith('/setup/status')) return route.fulfill({ json: { checks: [], readyForSmoke: false } });
      return route.fulfill({ json: { enabled: false, available: true, items: [], total: 0 } });
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/settings');
    const summary = page.getByText(language === 'zh'
      ? '開啟後可運行選股策略，候選可繼續進入單股分析；關閉時仍可從導航進入並查看開啟提示。'
      : 'Enable screening strategies and continue to single-stock analysis from candidates. When disabled, the navigation entry still opens the setup prompt.', { exact: true });
    await expect(summary).toBeVisible();
    await summary.scrollIntoViewIfNeeded();
    const screenshot = testInfo.outputPath(`screening-settings-${language}.png`);
    await page.screenshot({ path: screenshot, animations: 'disabled' });
    await testInfo.attach(`settings-${language}`, { path: screenshot, contentType: 'image/png' });
  });
}
