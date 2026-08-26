import { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    fetch("http://localhost:8000/health")
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("backend unreachable"));
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">RazorGate</h1>
      <p>Backend status: {status}</p>
    </div>
  );
}

export default App;
