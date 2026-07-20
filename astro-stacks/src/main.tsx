import React from "react";
import ReactDOM from "react-dom/client";
import { ChakraProvider } from "@chakra-ui/react";
import App from "./App";
import { system } from "./theme";
import { ThemeModeProvider } from "./theme/ThemeModeProvider";
import "./styles/globals.scss";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ChakraProvider value={system}>
        <App />
      </ChakraProvider>
    </ThemeModeProvider>
  </React.StrictMode>,
);
