import requests, os, json

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MEMORY_PATH = "/Users/jonathanprocter/Desktop/resource_memory.json"

def load_memory():
    if not os.path.exists(MEMORY_PATH):
        return {}
    return json.load(open(MEMORY_PATH))

def save_memory(data):
    json.dump(data, open(MEMORY_PATH, "w"), indent=2)

def call_model(prompt):

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    data = res.json()

    if "error" in data:
        return ""

    return data["content"][0]["text"]

def recommend_resources(client_name, formulation, clusters):

    output = call_model(f"""
For each cluster:

Provide:
- book
- psychoeducation
- handout
- short explanation

{clusters}
""")

    return [{
        "title": "Clinical Resources",
        "type": "AI",
        "content": output
    }]

def register_feedback(client, resource, helpful):

    memory = load_memory()

    memory.setdefault(client, {})
    memory[client].setdefault(resource, {"up":0,"down":0})

    if helpful:
        memory[client][resource]["up"] += 1
    else:
        memory[client][resource]["down"] += 1

    save_memory(memory)

    return {"status":"saved"}
