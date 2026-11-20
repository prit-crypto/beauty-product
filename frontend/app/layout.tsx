import type { Metadata } from "next";
import { Cardo, Lato, Noto_Naskh_Arabic } from "next/font/google";

import ChatWidget from "@/components/chat/ChatWidget";
import DemoBanner from "@/components/DemoBanner";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import { CartProvider } from "@/lib/cart";

import "./globals.css";

const cardo = Cardo({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-cardo" });
const lato = Lato({ subsets: ["latin"], weight: ["300", "400", "700"], variable: "--font-lato" });
const naskh = Noto_Naskh_Arabic({ subsets: ["arabic"], weight: ["400", "600"], variable: "--font-naskh" });

export const metadata: Metadata = {
  title: "Dr. Beauty Care · Skincare, Haircare, Protein & Supplements (concept demo)",
  description: "Concept demo of Dr. Beauty Care with the Ask Dr. Beauty AI shopping assistant.",
  robots: { index: false, follow: false },
  icons: { icon: "/brand/logo.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${cardo.variable} ${lato.variable} ${naskh.variable} antialiased`}>
        <CartProvider>
          <DemoBanner />
          <Header />
          <main>{children}</main>
          <Footer />
          <ChatWidget />
        </CartProvider>
      </body>
    </html>
  );
}
