/** "Mark as acquired": wishlist → backlog with price/format/date. */

import { useEffect, useRef, useState } from "react";
import { useAcquireItem } from "../lib/queries";
import type { Item } from "../lib/types";

interface Props {
  item: Item;
  onClose: () => void;
  onDone?: () => void;
}

export function AcquireDialog({ item, onClose, onDone }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const acquire = useAcquireItem(item.id);
  const [format, setFormat] = useState("physical");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));

  useEffect(() => {
    dialogRef.current?.showModal();
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    acquire.mutate(
      {
        format,
        purchase_price: price ? Number(price) : null,
        currency: price ? currency : null,
        acquisition_date: date || null,
      },
      {
        onSuccess: () => {
          onClose();
          onDone?.();
        },
      },
    );
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="m-auto w-[calc(100vw-48px)] max-w-[420px] rounded-2xl border border-line bg-raised p-7 text-text shadow-lift backdrop:bg-black/65 backdrop:backdrop-blur-sm"
    >
      <h3 className="m-0 mb-0.5 text-xl font-extrabold tracking-tight">Acquired: {item.title}</h3>
      <p className="m-0 mb-5 text-[13.5px] text-muted">
        Moves it from your wishlist to the backlog and records the acquisition.
      </p>
      <form onSubmit={submit} className="grid grid-cols-2 gap-3.5">
        <label className="field">
          Price paid
          <input
            inputMode="decimal"
            placeholder="24.99"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </label>
        <label className="field">
          Currency
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option>EUR</option>
            <option>USD</option>
            <option>GBP</option>
          </select>
        </label>
        <label className="field">
          Format
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="physical">Physical</option>
            <option value="digital">Digital</option>
          </select>
        </label>
        <label className="field">
          Acquired on
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        {acquire.isError && (
          <p className="col-span-2 m-0 text-[13px] text-movie">{(acquire.error as Error).message}</p>
        )}
        <div className="col-span-2 mt-1.5 flex justify-end gap-2.5">
          <button type="button" className="btn btn-ghost" onClick={() => dialogRef.current?.close()}>
            Cancel
          </button>
          <button type="submit" className="btn btn-go" disabled={acquire.isPending}>
            {acquire.isPending ? "Saving…" : "Add to backlog"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
