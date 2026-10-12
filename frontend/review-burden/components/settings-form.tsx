"use client";

import { useActionState, useState } from "react";

import { type SettingsState, settingsAction } from "@/app/settings/actions";
import { type FormValues, type NumberField, SETTINGS_GROUPS, WEIGHT_KEYS } from "@/lib/settings-fields";

function weightTotal(values: Partial<FormValues>): number {
  return Math.round(WEIGHT_KEYS.reduce((sum, key) => sum + (Number(values[key]) || 0), 0) * 100) / 100;
}

export function SettingsForm({ values, defaults }: { values: FormValues; defaults: FormValues }) {
  const [state, action, pending] = useActionState<SettingsState, FormData>(settingsAction, {
    version: 0,
    values,
    saved: values,
    message: null,
  });

  return (
    <div className="space-y-4">
      {state.message && (
        <div
          role={state.message.kind === "error" ? "alert" : "status"}
          className={`alert alert-soft ${state.message.kind === "error" ? "alert-error" : "alert-success"}`}
        >
          {state.message.text}
        </div>
      )}
      <SettingsFields key={state.version} values={state.values} defaults={defaults} action={action} pending={pending} />
    </div>
  );
}

function SettingsFields({
  values,
  defaults,
  action,
  pending,
}: {
  values: FormValues;
  defaults: FormValues;
  action: (formData: FormData) => void;
  pending: boolean;
}) {
  const [total, setTotal] = useState(() => weightTotal(values));

  function onChange(event: React.FormEvent<HTMLFormElement>) {
    const data = Object.fromEntries(new FormData(event.currentTarget)) as Partial<FormValues>;
    setTotal(weightTotal(data));
  }

  return (
    <form action={action} onChange={onChange} className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        {SETTINGS_GROUPS.map((group) => (
          <fieldset key={group.title} className="card bg-base-100 shadow-sm">
            <div className="card-body gap-3">
              <legend className="card-title text-base">{group.title}</legend>
              <p className="text-sm opacity-70">{group.description}</p>
              {group.fields.map((field) => (
                <NumberInput key={field.key} field={field} value={values[field.key]} fallback={defaults[field.key]} />
              ))}
              {group.phrases && (
                <label className="flex flex-col gap-1">
                  <span className="text-sm">Stock phrases, one per line (never substantive)</span>
                  <textarea
                    name="stock_phrases"
                    defaultValue={values.stock_phrases}
                    rows={4}
                    className="textarea w-full"
                  />
                </label>
              )}
              {group.fields.some((f) => WEIGHT_KEYS.includes(f.key)) && (
                <p className={`text-sm ${total === 100 ? "opacity-70" : "font-medium text-error"}`}>
                  Weights add up to {total}%
                </p>
              )}
            </div>
          </fieldset>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" name="intent" value="save" className="btn btn-primary" disabled={pending}>
          Save and re-run rules
        </button>
        <button type="submit" name="intent" value="reset" className="btn" disabled={pending} formNoValidate>
          Reset to defaults
        </button>
        <button type="submit" name="intent" value="rerun" className="btn btn-ghost" disabled={pending} formNoValidate>
          Re-run rules with saved settings
        </button>
        {pending && <span className="loading loading-spinner loading-sm" aria-label="Working" />}
      </div>
    </form>
  );
}

function NumberInput({ field, value, fallback }: { field: NumberField; value: string; fallback: string }) {
  const changed = value !== fallback;
  return (
    <label className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5">
      <span className="text-sm">{field.label}</span>
      <span className="flex items-center gap-2">
        <input
          type="number"
          name={field.key}
          defaultValue={value}
          step={field.step ?? 1}
          min={field.min}
          max={field.max}
          required
          className={`input input-sm w-24 text-right ${changed ? "input-warning" : ""}`}
        />
        <span className="w-28 text-xs opacity-70">{field.unit}</span>
      </span>
      <span className="col-span-2 text-xs opacity-60">
        Default {fallback}
        {field.percent ? "%" : ""}
        {changed && " (changed)"}
      </span>
    </label>
  );
}
