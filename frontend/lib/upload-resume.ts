import { getStoredAccessToken } from "./auth-store";
import { API_BASE_URL, ApiError, tryRefreshToken } from "./api";
import type { ResumeUploadResponse } from "./types";

function send(file: File, token: string | null, onProgress: (pct: number) => void) {
  return new Promise<{ status: number; parsed: unknown }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open("POST", `${API_BASE_URL}/candidate/resume/upload`, true);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      let parsed: unknown = null;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        parsed = null;
      }
      resolve({ status: xhr.status, parsed });
    };

    xhr.onerror = () => {
      reject(
        new ApiError(
          "Unable to reach the server. Please check your connection and try again.",
          0
        )
      );
    };

    xhr.ontimeout = () => {
      reject(new ApiError("The upload timed out. Please try again.", 0));
    };

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/**
 * Uploads the resume file via XMLHttpRequest (rather than fetch) so we can
 * report real byte-level transfer progress for the "Uploading" stage of the
 * processing screen. The server call itself blocks for a while after the
 * transfer completes (synchronous LLM parsing), which the caller should
 * represent with the staged processing UI while this promise is pending.
 *
 * On a 401 (expired access token — the app's tokens last 60 minutes and a
 * user can easily sit on this page longer than that), this silently refreshes
 * and retries once, same as every other authenticated call made through
 * `request()` in api.ts. Without this, uploading after a token expiry would
 * fail with a confusing "Could not validate credentials" error instead of
 * transparently continuing.
 */
export async function uploadResumeWithProgress(
  file: File,
  onProgress: (pct: number) => void
): Promise<ResumeUploadResponse> {
  const token = getStoredAccessToken();
  let { status, parsed } = await send(file, token, onProgress);

  if (status === 401) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      onProgress(0);
      ({ status, parsed } = await send(file, newToken, onProgress));
    }
  }

  if (status >= 200 && status < 300) {
    return parsed as ResumeUploadResponse;
  }

  const detail =
    parsed && typeof parsed === "object" && "detail" in (parsed as Record<string, unknown>)
      ? String((parsed as Record<string, unknown>).detail)
      : status === 401
      ? "Your session has expired. Please log in again."
      : `Upload failed (${status})`;
  throw new ApiError(detail, status, parsed);
}
