'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Guard } from '@/components/Guard';
import { certificates, type Certificate } from '@/lib/api';

function CertificateList() {
  const [items, setItems] = useState<Certificate[] | null>(null);

  useEffect(() => {
    certificates.mine().then(setItems).catch(() => setItems([]));
  }, []);

  if (!items) return <p className="text-slate-500 py-12 text-center">Yuklanmoqda...</p>;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-8">
        <h1 className="text-3xl font-extrabold gradient-text">Sertifikatlarim</h1>
        <Link
          href="/sertifikat-tekshirish"
          className="text-sm text-primary hover:underline"
        >
          Sertifikatni tekshirish →
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="glass lift rounded-2xl p-12 text-center">
          <p className="text-slate-400 mb-2">Hozircha sertifikat yo&apos;q.</p>
          <p className="text-sm text-slate-600 mb-6">
            Testda 80% va undan yuqori ball olsangiz sertifikat avtomatik beriladi.
          </p>
          <Link href="/testlar" className="btn inline-block">
            Testlarga o&apos;tish
          </Link>
        </div>
      ) : (
        <div className="grid stagger sm:grid-cols-2 gap-4">
          {items.map((certificate) => (
            <div
              key={certificate.code}
              className={`glass rounded-2xl p-5 ${
                !certificate.is_valid ? 'opacity-60' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0">
                  <p className="font-bold truncate">{certificate.quiz_title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {certificate.category_name}
                  </p>
                </div>
                <span
                  className={`text-xl font-black shrink-0 ${
                    certificate.score_percentage >= 90
                      ? 'text-emerald-400'
                      : 'text-primary'
                  }`}
                >
                  {certificate.score_percentage}%
                </span>
              </div>

              <p className="font-mono text-[11px] text-slate-600 mb-4">
                {certificate.code}
              </p>

              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500">
                  {new Date(certificate.issued_at).toLocaleDateString('uz-UZ')}
                </span>

                {certificate.is_valid ? (
                  <a
                    href={certificate.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline font-semibold"
                  >
                    PDF yuklab olish
                  </a>
                ) : (
                  <span className="text-sm text-red-400">Bekor qilingan</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function CertificatesPage() {
  return (
    <Guard>
      <CertificateList />
    </Guard>
  );
}
