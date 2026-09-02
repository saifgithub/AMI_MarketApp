"""Thin Gemini client for the Room replay. Key is read from infra/alpha.env, never printed."""
import json, os, urllib.request, urllib.error, pathlib

ENV = pathlib.Path("/Volumes/Extreme Pro/AMI_MarketApp/infra/alpha.env")

def key():
    for line in ENV.read_text().splitlines():
        if line.startswith("GOOGLE_AI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no GOOGLE_AI_API_KEY in alpha.env")

def call(model, system, user, *, max_tokens=16000, thinking=True, timeout=600):
    body = {
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if thinking:
        body["generationConfig"]["thinkingConfig"] = {"includeThoughts": True}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key()},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:400]}"}
    d = json.loads(raw)
    if "error" in d:
        return {"error": f"{d['error'].get('code')}: {d['error'].get('message','')[:300]}"}
    c = d["candidates"][0]
    parts = c.get("content", {}).get("parts", []) or []
    u = d.get("usageMetadata", {})
    return {
        "thought": "\n".join(p["text"] for p in parts if p.get("thought") and "text" in p),
        "answer": "\n".join(p["text"] for p in parts if not p.get("thought") and "text" in p),
        "finish": c.get("finishReason"),
        "tok_prompt": u.get("promptTokenCount"), "tok_think": u.get("thoughtsTokenCount"),
        "tok_out": u.get("candidatesTokenCount"),
    }

if __name__ == "__main__":
    for m in ("gemini-3.1-pro-preview", "gemini-2.5-pro"):
        r = call(m, None, "FCF $8,961M TTM, buybacks $5,910M, dividend yield 1.4%, "
                          "market cap $193,390M. What fraction of FCF was returned? One line.")
        if "error" in r:
            print(f"{m:26s} ERROR {r['error'][:160]}")
        else:
            print(f"{m:26s} think={len(r['thought'])}c/{r['tok_think']}tok  "
                  f"answer={len(r['answer'])}c  finish={r['finish']}")
            print(f"    -> {r['answer'][:160]}")
