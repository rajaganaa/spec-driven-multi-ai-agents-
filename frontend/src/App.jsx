import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import BackendPill from "./components/BackendPill.jsx";
import BuildTab from "./components/BuildTab.jsx";
import StatusTab from "./components/StatusTab.jsx";
import FilesTab from "./components/FilesTab.jsx";
import LogPanel from "./components/LogPanel.jsx";

const TABS = [
  { id: "build", label: "Build" },
  { id: "status", label: "Status" },
  { id: "files", label: "Files" },
];

let logIdCounter = 0;

export default function App() {
  const [activeTab, setActiveTab] = useState("build");
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [runState, setRunState] = useState({ running: false, kind: null, last_result: null });
  const [modelStatus, setModelStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);

  const wasRunningRef = useRef(false);

  const pushLog = useCallback((type, text) => {
    logIdCounter += 1;
    setLogs((prev) => [...prev.slice(-199), { id: logIdCounter, type, text }]);
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await api.getStatus();
      setProject(res.project);
      setTasks(res.tasks || []);
      setRunState(res.run_state || { running: false });
    } catch {
      // No active project yet, or backend unreachable — both are
      // normal/expected states here, not worth spamming the log.
    }
  }, []);

  const refreshModelStatus = useCallback(async () => {
    try {
      setModelStatus(await api.getModelStatus());
    } catch {
      setModelStatus(null);
    }
  }, []);

  // Poll status every 3s (cheap, drives the live task board + the
  // "Running…" indicator) and the model backend every 15s.
  useEffect(() => {
    refreshStatus();
    refreshModelStatus();
    const statusInterval = setInterval(refreshStatus, 3000);
    const modelInterval = setInterval(refreshModelStatus, 15000);
    return () => {
      clearInterval(statusInterval);
      clearInterval(modelInterval);
    };
  }, [refreshStatus, refreshModelStatus]);

  // Announce when a background run finishes, since /api/run itself
  // only confirms it *started*.
  useEffect(() => {
    if (wasRunningRef.current && !runState.running) {
      const r = runState.last_result;
      if (r?.results) {
        pushLog("ok", `Run finished: ${r.done_count} done, ${r.failed_count} failed (of ${r.task_count}).`);
      } else if (r) {
        pushLog(r.ok ? "ok" : "err", r.ok ? `Task ${r.task_id} done.` : `Task ${r.task_id} failed: ${r.error}`);
      }
    }
    wasRunningRef.current = runState.running;
  }, [runState, pushLog]);

  async function handleNewProject(goal, stack, constraints) {
    setBusy(true);
    pushLog("info", `Creating project: "${goal}"`);
    try {
      const res = await api.newProject(goal, stack, constraints);
      setProject(res.project);
      pushLog("ok", `Project created: ${res.project.project_id}`);
    } catch (e) {
      pushLog("err", e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handlePlan(model) {
    setBusy(true);
    pushLog("info", "Planning: Orchestrator decomposing goal into features…");
    try {
      const res = await api.planProject(model);
      pushLog("ok", `${res.feature_count} feature(s), ${res.total_tasks} task(s) ready.`);
      for (const f of res.features) {
        pushLog(f.ok ? "ok" : "err", f.ok ? `${f.feature}: ${f.task_count} task(s)` : `${f.feature} failed: ${f.error}`);
      }
      await refreshStatus();
    } catch (e) {
      pushLog("err", e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRunAll(model) {
    setBusy(true);
    try {
      const res = await api.runTasks(null, model);
      if (res.started) {
        pushLog("info", `Started running ${res.pending_count} pending task(s)…`);
      } else {
        pushLog("info", res.message);
      }
      await refreshStatus();
    } catch (e) {
      pushLog("err", e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRunTask(taskId) {
    setBusy(true);
    try {
      await api.runTasks(taskId, null);
      pushLog("info", `Started ${taskId}…`);
      await refreshStatus();
    } catch (e) {
      pushLog("err", e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <div className="brand">
          <span className="brand-mark">
            Agent<span>Forge</span>
          </span>
          <span className="brand-sub">spec-driven multi-agent coding hub</span>
        </div>
        <BackendPill modelStatus={modelStatus} />
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${activeTab === t.id ? "active" : ""}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="main">
        <div className="content">
          {activeTab === "build" && (
            <BuildTab
              project={project}
              runState={runState}
              busy={busy}
              onNewProject={handleNewProject}
              onPlan={handlePlan}
              onRunAll={handleRunAll}
            />
          )}
          {activeTab === "status" && (
            <StatusTab project={project} tasks={tasks} runState={runState} busy={busy} onRunTask={handleRunTask} />
          )}
          {activeTab === "files" && <FilesTab project={project} active={activeTab === "files"} />}
        </div>
        <LogPanel logs={logs} />
      </main>
    </div>
  );
}
