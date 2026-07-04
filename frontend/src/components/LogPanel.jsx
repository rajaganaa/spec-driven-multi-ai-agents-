import { useEffect, useRef } from "react";

export default function LogPanel({ logs }) {
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="log-panel">
      <div className="log-panel-header">
        <span>agent log</span>
        <span>{logs.length} line{logs.length === 1 ? "" : "s"}</span>
      </div>
      <div className="log-panel-body" ref={bodyRef}>
        {logs.length === 0 && <div className="log-line">waiting for activity…</div>}
        {logs.map((line) => (
          <div key={line.id} className={`log-line ${line.type}`}>
            {line.text}
          </div>
        ))}
        <span className="cursor" />
      </div>
    </div>
  );
}
