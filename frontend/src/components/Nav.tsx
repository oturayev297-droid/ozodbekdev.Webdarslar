'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

/**
 * Bu sahifalarda navdagi "Kirish" va "Ro'yxatdan o'tish"
 * KO'RSATILMAYDI.
 *
 * Sabab bitta: o'sha ikkalasi sahifaning O'ZIDA allaqachon bor.
 * Bosh sahifada ular katta tugmalar bo'lib o'rtada turadi, kirish
 * va ro'yxatdan o'tish sahifalarida esa forma va uning tagidagi
 * havola. Navda ham turgani ekranda bir xil tugmani ikki marta
 * ko'rsatardi — ustiga ro'yxatdan o'tish sahifasining tepasida
 * "Ro'yxatdan o'tish" tugmasi foydalanuvchini allaqachon turgan
 * joyiga chaqirardi.
 *
 * BOSH SAHIFA `startsWith` BILAN TEKSHIRILMAYDI: '/' hamma manzilning
 * boshida turadi va u ro'yxatga qo'shilsa, tugmalar SAYTNING HAMMA
 * yeridan yo'qolardi.
 */
const AUTH_PAGES = ['/login', '/register', '/parolni-tiklash'];

const LINKS = [
  { href: '/dashboard', label: 'Bosh sahifa' },
  { href: '/kurslar', label: 'Kurslar' },
  { href: '/testlar', label: 'Testlar' },
  { href: '/muharrir', label: 'Muharrir' },
  { href: '/loyihalar', label: 'Loyihalar' },
  { href: '/sertifikatlar', label: 'Sertifikatlar' },
];

export function Nav() {
  const { user, subscription, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const hideAuthLinks =
    pathname === '/' || AUTH_PAGES.some((path) => pathname.startsWith(path));

  /*
   * Panelda logotipdan boshqa hech narsa qolmagan bo'lsa, u
   * O'RTAGA turadi. Chapda yolg'iz turgan nom keng ekranda o'ng
   * tomonni bo'm-bo'sh qoldirardi.
   *
   * `user` YUKLANAYOTGANDA ham bo'sh bo'ladi va bu ATAYLAB shunday
   * hisoblanadi: bu sahifalarga asosan tizimga kirmagan odam
   * keladi, ya'ni logotip darhol o'z joyida chiziladi va keyin
   * sakrab ko'chmaydi.
   */
  const logoAlone = hideAuthLinks && !user;

  async function handleLogout() {
    await logout();
    router.push('/login');
  }

  return (
    <nav className="glass border-b border-white/5 sticky top-0 z-40">
      <div
        className={`max-w-6xl mx-auto px-4 h-16 flex items-center gap-4 ${
          logoAlone ? 'justify-center' : 'justify-between'
        }`}
      >
        <Link href="/" className="font-extrabold text-lg tracking-tight shrink-0">
          ozodbekdev<span className="text-primary">.uz</span>
        </Link>

        {/*
          Yuklanayotganda hech narsa ko'rsatmaymiz. Aks holda "Kirish"
          tugmasi bir lahzaga chaqnab, keyin foydalanuvchi nomiga
          almashardi — sahifa buzilgandek ko'rinardi.
        */}
        {loading ? null : user ? (
          <>
            {/* Katta ekran */}
            <div className="hidden md:flex items-center gap-4 text-sm">
              {user.is_approved &&
                LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={
                      pathname.startsWith(link.href)
                        ? 'text-primary font-semibold'
                        : 'text-slate-300 hover:text-white'
                    }
                  >
                    {link.label}
                  </Link>
                ))}

              {user.is_approved && (
                <Link href="/obuna" className="text-slate-300 hover:text-white">
                  Obuna
                  {subscription && !subscription.active && (
                    <span className="ml-1.5 w-2 h-2 inline-block rounded-full bg-amber-400" />
                  )}
                </Link>
              )}

              {/*
                Havola FAQAT farzandi bo'lganga ko'rinadi va
                `is_approved` ga BOG'LIQ EMAS: ota-onaga dars ruxsati
                kerak emas, u tasdiqlanmagan bo'lishi mumkin.

                Ilgari havola hammaga ko'rinardi va bosgan o'quvchi
                doim bo'sh sahifaga tushardi — menyuda hech qachon
                ishlamaydigan band turardi.
              */}
              {user.is_parent && (
                <Link href="/farzandlarim" className="text-slate-300 hover:text-white">
                  Farzandlarim
                </Link>
              )}
              <Link href="/profil" className="text-slate-500 hover:text-slate-300">
                {user.username}
              </Link>
              <button onClick={handleLogout} className="text-slate-400 hover:text-red-400">
                Chiqish
              </button>
            </div>

            {/* Mobil */}
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="md:hidden px-3 py-2 rounded-lg bg-white/5 text-sm"
            >
              Menyu
            </button>
          </>
        ) : hideAuthLinks ? null : (
          <div className="flex items-center gap-3 text-sm">
            <Link href="/login" className="text-slate-300 hover:text-white">
              Kirish
            </Link>
            <Link href="/register" className="btn text-sm py-2">
              Ro&apos;yxatdan o&apos;tish
            </Link>
          </div>
        )}
      </div>

      {menuOpen && user && (
        <div className="md:hidden border-t border-white/5 px-4 py-3 space-y-1 text-sm">
          {user.is_approved &&
            [...LINKS, { href: '/obuna', label: 'Obuna' }].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="block py-2 text-slate-300"
              >
                {link.label}
              </Link>
            ))}
          {user.is_parent && (
            <Link
              href="/farzandlarim"
              onClick={() => setMenuOpen(false)}
              className="block py-2 text-slate-300"
            >
              Farzandlarim
            </Link>
          )}
          <Link
            href="/profil"
            onClick={() => setMenuOpen(false)}
            className="block py-2 text-slate-300"
          >
            Profil
          </Link>
          <button onClick={handleLogout} className="block py-2 text-red-400">
            Chiqish
          </button>
        </div>
      )}
    </nav>
  );
}
