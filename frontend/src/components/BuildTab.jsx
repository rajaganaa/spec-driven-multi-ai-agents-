import { useState } from "react";

export default function BuildTab({ project, runState, onNewProject, onPlan, onRunAll, busy }) {
  const [goal, setGoal] = useState("");
  const [stack, setStack] = useState("python,fastapi,react");
  const [constraints, setConstraints] = useState("");
  const [model, setModel] = useState("");
  const [startNew, setStartNew] = useState(false);

  const hasProject = Boolean(project) && !startNew;
  const isRunning = runState?.running;

  return (
    <div>
      <div className="card">
        <h2 className="card-title">{hasProject ? "Current project" : "Start a new project"}</h2>

        {hasProject ? (
          <div className="field">
            <label>Goal</label>
            <div style={{ fontSize: 14 }}>{project.goal}</div>
            <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
              {(project.stack || []).map((s) => (
                <span key={s} className="pill pending mono">
                  {s}
                </span>
              ))}
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-faint)" }} className="mono">
              {project.project_id}
            </div>
          </div>
        ) : (
          <>
            <div className="field">
              <label>What do you want to build?</label>
              <textarea
                rows={3}
                placeholder="Describe what you want to build..."
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              />
            </div>
            <div className="field">
              <label>Stack (comma-separated)</label>
              <input type="text" value={stack} onChange={(e) => setStack(e.target.value)} />
            </div>
            <div className="field">
              <label>Constraints (optional, comma-separated)</label>
              <input
                type="text"
                placeholder="e.g. no third-party auth, must run offline"
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
              />
            </div>
          </>
        )}

        <div className="field">
          <label>Model override (optional — leave blank to use the configured router)</label>
          <input type="text" placeholder="e.g. gemini-2.5-flash" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>

        <div className="btn-row">
          {!hasProject && (
            <>
              <button
                className="btn"
                disabled={busy || !goal.trim()}
                onClick={() => {
                  onNewProject(
                    goal.trim(),
                    stack.split(",").map((s) => s.trim()).filter(Boolean),
                    constraints.split(",").map((s) => s.trim()).filter(Boolean)
                  );
                  setStartNew(false);
                }}
              >
                Create project
              </button>
              {Boolean(project) && (
                <button className="btn secondary" disabled={busy} onClick={() => setStartNew(false)}>
                  Cancel
                </button>
              )}
            </>
          )}
          {hasProject && (
            <>
              <button className="btn" disabled={busy || isRunning} onClick={() => onPlan(model.trim())}>
                Plan (Orchestrator + Feature Leads)
              </button>
              <button className="btn secondary" disabled={busy || isRunning} onClick={() => onRunAll(model.trim())}>
                {isRunning ? "Running…" : "Run all pending tasks"}
              </button>
              <button className="btn secondary" disabled={busy || isRunning} onClick={() => setStartNew(true)}>
                Start a different project
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
