import requests, os, time
from notion_client_registry import CLIENTS
from resource_recommender import recommend_resources

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ValueError("Anthropic API key not set")

CACHE = {}

# ---------- CLEAN OUTPUT ----------
def clean(text):
    if not text:
        return ""
    return (
        text.replace("*", "")
            .replace("#", "")
            .replace("```", "")
            .strip()
    )

# ---------- MODEL CALL ----------
def call_model(prompt, max_tokens=1400):

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        timeout=60
    )

    data = res.json()

    if "error" in data:
        print("MODEL ERROR:", data)
        return ""

    try:
        return clean(data["content"][0]["text"])
    except:
        return ""

# ---------- SAFE NOTION FETCH ----------
def fetch_sessions(client_name):

    if client_name in CACHE:
        return CACHE[client_name]

    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_API_KEY')}",
        "Notion-Version": "2022-06-28"
    }

    db = CLIENTS.get(client_name)

    data = requests.post(
        f"https://api.notion.com/v1/databases/{db}/query",
        headers=headers
    ).json()

    sessions = []

    for page in data.get("results", []):
        blocks = requests.get(
            f"https://api.notion.com/v1/blocks/{page['id']}/children",
            headers=headers
        ).json()

        text = ""

        for b in blocks.get("results", []):
            try:
                btype = b.get("type")

                if not btype:
                    continue

                content = b.get(btype, {})

                if "rich_text" in content:
                    text += " ".join([
                        t.get("plain_text", "")
                        for t in content["rich_text"]
                        if isinstance(t, dict)
                    ]) + " "

            except Exception as e:
                print("Skipping block:", e)
                continue

        text = text.strip()

        # 🔥 FILTER NON-CLINICAL / EMPTY
        if len(text) > 200 and "no clinical concerns" not in text.lower():
            sessions.append(text)

    CACHE[client_name] = sessions
    return sessions

# ---------- MAIN PIPELINE ----------
def run_client_pipeline_stream(client_name, write_back=False, emit=None):

    def send(event, data):
        if emit:
            emit(event, data)

    send("status", {"message": "Loading sessions..."})

    sessions = fetch_sessions(client_name)

    if not sessions:
        send("error", {"message": "No usable clinical data"})
        return

    combined = "\n\n".join(sessions[-5:])

    # ---------- FORMULATION ----------
    send("status", {"message": "Building formulation..."})

    formulation = call_model(f"""
You are a senior clinical psychologist.

Return plain text only.

FORMULATION:
Explain underlying mechanisms and dynamics.

CORE PATTERNS:
Identify repeated behavioral/emotional loops.

CLINICAL THEMES:
Attachment, identity, avoidance, regulation.

INTERVENTIONS:
Mechanism-targeted, specific.

Ignore scheduling, cancellations, and admin data.

{combined}
""")

    send("analysis", {"content": formulation})

    # ---------- CLUSTERS ----------
    send("status", {"message": "Building clusters..."})

    clusters = call_model(f"""
Identify meaningful psychological clusters.

Each cluster must include:
Name:
Weight (0–1):
Mechanism:
Interventions:

Rules:
- Only psychological patterns
- Ignore admin or missing data

{combined}
""")

    send("clusters", {"content": clusters})

    # ---------- SESSION PLAN ----------
    send("status", {"message": "Generating session plan..."})

    session_plan = call_model(f"""
Create a next-session plan.

Return plain text.

SESSION PLAN

Primary Focus:
Secondary Targets:

Structure:
Opening:
Middle:
Closing:

Interventions:
(list)

Therapist Stance:

Homework:

DATA:
{clusters}
{formulation}
""", 1200)

    send("session_plan", {"content": session_plan})

    # ---------- OUTCOME ----------
    send("status", {"message": "Outcome prediction..."})

    outcome = call_model(f"""
Provide outcome prediction.

Improvement probability (0–1):
Stagnation risk (0–1):
Deterioration risk (0–1):

Drivers:
Barriers:
Interpretation:

{formulation}
""", 800)

    send("outcome", {"content": outcome})

    # ---------- RESOURCES ----------
    send("status", {"message": "Generating resources..."})

    resources = recommend_resources(client_name, formulation, clusters)

    send("resources", {"content": resources[0]["content"]})

    send("done", {"message": "Complete"})
