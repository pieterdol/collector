/** Camera barcode scanner.
 *
 * Uses the native BarcodeDetector where the browser has one (Chrome,
 * Android WebView); everywhere else (iOS Safari!) a WASM ponyfill with the
 * identical API takes over — far more reliable on 1D product barcodes than
 * the old zxing JS port. The stream is requested at 1080p with continuous
 * autofocus, because default low-res streams blur EAN/UPC bars together.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  onDetected: (code: string) => void;
}

interface DetectorLike {
  detect: (source: CanvasImageSource) => Promise<Array<{ rawValue: string }>>;
}

const FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];
const SCAN_INTERVAL_MS = 160;

async function makeDetector(): Promise<DetectorLike> {
  if ("BarcodeDetector" in window) {
    const Native = (window as unknown as { BarcodeDetector: new (o: object) => DetectorLike })
      .BarcodeDetector;
    try {
      const supported: string[] = await (
        Native as unknown as { getSupportedFormats?: () => Promise<string[]> }
      ).getSupportedFormats?.() ?? [];
      if (FORMATS.some((f) => supported.includes(f))) {
        return new Native({ formats: FORMATS.filter((f) => supported.includes(f)) });
      }
    } catch {
      /* fall through to the ponyfill */
    }
  }
  const [{ BarcodeDetector: Ponyfill, prepareZXingModule }, { default: wasmUrl }] =
    await Promise.all([
      import("barcode-detector/ponyfill"),
      import("zxing-wasm/reader/zxing_reader.wasm?url"),
    ]);
  // Serve the WASM from our own bundle — no CDN, works offline in the PWA.
  prepareZXingModule({
    overrides: {
      locateFile: (path: string, prefix: string) =>
        path.endsWith(".wasm") ? wasmUrl : prefix + path,
    },
  });
  return new Ponyfill({ formats: FORMATS as never });
}

export function BarcodeScanner({ onDetected }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const detectedRef = useRef(false);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    let timer: number | null = null;

    async function start() {
      const video = videoRef.current;
      if (!video) return;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "environment",
            // High resolution is what makes 1D barcodes readable.
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });
      } catch {
        setError(
          "Camera unavailable. Allow camera access (needs HTTPS or localhost), or type the code by hand below.",
        );
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      // Ask for continuous autofocus where the platform supports it.
      const [track] = stream.getVideoTracks();
      try {
        await track.applyConstraints({
          advanced: [{ focusMode: "continuous" } as MediaTrackConstraintSet],
        });
      } catch {
        /* not supported — fine */
      }

      video.srcObject = stream;
      await video.play().catch(() => undefined);

      const detector = await makeDetector();
      const tick = async () => {
        if (cancelled || detectedRef.current) return;
        try {
          if (video.readyState >= 2) {
            const codes = await detector.detect(video);
            const value = codes[0]?.rawValue?.trim();
            if (value) {
              detectedRef.current = true;
              onDetected(value);
              return;
            }
          }
        } catch {
          /* frame not ready or decoder hiccup — try again */
        }
        timer = window.setTimeout(tick, SCAN_INTERVAL_MS);
      };
      void tick();
    }

    void start();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onDetected]);

  return (
    <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-2xl bg-black">
      <video ref={videoRef} className="absolute inset-0 h-full w-full object-cover" muted playsInline />
      {!error && (
        <>
          <div
            className="relative z-10 h-[38%] w-[72%] rounded-xl"
            style={{ boxShadow: "0 0 0 999px rgb(5 4 14 / 0.5)" }}
          />
          <div className="scanline z-10" />
          <div className="absolute bottom-3.5 z-10 w-full text-center font-mono text-[10.5px] uppercase tracking-[0.12em] text-white/80">
            Fill the frame · hold steady
          </div>
        </>
      )}
      {error && <p className="relative z-10 max-w-xs p-6 text-center text-sm text-white/85">{error}</p>}
    </div>
  );
}
