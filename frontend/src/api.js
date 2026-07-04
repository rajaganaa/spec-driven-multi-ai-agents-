// src/api.js — thin fetch wrapper around api.py.
//
// VITE_API_URL is read at BUILD time (Vite inlines import.meta.env.*
// into the bundle) — set it in frontend/.env before `npm run build`,
// not as a runtime environment variable.

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8080";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = body?.detail || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

export const api = {
  newProject: (goal, stack, constraints) =>
    request("/api/new", {
      method: "POST",
      body: JSON.stringify({ goal, stack, constraints }),
    }),

  planProject: (model) =>
    request("/api/plan", {
      method: "POST",
      body: JSON.stringify({ model: model || null }),
    }),

  runTasks: (taskId, model, maxRetries) =>
    request("/api/run", {
      method: "POST",
      body: JSON.stringify({
        task_id: taskId || null,
        model: model || null,
        max_retries: maxRetries ?? null,
      }),
    }),

  getStatus: () => request("/api/status"),

  getFiles: () => request("/api/files"),

  getFileContent: (path) =>
    request(`/api/files/content?path=${encodeURIComponent(path)}`),

  getModelStatus: () => request("/api/model-status"),
};
