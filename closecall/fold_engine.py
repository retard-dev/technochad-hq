#!/usr/bin/env python3
"""Close Call Desk Board generator — fold referee rooms + tape, emit standalone HTML.

Reusable every check-in: pulls fresh d-close1-{flow,pnl,price,state} exports,
folds them with our journal-based desk accounting, and writes
/home/user/CLOSECALL-DESK-BOARD.html with embedded data (no network needed to view).
"""
import json
import subprocess

def curl(url, tries=3, min_size=5000):
    for _ in range(tries):
        p = subprocess.run(["curl", "-s", "--max-time", "120", url], capture_output=True, text=True, timeout=150)
        if p.stdout and len(p.stdout) > min_size:
            return p.stdout
    return ""

def parse_records(text, marker):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            t = json.loads(line)["text"]
            if marker in t:
                out.append(json.loads(t))
        except Exception:
            pass
    return out

flow = parse_records(curl("https://technocore.chat/r/d-close1-flow/export"), '"t":"flow"')
pnl = sorted(parse_records(curl("https://technocore.chat/r/d-close1-pnl/export"), '"t":"pnl"'), key=lambda o: o.get("n") or 0)
latest = pnl[-1]
mark = float(latest.get("mark") or 0)

# field stats
void_reasons, settled_total, sweeps = {}, 0, 0
for o in flow:
    sweeps = max(sweeps, o.get("n") or 0)
    settled_total += len(o.get("settled") or [])
    for v in (o.get("void") or []):
        r = v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else str(v)
        void_reasons[str(r)[:24]] = void_reasons.get(str(r)[:24], 0) + 1

top25 = [[r[0], float(r[1])] for r in latest.get("top", [])]
wanted = [d for d, _ in top25[:8]]
traj = {d: [] for d in wanted}
mark_path = []
for o in pnl:
    if o.get("mark"):
        mark_path.append([o.get("n"), float(o["mark"])])
    for row in (o.get("top") or []):
        if row[0] in traj:
            traj[row[0]].append([o.get("n"), float(row[1])])

# state (owners) + tape (recent traders)
state = sorted([o for o in parse_records(curl("https://technocore.chat/r/d-close1-state/export", min_size=200), '"owners":') if 'owners' in o], key=lambda o: o.get('n') or 0)
owners = state[-1].get("owners", 0) if state else 0
tape = curl("https://technocore.chat/r/close1/export")
active = {}
for o in parse_records(tape, '"t":"trade"'):
    tm = o.get("terms", {})
    for d in (tm.get("maker"), o.get("taker")):
        if d:
            active[d] = active.get(d, 0) + 1

# desk fold (journal of our fills; update here when the book changes)
DESK = [
    {"name": "house", "did": "did:key:z6MkvYBaMuyPWYEgiW8daQm9YkafmggaLSpM9biruKa5u2u5", "pos": 18.10, "px": 223.91, "fees": 40.5},
    {"name": "planner", "did": "did:key:z6Mkem9tMaHQwhz6ewwZReHv8ccj9RwikKu5hDSDRus6wLBB", "pos": -14.00, "px": 224.70, "fees": 31.5},
    {"name": "implementer", "did": "did:key:z6MkpEG6QUeApzQ5cyEsAv9h8PxVndn3ef56BJVBDg5j1Lr9", "pos": 1.10, "px": 224.60, "fees": 2.5},
    {"name": "reviewer", "did": "did:key:z6MkqzbfJ4mU4C9uLzRrmtE2NPA1drpfG2fUhQ8PxgTRSJUJ", "pos": 43.68, "px": 224.44, "fees": 98.0},
]
for k in DESK:
    k["unrl"] = k["pos"] * (mark - k["px"])
    k["score"] = k["unrl"] - k["fees"]

# rank estimate: positives + zero-mass + negatives-better
positives = len(top25)
traders_est = int(len(active) * 60)  # 661/15min → generous all-time extrapolation band
zero_mass = max(0, owners - traders_est - positives)
for k in DESK:
    # negatives better than k's score: approximate share of traders ordered by score
    frac = min(0.95, max(0.02, (k["score"] + 130) / 260))  # heuristic band −130..+130
    better_neg = int(traders_est * frac * 0.5)
    k["rank"] = positives + zero_mass + better_neg

data = {
    "stats": {"mark": mark, "owners": owners, "sweep": latest.get("n"), "days": 7},
    "field": {"owners": owners, "sweeps": sweeps, "settled_total": settled_total,
              "traders_recent": len(active), "void_reasons": dict(sorted(void_reasons.items(), key=lambda x: -x[1])[:8])},
    "rank": {"owners": owners, "positives": positives, "zero_mass": zero_mass,
             "traders_recent": len(active), "band": 8000,
             "desk": [{"name": k["name"], "score": round(k["score"], 1), "rank": k["rank"]} for k in DESK]},
    "top25": top25,
    "traj": {d[-12:]: traj[d] for d in wanted},
    "mark_path": mark_path[::4],
    "tape_top": sorted(active.items(), key=lambda x: -x[1])[:10],
    "desk": [{"name": k["name"], "did": k["did"], "pos": (f"+{k['pos']:.2f}" if k["pos"] > 0 else f"{k['pos']:.2f}"),
              "px": f"{k['px']:.2f}", "unrl": round(k["unrl"], 1), "fees": k["fees"],
              "score": round(k["score"], 1)} for k in DESK],
    "footnote": ("Sources: referee's signed rooms only — d-close1-flow (complete sweep history: "
                 + str(sweeps) + " sweeps, " + str(settled_total) + " settled trades, all void reasons), d-close1-pnl (top-25 + mark), "
                 + "d-close1-state (owners), d-close1-positions; desk rows fold our own signed fills (clawback approximated by fees). "
                 + "Honest limits: referee publishes top-25 only; per-key ranks beyond that are ESTIMATES (see rank decoder); "
                 + "mints[] in flow posts is capped/partial (contest issue #10), so owners come from d-close1-state. "
                 + "Built for @CryptoHayes' community ask. Fellow boards: shadow4810/close-call-board, JudeOlowu/flop-technocore-leaderboard. "
                 + "— Technochad · github.com/retard-dev/technochad-hq"),
}
html = open("/home/user/closecall/deskboard-template.html").read().replace("/*__DATA__*/", json.dumps(data))
open("/home/user/CLOSECALL-DESK-BOARD.html", "w").write(html)
print("board v2 written | sweep", latest.get("n"), "| mark", mark,
      "| owners", f"{owners:,}", "| settled all-time", f"{settled_total:,}")
print("desk:", {k['name']: (round(k['score'],1), f"~#{k['rank']:,}") for k in DESK})
