import type { Metadata } from 'next';
import { AuthProvider } from '@/lib/auth-context';
import { Nav } from '@/components/Nav';
import './globals.css';

export const metadata: Metadata = {
  title: 'Ozodbek.web — Onlayn ta\'lim',
  description: 'Python, Django, React, JavaScript va sun\'iy intellekt kurslari',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uz">
      <body className="min-h-screen">
        <AuthProvider>
          <Nav />
          <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
