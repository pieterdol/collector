/** Camera barcode scanner.
 *
 * Uses the native BarcodeDetector API when the browser has it (Chrome,
 * Android WebView); otherwise falls back to @zxing/browser. Emits the
 * first successfully decoded EAN/UPC/ISBN string, then stops.
 */

import { useEffect, useRef, useState } from "react";

interface Props {
  onDetected: (code: string) => void;
}

type NativeDetector = {
  detect: (source: CanvasImageSource) => Promise<Array<{ rawValue: string }>>;
};

const NATIVE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"];

export function BarcodeScanner({ onDetected }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const detectedRef = useRef(false);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let cancelled = false;
    let stopZxing: (() => void) | null = null;
    let nativeTimer: number | null = null;

    const emit = (code: string) => {
      if (detectedRef.current || cancelled) return;
      detectedRef.current = true;
      onDetected(code);
    };

    async function start() {
      const video = videoRef.current;
      if (!video) return;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
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
      video.srcObject = stream;
      await video.play().catch(() => undefined);

      if ("BarcodeDetector" in window) {
        const Detector = (window as unknown as { BarcodeDetector: new (o: object) => NativeDetector })
          .BarcodeDetector;
        const detector = new Detector({ formats: NATIVE_FORMATS });
        const tick = async () => {
          if (cancelled || detectedRef.current) return;
          try {
            const codes = await detector.detect(video);
            if (codes.length > 0) return emit(codes[0].rawValue);
          } catch {
            /* frame not ready yet */
          }
          nativeTimer = window.setTimeout(tick, 180);
        };
        void tick();
      } else {
        // Fallback: zxing reads frames from the same <video> element.
        const { BrowserMultiFormatReader } = await import("@zxing/browser");
        const reader = new BrowserMultiFormatReader();
        const controls = await reader.decodeFromVideoElement(video, (result) => {
          if (result) emit(result.getText());
        });
        stopZxing = () => controls.stop();
      }
    }

    void start();
    return () => {
      cancelled = true;
      if (nativeTimer !== null) clearTimeout(nativeTimer);
      stopZxing?.();
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onDetected]);

  return (
    <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-2xl bg-black">
      <video ref={videoRef} className="absolute inset-0 h-full w-full object-cover" muted playsInline />
      {!error && (
        <>
          <div
            className="relative z-10 h-[38%] w-[64%] rounded-xl"
            style={{ boxShadow: "0 0 0 999px rgb(5 4 14 / 0.5)" }}
          />
          <div className="scanline z-10" />
          <div className="absolute bottom-3.5 z-10 w-full text-center font-mono text-[10.5px] uppercase tracking-[0.12em] text-white/80">
            Point at the barcode
          </div>
        </>
      )}
      {error && <p className="relative z-10 max-w-xs p-6 text-center text-sm text-white/85">{error}</p>}
    </div>
  );
}
