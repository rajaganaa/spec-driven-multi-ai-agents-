import { useEffect, useState } from "react";
import { api } from "../api.js";

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function FilesTab({ project, active }) {
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!active || !project) return;
    api
      .getFiles()
      .then((res) => setFiles(res.files || []))
      .catch((e) => setError(e.message));
  }, [active, project]);

  function openFile(path) {
    setSelected(path);
    setLoading(true);
    setError(null);
    api
      .getFileContent(path)
      .then((res) => setContent(res.content))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  if (!project) {
    return <div className="empty-state">No active project yet — create one in the Build tab.</div>;
  }

  if (files.length === 0) {
    return <div className="empty-state">No generated files yet. Run some tasks first.</div>;
  }

  return (
    <div className="files-layout">
      <div className="file-list">
        {files.map((f) => (
          <div
            key={f.path}
            className={`file-item ${selected === f.path ? "selected" : ""}`}
            onClick={() => openFile(f.path)}
          >
            <span>{f.path}</span>
            <span className="file-size">{formatSize(f.size)}</span>
          </div>
        ))}
      </div>
      <div className="file-viewer">
        {!selected && <div className="empty-state">Select a file to view it.</div>}
        {selected && loading && <div className="empty-state">Loading…</div>}
        {selected && error && <div className="error-banner">{error}</div>}
        {selected && !loading && !error && (
          <pre>
            <code>{content}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
