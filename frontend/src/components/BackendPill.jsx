export default function BackendPill({ modelStatus }) {
  if (!modelStatus) {
    return (
      <div className="backend-pill">
        <span className="backend-dot unknown" />
        checking backend…
      </div>
    );
  }

  if (!modelStatus.vllm_configured) {
    return (
      <div className="backend-pill" title="VLLM_BASE_URL is not set — every role is using Gemini directly.">
        <span className="backend-dot gemini" />
        gemini · no vLLM configured
      </div>
    );
  }

  if (modelStatus.vllm_healthy) {
    const shortModel = (modelStatus.vllm_model || "").split("/").pop();
    return (
      <div className="backend-pill" title={modelStatus.vllm_base_url}>
        <span className="backend-dot vllm" />
        vllm · {shortModel}
      </div>
    );
  }

  return (
    <div className="backend-pill" title="vLLM is configured but the health check is failing — falling back to Gemini.">
      <span className="backend-dot gemini" />
      gemini · vllm fallback active
    </div>
  );
}
