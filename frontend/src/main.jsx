import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme, localStorageColorSchemeManager } from "@mantine/core";
import { DatesProvider } from "@mantine/dates";
import { Notifications } from "@mantine/notifications";
import { ModalsProvider } from "@mantine/modals";
import "dayjs/locale/vi";

import "@mantine/core/styles.css";
import "@mantine/dates/styles.css";
import "@mantine/dropzone/styles.css";
import "@mantine/notifications/styles.css";
import "@xyflow/react/dist/style.css";
import "./styles.css";

import App from "./App";

const theme = createTheme({
  primaryColor: "indigo",
  fontFamily: '"Be Vietnam Pro", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  headings: { fontFamily: '"Be Vietnam Pro", system-ui, sans-serif', fontWeight: "700" },
  defaultRadius: "md",
  cursorType: "pointer",
  components: {
    Card: { defaultProps: { withBorder: true, radius: "lg", shadow: "xs" } },
    Paper: { defaultProps: { radius: "lg" } },
    Button: { defaultProps: { radius: "md" } },
  },
});

const colorSchemeManager = localStorageColorSchemeManager({ key: "supload-color-scheme" });

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="auto" colorSchemeManager={colorSchemeManager}>
      <DatesProvider settings={{ locale: "vi", firstDayOfWeek: 1 }}>
        <ModalsProvider labels={{ confirm: "Đồng ý", cancel: "Huỷ" }}>
          <Notifications position="bottom-right" limit={4} />
          <App />
        </ModalsProvider>
      </DatesProvider>
    </MantineProvider>
  </React.StrictMode>
);
