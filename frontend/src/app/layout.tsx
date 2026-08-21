import type { Metadata } from 'next';
import { AuthProvider } from '@/lib/auth-context';
import { Backdrop } from '@/components/Backdrop';
import { Nav } from '@/components/Nav';
import './globals.css';

export const metadata: Metadata = {
  title: 'ozodbekdev.uz — Onlayn ta\'lim',
  description: 'Python, Django, React, JavaScript va sun\'iy intellekt kurslari',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body className="min-h-screen">
        {/*
          Fon HAMMA sahifada bitta va u yerda TURIB QOLADI: `Backdrop`
          layoutda bo'lgani uchun sahifadan sahifaga o'tganda qayta
          yaratilmaydi. Har sahifada alohida qo'yilsa, har o'tishda
          canvas noldan boshlanib, zarralar sakrab ketardi.
        */}
        <Backdrop />

        <AuthProvider>
          <div className="page-content">
            <Nav />
            <main className="max-w-6xl mx-auto px-4 py-8 reveal">{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
