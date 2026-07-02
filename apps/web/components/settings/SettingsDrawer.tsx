"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";

export function SettingsDrawer({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  if (!open) return null;
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 dark:bg-black/50" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700">
          <h2 className="font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
          <button className="btn-ghost p-2" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">{children}</div>
        {footer && (
          <div className="border-t border-slate-200 dark:border-slate-700 px-5 py-4 flex items-center gap-3">
            {footer}
          </div>
        )}
      </div>
    </>
  );
}
