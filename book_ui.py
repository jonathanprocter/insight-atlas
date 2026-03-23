from flask import Flask, request, render_template_string, Response, redirect
from uuid import uuid4
import json, queue, threading, time

from notion_client_registry import CLIENTS
from client_intelligence_engine import run_client_pipeline_stream

app = Flask(__name__)
STREAMS = {}

def create_stream():
    sid = str(uuid4())
    STREAMS[sid] = {
        "queue": queue.Queue(),
        "created": time.time()
    }
    return sid

def emit(sid, event, data):
    if sid in STREAMS:
        STREAMS[sid]["queue"].put((event, data))

def start_job(sid, client):
    def runner():
        try:
            run_client_pipeline_stream(
                client,
                emit=lambda e, d: emit(sid, e, d)
            )
        except Exception as e:
            emit(sid, "error", {"message": str(e)})
    threading.Thread(target=runner, daemon=True).start()

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        client = request.form.get("client")
        sid = create_stream()
        start_job(sid, client)
        return redirect(f"/job/{sid}")

    return render_template_string(HOME, clients=sorted(CLIENTS.keys()))

@app.route("/job/<sid>")
def job(sid):
    return render_template_string(JOB, sid=sid)

@app.route("/events/<sid>")
def events(sid):
    def stream():
        if sid not in STREAMS:
            yield "event: error\ndata: {}\n\n"
            return

        q = STREAMS[sid]["queue"]

        while True:
            try:
                e, d = q.get(timeout=60)
                yield f"event: {e}\n"
                yield f"data: {json.dumps(d)}\n\n"
                if e in ["done", "error"]:
                    break
            except:
                yield "event: ping\ndata: {}\n\n"

    return Response(stream(), mimetype="text/event-stream")

HOME = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insight Atlas</title>
<style>
:root{
  --bg:#f5f7fb;
  --card:#ffffff;
  --text:#0f172a;
  --muted:#64748b;
  --line:#e2e8f0;
  --brand:#2563eb;
  --brand-soft:#dbeafe;
  --shadow:0 10px 30px rgba(15,23,42,.08);
  --radius:18px;
}
*{box-sizing:border-box}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",sans-serif;
  background:
    radial-gradient(circle at top left, #e0ecff 0%, transparent 30%),
    radial-gradient(circle at bottom right, #eef4ff 0%, transparent 35%),
    var(--bg);
  color:var(--text);
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:24px;
}
.shell{
  width:min(460px, 100%);
  background:rgba(255,255,255,.78);
  backdrop-filter: blur(14px);
  border:1px solid rgba(255,255,255,.6);
  box-shadow:var(--shadow);
  border-radius:24px;
  padding:28px;
}
.logo{
  font-size:32px;
  font-weight:800;
  margin:0 0 8px 0;
  letter-spacing:-0.02em;
}
.sub{
  color:var(--muted);
  margin:0 0 20px 0;
  font-size:14px;
}
label{
  display:block;
  margin:0 0 8px 2px;
  font-size:13px;
  color:var(--muted);
  font-weight:600;
}
select, button{
  width:100%;
  border-radius:14px;
  padding:14px 16px;
  font-size:15px;
}
select{
  border:1px solid var(--line);
  background:#fff;
  color:var(--text);
  outline:none;
}
button{
  margin-top:14px;
  border:none;
  background:linear-gradient(135deg, #2563eb, #3b82f6);
  color:white;
  font-weight:700;
  box-shadow:0 10px 24px rgba(37,99,235,.24);
  cursor:pointer;
  transition:transform .15s ease, box-shadow .2s ease;
}
button:hover{
  transform:translateY(-1px);
  box-shadow:0 14px 30px rgba(37,99,235,.28);
}
button:active{
  transform:translateY(0);
}
.footer{
  margin-top:16px;
  color:var(--muted);
  font-size:12px;
}
</style>
</head>
<body>
  <div class="shell">
    <div class="logo">Insight Atlas</div>
    <p class="sub">Clinical intelligence workspace with live analysis, clusters, session planning, outcome review, and resources.</p>
    <form method="post">
      <label>Select client</label>
      <select name="client" required>
        <option value="">Choose a client</option>
        {% for c in clients %}
        <option value="{{c}}">{{c}}</option>
        {% endfor %}
      </select>
      <button type="submit">Analyze Client</button>
    </form>
    <div class="footer">Streaming output enabled</div>
  </div>
</body>
</html>
"""

JOB = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Insight Atlas</title>
<style>
:root{
  --bg:#f5f7fb;
  --sidebar:#172033;
  --sidebar-2:#0f172a;
  --card:#ffffff;
  --text:#0f172a;
  --muted:#64748b;
  --line:#e2e8f0;
  --brand:#2563eb;
  --brand-soft:#dbeafe;
  --green:#16a34a;
  --green-soft:#dcfce7;
  --red:#dc2626;
  --red-soft:#fee2e2;
  --shadow:0 10px 30px rgba(15,23,42,.08);
  --radius:18px;
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",sans-serif;
  background:
    radial-gradient(circle at top left, #e0ecff 0%, transparent 30%),
    radial-gradient(circle at bottom right, #eef4ff 0%, transparent 35%),
    var(--bg);
  color:var(--text);
}
.app{
  display:grid;
  grid-template-columns: 290px 1fr;
  min-height:100vh;
}
.sidebar{
  background:linear-gradient(180deg, var(--sidebar), var(--sidebar-2));
  color:white;
  padding:28px 20px;
  position:sticky;
  top:0;
  height:100vh;
}
.brand{
  font-size:20px;
  font-weight:800;
  margin-bottom:22px;
  letter-spacing:-0.02em;
}
.client-card{
  background:rgba(255,255,255,.08);
  border:1px solid rgba(255,255,255,.08);
  border-radius:16px;
  padding:14px;
  margin-bottom:14px;
}
.client-label{
  font-size:12px;
  color:#cbd5e1;
  margin-bottom:6px;
  text-transform:uppercase;
  letter-spacing:.08em;
}
.client-name{
  font-size:16px;
  font-weight:700;
}
.link{
  display:inline-block;
  margin-top:8px;
  color:#bfdbfe;
  text-decoration:none;
  font-weight:600;
}
.main{
  padding:28px;
}
.topbar{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:14px;
  margin-bottom:18px;
}
.page-title{
  font-size:28px;
  font-weight:800;
  letter-spacing:-0.03em;
}
.badge{
  padding:8px 12px;
  border-radius:999px;
  background:rgba(255,255,255,.7);
  border:1px solid rgba(255,255,255,.9);
  color:var(--muted);
  font-size:12px;
  font-weight:700;
  box-shadow:var(--shadow);
}
.status-card{
  background:linear-gradient(180deg, rgba(220,252,231,.92), rgba(255,255,255,.88));
  border:1px solid #c7f0d2;
  box-shadow:var(--shadow);
  border-radius:22px;
  padding:24px;
  margin-bottom:18px;
}
.status-title{
  font-size:14px;
  color:#166534;
  font-weight:800;
  margin-bottom:10px;
  text-transform:uppercase;
  letter-spacing:.08em;
}
.status-text{
  font-size:28px;
  font-weight:800;
  margin-bottom:8px;
  letter-spacing:-0.03em;
}
.status-sub{
  color:#166534;
  opacity:.82;
  font-size:14px;
}
.progress-wrap{
  margin-top:18px;
}
.progress{
  height:12px;
  background:#dbeafe;
  border-radius:999px;
  overflow:hidden;
  box-shadow: inset 0 1px 2px rgba(0,0,0,.06);
}
.progress-bar{
  height:100%;
  width:0%;
  background:linear-gradient(90deg, #2563eb, #3b82f6, #60a5fa);
  transition:width .35s ease;
}
.tabs{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom:18px;
}
.tab{
  padding:10px 16px;
  border-radius:999px;
  background:rgba(255,255,255,.7);
  border:1px solid rgba(255,255,255,.9);
  box-shadow:var(--shadow);
  color:var(--muted);
  font-weight:700;
  cursor:pointer;
  transition:all .18s ease;
  user-select:none;
}
.tab:hover{
  transform:translateY(-1px);
}
.tab.active{
  background:linear-gradient(135deg, #2563eb, #3b82f6);
  color:white;
  border-color:transparent;
}
.panel{
  display:none;
}
.panel.active{
  display:block;
  animation:fadeUp .26s ease;
}
@keyframes fadeUp{
  from{opacity:0; transform:translateY(8px)}
  to{opacity:1; transform:translateY(0)}
}
.card{
  background:rgba(255,255,255,.84);
  backdrop-filter: blur(10px);
  border:1px solid rgba(255,255,255,.9);
  box-shadow:var(--shadow);
  border-radius:22px;
  padding:22px;
}
.card-title{
  font-size:16px;
  font-weight:800;
  margin:0 0 16px 0;
}
.meta{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom:16px;
}
.pill{
  padding:8px 12px;
  border-radius:999px;
  background:var(--brand-soft);
  color:#1d4ed8;
  font-size:12px;
  font-weight:700;
}
.content{
  font-size:16px;
  line-height:1.65;
  white-space:pre-wrap;
  min-height:120px;
}
.grid{
  display:grid;
  grid-template-columns: repeat(3, 1fr);
  gap:14px;
  margin-top:18px;
}
.metric{
  background:rgba(255,255,255,.7);
  border:1px solid var(--line);
  border-radius:18px;
  padding:16px;
}
.metric-label{
  color:var(--muted);
  font-size:13px;
  font-weight:700;
  margin-bottom:10px;
}
.metric-value{
  font-size:20px;
  font-weight:800;
}
.metric-bar{
  margin-top:12px;
  height:8px;
  background:#e5e7eb;
  border-radius:999px;
  overflow:hidden;
}
.metric-bar-fill{
  height:100%;
  width:0%;
  background:linear-gradient(90deg, #2563eb, #60a5fa);
}
.resources .resource-item{
  background:rgba(255,255,255,.76);
  border:1px solid var(--line);
  border-radius:18px;
  padding:16px;
  margin-bottom:14px;
}
.resource-top{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:10px;
  margin-bottom:8px;
}
.resource-title{
  font-weight:800;
}
.resource-type{
  color:var(--muted);
  font-size:12px;
  font-weight:700;
}
.resource-body{
  color:var(--text);
  line-height:1.6;
  white-space:pre-wrap;
}
.resource-actions{
  display:flex;
  gap:10px;
  margin-top:12px;
}
.action{
  padding:10px 14px;
  border-radius:12px;
  border:none;
  cursor:pointer;
  font-weight:700;
}
.action.good{
  background:var(--green-soft);
  color:#166534;
}
.action.bad{
  background:var(--red-soft);
  color:#991b1b;
}
.empty{
  color:var(--muted);
}
@media (max-width: 980px){
  .app{grid-template-columns:1fr}
  .sidebar{height:auto; position:relative}
  .grid{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">🧠 Insight Atlas</div>
    <div class="client-card">
      <div class="client-label">Current view</div>
      <div class="client-name">Live analysis</div>
      <a href="/" class="link">← New Analysis</a>
    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div class="page-title">Clinical Intelligence Workspace</div>
      <div class="badge">Streaming session</div>
    </div>

    <section class="status-card">
      <div class="status-title">Live Status</div>
      <div id="statusText" class="status-text">Starting…</div>
      <div id="stageText" class="status-sub">Initializing pipeline</div>
      <div class="progress-wrap">
        <div class="progress">
          <div id="bar" class="progress-bar"></div>
        </div>
      </div>
    </section>

    <div class="tabs">
      <div class="tab active" onclick="show('analysis', this)">Clinical Output</div>
      <div class="tab" onclick="show('clusters', this)">Clusters</div>
      <div class="tab" onclick="show('session', this)">Session Plan</div>
      <div class="tab" onclick="show('outcome', this)">Outcome Prediction</div>
      <div class="tab" onclick="show('resources', this)">Resources</div>
    </div>

    <section id="analysis" class="panel active">
      <div class="card">
        <h3 class="card-title">Clinical Output</h3>
        <div class="meta">
          <div id="analysisModel" class="pill" style="display:none;"></div>
          <div id="analysisConfidence" class="pill" style="display:none;"></div>
        </div>
        <div id="analysisText" class="content"></div>
        <div class="grid">
          <div class="metric">
            <div class="metric-label">Analysis Quality</div>
            <div id="analysisQualityValue" class="metric-value">—</div>
            <div class="metric-bar"><div id="analysisQualityBar" class="metric-bar-fill"></div></div>
          </div>
          <div class="metric">
            <div class="metric-label">Confidence</div>
            <div id="analysisConfidenceValue" class="metric-value">—</div>
          </div>
          <div class="metric">
            <div class="metric-label">Sessions Used</div>
            <div id="sessionsUsedValue" class="metric-value">—</div>
          </div>
        </div>
      </div>
    </section>

    <section id="clusters" class="panel">
      <div class="card">
        <h3 class="card-title">Clusters + Interventions</h3>
        <div id="clustersText" class="content"></div>
      </div>
    </section>

    <section id="session" class="panel">
      <div class="card">
        <h3 class="card-title">Session Plan</h3>
        <div id="sessionText" class="content"></div>
      </div>
    </section>

    <section id="outcome" class="panel">
      <div class="card">
        <h3 class="card-title">Outcome Prediction</h3>
        <div id="outcomeText" class="content"></div>
      </div>
    </section>

    <section id="resources" class="panel">
      <div class="card resources">
        <h3 class="card-title">Recommended Resources</h3>
        <div id="resourcesList" class="empty">Waiting for resource generation…</div>
      </div>
    </section>
  </main>
</div>

<script>
function show(id, el){
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}

function typeInto(el, text, speed=2){
  el.textContent = "";
  let i = 0;
  function step(){
    if(i < text.length){
      el.textContent += text.charAt(i);
      i += 1;
      setTimeout(step, speed);
    }
  }
  step();
}

function setMetricBar(id, value){
  const v = Math.max(0, Math.min(1, Number(value || 0)));
  document.getElementById(id).style.width = (v * 100) + "%";
}

function renderResources(text){
  const wrap = document.getElementById("resourcesList");
  if(!text || !text.trim()){
    wrap.innerHTML = '<div class="empty">No resource recommendations available.</div>';
    return;
  }

  const blocks = text.split(/\\n\\s*\\n/).filter(Boolean);
  wrap.innerHTML = blocks.map((block, idx) => {
    return `
      <div class="resource-item">
        <div class="resource-top">
          <div class="resource-title">Resource ${idx + 1}</div>
          <div class="resource-type">AI Generated</div>
        </div>
        <div class="resource-body">${escapeHtml(block)}</div>
        <div class="resource-actions">
          <button class="action good">Helpful</button>
          <button class="action bad">Not Helpful</button>
        </div>
      </div>
    `;
  }).join("");
}

function escapeHtml(str){
  return str
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

const es = new EventSource("/events/{{sid}}");

es.addEventListener("status", e => {
  const d = JSON.parse(e.data);
  document.getElementById("statusText").textContent = d.message || "Working…";
  document.getElementById("stageText").textContent = d.message || "Running";
});

es.addEventListener("progress", e => {
  const d = JSON.parse(e.data);
  document.getElementById("bar").style.width = (d.percent || 0) + "%";
  if(d.label){
    document.getElementById("stageText").textContent = d.label;
  }
});

es.addEventListener("meta", e => {
  const d = JSON.parse(e.data);
  if(d.sessions){
    document.getElementById("sessionsUsedValue").textContent = d.sessions;
  }
});

es.addEventListener("analysis", e => {
  const d = JSON.parse(e.data);
  typeInto(document.getElementById("analysisText"), d.content || "");
  if(d.model){
    const pill = document.getElementById("analysisModel");
    pill.style.display = "inline-block";
    pill.textContent = "Model: " + d.model;
  }
  if(d.confidence){
    const pill = document.getElementById("analysisConfidence");
    pill.style.display = "inline-block";
    pill.textContent = "Confidence: " + d.confidence;
    document.getElementById("analysisConfidenceValue").textContent = d.confidence;
  }
  if(d.quality !== undefined){
    document.getElementById("analysisQualityValue").textContent = Number(d.quality).toFixed(2);
    setMetricBar("analysisQualityBar", d.quality);
  }
});

es.addEventListener("clusters", e => {
  const d = JSON.parse(e.data);
  typeInto(document.getElementById("clustersText"), d.content || "");
});

es.addEventListener("session_plan", e => {
  const d = JSON.parse(e.data);
  typeInto(document.getElementById("sessionText"), d.content || "");
});

es.addEventListener("outcome", e => {
  const d = JSON.parse(e.data);
  typeInto(document.getElementById("outcomeText"), d.content || "");
});

es.addEventListener("resources", e => {
  const d = JSON.parse(e.data);
  renderResources(d.content || "");
});

es.addEventListener("done", e => {
  document.getElementById("statusText").textContent = "Complete";
  document.getElementById("stageText").textContent = "Finished successfully";
  document.getElementById("bar").style.width = "100%";
});

es.addEventListener("error", e => {
  document.getElementById("statusText").textContent = "An error occurred";
  document.getElementById("stageText").textContent = "Check the terminal for details";
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(port=5050, threaded=True)
