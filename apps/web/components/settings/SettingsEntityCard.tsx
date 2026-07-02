"use client";

import { Trash2 } from "lucide-react";
import type { ReactNode } from "react";

export function SettingsEntityCard({
  title,
  subtitle,
  badges,
  onClick,
  onDelete,
}: {
  title: string;
  subtitle?: string;
  badges?: ReactNode;
  onClick: () => void;
  onDelete?: () => void;
}) {
  return (
    <div
      className="card cursor-pointer hover:border-primary/40 transition-colors group relative"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
    >
      {onDelete && (
        <button
          className="btn-ghost text-red-500 absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity p-1.5"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          aria-label="Delete"
        >
          <Trash2 size={14} />
        </button>
      )}
      <div className="pr-8">
        <h3 className="font-medium text-slate-900 dark:text-slate-100 truncate">{title}</h3>
        {subtitle && (
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 truncate">{subtitle}</p>
        )}
        {badges && <div className="flex flex-wrap gap-1.5 mt-2">{badges}</div>}
      </div>
    </div>
  );
}
