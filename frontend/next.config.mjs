/**
 * Next.js sozlamalari.
 *
 * ENG MUHIM QISM — `rewrites`.
 *
 * `/api/*` so'rovlari Vercel tomonidan Railway'ga UZATILADI. Bu shunchaki
 * qulaylik emas, XAVFSIZLIK qarori:
 *
 *   - Brauzer uchun so'rov O'Z domenimizga ketayotgandek ko'rinadi,
 *     shuning uchun sessiya cookie BIRINCHI TOMON bo'lib qoladi.
 *   - Safari va iOS uchinchi tomon cookie'larini bloklaydi. To'g'ridan-
 *     to'g'ri `railway.app` ga murojaat qilinsa, o'sha brauzerlarda
 *     kirish umuman ishlamasdi.
 *   - CORS umuman kerak bo'lmaydi.
 *
 * Muqobil yo'l — tokenni localStorage da saqlash — sahifadagi har qanday
 * skript uni o'qiy olishini bildiradi. Sessiya cookie esa HttpOnly.
 */
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  /**
   * OXIRIDAGI `/` SAQLANADI — busiz API umuman ishlamaydi.
   *
   * Next.js standart holatda `/api/v1/auth/csrf/` ni `/api/v1/auth/csrf`
   * ga 308 bilan yo'naltiradi. Django esa manzillarni oxirida `/` bilan
   * belgilagan va slashsiz manzilni tanimaydi.
   *
   * Natijada har bir API so'rovi redirectga tushib, POST so'rovlar
   * GET ga aylanib qolardi — kirish, ro'yxatdan o'tish va test
   * topshirish umuman ishlamasdi.
   */
  skipTrailingSlashRedirect: true,

  async rewrites() {
    return [
      /*
       * MANZIL OXIRIDA `/` — ATAYLAB va MAJBURIY.
       *
       * `:path*` naqshi oxiridagi slashni YUTIB YUBORADI: so'rov
       * `/api/v1/auth/csrf/` bo'lsa ham, backendga `/api/v1/auth/csrf`
       * ketadi. Django esa CommonMiddleware bilan uni `/` li
       * manzilga 301 qiladi, Next.js yana slashni yechadi — va
       * CHEKSIZ AYLANISH hosil bo'ladi.
       *
       * Django API manzillari HAR DOIM `/` bilan tugagani uchun uni
       * shu yerda ochiq yozib qo'yamiz.
       */
      { source: '/api/:path*', destination: `${BACKEND}/api/:path*/` },

      // Video va sertifikat PDF ham backenddan keladi. Ular huquq
      // tekshiruvidan o'tadi, shuning uchun ochiq uzatilmaydi.
      { source: '/lessons/:id/video', destination: `${BACKEND}/lessons/:id/video/` },
      { source: '/certificates/:code/pdf', destination: `${BACKEND}/certificates/:code/pdf/` },

      // Media — dars rasmlari va profil suratlari. Bu yerda slash
      // QO'SHILMAYDI: fayl manzili slash bilan tugamaydi.
      { source: '/media/:path*', destination: `${BACKEND}/media/:path*` },
    ];
  },
};

export default nextConfig;
