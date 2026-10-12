"use client";

import { useRef, useState, useTransition } from "react";

import type { FlagStatus } from "@/lib/api-types";

import { triageFlag } from "./actions";

type TriageControlsProps = {
  flagId: number;
  status: FlagStatus;
  label: string;
};

export function TriageControls({ flagId, status, label }: TriageControlsProps) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  function openDismiss() {
    setError(null);
    setDismissing(true);
    dialogRef.current?.showModal();
  }

  function update(next: FlagStatus, reason?: string) {
    setError(null);
    startTransition(async () => {
      const result = await triageFlag(flagId, next, reason);
      if (result) setError(result.error);
      else dialogRef.current?.close();
    });
  }

  function onDismiss(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    update("dismissed", String(new FormData(event.currentTarget).get("reason") ?? ""));
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="join whitespace-nowrap">
        {status === "open" && (
          <button className="btn btn-xs join-item" disabled={pending} onClick={() => update("acknowledged")}>
            Acknowledge
          </button>
        )}
        {status !== "dismissed" && (
          <button className="btn btn-xs join-item" disabled={pending} onClick={openDismiss}>
            Dismiss
          </button>
        )}
        {status !== "open" && (
          <button className="btn btn-xs btn-ghost join-item" disabled={pending} onClick={() => update("open")}>
            Reopen
          </button>
        )}
      </div>
      {error && !dismissing && <p className="text-error text-xs">{error}</p>}

      <dialog ref={dialogRef} className="modal" onClose={() => setDismissing(false)}>
        <form className="modal-box space-y-3 text-left" onSubmit={onDismiss}>
          <h3 className="text-lg font-semibold">Dismiss flag</h3>
          <p className="text-sm opacity-70">{label}</p>
          <label className="flex flex-col gap-1">
            <span className="text-sm">Why is this not a problem?</span>
            <textarea
              name="reason"
              className="textarea w-full"
              rows={3}
              maxLength={2000}
              required
              placeholder="e.g. Paired on it live, so the fast approval was expected."
            />
          </label>
          {error && dismissing && <p className="text-error text-sm">{error}</p>}
          <div className="modal-action">
            <button type="button" className="btn btn-ghost" onClick={() => dialogRef.current?.close()}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={pending}>
              {pending ? "Dismissing..." : "Dismiss"}
            </button>
          </div>
        </form>
        <form method="dialog" className="modal-backdrop">
          <button aria-label="Close">close</button>
        </form>
      </dialog>
    </div>
  );
}
