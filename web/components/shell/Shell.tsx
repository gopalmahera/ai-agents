"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Moon, Sun, Menu, X, ChevronDown } from "lucide-react";
import { useState, useEffect, useRef } from "react";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  {
    label: "Config",
    children: [
      { href: "/config/ai", label: "AI Provider" },
      { href: "/config/mcp", label: "Service Endpoints" },
      { href: "/config/storage", label: "Storage & Behavior" },
    ],
  },
  { href: "/routing", label: "Routing" },
  { href: "/logs", label: "Logs" },
  { href: "/reports", label: "Reports" },
];

function navLinkClass(active: boolean) {
  return `rounded-md px-3 py-1.5 text-sm font-medium font-[Poppins] transition-colors ${
    active
      ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-indigo-300"
      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
  }`;
}

function ConfigDropdown({ pathname }: { pathname: string }) {
  const item = NAV.find((n) => "children" in n)!;
  const children = (item as { children: { href: string; label: string }[] }).children;
  const active = children.some((c) => pathname.startsWith(c.href));
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`${navLinkClass(active)} inline-flex items-center gap-1`}
      >
        Config
        <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-44 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg py-1 z-50">
          {children.map((c) => (
            <Link
              key={c.href}
              href={c.href}
              onClick={() => setOpen(false)}
              className={`block px-4 py-2 text-sm transition-colors ${
                pathname === c.href
                  ? "text-primary font-medium"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"
              }`}
            >
              {c.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const isDark = saved === "dark" || (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  return (
    <button onClick={toggle} className="btn-ghost p-2" aria-label="Toggle theme">
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // close mobile menu on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Top navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2 shrink-0 mr-2">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
              <Bell size={13} className="text-white" />
            </div>
            <span className="font-[Poppins] font-semibold text-sm text-slate-900 dark:text-slate-100 hidden sm:block">
              AI Alert Agent
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden sm:flex items-center gap-0.5 flex-1">
            {NAV.map((item) =>
              "children" in item ? (
                <ConfigDropdown key="config" pathname={pathname} />
              ) : (
                <Link
                  key={item.href}
                  href={item.href}
                  className={navLinkClass(pathname === item.href || pathname.startsWith(item.href + "/"))}
                >
                  {item.label}
                </Link>
              )
            )}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            {/* Hamburger — mobile only */}
            <button
              className="sm:hidden btn-ghost p-2"
              onClick={() => setMobileOpen((v) => !v)}
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              {mobileOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {/* Mobile drawer */}
        {mobileOpen && (
          <>
            <div
              className="sm:hidden fixed inset-0 z-30 bg-black/20 dark:bg-black/40"
              onClick={() => setMobileOpen(false)}
            />
            <div className="sm:hidden absolute left-0 right-0 top-full z-40 border-b border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm shadow-lg">
              <nav className="flex flex-col gap-0.5 px-4 py-3" onClick={() => setMobileOpen(false)}>
                {NAV.flatMap((item) =>
                  "children" in item
                    ? (item as { children: { href: string; label: string }[] }).children.map((c) => (
                        <Link
                          key={c.href}
                          href={c.href}
                          className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                            pathname === c.href
                              ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-indigo-300"
                              : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                          }`}
                        >
                          <span className="text-xs text-slate-400 dark:text-slate-600">Config /</span>
                          {c.label}
                        </Link>
                      ))
                    : [
                        <Link
                          key={item.href}
                          href={item.href}
                          className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                            pathname === item.href || pathname.startsWith(item.href + "/")
                              ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-indigo-300"
                              : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                          }`}
                        >
                          {item.label}
                        </Link>,
                      ]
                )}
              </nav>
            </div>
          </>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-6 sm:py-8">
        {children}
      </main>
    </div>
  );
}
