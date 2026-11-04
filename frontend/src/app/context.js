import { createContext, useContext } from "react";

/** Trạng thái chung của ứng dụng: state từ máy chủ, refresh(), điều hướng, chuyển bài sang trang Soạn. */
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
