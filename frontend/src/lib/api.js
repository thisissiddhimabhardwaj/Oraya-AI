const BASE = import.meta.env.VITE_API_URL || "/api/v1";
const TOKEN_KEY = "oraya_token";

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

function authHeaders(extra = {}) {
  const token = tokenStore.get();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function parseError(res) {
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    /* non-JSON error body */
  }
  const detail = payload?.detail;
  let message =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || String(d)).join("\n")
        : `Request failed (${res.status})`;
  if (res.status === 401) {
    tokenStore.clear();
    window.dispatchEvent(new CustomEvent("oraya:unauthorized"));
  }
  return new ApiError(message, res.status, payload);
}

async function request(
  path,
  { method = "GET", body, headers = {}, signal } = {},
) {
  const opts = { method, headers: authHeaders(headers), signal };
  if (body !== undefined) {
    if (body instanceof FormData) {
      opts.body = body;
    } else {
      opts.headers = { "Content-Type": "application/json", ...opts.headers };
      opts.body = JSON.stringify(body);
    }
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, opts);
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new ApiError(
      "Can't reach the ORAYA server. Check your connection and try again.",
      0,
      null,
    );
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return null;
  return res.json();
}

async function getBlob(path, signal) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { headers: authHeaders(), signal });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new ApiError(
      "Can't load this file. Check your connection and try again.",
      0,
      null,
    );
  }
  if (!res.ok) throw await parseError(res);
  return res.blob();
}

function download(path, filename) {
  return getBlob(path).then((blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  });
}

export const api = {
  get: (path, signal) => request(path, { signal }),
  post: (path, body, signal) => request(path, { method: "POST", body, signal }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  del: (path) => request(path, { method: "DELETE" }),
  upload: (path, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(path, { method: "POST", body: fd });
  },
  download,
  blob: getBlob,
  baseUrl: BASE,
};
