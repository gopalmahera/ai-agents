"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NamedTimeInterval, TimeIntervalsConfig } from "@/lib/types";
import { validateTimeIntervals, type TimeIntervalsValidation } from "@/lib/time-intervals-validation";
import { toTimeIntervalsYaml } from "@/lib/time-intervals-yaml";
import { Plus, Trash2, Save, CheckCircle, AlertCircle, Copy, FileCode2, Clock } from "lucide-react";

const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const TIMEZONES = ["UTC", "Asia/Kolkata", "America/New_York", "Europe/London"];

function newInterval(): NamedTimeInterval {
  return {
    name: "",
    time_intervals: [
      {
        weekdays: ["monday", "tuesday", "wednesday", "thursday", "friday"],
        times: [{ start_time: "22:00", end_time: "06:00" }],
        location: "UTC",
      },
    ],
  };
}

function YamlPreview({ yaml, saved }: { yaml: string; saved: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className={`card sticky top-4 ${saved ? "border-emerald-300 dark:border-emerald-800" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileCode2 size={16} className="text-indigo-500" />
          <div>
            <h2 className="text-sm font-semibold">time_intervals.yaml</h2>
            <p className="text-xs text-slate-400">{saved ? "Saved" : "Live preview"}</p>
          </div>
        </div>
        <button
          type="button"
          className="btn-secondary text-xs px-2.5 py-1.5"
          onClick={async () => {
            await navigator.clipboard.writeText(yaml);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
        >
          <Copy size={12} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="text-xs font-mono bg-slate-950/5 dark:bg-slate-950/40 rounded-lg p-3 overflow-auto max-h-[calc(100vh-10rem)] whitespace-pre-wrap">
        {yaml}
      </pre>
    </div>
  );
}

export default function TimeIntervalsPage() {
  const qc = useQueryClient();
  const [intervals, setIntervals] = useState<NamedTimeInterval[]>([]);
  const [validation, setValidation] = useState<TimeIntervalsValidation | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["time-intervals"],
    queryFn: () => api.get<TimeIntervalsConfig>("/api/config/time-intervals"),
  });

  useEffect(() => {
    if (!data) return;
    setIntervals(data.time_intervals ?? []);
    setValidation(null);
  }, [data]);

  const config = useMemo(() => ({ time_intervals: intervals }), [intervals]);
  const yamlPreview = useMemo(() => toTimeIntervalsYaml(config), [config]);

  const saveMutation = useMutation({
    mutationFn: () => api.post("/api/config/time-intervals", config),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["time-intervals"] });
      setValidation(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  const handleSave = () => {
    const result = validateTimeIntervals(intervals);
    setValidation(result);
    if (!result.valid) return;
    saveMutation.mutate();
  };

  if (isLoading) return <div className="card h-64 animate-pulse" />;

  return (
    <div className="max-w-6xl">
      <div className="mb-6">
        <h1 className="text-xl font-[Poppins] font-semibold flex items-center gap-2">
          <Clock size={20} /> Time Intervals
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Named schedules used by routing rules to mute Slack notifications during specific windows
          (Alertmanager-style).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_26rem] gap-6 items-start">
        <div className="min-w-0 space-y-4">
          {intervals.map((entry, idx) => (
            <div key={idx} className="card space-y-3">
              <div className="flex gap-2 items-center">
                <input
                  className={`input flex-1 ${validation?.intervals[idx] ? "border-red-400" : ""}`}
                  value={entry.name}
                  onChange={(e) =>
                    setIntervals((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, name: e.target.value } : r)),
                    )
                  }
                  placeholder="Interval name (e.g. night_hours)"
                />
                <button
                  type="button"
                  className="btn-ghost p-2 text-red-500"
                  onClick={() => setIntervals((rows) => rows.filter((_, i) => i !== idx))}
                >
                  <Trash2 size={14} />
                </button>
              </div>
              {validation?.intervals[idx] && (
                <p className="text-xs text-red-600">{validation.intervals[idx]}</p>
              )}
              <div className="space-y-2">
                <p className="text-xs font-medium text-slate-500">Weekdays</p>
                <div className="flex flex-wrap gap-2">
                  {WEEKDAYS.map((day) => {
                    const selected = entry.time_intervals[0]?.weekdays?.includes(day);
                    return (
                      <button
                        key={day}
                        type="button"
                        className={`text-xs px-2 py-1 rounded border ${
                          selected
                            ? "bg-primary/10 border-primary text-primary"
                            : "border-slate-200 dark:border-slate-600"
                        }`}
                        onClick={() => {
                          setIntervals((rows) =>
                            rows.map((r, i) => {
                              if (i !== idx) return r;
                              const sub = { ...r.time_intervals[0] };
                              const days = new Set(sub.weekdays ?? []);
                              if (days.has(day)) days.delete(day);
                              else days.add(day);
                              sub.weekdays = Array.from(days);
                              return { ...r, time_intervals: [sub] };
                            }),
                          );
                        }}
                      >
                        {day.slice(0, 3)}
                      </button>
                    );
                  })}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    className="input text-sm"
                    value={entry.time_intervals[0]?.times?.[0]?.start_time ?? "22:00"}
                    onChange={(e) =>
                      setIntervals((rows) =>
                        rows.map((r, i) =>
                          i === idx
                            ? {
                                ...r,
                                time_intervals: [
                                  {
                                    ...r.time_intervals[0],
                                    times: [
                                      {
                                        ...(r.time_intervals[0]?.times?.[0] ?? {
                                          start_time: "22:00",
                                          end_time: "06:00",
                                        }),
                                        start_time: e.target.value,
                                      },
                                    ],
                                  },
                                ],
                              }
                            : r,
                        ),
                      )
                    }
                    placeholder="Start HH:MM"
                  />
                  <input
                    className="input text-sm"
                    value={entry.time_intervals[0]?.times?.[0]?.end_time ?? "06:00"}
                    onChange={(e) =>
                      setIntervals((rows) =>
                        rows.map((r, i) =>
                          i === idx
                            ? {
                                ...r,
                                time_intervals: [
                                  {
                                    ...r.time_intervals[0],
                                    times: [
                                      {
                                        ...(r.time_intervals[0]?.times?.[0] ?? {
                                          start_time: "22:00",
                                          end_time: "06:00",
                                        }),
                                        end_time: e.target.value,
                                      },
                                    ],
                                  },
                                ],
                              }
                            : r,
                        ),
                      )
                    }
                    placeholder="End HH:MM"
                  />
                </div>
                <select
                  className="input text-sm"
                  value={entry.time_intervals[0]?.location ?? "UTC"}
                  onChange={(e) =>
                    setIntervals((rows) =>
                      rows.map((r, i) =>
                        i === idx
                          ? {
                              ...r,
                              time_intervals: [{ ...r.time_intervals[0], location: e.target.value }],
                            }
                          : r,
                      ),
                    )
                  }
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}

          <button type="button" className="btn-secondary" onClick={() => setIntervals((r) => [...r, newInterval()])}>
            <Plus size={14} /> Add time interval
          </button>

          {validation && !validation.valid && (
            <div className="card border-red-200 bg-red-50 dark:bg-red-950/20">
              <div className="flex gap-2">
                <AlertCircle size={16} className="text-red-500 shrink-0" />
                <ul className="text-xs text-red-700 list-disc list-inside">
                  {validation.global.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button type="button" className="btn-primary" onClick={handleSave} disabled={saveMutation.isPending}>
              <Save size={14} /> {saveMutation.isPending ? "Saving…" : "Save"}
            </button>
            {saved && (
              <span className="text-sm text-emerald-600 flex items-center gap-1">
                <CheckCircle size={14} /> Saved
              </span>
            )}
            {saveMutation.isError && (
              <span className="text-sm text-red-600">{(saveMutation.error as Error).message}</span>
            )}
          </div>
        </div>

        <aside>
          <YamlPreview yaml={yamlPreview} saved={saved} />
        </aside>
      </div>
    </div>
  );
}
