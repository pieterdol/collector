/** In-app image viewer: backdrop click, Escape, arrow keys, ‹ › buttons. */

import { useEffect } from "react";

interface Props {
  images: string[];
  index: number;
  onClose: () => void;
  onIndex: (index: number) => void;
}

export function Lightbox({ images, index, onClose, onIndex }: Props) {
  const prev = () => onIndex((index - 1 + images.length) % images.length);
  const next = () => onIndex((index + 1) % images.length);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }); // re-binds each render so prev/next capture the current index

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Screenshot viewer"
      onClick={onClose}
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: "rgba(8, 8, 12, 0.92)", backdropFilter: "blur(4px)" }}
    >
      <img
        src={images[index]}
        alt=""
        onClick={(e) => e.stopPropagation()}
        className="max-h-[88vh] max-w-full rounded-xl object-contain shadow-lift"
      />
      {images.length > 1 && (
        <>
          <button
            type="button"
            aria-label="Previous screenshot"
            onClick={(e) => {
              e.stopPropagation();
              prev();
            }}
            className="absolute left-3 top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full bg-black/50 text-xl text-white/90 backdrop-blur hover:bg-black/70"
          >
            ‹
          </button>
          <button
            type="button"
            aria-label="Next screenshot"
            onClick={(e) => {
              e.stopPropagation();
              next();
            }}
            className="absolute right-3 top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full bg-black/50 text-xl text-white/90 backdrop-blur hover:bg-black/70"
          >
            ›
          </button>
          <span className="absolute bottom-4 left-1/2 -translate-x-1/2 font-mono text-[11px] tracking-[0.1em] text-white/70">
            {index + 1} / {images.length}
          </span>
        </>
      )}
      <button
        type="button"
        aria-label="Close viewer"
        onClick={onClose}
        className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-full bg-black/50 text-lg text-white/90 backdrop-blur hover:bg-black/70"
      >
        ×
      </button>
    </div>
  );
}
