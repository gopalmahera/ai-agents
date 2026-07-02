"use client";

import type { ReactNode } from "react";

export function SettingsPageLayout({
  title,
  description,
  toolbar,
  children,
}: {
  title: string;
  description?: string;
  toolbar?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
        {description && (
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>
        )}
      </div>
      {toolbar}
      {children}
    </div>
  );
}
