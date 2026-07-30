/** Preparing a camera photo for upload.
 *
 * A 12MP phone photo is ~4MB and reads *worse* than a 1024px one — the
 * vision model answers slower and sometimes not at all. The backend
 * normalises again (it must, for any other client), so this is purely about
 * not pushing megabytes over wifi.
 */

const MAX_EDGE = 1024;

/** Downscale and upright a photo; the original is returned untouched when
 * the browser can't do it (or it isn't an image). */
export async function shrinkForUpload(file: File): Promise<File> {
  if (typeof createImageBitmap !== "function" || typeof document === "undefined") return file;
  try {
    // from-image: honour the EXIF rotation phones record instead of
    // rotating pixels. Sideways covers read badly.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) return file;
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.85),
    );
    if (!blob) return file;
    return new File([blob], "cover.jpg", { type: "image/jpeg" });
  } catch {
    return file; // jsdom, exotic formats, tainted canvas — send as-is
  }
}
