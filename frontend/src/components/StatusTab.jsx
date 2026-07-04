import StatusPill from "./StatusPill.jsx";

export default function StatusTab({ project, tasks, onRunTask, busy, runState }) {
  if (!project) {
    return <div className="empty-state">No active project yet — create one in the Build tab.</div>;
  }

  if (!tasks || tasks.length === 0) {
    return <div className="empty-state">No tasks yet. Run Plan in the Build tab first.</div>;
  }

  return (
    <div className="card">
      <h2 className="card-title">Task board</h2>
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Feature</th>
            <th>Status</th>
            <th>Agent</th>
            <th>Commit</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr key={t.id}>
              <td className="mono">{t.id}</td>
              <td className="mono">{t.feature || "—"}</td>
              <td>
                <StatusPill status={t.status} />
              </td>
              <td>{t.agent || "—"}</td>
              <td className="mono">{t.commit ? t.commit.slice(0, 8) : "—"}</td>
              <td>
                {t.status !== "done" && (
                  <button
                    className="btn secondary"
                    style={{ padding: "4px 10px", fontSize: 12 }}
                    disabled={busy || runState?.running}
                    onClick={() => onRunTask(t.id)}
                  >
                    Run
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
