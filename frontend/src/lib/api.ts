/**
 * Backend bilan aloqa.
 *
 * IKKI QAT'IY QOIDA:
 *
 * 1. `credentials: 'include'` HAR SO'ROVDA. Autentifikatsiya sessiya
 *    cookie bilan ishlaydi va u avtomatik yuborilmaydi — brauzer uni
 *    faqat shu bayroq bilan qo'shadi. Unutilsa so'rov 403 qaytaradi
 *    va sababi umuman ko'rinmaydi.
 *
 * 2. O'ZGARTIRUVCHI so'rovlarda CSRF tokeni. Django uni cookie'da
 *    beradi, lekin sarlavhada KUTADI — ikkalasi mos kelishi shart.
 *
 * MANZILLAR NISBIY (`/api/v1/...`). Backend domeni bu yerda
 * yozilmaydi: uni Next.js `rewrites` hal qiladi va shu sabab cookie
 * birinchi tomon bo'lib qoladi (`next.config.mjs` ga qarang).
 */

const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, data: any) {
    super(
      data?.detail ||
        // DRF maydon xatolarini o'qiladigan matnga aylantiramiz
        (typeof data === 'object' && data
          ? Object.values(data).flat().join(' ')
          : 'Xatolik yuz berdi'),
    );
    this.status = status;
    this.data = data;
  }

  /** Ruxsat kutilmoqda (admin hali tasdiqlamagan). */
  get needsApproval() {
    return this.status === 403 && this.data?.code === 'APPROVAL_REQUIRED';
  }

  /** Obuna kerak. */
  get needsSubscription() {
    return this.status === 402;
  }

  /** Tizimga kirish kerak. */
  get needsLogin() {
    return this.status === 401 || (this.status === 403 && !this.data?.code);
  }
}

function readCookie(name: string): string {
  if (typeof document === 'undefined') return '';
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : '';
}

/**
 * CSRF tokenini ta'minlaydi.
 *
 * Cookie hali yo'q bo'lsa (birinchi tashrif) backenddan so'raymiz.
 * Busiz birinchi login so'rovi har doim 403 bo'lardi.
 */
async function ensureCsrf(): Promise<string> {
  let token = readCookie('csrftoken');
  if (token) return token;

  await fetch(`${BASE}/auth/csrf/`, { credentials: 'include' });
  return readCookie('csrftoken');
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method || 'GET';
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  // O'zgartiruvchi so'rovlarda CSRF majburiy
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers['X-CSRFToken'] = await ensureCsrf();
  }

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 204) return undefined as T;

  let data: any = null;
  try {
    data = await response.json();
  } catch {
    // Bo'sh yoki JSON bo'lmagan javob
  }

  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
};

// ══════════════════════════ Turlar ══════════════════════════

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  level: number;
  is_staff: boolean;
  is_approved: boolean;
  rejection_reason: string;
  telegram_linked: boolean;
  avatar: string | null;
  /** Bu odamga o'quvchi biriktirilganmi — menyuda "Farzandlarim" shunga bog'liq */
  is_parent: boolean;
}

export interface SubscriptionState {
  status: string;
  status_label: string;
  active: boolean;
  current_period_end: string | null;
  days_left: number;
  in_grace: boolean;
  in_hold: boolean;
}

export interface Me {
  user: User;
  subscription: SubscriptionState;
}

export interface Course {
  id: number;
  name: string;
  slug: string;
  description: string;
  total_lessons: number;
  free_lessons: number;
  completed_lessons: number;
}

export interface LessonSummary {
  id: number;
  title: string;
  order: number;
  is_free: boolean;
  unlocked: boolean;
  completed: boolean;
  has_video: boolean;
  has_text: boolean;
}

export interface LessonImage {
  id: number;
  url: string;
  caption: string;
  alt: string;
  order: number;
}

/**
 * To'liq dars.
 *
 * DIQQAT: mazmun maydonlari IXTIYORIY. Qulflangan darsda ular
 * javobga umuman tushmaydi — bo'sh satr sifatida ham kelmaydi.
 * Frontend ularning yo'qligiga tayyor bo'lishi kerak.
 */
export interface LessonDetail extends LessonSummary {
  category: string;
  category_slug: string;
  theory_html?: string;
  practice_code?: string;
  images?: LessonImage[];
  video_url?: string | null;
  quiz_id?: number | null;
  locked_reason?: string;
}

export interface Module {
  id: number;
  title: string;
  order: number;
  lessons: LessonSummary[];
}

export interface Quiz {
  id: number;
  title: string;
  time_limit: number;
  lesson_id: number;
  lesson_title: string;
  category: string;
  question_count: number;
  unlocked?: boolean;
  best_score?: number | null;
  attempts?: number;
}

export interface Choice {
  id: number;
  text: string;
  // `is_correct` ATAYLAB YO'Q va hech qachon qo'shilmasin — to'g'ri
  // javob klientga yuborilmaydi, ball serverda hisoblanadi.
}

export interface Question {
  id: number;
  text: string;
  choices: Choice[];
}

export interface QuizDetail extends Quiz {
  questions: Question[];
}

export interface QuizOutcome {
  score: number;
  correct: number;
  total: number;
  attempts: number;
  new_level: number;
  leveled_up: boolean;
  certificate: Certificate | null;
}

export interface Certificate {
  code: string;
  quiz_title: string;
  category_name: string;
  score_percentage: number;
  full_name: string;
  issued_at: string;
  is_valid: boolean;
  pdf_url: string;
}

export interface PlanOption {
  months: number;
  amount_tiyin: number;
  amount_display: string;
}

export interface SubscriptionInfo {
  state: SubscriptionState;
  plan: {
    name: string;
    price_per_month_tiyin: number;
    price_display: string;
    grace_days: number;
  };
  options: PlanOption[];
  open_request: {
    id: number;
    months: number;
    amount_display: string;
    status: string;
    status_label: string;
  } | null;
}

export interface Challenge {
  id: number;
  title: string;
  language: 'python' | 'javascript';
  difficulty: string;
  order: number;
  /** O'quvchi bu topshiriqni yechganmi (serverda saqlanadi). */
  solved: boolean;
  // `solution_code` ATAYLAB YO'Q — yechim alohida so'raladi
}

export interface ChallengeDetail extends Challenge {
  description_html: string;
  initial_code: string;
  has_solution: boolean;
  /**
   * Tekshirish sozlanganmi.
   *
   * Kutilgan natijaning O'ZI berilmaydi — berilsa, topshiriqni
   * yechmasdan ko'chirib qo'yish mumkin bo'lardi.
   */
  has_check: boolean;
  next_id: number | null;
}

export interface CheckResult {
  correct: boolean;
  detail: string;
  attempts: number;
  solved_at?: string | null;
  /** Faqat BIRINCHI farq qilgan qator — butun javob emas. */
  diff?: { line: number; expected: string | null; actual: string | null } | null;
}

export interface MentorMessage {
  id: number;
  question: string;
  answer: string;
  lesson_title: string;
  created_at: string;
}

export interface Project {
  id: number;
  title: string;
  description_html: string;
  image_url: string | null;
  difficulty: string;
  tech_list: string[];
  demo_url: string | null;
  repo_url: string | null;
  order: number;
}

export interface StudyDay {
  date: string;
  label: string;
  seconds: number;
  minutes: number;
  hours: number;
  lessons_completed: number;
}

export interface StudySummary {
  today_minutes: number;
  total_seconds: number;
  total_hours: number;
  active_days: number;
  average_minutes: number;
  all_time_hours: number;
}

export interface Child {
  student_id: number;
  username: string;
  full_name: string;
  relation: string;
}

/**
 * Farzandlar ro'yxati va ota-onaning O'Z obuna holati.
 *
 * Ikkalasi bitta javobda keladi: panel ochilishidayoq hisobot
 * ko'rsatiladimi yoki obuna taklif qilinadimi — hal bo'lishi kerak.
 * Alohida so'rov bo'lsa sahifa avval ochilib, keyin yopilardi.
 */
export interface ParentOverview {
  children: Child[];
  /** Egasi ota-ona paneliga narx qo'yganmi */
  reports_are_paid: boolean;
  can_view_reports: boolean;
  subscription: SubscriptionState;
}

export interface ChildReport {
  student: {
    id: number;
    username: string;
    full_name: string;
    relation: string;
    level: number;
  };
  study: { summary: StudySummary; series: StudyDay[] };
  lessons: { total: number; completed: number; percent: number };
  quizzes: {
    taken: number;
    average_score: number;
    recent: {
      quiz: string;
      category: string;
      score: number;
      correct: number;
      total: number;
      attempts: number;
      completed_at: string;
    }[];
  };
  certificates: Certificate[];
  subscription: SubscriptionState;
}

export interface DashboardData {
  lessons: { total: number; completed: number; percent: number };
  quizzes: { taken: number; average_score: number };
  certificates: number;
  level: number;
}

// ══════════════════════════ Endpointlar ══════════════════════════

export const auth = {
  me: () => api.get<Me>('/auth/me/'),
  login: (username: string, password: string) =>
    api.post<Me>('/auth/login/', { username, password }),
  logout: () => api.post<void>('/auth/logout/'),
  register: (data: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => api.post<Me>('/auth/register/', data),
  requestPasswordReset: (email: string) =>
    api.post<{ detail: string }>('/auth/password-reset/', { email }),
  confirmPasswordReset: (email: string, code: string, new_password: string) =>
    api.post<{ detail: string }>('/auth/password-reset/confirm/', {
      email,
      code,
      new_password,
    }),
};

export const courses = {
  list: () => api.get<Course[]>('/courses/'),
  detail: (slug: string) =>
    api.get<{ category: Course; modules: Module[] }>(`/courses/${slug}/`),
};

export const lessons = {
  detail: (id: number) => api.get<LessonDetail>(`/lessons/${id}/`),
  complete: (id: number) =>
    api.post<{ completed: boolean; total_lessons: number; completed_lessons: number }>(
      `/lessons/${id}/complete/`,
    ),
};

export const quizzes = {
  list: () => api.get<Quiz[]>('/quizzes/'),
  detail: (id: number) => api.get<QuizDetail>(`/quizzes/${id}/`),
  submit: (id: number, answers: Record<number, number>) =>
    api.post<QuizOutcome>(`/quizzes/${id}/submit/`, { answers }),
};

export const subscription = {
  info: () => api.get<SubscriptionInfo>('/subscription/'),
  createRequest: (months: number) =>
    api.post<{ id: number; months: number; amount_display: string; status: string }>(
      '/subscription/request/',
      { months },
    ),
  markReceipt: (source?: string) =>
    api.post<{ id: number; status: string }>('/subscription/receipt/', { source }),
  card: () => api.get<any>('/subscription/card/'),
};

export const certificates = {
  mine: () => api.get<Certificate[]>('/certificates/'),
  verify: (code: string) =>
    api.get<any>(`/certificates/verify/?code=${encodeURIComponent(code)}`),
};

export const mentor = {
  ask: (question: string, lesson_id?: number) =>
    api.post<{ answer_html: string; mock: boolean }>('/mentor/ask/', {
      question,
      lesson_id,
    }),
};

export const dashboard = {
  get: () => api.get<DashboardData>('/dashboard/'),
};

export const challenges = {
  list: (language?: string) =>
    api.get<Challenge[]>(`/challenges/${language ? `?language=${language}` : ''}`),
  detail: (id: number) => api.get<ChallengeDetail>(`/challenges/${id}/`),
  // Yechim FAQAT so'ralganda olinadi
  solution: (id: number) => api.get<{ solution: string }>(`/challenges/${id}/solution/`),
  /*
   * Tekshirish SERVERDA. Bu yerdan faqat kodning CHIQARGAN MATNI
   * ketadi — kodning o'zi emas: u brauzerda ishlaydi va shunday
   * bo'lib qoladi.
   */
  check: (id: number, output: string) =>
    api.post<CheckResult>(`/challenges/${id}/check/`, { output }),
};

export const profile = {
  get: () => api.get<User>('/profile/'),
  update: (data: { full_name?: string; bio?: string }) =>
    request<User>('/profile/', { method: 'PATCH', body: data }),
  uploadAvatar: async (file: File) => {
    // Fayl JSON bilan ketmaydi — `multipart/form-data` kerak,
    // shuning uchun umumiy `request` ishlatilmaydi.
    const body = new FormData();
    body.append('image', file);

    const response = await fetch(`${BASE}/profile/avatar/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': await ensureCsrf() },
      credentials: 'include',
      body,
    });

    const data = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status, data);
    return data as User;
  },
  linkTelegram: () => api.post<{ url: string }>('/profile/telegram/'),
  unlinkTelegram: () => request<void>('/profile/telegram/', { method: 'DELETE' }),
};

export const mentorHistory = {
  list: () => api.get<MentorMessage[]>('/mentor/history/'),
};

export const projects = {
  list: () => api.get<Project[]>('/projects/'),
};

export const study = {
  /** "Men shu yerdaman" signali. Sana va miqdor SERVERDA belgilanadi. */
  ping: () => api.post<{ counted: boolean; seconds_today: number }>('/study/ping/'),
  me: () => api.get<{ summary: StudySummary; series: StudyDay[] }>('/study/me/'),
};

export const parent = {
  children: () => api.get<ParentOverview>('/parent/children/'),
  report: (studentId: number) => api.get<ChildReport>(`/parent/children/${studentId}/`),

  /**
   * FARZAND uchun to'lov so'rovi.
   *
   * So'rov o'quvchi nomiga ochiladi — pul uning obunasiga tushadi.
   * Ota-onaning o'z obunasi bundan alohida.
   */
  payForChild: (studentId: number, months = 1) =>
    api.post<{ id: number; amount_display: string; status: string }>(
      `/parent/children/${studentId}/pay/`,
      { months },
    ),
};
