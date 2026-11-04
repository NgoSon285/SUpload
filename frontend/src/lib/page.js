/** Các Page đã kết nối, suy ra từ state của máy chủ (GET /api/state). */
export const pagesOf = (state) => state?.pages || [];

export const configured = (state) => pagesOf(state).length > 0;

export const defaultPage = (state) => pagesOf(state).find((p) => p.default) || pagesOf(state)[0] || null;

export const pageById = (state, id) => pagesOf(state).find((p) => p.id === id) || null;

/** Page thực sự nhận bài: Page đã chọn, hoặc Page mặc định. */
export const targetPage = (state, id) => pageById(state, id) || defaultPage(state);

export const pageInitial = (page) => (page?.name || "?").trim()[0]?.toUpperCase() || "?";

export const KIND_LABEL = { api: "Graph API", browser: "Trình duyệt" };
