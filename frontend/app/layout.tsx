import type { Metadata, Viewport } from "next";
import "./globals.css";
import { I18nProvider } from "../lib/i18n";
import { ApiProvider } from "../lib/api";
import { ToastProvider } from "../components/Toast";
import Header from "../components/Header";
import SyncBoot from "../components/SyncBoot";

export const metadata: Metadata = {
  title: "Sahayta — When disaster strikes, help finds you",
  description: "Offline-first disaster-response OS for India: report SOS, AI severity, volunteer dispatch, multilingual alerts.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#1D4ED8",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

const FONT_URL =
  "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700;800&family=Noto+Sans+Bengali:wght@400;600;700&family=Noto+Sans+Tamil:wght@400;600;700&family=Noto+Sans+Telugu:wght@400;600;700&family=Noto+Sans+Kannada:wght@400;600;700&family=Noto+Sans+Malayalam:wght@400;600;700&family=Noto+Sans+Gujarati:wght@400;600;700&family=Noto+Sans+Gurmukhi:wght@400;600;700&family=Noto+Serif:wght@700;800&display=swap";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="hi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href={FONT_URL} rel="stylesheet" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body>
        <I18nProvider>
          <ToastProvider>
            <ApiProvider>
              <SyncBoot />
              <Header />
              <main className="mx-auto min-h-[70vh] w-full max-w-6xl px-4 pb-16 pt-4">{children}</main>
            </ApiProvider>
          </ToastProvider>
        </I18nProvider>
        <script
          dangerouslySetInnerHTML={{
            __html: `if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js').catch(()=>{})});}`,
          }}
        />
      </body>
    </html>
  );
}
