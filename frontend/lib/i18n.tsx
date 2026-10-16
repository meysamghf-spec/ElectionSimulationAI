"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_LOCALE, directionOf, type Locale } from "./locale";

export { DEFAULT_LOCALE, directionOf, type Locale };

const STORAGE_KEY = "electionsim.locale";

const en = {
  "skip": "Skip to content",
  "menu.open": "Menu",
  "menu.close": "Close menu",
  "nav.new": "New simulation",
  "nav.prompt": "Prompt",
  "nav.configure": "Configuration",
  "nav.history": "History",
  "nav.import": "Import",
  "nav.help": "Help",
  "nav.settings": "Settings",
  "nav.signin": "Sign in",
  "nav.signout": "Sign out",
  "lang.switch": "فارسی",
  "lang.switchLabel": "Switch the interface to Persian",
  "banner":
    "Simulation only. Results on this site are hypothetical simulations from stated assumptions. They are not official election results, not polls, and not real predictions or forecasts.",
  "footer": "Hypothetical model output. Not an official result, poll, or forecast.",
  "footer.privacy": "Privacy and limitations",
  "home.eyebrow": "Simulation and statistical analysis",
  "home.title": "Describe an election. Inspect the assumptions. Run the math.",
  "home.lead":
    "ElectionSimulationAI turns a written description into a validated specification, then runs a reproducible Monte Carlo model. The numbers come from the simulation engine, not from a language model.",
  "home.step1": "Write a prompt or start from an example.",
  "home.step2": "Review extracted facts and inferred assumptions.",
  "home.step3": "Edit the structured configuration.",
  "home.step4": "Run the simulation and read the dashboard.",
  "home.step5": "Compare scenarios and export the computed results.",
  "home.start": "Start a simulation",
  "home.method": "Read the methodology",
  "home.what": "What this platform does",
  "home.f1": "Plurality, two-round, ranked-choice, and D'Hondt seat allocation.",
  "home.f2": "Regional turnout, preferences, blank ballots, and invalid ballots.",
  "home.f3": "Monte Carlo distributions, scenario differences, and sensitivity sweeps.",
  "home.f4": "CSV and JSON import, plus CSV, JSON, and PDF export of computed runs.",
  "home.not":
    "It does not retrieve official returns or polls. A saved result stays labeled hypothetical even when you imported your own aggregate inputs.",
  "login.title": "Sign in",
  "login.lead": "The session stays in an HttpOnly cookie. The password is not stored in this browser.",
  "login.email": "Email",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.pending": "Signing in…",
  "login.register": "Create an account",
  "login.loading": "Loading sign-in…",
  "history.title": "Simulation history",
  "history.lead":
    "Saved configurations and runs stored by the API. A server restart keeps them when the database file or PostgreSQL volume is intact.",
  "history.loading": "Loading saved simulations…",
  "history.empty": "No saved simulations yet.",
  "history.create": "Create one",
  "history.status": "Status",
  "history.method": "Method",
  "history.iterations": "Iterations",
  "history.updated": "Updated",
  "history.details": "Details",
  "history.results": "Results",
  "history.execution": "Execution",
  "history.prev": "Previous page",
  "history.next": "Next page",
  "history.none": "0 saved",
  "history.of": "of",
  "notfound.title": "Page not found",
  "notfound.lead": "That address is not part of ElectionSimulationAI.",
  "notfound.home": "Go to the home page",
  "error.title": "This page failed to render",
  "error.unknown": "An unexpected error occurred.",
  "error.retry": "Try again",
  "partial":
    "Some detailed screens (configuration editor, results dashboard, import) are still in English.",
} as const;

export type MessageKey = keyof typeof en;

const fa: Record<MessageKey, string> = {
  "skip": "رفتن به محتوا",
  "menu.open": "منو",
  "menu.close": "بستن منو",
  "nav.new": "شبیه‌سازی جدید",
  "nav.prompt": "توضیح متنی",
  "nav.configure": "پیکربندی",
  "nav.history": "تاریخچه",
  "nav.import": "ورود داده",
  "nav.help": "راهنما",
  "nav.settings": "تنظیمات",
  "nav.signin": "ورود",
  "nav.signout": "خروج",
  "lang.switch": "English",
  "lang.switchLabel": "Switch the interface to English",
  "banner":
    "فقط شبیه‌سازی: نتایج این سامانه شبیه‌سازی آماری فرضی بر پایهٔ فرض‌های واردشده است. این نتایج، نتیجهٔ رسمی انتخابات، نظرسنجی یا پیش‌بینی واقعی نیستند.",
  "footer": "خروجی مدل فرضی است؛ نتیجهٔ رسمی، نظرسنجی یا پیش‌بینی نیست.",
  "footer.privacy": "حریم خصوصی و محدودیت‌ها",
  "home.eyebrow": "شبیه‌سازی و تحلیل آماری",
  "home.title": "یک انتخابات فرضی را توصیف کنید، فرض‌ها را بررسی کنید و محاسبه را اجرا کنید.",
  "home.lead":
    "این سامانه توضیح نوشتاری شما را به یک مشخصات معتبر تبدیل می‌کند و سپس یک مدل مونت‌کارلوی تکرارپذیر را اجرا می‌کند. اعداد از موتور شبیه‌سازی می‌آیند، نه از مدل زبانی.",
  "home.step1": "یک توضیح بنویسید یا از یک نمونه شروع کنید.",
  "home.step2": "واقعیت‌های استخراج‌شده و فرض‌های استنباط‌شده را بازبینی کنید.",
  "home.step3": "پیکربندی ساختاریافته را ویرایش کنید.",
  "home.step4": "شبیه‌سازی را اجرا کنید و داشبورد را بخوانید.",
  "home.step5": "سناریوها را مقایسه کنید و نتایج محاسبه‌شده را خروجی بگیرید.",
  "home.start": "شروع شبیه‌سازی",
  "home.method": "خواندن روش‌شناسی",
  "home.what": "این سامانه چه می‌کند",
  "home.f1": "روش‌های اکثریت نسبی، دو مرحله‌ای، رتبه‌ای و تخصیص کرسی به روش دی‌هانت.",
  "home.f2": "مشارکت منطقه‌ای، ترجیحات، آرای سفید و آرای باطله.",
  "home.f3": "توزیع‌های مونت‌کارلو، تفاوت سناریوها و تحلیل حساسیت.",
  "home.f4": "ورود داده CSV و JSON و خروجی CSV، JSON و PDF از اجراهای محاسبه‌شده.",
  "home.not":
    "این سامانه هیچ نتیجهٔ رسمی یا نظرسنجی‌ای دریافت نمی‌کند. هر نتیجهٔ ذخیره‌شده، حتی اگر دادهٔ تجمیعی خودتان را وارد کرده باشید، «فرضی» علامت می‌خورد.",
  "login.title": "ورود",
  "login.lead": "نشست در یک کوکی HttpOnly نگه داشته می‌شود و گذرواژه در این مرورگر ذخیره نمی‌شود.",
  "login.email": "ایمیل",
  "login.password": "گذرواژه",
  "login.submit": "ورود",
  "login.pending": "در حال ورود…",
  "login.register": "ساخت حساب",
  "login.loading": "در حال بارگذاری…",
  "history.title": "تاریخچهٔ شبیه‌سازی‌ها",
  "history.lead":
    "پیکربندی‌ها و اجراهای ذخیره‌شده در سرور. با راه‌اندازی دوبارهٔ سرور، تا وقتی پایگاه داده سالم باشد، حفظ می‌شوند.",
  "history.loading": "در حال بارگذاری شبیه‌سازی‌های ذخیره‌شده…",
  "history.empty": "هنوز هیچ شبیه‌سازی‌ای ذخیره نشده است.",
  "history.create": "ساختن اولین شبیه‌سازی",
  "history.status": "وضعیت",
  "history.method": "روش",
  "history.iterations": "تعداد تکرار",
  "history.updated": "به‌روزرسانی",
  "history.details": "جزئیات",
  "history.results": "نتایج",
  "history.execution": "اجرا",
  "history.prev": "صفحهٔ قبل",
  "history.next": "صفحهٔ بعد",
  "history.none": "۰ مورد ذخیره‌شده",
  "history.of": "از",
  "notfound.title": "صفحه پیدا نشد",
  "notfound.lead": "این نشانی بخشی از سامانه نیست.",
  "notfound.home": "رفتن به صفحهٔ اصلی",
  "error.title": "نمایش این صفحه با خطا روبه‌رو شد",
  "error.unknown": "خطای غیرمنتظره‌ای رخ داد.",
  "error.retry": "تلاش دوباره",
  "partial": "برخی صفحه‌های تخصصی (ویرایشگر پیکربندی، داشبورد نتایج و ورود داده) هنوز انگلیسی هستند.",
};

const MESSAGES: Record<Locale, Record<MessageKey, string>> = { en, fa };

export function translate(locale: Locale, key: MessageKey): string {
  return MESSAGES[locale][key] ?? en[key];
}

type I18nValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
  numberLocale: string;
};

const I18nContext = createContext<I18nValue>({
  locale: DEFAULT_LOCALE,
  setLocale: () => undefined,
  t: (key) => translate(DEFAULT_LOCALE, key),
  numberLocale: DEFAULT_LOCALE === "fa" ? "fa-IR" : "en-US",
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- read the saved choice once after hydration
      if (stored === "fa" || stored === "en") setLocaleState(stored);
    } catch {
      // Storage can be blocked. Keep the default.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = directionOf(locale);
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore blocked storage.
    }
  }, []);

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      setLocale,
      t: (key) => translate(locale, key),
      numberLocale: locale === "fa" ? "fa-IR" : "en-US",
    }),
    [locale, setLocale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
