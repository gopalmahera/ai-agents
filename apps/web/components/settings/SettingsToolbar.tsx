"use client";

import { Plus, Search } from "lucide-react";
import type { ReactNode } from "react";

type FilterOption = { value: string; label: string };

export function SettingsToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  filter,
  filterOptions,
  onFilterChange,
  addLabel = "Add",
  onAdd,
  extra,
}: {
  search: string;
  onSearchChange: (v: string) => void;
  searchPlaceholder?: string;
  filter?: string;
  filterOptions?: FilterOption[];
  onFilterChange?: (v: string) => void;
  addLabel?: string;
  onAdd: () => void;
  extra?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-5">
      <div className="relative flex-1 min-w-48">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          className="input pl-8"
          placeholder={searchPlaceholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
      {filterOptions && onFilterChange && (
        <select className="input w-40 flex-none" value={filter ?? ""} onChange={(e) => onFilterChange(e.target.value)}>
          {filterOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
      {extra}
      <button className="btn-primary ml-auto" onClick={onAdd}>
        <Plus size={14} /> {addLabel}
      </button>
    </div>
  );
}
