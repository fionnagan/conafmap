#!/usr/bin/env python3
"""build_host_profiles.py — offline cross-episode profiles for recurring hosts.

The three hosts (Conan, Sona, Matt) recur across nearly every episode, so
synthesis questions ("what advice does Sona give", "recurring jokes Matt has")
are retrieval's weak spot: top-15 chunks under-sample content spread across 150+
episodes. This precomputes an aggregate profile per host by map-reducing every
chunk that mentions them, so api/ask.py can inject comprehensive host context.

Map: batch the host's chunks, Haiku extracts statements (facts/advice/stories/
themes) actually attributable to or about that host. Reduce: dedupe + synthesize
into one profile. Output: data/rag/host_profiles.json
  {Conan:{summary, facts[], advice[], stories[], recurring_themes[]}, Sona:{...}, Matt:{...}}

Auth: ANTHROPIC_API_KEY / CLAUDE / Anthropic_API from env or .env.local.
Usage: python3 scripts/build_host_profiles.py [--host Matt] [--limit N]
"""
import os
import re
import sys
import json

import anthropic

META = "data/rag/chunks_meta.json"
OUT = "data/rag/host_profiles.json"
MODEL = "claude-haiku-4-5"
HOSTS = ["Conan", "Sona", "Matt"]
BATCH = 20

MAP_PROMPT = (
    "You are extracting facts about {host} from a Conan O'Brien podcast. Below are "
    "transcript excerpts that mention {host}. Extract ONLY things genuinely about "
    "{host} (said BY {host}, or clearly true OF {host}). Ignore the fans.\n\n"
    "Return STRICT JSON: {{\"facts\":[],\"advice\":[],\"stories\":[],\"themes\":[]}}\n"
    "- facts: biographical/personal facts about {host}\n"
    "- advice: advice or opinions {host} gives\n"
    "- stories: anecdotes {host} tells\n"
    "- themes: recurring bits, jokes, or patterns for {host}\n"
    "Each item a short string. Empty arrays if nothing. JSON only, no prose.\n\n"
    "EXCERPTS:\n{excerpts}"
)

REDUCE_PROMPT = (
    "Synthesize a profile of {host} (a recurring voice on the Conan O'Brien "
    "podcast) from these extracted notes. Dedupe, merge, drop anything thin or "
    "contradictory. Return STRICT JSON: "
    "{{\"summary\":\"\",\"facts\":[],\"advice\":[],\"stories\":[],\"recurring_themes\":[]}}\n"
    "Keep each list to the strongest ~8 items. JSON only.\n\nNOTES:\n{notes}"
)


def load_env_local():
    if not os.path.exists(".env.local"):
        return
    for line in open(".env.local", encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key():
    for n in ("ANTHROPIC_API_KEY", "CLAUDE", "Anthropic_API"):
        if os.environ.get(n):
            return os.environ[n]
    return ""


def call_json(client, prompt):
    msg = client.messages.create(model=MODEL, max_tokens=1500,
                                 messages=[{"role": "user", "content": prompt}])
    txt = "".join(b.text for b in msg.content if b.type == "text").strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    try:
        return json.loads(m.group(0) if m else txt), msg.usage
    except Exception:
        return {}, msg.usage


IN, OUT_C = 0.80, 4.00


def cost(u):
    return (getattr(u, "input_tokens", 0) * IN
            + getattr(u, "output_tokens", 0) * OUT_C) / 1e6


def build_host(client, host, rows):
    pat = re.compile(r"\b" + re.escape(host) + r"\b", re.I)
    chunks = [r for r in rows if pat.search(r["text"])]
    notes = {"facts": [], "advice": [], "stories": [], "themes": []}
    total = 0.0
    for i in range(0, len(chunks), BATCH):
        excerpts = "\n\n".join(
            f'({c["episode_title"]}) {c["text"][:600]}' for c in chunks[i:i + BATCH])
        d, u = call_json(client, MAP_PROMPT.format(host=host, excerpts=excerpts))
        total += cost(u)
        for k in notes:
            notes[k].extend(d.get(k, []) or [])
        print(f"    {host}: mapped {min(i+BATCH,len(chunks))}/{len(chunks)} | ${total:.4f}")
    # reduce
    notes_str = json.dumps(notes)[:12000]
    profile, u = call_json(client, REDUCE_PROMPT.format(host=host, notes=notes_str))
    total += cost(u)
    print(f"    {host}: reduced. cost ${total:.4f}")
    return profile, total


def main():
    load_env_local()
    if not api_key():
        sys.exit("ERROR: Anthropic key not set.")
    client = anthropic.Anthropic(api_key=api_key())
    only = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else None
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0

    rows = json.load(open(META, encoding="utf-8"))["rows"]
    if limit:
        rows = rows[:limit]
    hosts = [only] if only else HOSTS
    profiles = {}
    if os.path.exists(OUT):
        profiles = json.load(open(OUT, encoding="utf-8"))
    grand = 0.0
    for host in hosts:
        print(f"  building {host}...")
        profiles[host], c = build_host(client, host, rows)
        grand += c
        json.dump(profiles, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nwrote {OUT} | total cost ${grand:.4f}")


if __name__ == "__main__":
    main()
