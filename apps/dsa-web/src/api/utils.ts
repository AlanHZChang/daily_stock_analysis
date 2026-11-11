import camelcaseKeys from 'camelcase-keys';

/**
 * 將 snake_case 對象鍵轉換為 camelCase
 * @param data API 響應數據 (snake_case)
 * @returns 轉換後的 camelCase 對象
 */
export function toCamelCase<T>(data: unknown): T {
    if (data === null || data === undefined) {
        return data as T;
    }
    return camelcaseKeys(data as Record<string, unknown>, { deep: true }) as T;
}
