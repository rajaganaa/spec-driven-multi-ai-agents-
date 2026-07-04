export default function StatusPill({ status }) {
  const s = status || "pending";
  const label = { in_progress: "running", done: "done", failed: "failed", pending: "pending" }[s] || s;
  return <span className={`pill ${s}`}>{label}</span>;
}
