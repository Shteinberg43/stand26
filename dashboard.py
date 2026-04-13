"""Interactive dashboard: load pseudocode, run through interpreter, view charts.

Users enter pseudocode for one or two algorithms, configure experiment
parameters and click "Run".  Press "+" to add a second algorithm for
comparison.  The interpreter (demo/) executes the code, publishing
StepEvents via EventBus; EventCollector + StatsCollector produce the
metrics displayed on dashboard tabs.

Usage:
    cd stand26-visualization
    python dashboard.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, List, Tuple

sys.setrecursionlimit(10000)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# --- src: generators ---
from src.generators import get_generator, list_generators
from src.generators.interfaces import ListInserter

# --- src: visualization ---
from src.event_bus import EventBus
from src.event_collector import EventCollector
from src.stats_collector import StatsCollector, RunResult
from src.counter_tracker import CounterTracker

# --- src: interpreter ---
from src.demo.models.generated_grammar import GRAMMAR
from src.demo.interpretators.generated_interpretator import GeneratedInterpretator
from src.demo.visitor.evalregistry import EvalContext
from src.demo.semantic_handlers.ebnfgrammar import register_evaluators


# =======================================================================
# INIT INTERPRETER
# =======================================================================

def _init_interpreter():
    if GRAMMAR._syntax_info:
        return
    for rg in GRAMMAR.graphs_rule:
        name, node = rg.to_tn_rule()
        GRAMMAR._syntax_info[name] = node
    register_evaluators()

_init_interpreter()


# =======================================================================
# PRESET PSEUDOCODE
# =======================================================================

ALGO_BUBBLE_SORT = """
ALGORITHM bubble_sort()
  n = len(arr)
  FOR i FROM 0 TO n - 2 DO
    FOR j FROM 0 TO n - i - 2 DO
      IF arr[j] > arr[j + 1] THEN
        temp = arr[j]
        arr[j] = arr[j + 1]
        arr[j + 1] = temp
      ENDIF
    ENDFOR
  ENDFOR
END
EXPERIMENT exp
END
""".strip()

ALGO_QUICKSORT = """
FUNC partition(a: list of int, lo: int, hi: int) : int
  pivot = a[hi]
  i = lo - 1
  FOR j FROM lo TO hi - 1 DO
    IF a[j] <= pivot THEN
      i = i + 1
      tmp = a[i]
      a[i] = a[j]
      a[j] = tmp
    ENDIF
  ENDFOR
  tmp = a[i + 1]
  a[i + 1] = a[hi]
  a[hi] = tmp
  RETURN i + 1
END

ALGORITHM quicksort(a: list of int, lo: int, hi: int)
  IF lo < hi THEN
    p = partition(a, lo, hi)
    quicksort(a, lo, p - 1)
    quicksort(a, p + 1, hi)
  ENDIF
END

EXPERIMENT exp
END
""".strip()

PRESETS: Dict[str, str] = {
    "bubble_sort": ALGO_BUBBLE_SORT,
    "quicksort": ALGO_QUICKSORT,
}


# =======================================================================
# PARSING
# =======================================================================

def _parse_source(source: str):
    """Parse pseudocode source text to AST."""
    return GeneratedInterpretator.run_syntax_analyzer(source)


# =======================================================================
# INPUT GENERATION
# =======================================================================

def generate_input(gen_name: str, size: int, seed: int) -> List[int]:
    gen = get_generator(gen_name)
    inserter = ListInserter()
    gen.fill(inserter, size, seed)
    return inserter.target


# =======================================================================
# SINGLE EXPERIMENT
# =======================================================================

def run_single_experiment(
    gen_name: str,
    size: int,
    seed: int,
    ast_node: Any,
    algorithm_name: str,
    max_ops: int = 500_000,
    collect_history: bool = False,
) -> dict:
    input_data = generate_input(gen_name, size, seed)

    bus = EventBus()
    tracker = CounterTracker()
    bus.subscribe(tracker.on_event)

    collector = None
    if collect_history:
        collector = EventCollector(counter_provider=tracker.snapshot)
        bus.subscribe(collector.on_event)

    ctx = EvalContext()
    ctx.event_bus = bus
    arr_copy = list(input_data)
    ctx.symbol_table["arr"] = arr_copy
    ctx.symbol_table["a"] = arr_copy
    ctx.symbol_table["lo"] = 0
    ctx.symbol_table["hi"] = len(arr_copy) - 1

    head = ast_node

    t0 = time.monotonic()
    status = "OK"
    error_msg = None

    try:
        head.evaluated(ctx)
    except Exception as exc:
        status = "ERROR"
        error_msg = str(exc)

    elapsed = time.monotonic() - t0

    counters = tracker.snapshot()
    if counters.get("total_ops", 0) > max_ops and status == "OK":
        status = "LIMIT"
        error_msg = f"total_ops={counters['total_ops']} > {max_ops}"

    out_arr = ctx.symbol_table.get("arr", arr_copy)
    sorted_ok = list(out_arr) == sorted(input_data) if status == "OK" else None

    return {
        "run_id": f"{algorithm_name}_{gen_name}_n{size}_s{seed}",
        "algorithm": algorithm_name,
        "generator_name": gen_name,
        "input_size": size,
        "seed": seed,
        "status": status,
        "error_message": error_msg,
        "sorted_correctly": sorted_ok,
        "counters": counters,
        "elapsed_sec": elapsed,
        "history": collector.history if collector else [],
        "input_sample": input_data[:20],
        "output_sample": list(out_arr)[:20],
    }


# =======================================================================
# DYNAMIC EXPERIMENT RUNNER  (1 or 2 algorithms)
# =======================================================================

def run_dynamic_experiments(
    algos: List[Tuple[str, str]],
    sizes: List[int],
    trials: int = 3,
) -> dict:
    """Parse 1..N algorithms and run all experiments.

    algos: list of (name, source_code) tuples.
    """

    algo_nodes: Dict[str, Any] = {}
    algo_names: List[str] = []
    for name, code in algos:
        print(f"  Parsing {name} ...", end=" ", flush=True)
        algo_nodes[name] = _parse_source(code)
        algo_names.append(name)
        print("OK")

    generators = list_generators()

    stats_by_algo: Dict[str, StatsCollector] = {a: StatsCollector() for a in algo_names}
    all_runs: List[dict] = []
    timeline_run = None

    total = len(algo_names) * len(generators) * len(sizes) * trials
    done = 0

    for algo_name in algo_names:
        ast_node = algo_nodes[algo_name]
        for gen_name in generators:
            for size in sizes:
                for trial in range(trials):
                    done += 1
                    if done % 10 == 0 or done == total or done == 1:
                        print(f"  [{done}/{total}] {algo_name} {gen_name} N={size} t={trial}")

                    need_history = (
                        algo_name == algo_names[0]
                        and gen_name == "random"
                        and size == sizes[-1]
                        and trial == 0
                    )
                    result = run_single_experiment(
                        gen_name, size, trial, ast_node, algo_name,
                        collect_history=need_history,
                    )
                    all_runs.append(result)

                    run_result = RunResult(
                        run_id=result["run_id"],
                        input_size=size,
                        generator_name=gen_name,
                        counters=result["counters"],
                        status=result["status"],
                        elapsed_sec=result["elapsed_sec"],
                    )
                    stats_by_algo[algo_name].add_run(run_result)

                    if need_history:
                        timeline_run = result

    # ---- build per-algorithm stats ----
    summaries: Dict[str, dict] = {}
    by_size: Dict[str, dict] = {}
    by_gen: Dict[str, dict] = {}

    for aname in algo_names:
        s = stats_by_algo[aname].summary()
        summaries[aname] = {k: v.as_dict() for k, v in s.items()}
        bs = stats_by_algo[aname].summary_by_size()
        by_size[aname] = {
            str(sz): {k: v.as_dict() for k, v in c.items()}
            for sz, c in bs.items()
        }
        bg = stats_by_algo[aname].summary_by_generator()
        by_gen[aname] = {
            g: {k: v.as_dict() for k, v in c.items()}
            for g, c in bg.items()
        }

    timeline = []
    if timeline_run:
        for step in timeline_run["history"]:
            timeline.append({
                "step": step.step_index,
                "op": step.op,
                "counters": step.counters,
                "timestamp": step.timestamp,
            })

    first_summary = stats_by_algo[algo_names[0]].summary()
    counter_names = sorted(first_summary.keys()) if first_summary else []

    return {
        "runs": [{
            "run_id": r["run_id"],
            "algorithm": r["algorithm"],
            "generator_name": r["generator_name"],
            "input_size": r["input_size"],
            "status": r["status"],
            "counters": r["counters"],
            "elapsed_sec": r["elapsed_sec"],
            "sorted_correctly": r["sorted_correctly"],
        } for r in all_runs],
        "summaries": summaries,
        "by_size": by_size,
        "by_gen": by_gen,
        "timeline": timeline,
        "timeline_info": {
            "algorithm": timeline_run["algorithm"] if timeline_run else "",
            "generator": timeline_run["generator_name"] if timeline_run else "",
            "size": timeline_run["input_size"] if timeline_run else 0,
            "input_sample": timeline_run["input_sample"] if timeline_run else [],
            "output_sample": timeline_run["output_sample"] if timeline_run else [],
            "total_steps": len(timeline),
        },
        "generators": generators,
        "sizes": sizes,
        "counter_names": counter_names,
        "algorithms": algo_names,
        "total_runs": len(all_runs),
        "ok_runs": sum(1 for r in all_runs if r["status"] == "OK"),
    }


# =======================================================================
# HTML DASHBOARD
# =======================================================================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interactive Pseudocode Dashboard</title>
<style>
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-card: #1e293b;
  --bg-card-hover: #334155;
  --border: #334155;
  --text: #e2e8f0;
  --text2: #94a3b8;
  --text3: #64748b;
  --blue: #3b82f6;
  --green: #22c55e;
  --orange: #f59e0b;
  --red: #ef4444;
  --purple: #a855f7;
  --cyan: #06b6d4;
  --pink: #ec4899;
  --shadow: 0 4px 6px -1px rgba(0,0,0,0.4);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',-apple-system,sans-serif; background:var(--bg-primary); color:var(--text); }

.topbar { background:linear-gradient(90deg,#1e293b,#0f172a); border-bottom:1px solid var(--border); padding:14px 24px; display:flex; align-items:center; justify-content:space-between; }
.topbar h1 { font-size:18px; display:flex; align-items:center; gap:10px; }
.topbar .logo { width:30px; height:30px; background:linear-gradient(135deg,var(--blue),var(--cyan)); border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:bold; }
.topbar-info { display:flex; gap:16px; font-size:12px; color:var(--text2); }
.topbar-info .val { color:var(--green); font-weight:600; }

.tabs { background:var(--bg-secondary); border-bottom:1px solid var(--border); display:flex; padding:0 24px; overflow-x:auto; }
.tab { padding:10px 18px; cursor:pointer; font-size:13px; color:var(--text2); border-bottom:2px solid transparent; transition:all .2s; user-select:none; white-space:nowrap; }
.tab:hover { color:var(--text); }
.tab.active { color:var(--cyan); border-bottom-color:var(--cyan); }

.page { padding:20px 24px; max-width:1600px; margin:0 auto; }
.tab-content { display:none; }
.tab-content.active { display:block; }

.grid1 { display:grid; grid-template-columns:1fr; gap:16px; margin-bottom:20px; }
.grid2 { display:grid; grid-template-columns:repeat(2,1fr); gap:16px; margin-bottom:20px; }
.grid3 { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:20px; }
.metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }

.card { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; }
.card:hover { border-color:var(--blue); }
.card-head { padding:12px 16px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
.card-title { font-size:13px; font-weight:600; }
.card-sub { font-size:10px; color:var(--text3); }
.card-body { padding:16px; position:relative; }
.card-body canvas { width:100%!important; height:300px!important; }

.mc { background:var(--bg-card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
.mc:hover { border-color:var(--cyan); }
.mc-label { font-size:10px; color:var(--text3); text-transform:uppercase; letter-spacing:.5px; margin-bottom:4px; }
.mc-val { font-size:24px; font-weight:700; line-height:1.1; }
.mc-sub { font-size:10px; color:var(--text2); margin-top:3px; }

.controls { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:center; }
.ctrl-label { font-size:12px; color:var(--text2); }
select,button { background:var(--bg-card); border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:6px; font-size:12px; cursor:pointer; }
button:hover { background:var(--bg-card-hover); }
button.primary { background:var(--cyan); border-color:var(--cyan); color:#000; font-weight:600; }
button.primary:hover { background:#0ea5e9; }
button.danger { background:transparent; border-color:var(--red); color:var(--red); }
button.danger:hover { background:var(--red); color:#fff; }

input[type="text"],input[type="number"] { background:var(--bg-card); border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:6px; font-size:12px; }

table { width:100%; border-collapse:collapse; font-size:12px; }
th { background:var(--bg-primary); border:1px solid var(--border); padding:7px 10px; text-align:left; font-weight:600; color:var(--text3); text-transform:uppercase; font-size:10px; letter-spacing:.5px; position:sticky; top:0; }
td { border:1px solid var(--border); padding:5px 10px; }
tr:hover td { background:var(--bg-card-hover); }
.tbl-wrap { max-height:420px; overflow-y:auto; }

.badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:600; }
.b-ok { background:rgba(34,197,94,.15); color:var(--green); }
.b-err { background:rgba(239,68,68,.15); color:var(--red); }
.b-lim { background:rgba(245,158,11,.15); color:var(--orange); }

.tl-bar { display:inline-block; width:3px; margin:0 .5px; border-radius:1px; cursor:pointer; vertical-align:bottom; transition:opacity .1s; }
.tl-bar:hover { opacity:.7; }
.legend { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; }
.legend-i { display:flex; align-items:center; gap:4px; font-size:11px; color:var(--text2); }
.legend-c { width:10px; height:10px; border-radius:2px; }
.tooltip { position:fixed; background:var(--bg-secondary); border:1px solid var(--border); border-radius:6px; padding:8px 12px; font-size:11px; pointer-events:none; z-index:200; display:none; box-shadow:var(--shadow); }

.algo-toggle { display:flex; border:1px solid var(--border); border-radius:6px; overflow:hidden; min-height:30px; }
.algo-btn { padding:6px 16px; font-size:12px; cursor:pointer; background:var(--bg-card); color:var(--text2); border:none; }
.algo-btn.active { background:var(--cyan); color:#000; font-weight:600; }

.editor-ta { width:100%; height:360px; background:var(--bg-primary); border:1px solid var(--border); color:var(--cyan); padding:10px; border-radius:6px; font-family:'Consolas','Courier New',monospace; font-size:12px; line-height:1.5; resize:vertical; tab-size:2; }
.editor-name { width:100%; margin-bottom:6px; background:var(--bg-primary); border:1px solid var(--border); color:var(--text); padding:6px 10px; border-radius:4px; font-size:13px; }

.empty-state { text-align:center; padding:80px 20px; color:var(--text3); }
.empty-state h2 { font-size:22px; margin-bottom:10px; color:var(--text2); }
.empty-state p { font-size:14px; }

#add-algo-card { display:flex; align-items:center; justify-content:center; min-height:200px; cursor:pointer; border-style:dashed; }
#add-algo-card:hover { border-color:var(--cyan); background:rgba(6,182,212,.04); }
.add-label { font-size:36px; color:var(--text3); line-height:1; }
.add-sub { font-size:12px; color:var(--text3); margin-top:6px; }

@media(max-width:900px) { .grid2,.grid3 { grid-template-columns:1fr; } .metrics { grid-template-columns:repeat(2,1fr); } }
</style>
</head>
<body>

<div class="topbar">
  <h1><span class="logo">P</span> Interactive Pseudocode Dashboard</h1>
  <div class="topbar-info">
    <span>Runs: <span class="val" id="hdr-runs">—</span></span>
    <span>OK: <span class="val" id="hdr-ok">—</span></span>
    <span>Generators: <span class="val" id="hdr-gens">—</span></span>
    <span>Sizes: <span class="val" id="hdr-sizes">—</span></span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="editor">&#9998; Editor</div>
  <div class="tab" data-tab="overview">Overview</div>
  <div class="tab" data-tab="complexity">Complexity</div>
  <div class="tab" data-tab="timeline">Timeline</div>
  <div class="tab" data-tab="compare" id="tab-compare-btn" style="display:none">Compare</div>
  <div class="tab" data-tab="data">Raw Data</div>
</div>

<div class="page">

<!-- ======================= EDITOR ======================= -->
<div class="tab-content active" id="tab-editor">
  <div id="editors-grid" class="grid1" style="margin-bottom:14px">
    <!-- Algorithm A — always present -->
    <div class="card" id="editor-card-a">
      <div class="card-head">
        <div><div class="card-title">Algorithm</div></div>
        <div>
          <select id="preset-a" style="font-size:11px">
            <option value="">— Load preset —</option>
            <option value="bubble_sort" selected>BubbleSort</option>
            <option value="quicksort">QuickSort</option>
          </select>
        </div>
      </div>
      <div class="card-body" style="padding:10px">
        <input type="text" id="name-a" class="editor-name" value="bubble_sort" placeholder="Algorithm name">
        <textarea id="code-a" class="editor-ta" spellcheck="false"></textarea>
      </div>
    </div>
    <!-- Placeholder: + button to add second algorithm -->
    <div class="card" id="add-algo-card">
      <div style="text-align:center">
        <div class="add-label">+</div>
        <div class="add-sub">Add second algorithm for comparison</div>
      </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:14px">
    <div class="card-body" style="padding:12px 16px">
      <div class="controls" style="margin-bottom:0">
        <span class="ctrl-label">Sizes:</span>
        <input type="text" id="cfg-sizes" value="5,10,20,50" style="width:140px">
        <span class="ctrl-label">Trials:</span>
        <input type="number" id="cfg-trials" value="3" min="1" max="20" style="width:60px">
        <button class="primary" id="btn-run" style="padding:8px 28px;font-size:13px">&#9654; Run Experiments</button>
        <span id="run-status" style="font-size:12px;margin-left:8px"></span>
      </div>
    </div>
  </div>

  <div style="font-size:12px;color:var(--text3);line-height:1.7;padding:0 4px">
    <b>Pseudocode conventions:</b>
    Use <code style="color:var(--cyan)">arr</code> for the input array.
    Variables <code style="color:var(--cyan)">a</code>,
    <code style="color:var(--cyan)">lo</code>,
    <code style="color:var(--cyan)">hi</code> are also pre-set (alias for partition-style algorithms).
    Each source must contain
    <code style="color:var(--cyan)">ALGORITHM name(...) ... END</code> and
    <code style="color:var(--cyan)">EXPERIMENT exp END</code>.
  </div>
</div>

<!-- ======================= OVERVIEW ======================= -->
<div class="tab-content" id="tab-overview">
  <div id="ov-empty" class="empty-state"><h2>No data yet</h2><p>Go to the Editor tab, enter pseudocode and click Run.</p></div>
  <div id="ov-content" style="display:none">
    <div class="controls">
      <div class="algo-toggle" id="ov-algo-toggle"></div>
    </div>
    <div class="metrics" id="ov-metrics"></div>
    <div class="grid2">
      <div class="card"><div class="card-head"><div><div class="card-title">Operations by generator</div><div class="card-sub">total_ops (mean)</div></div></div><div class="card-body"><canvas id="ch-gen-bars"></canvas></div></div>
      <div class="card"><div class="card-head"><div><div class="card-title">Operation distribution</div><div class="card-sub">mean ratios</div></div></div><div class="card-body"><canvas id="ch-pie"></canvas></div></div>
    </div>
    <div class="grid1"><div class="card"><div class="card-head"><div><div class="card-title">Summary table</div></div></div><div class="card-body"><div class="tbl-wrap" id="ov-tbl"></div></div></div></div>
  </div>
</div>

<!-- ======================= COMPLEXITY ======================= -->
<div class="tab-content" id="tab-complexity">
  <div id="cx-empty" class="empty-state"><h2>No data yet</h2><p>Run experiments first.</p></div>
  <div id="cx-content" style="display:none">
    <div class="controls">
      <div class="algo-toggle" id="cx-algo-toggle"></div>
      <span class="ctrl-label">Counter:</span><select id="cx-counter"></select>
      <span class="ctrl-label">Y scale:</span>
      <select id="cx-scale"><option value="linear">Linear</option><option value="log">Log</option></select>
    </div>
    <div class="grid1"><div class="card"><div class="card-head"><div><div class="card-title">Complexity curves by generator</div><div class="card-sub">mean by N</div></div></div><div class="card-body"><canvas id="ch-curves" style="height:400px!important"></canvas></div></div></div>
    <div class="grid2">
      <div class="card"><div class="card-head"><div><div class="card-title">Boxplot by size</div></div></div><div class="card-body"><canvas id="ch-box"></canvas></div></div>
      <div class="card"><div class="card-head"><div><div class="card-title">Coefficient of variation (CV)</div><div class="card-sub">std/mean by size</div></div></div><div class="card-body"><canvas id="ch-cv"></canvas></div></div>
    </div>
  </div>
</div>

<!-- ======================= TIMELINE ======================= -->
<div class="tab-content" id="tab-timeline">
  <div id="tl-empty" class="empty-state"><h2>No data yet</h2><p>Run experiments first.</p></div>
  <div id="tl-content" style="display:none">
    <div class="controls">
      <span class="ctrl-label">Speed (ms):</span>
      <select id="tl-speed"><option value="5">5</option><option value="15" selected>15</option><option value="30">30</option><option value="50">50</option><option value="100">100</option></select>
      <button class="primary" id="btn-play">&#9654; Play</button>
      <button id="btn-pause">&#10074;&#10074;</button>
      <button id="btn-reset">&#8634; Reset</button>
      <span id="tl-info" style="font-size:12px;color:var(--text2);margin-left:8px">Step 0 / 0</span>
    </div>
    <div id="tl-meta" style="font-size:12px;color:var(--text2);margin-bottom:12px"></div>
    <div class="grid1"><div class="card"><div class="card-head"><div><div class="card-title">Live counters</div><div class="card-sub">step-by-step (pseudocode -> interpreter -> EventBus)</div></div></div><div class="card-body"><canvas id="ch-live" style="height:350px!important"></canvas></div></div></div>
    <div class="grid1"><div class="card"><div class="card-head"><div><div class="card-title">Operations timeline</div></div></div><div class="card-body"><div id="tl-bars" style="overflow-x:auto;padding:8px 0"></div><div class="legend" id="tl-legend"></div></div></div></div>
  </div>
</div>

<!-- ======================= COMPARE ======================= -->
<div class="tab-content" id="tab-compare">
  <div id="cmp-empty" class="empty-state"><h2>No data yet</h2><p>Run experiments with two algorithms first.</p></div>
  <div id="cmp-content" style="display:none">
    <div class="controls">
      <span class="ctrl-label">Counter:</span><select id="cmp-counter"></select>
      <span class="ctrl-label">Generator:</span><select id="cmp-gen"></select>
    </div>
    <div class="grid1"><div class="card"><div class="card-head"><div><div class="card-title" id="cmp-title">A vs B</div></div></div><div class="card-body"><canvas id="ch-vs" style="height:380px!important"></canvas></div></div></div>
    <div class="grid2">
      <div class="card"><div class="card-head"><div><div class="card-title" id="cmp-radar-title">Radar comparison</div><div class="card-sub">normalized metrics</div></div></div><div class="card-body"><canvas id="ch-radar"></canvas></div></div>
      <div class="card"><div class="card-head"><div><div class="card-title">Stacked: operation contributions by N</div></div></div><div class="card-body"><canvas id="ch-stacked"></canvas></div></div>
    </div>
  </div>
</div>

<!-- ======================= RAW DATA ======================= -->
<div class="tab-content" id="tab-data">
  <div id="dt-empty" class="empty-state"><h2>No data yet</h2><p>Run experiments first.</p></div>
  <div id="dt-content" style="display:none">
    <div class="controls">
      <span class="ctrl-label">Algorithm:</span><select id="df-algo"><option value="all">All</option></select>
      <span class="ctrl-label">Generator:</span><select id="df-gen"><option value="all">All</option></select>
      <span class="ctrl-label">Size:</span><select id="df-size"><option value="all">All</option></select>
      <button id="btn-csv">&#x2193; CSV</button>
    </div>
    <div class="card"><div class="card-body"><div class="tbl-wrap" id="raw-tbl" style="max-height:600px"></div></div></div>
  </div>
</div>

</div>
<div class="tooltip" id="tip"></div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script>
/* ============================================================
   STATE
   ============================================================ */
let D = null;
const PRESETS = __PRESETS__;
let hasTwoAlgos = false;   // whether second editor panel is visible

/* ============================================================
   EDITOR MANAGEMENT
   ============================================================ */
document.getElementById('code-a').value = PRESETS['bubble_sort'] || '';
document.getElementById('preset-a').addEventListener('change', function(){
  if(PRESETS[this.value]){document.getElementById('code-a').value=PRESETS[this.value];document.getElementById('name-a').value=this.value;}
});

/* create second editor card (hidden initially) */
function buildEditorB(){
  const card=document.createElement('div');
  card.className='card'; card.id='editor-card-b';
  card.innerHTML=`
    <div class="card-head">
      <div><div class="card-title">Algorithm B</div></div>
      <div style="display:flex;gap:6px;align-items:center">
        <select id="preset-b" style="font-size:11px">
          <option value="">— Load preset —</option>
          <option value="bubble_sort">BubbleSort</option>
          <option value="quicksort" selected>QuickSort</option>
        </select>
        <button class="danger" id="btn-remove-b" title="Remove" style="padding:3px 8px;font-size:14px;line-height:1">&times;</button>
      </div>
    </div>
    <div class="card-body" style="padding:10px">
      <input type="text" id="name-b" class="editor-name" value="quicksort" placeholder="Algorithm name">
      <textarea id="code-b" class="editor-ta" spellcheck="false"></textarea>
    </div>`;
  return card;
}

function addAlgoB(){
  if(hasTwoAlgos) return;
  hasTwoAlgos=true;
  const grid=document.getElementById('editors-grid');
  grid.className='grid2';
  document.getElementById('editor-card-a').querySelector('.card-title').textContent='Algorithm A';
  const addCard=document.getElementById('add-algo-card');
  addCard.style.display='none';
  const card=buildEditorB();
  grid.insertBefore(card, addCard);
  document.getElementById('code-b').value=PRESETS['quicksort']||'';
  document.getElementById('preset-b').addEventListener('change', function(){
    if(PRESETS[this.value]){document.getElementById('code-b').value=PRESETS[this.value];document.getElementById('name-b').value=this.value;}
  });
  document.getElementById('btn-remove-b').addEventListener('click', removeAlgoB);
}

function removeAlgoB(){
  if(!hasTwoAlgos) return;
  hasTwoAlgos=false;
  const card=document.getElementById('editor-card-b');
  if(card) card.remove();
  document.getElementById('editors-grid').className='grid1';
  document.getElementById('editor-card-a').querySelector('.card-title').textContent='Algorithm';
  document.getElementById('add-algo-card').style.display='';
}

document.getElementById('add-algo-card').addEventListener('click', addAlgoB);

/* ============================================================
   COLORS
   ============================================================ */
const OC={comparisons:'#3b82f6',reads:'#06b6d4',writes:'#a855f7',assignments:'#22c55e',branches:'#f59e0b',calls:'#ec4899',returns:'#ef4444',allocations:'#9333ea',total_ops:'#94a3b8'};
const GC={random:'#3b82f6',sorted:'#22c55e',reverse:'#ef4444',nearly_sorted:'#f59e0b',duplicates:'#a855f7'};
const TC={CMP:'#3b82f6',READ:'#06b6d4',WRITE:'#a855f7',ASSIGN:'#22c55e',BRANCH:'#f59e0b',CALL:'#ec4899',RETURN:'#ef4444',ALLOC:'#9333ea',MATH:'#64748b'};

/* ============================================================
   TABS
   ============================================================ */
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(x=>x.classList.remove('active'));
  t.classList.add('active'); document.getElementById('tab-'+t.dataset.tab).classList.add('active');
}));

/* ============================================================
   HELPERS
   ============================================================ */
function fmt(n,d=1){if(n>=1e6)return(n/1e6).toFixed(d)+'M';if(n>=1e3)return(n/1e3).toFixed(d)+'K';return typeof n==='number'?n.toFixed(d):n;}
let CI={};
function mc(id,cfg){if(CI[id])CI[id].destroy();CI[id]=new Chart(document.getElementById(id),cfg);return CI[id];}
function dopt(){return{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#94a3b8',font:{size:11}}}},scales:{x:{ticks:{color:'#64748b',font:{size:10}},grid:{color:'rgba(51,65,85,0.4)'}},y:{ticks:{color:'#64748b',font:{size:10}},grid:{color:'rgba(51,65,85,0.4)'}}}};}

function setupToggle(id,cb){document.querySelectorAll('#'+id+' .algo-btn').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('#'+id+' .algo-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');cb(b.dataset.algo);}));}

let ovAlgo='',cxAlgo='';
const isMulti=()=>D&&D.algorithms.length>1;

function getSummary(algo){if(!D)return {};return D.summaries[algo]||{};}
function getBySize(algo){if(!D)return {};return D.by_size[algo]||{};}
function getByGen(algo){if(!D)return {};return D.by_gen[algo]||{};}
function getRuns(algo){if(!D)return [];return algo==='all'?D.runs:D.runs.filter(r=>r.algorithm===algo);}

/* ============================================================
   RENDER: OVERVIEW
   ============================================================ */
function renderOverview(){
  if(!D)return;
  const s=getSummary(ovAlgo);
  const keys=D.counter_names;
  const ac=['var(--blue)','var(--cyan)','var(--purple)','var(--green)','var(--orange)','var(--pink)','var(--red)','var(--text2)','#9333ea'];
  document.getElementById('ov-metrics').innerHTML=keys.map((k,i)=>{const c=s[k];if(!c)return'';return`<div class="mc"><div class="mc-label">${k.replace(/_/g,' ')}</div><div class="mc-val" style="color:${ac[i%ac.length]}">${fmt(c.mean)}</div><div class="mc-sub">std=${fmt(c.stddev)} med=${fmt(c.median)}</div></div>`;}).join('');

  const bg=getByGen(ovAlgo),gens=D.generators;
  mc('ch-gen-bars',{type:'bar',data:{labels:gens,datasets:[{label:'total_ops',data:gens.map(g=>bg[g]&&bg[g].total_ops?bg[g].total_ops.mean:0),backgroundColor:gens.map(g=>GC[g]||'#666')}]},options:dopt()});

  const opk=keys.filter(k=>k!=='total_ops');
  mc('ch-pie',{type:'doughnut',data:{labels:opk.map(k=>k.replace(/_/g,' ')),datasets:[{data:opk.map(k=>s[k]?s[k].mean:0),backgroundColor:opk.map(k=>OC[k]||'#666'),borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'right',labels:{color:'#94a3b8',font:{size:11},padding:10}}}}});

  let h='<table><thead><tr><th>Counter</th><th>N</th><th>Mean</th><th>Median</th><th>Std</th><th>Min</th><th>Max</th><th>Q25</th><th>Q75</th><th>IQR</th><th>CV</th></tr></thead><tbody>';
  keys.forEach(k=>{const c=s[k];if(!c)return;h+=`<tr><td style="color:${OC[k]||'#fff'}">${k}</td><td>${c.count}</td><td>${fmt(c.mean)}</td><td>${fmt(c.median)}</td><td>${fmt(c.stddev)}</td><td>${c.min}</td><td>${fmt(c.max)}</td><td>${fmt(c.q25)}</td><td>${fmt(c.q75)}</td><td>${fmt(c.iqr)}</td><td>${c.cv.toFixed(3)}</td></tr>`;});
  h+='</tbody></table>';document.getElementById('ov-tbl').innerHTML=h;
}

/* ============================================================
   RENDER: COMPLEXITY
   ============================================================ */
function renderComplexity(){
  if(!D)return;
  const sel=document.getElementById('cx-counter');
  if(!sel.options.length)D.counter_names.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;if(n==='comparisons')o.selected=true;sel.appendChild(o);});
  const counter=sel.value||D.counter_names[0]||'comparisons',scale=document.getElementById('cx-scale').value;
  const sizes=D.sizes,gens=D.generators,algo=cxAlgo;

  const ds=gens.map(g=>{
    const means=sizes.map(sz=>{const runs=getRuns(algo).filter(r=>r.generator_name===g&&r.input_size===sz&&r.status==='OK');if(!runs.length)return 0;return runs.reduce((s,r)=>s+(r.counters[counter]||0),0)/runs.length;});
    return{label:g,data:means,borderColor:GC[g]||'#666',backgroundColor:(GC[g]||'#666')+'20',tension:.3,fill:false,pointRadius:4,borderWidth:2};
  });
  mc('ch-curves',{type:'line',data:{labels:sizes.map(String),datasets:ds},options:{...dopt(),scales:{...dopt().scales,y:{...dopt().scales.y,type:scale==='log'?'logarithmic':'linear'}}}});

  const bd=sizes.map(sz=>{const vals=getRuns(algo).filter(r=>r.input_size===sz&&r.status==='OK').map(r=>r.counters[counter]||0).sort((a,b)=>a-b);if(!vals.length)return{min:0,q25:0,med:0,q75:0,max:0};const p=f=>{const k=(vals.length-1)*f,fl=Math.floor(k);return vals[fl]+(vals[Math.ceil(k)]-vals[fl])*(k-fl);};return{min:vals[0],q25:p(.25),med:p(.5),q75:p(.75),max:vals[vals.length-1]};});
  mc('ch-box',{type:'bar',data:{labels:sizes.map(String),datasets:[{label:'IQR',data:bd.map(b=>b.q75-b.q25),backgroundColor:'#3b82f640',borderColor:'#3b82f6',borderWidth:1},{label:'Median',data:bd.map(b=>b.med),type:'line',borderColor:'#f59e0b',pointRadius:5,borderWidth:2,fill:false}]},options:dopt()});

  const bs=getBySize(algo);
  mc('ch-cv',{type:'bar',data:{labels:sizes.map(String),datasets:[{label:'CV',data:sizes.map(sz=>{const b=bs[String(sz)];return b&&b[counter]?b[counter].cv:0;}),backgroundColor:'#a855f780',borderColor:'#a855f7',borderWidth:1}]},options:dopt()});
}
document.getElementById('cx-counter').addEventListener('change',renderComplexity);
document.getElementById('cx-scale').addEventListener('change',renderComplexity);

/* ============================================================
   RENDER: TIMELINE
   ============================================================ */
let tlAnim=null,tlStep=0,tlPlay=false;

function renderTimeline(){
  if(!D||!D.timeline||!D.timeline.length)return;
  const tl=D.timeline,total=tl.length;
  const info=D.timeline_info;
  document.getElementById('tl-meta').innerHTML=`<b>${info.algorithm}</b> | gen: <b>${info.generator}</b> | N=<b>${info.size}</b> | steps: <b>${info.total_steps}</b> | in: [${(info.input_sample||[]).join(', ')}...] -> [${(info.output_sample||[]).join(', ')}...]`;
  document.getElementById('tl-info').textContent=`Step 0 / ${total}`;

  document.getElementById('tl-legend').innerHTML=Object.entries(TC).map(([op,c])=>`<div class="legend-i"><div class="legend-c" style="background:${c}"></div>${op}</div>`).join('');

  document.getElementById('tl-bars').innerHTML=tl.map((s,i)=>`<div class="tl-bar" data-i="${i}" style="height:24px;background:${TC[s.op]||'#666'};opacity:.15"></div>`).join('');

  const tip=document.getElementById('tip');
  document.querySelectorAll('#tl-bars .tl-bar').forEach(b=>{
    b.addEventListener('mouseenter',e=>{const s=tl[b.dataset.i];tip.innerHTML=`<b>Step ${b.dataset.i}</b> | ${s.op}<br>${Object.entries(s.counters).map(([k,v])=>`${k}: ${v}`).join('<br>')}`;tip.style.display='block';tip.style.left=e.clientX+12+'px';tip.style.top=e.clientY-10+'px';});
    b.addEventListener('mouseleave',()=>tip.style.display='none');
  });

  const _ks=new Set();tl.forEach(s=>Object.keys(s.counters||{}).forEach(k=>_ks.add(k)));const cnames=[..._ks].filter(k=>k!=='total_ops').sort();
  mc('ch-live',{type:'line',data:{labels:[],datasets:cnames.map(n=>({label:n,data:[],borderColor:OC[n]||'#666',borderWidth:2,tension:.2,fill:false,pointRadius:0}))},options:{...dopt(),animation:{duration:0}}});
}

function playTL(){
  if(!D||tlPlay)return;tlPlay=true;
  const tl=D.timeline,spd=parseInt(document.getElementById('tl-speed').value),ch=CI['ch-live'],bars=document.querySelectorAll('#tl-bars .tl-bar');
  const _ks2=new Set();tl.forEach(s=>Object.keys(s.counters||{}).forEach(k=>_ks2.add(k)));const cn=[..._ks2].filter(k=>k!=='total_ops').sort();
  function step(){
    if(!tlPlay||tlStep>=tl.length){tlPlay=false;return;}
    const s=tl[tlStep];
    if(bars[tlStep])bars[tlStep].style.opacity='1';
    ch.data.labels.push(tlStep);
    cn.forEach((n,di)=>ch.data.datasets[di].data.push(s.counters[n]||0));
    ch.update();
    document.getElementById('tl-info').textContent=`Step ${tlStep+1} / ${tl.length}`;
    tlStep++;tlAnim=setTimeout(step,spd);
  }
  step();
}
function pauseTL(){tlPlay=false;clearTimeout(tlAnim);}
function resetTL(){pauseTL();tlStep=0;document.querySelectorAll('#tl-bars .tl-bar').forEach(b=>b.style.opacity='.15');if(D&&D.timeline)document.getElementById('tl-info').textContent=`Step 0 / ${D.timeline.length}`;const ch=CI['ch-live'];if(ch){ch.data.labels=[];ch.data.datasets.forEach(d=>d.data=[]);ch.update();}}
document.getElementById('btn-play').addEventListener('click',playTL);
document.getElementById('btn-pause').addEventListener('click',pauseTL);
document.getElementById('btn-reset').addEventListener('click',resetTL);

/* ============================================================
   RENDER: COMPARE  (only when 2 algos)
   ============================================================ */
function renderCompare(){
  if(!D||!isMulti())return;
  const csel=document.getElementById('cmp-counter'),gsel=document.getElementById('cmp-gen');
  if(!csel.options.length){D.counter_names.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;if(n==='comparisons')o.selected=true;csel.appendChild(o);});D.generators.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;gsel.appendChild(o);});}
  const counter=csel.value||D.counter_names[0]||'comparisons',gen=gsel.value||'random';
  const [A,B]=D.algorithms;

  document.getElementById('cmp-title').textContent=A+' vs '+B+': complexity curves';
  document.getElementById('cmp-radar-title').textContent='Radar: '+A+' vs '+B;

  const sizes=D.sizes;
  const mkLine=(algo,color,dash)=>{
    const means=sizes.map(sz=>{const runs=D.runs.filter(r=>r.algorithm===algo&&r.generator_name===gen&&r.input_size===sz&&r.status==='OK');if(!runs.length)return 0;return runs.reduce((s,r)=>s+(r.counters[counter]||0),0)/runs.length;});
    return{label:algo,data:means,borderColor:color,borderDash:dash||[],tension:.3,fill:false,pointRadius:4,borderWidth:2};
  };
  mc('ch-vs',{type:'line',data:{labels:sizes.map(String),datasets:[mkLine(A,'#3b82f6'),mkLine(B,'#ef4444',[6,3])]},options:dopt()});

  const cn=D.counter_names.filter(k=>k!=='total_ops');
  const rv=(algo)=>cn.map(c=>{const runs=D.runs.filter(r=>r.algorithm===algo&&r.generator_name===gen&&r.status==='OK');if(!runs.length)return 0;return runs.reduce((s,r)=>s+(r.counters[c]||0),0)/runs.length;});
  const rl=rv(A),rh=rv(B),mx=cn.map((_,i)=>Math.max(rl[i],rh[i],1));
  mc('ch-radar',{type:'radar',data:{labels:cn.map(c=>c.replace(/_/g,' ')),datasets:[{label:A,data:rl.map((v,i)=>v/mx[i]),borderColor:'#3b82f6',backgroundColor:'#3b82f620',borderWidth:2,pointRadius:3},{label:B,data:rh.map((v,i)=>v/mx[i]),borderColor:'#ef4444',backgroundColor:'#ef444420',borderWidth:2,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,scales:{r:{angleLines:{color:'rgba(51,65,85,0.5)'},grid:{color:'rgba(51,65,85,0.5)'},pointLabels:{color:'#94a3b8',font:{size:10}},ticks:{display:false},suggestedMin:0,suggestedMax:1}},plugins:{legend:{labels:{color:'#94a3b8'}}}}});

  const sds=cn.map(c=>({label:c.replace(/_/g,' '),data:sizes.map(sz=>{const runs=D.runs.filter(r=>r.generator_name===gen&&r.input_size===sz&&r.status==='OK');if(!runs.length)return 0;return runs.reduce((s,r)=>s+(r.counters[c]||0),0)/runs.length;}),backgroundColor:OC[c]||'#666',borderWidth:0}));
  mc('ch-stacked',{type:'bar',data:{labels:sizes.map(String),datasets:sds},options:{...dopt(),scales:{...dopt().scales,x:{...dopt().scales.x,stacked:true},y:{...dopt().scales.y,stacked:true}}}});
}
document.getElementById('cmp-counter').addEventListener('change',renderCompare);
document.getElementById('cmp-gen').addEventListener('change',renderCompare);

/* ============================================================
   RENDER: RAW DATA
   ============================================================ */
function renderData(){
  if(!D)return;
  const g=document.getElementById('df-gen'),s=document.getElementById('df-size');
  let f=D.runs;
  const fa=document.getElementById('df-algo').value;
  if(fa!=='all')f=f.filter(r=>r.algorithm===fa);
  if(g.value!=='all')f=f.filter(r=>r.generator_name===g.value);
  if(s.value!=='all')f=f.filter(r=>r.input_size===parseInt(s.value));
  const cn=D.counter_names;
  let h='<table><thead><tr><th>#</th><th>Algo</th><th>Gen</th><th>N</th><th>Status</th>';
  cn.forEach(k=>h+=`<th>${k}</th>`);
  h+='<th>ms</th><th>OK</th></tr></thead><tbody>';
  f.slice(0,500).forEach((r,i)=>{
    h+=`<tr><td>${i+1}</td><td>${r.algorithm}</td><td style="color:${GC[r.generator_name]||'#fff'}">${r.generator_name}</td><td>${r.input_size}</td>`;
    h+=`<td><span class="badge ${r.status==='OK'?'b-ok':r.status==='LIMIT'?'b-lim':'b-err'}">${r.status}</span></td>`;
    cn.forEach(k=>h+=`<td>${r.counters[k]||0}</td>`);
    h+=`<td>${(r.elapsed_sec*1000).toFixed(2)}</td><td>${r.sorted_correctly?'Y':'N'}</td></tr>`;
  });
  h+='</tbody></table>';document.getElementById('raw-tbl').innerHTML=h;
}
['df-algo','df-gen','df-size'].forEach(id=>document.getElementById(id).addEventListener('change',renderData));
document.getElementById('btn-csv').addEventListener('click',()=>{
  if(!D)return;
  const cn=D.counter_names;let csv='run_id,algorithm,generator,size,status,'+cn.join(',')+',elapsed_ms,sorted\n';
  D.runs.forEach(r=>{csv+=`${r.run_id},${r.algorithm},${r.generator_name},${r.input_size},${r.status},`;csv+=cn.map(k=>r.counters[k]||0).join(',');csv+=`,${(r.elapsed_sec*1000).toFixed(2)},${r.sorted_correctly}\n`;});
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='experiment_data.csv';a.click();
});

/* ============================================================
   RUN EXPERIMENTS (fetch -> POST)
   ============================================================ */
document.getElementById('btn-run').addEventListener('click', async function(){
  const btn=this;
  btn.disabled=true;
  btn.innerHTML='&#9203; Running\u2026';
  const status=document.getElementById('run-status');
  status.innerHTML='<span style="color:var(--orange)">Parsing &amp; running experiments\u2026</span>';

  try{
    const sizesRaw=document.getElementById('cfg-sizes').value.split(',').map(s=>parseInt(s.trim())).filter(n=>!isNaN(n)&&n>0);
    if(!sizesRaw.length) throw new Error('Provide at least one valid size');
    const trials=parseInt(document.getElementById('cfg-trials').value)||3;

    /* collect algorithms */
    const algos=[];
    const nameA=document.getElementById('name-a').value.trim();
    const codeA=document.getElementById('code-a').value;
    if(!nameA) throw new Error('Algorithm name is required');
    if(!codeA.trim()) throw new Error('Algorithm source is required');
    algos.push({name:nameA, code:codeA});

    if(hasTwoAlgos){
      const nameB=document.getElementById('name-b').value.trim();
      const codeB=document.getElementById('code-b').value;
      if(!nameB) throw new Error('Algorithm B name is required');
      if(!codeB.trim()) throw new Error('Algorithm B source is required');
      algos.push({name:nameB, code:codeB});
    }

    const resp=await fetch('/api/run',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({algorithms:algos, sizes:sizesRaw, trials:trials})
    });
    const result=await resp.json();
    if(!resp.ok) throw new Error(result.error||'Server error');

    D=result;
    renderAll();
    document.querySelector('.tab[data-tab="overview"]').click();
    status.innerHTML='<span style="color:var(--green)">\u2713 Done! '+D.ok_runs+'/'+D.total_runs+' OK</span>';
  }catch(e){
    status.innerHTML='<span style="color:var(--red)">\u2717 '+e.message+'</span>';
  }finally{
    btn.disabled=false;
    btn.innerHTML='&#9654; Run Experiments';
  }
});

/* ============================================================
   renderAll — refresh everything after new data arrives
   ============================================================ */
function renderAll(){
  if(!D)return;
  const multi=isMulti();

  /* header */
  document.getElementById('hdr-runs').textContent=D.total_runs;
  document.getElementById('hdr-ok').textContent=D.ok_runs;
  document.getElementById('hdr-gens').textContent=D.generators.length;
  document.getElementById('hdr-sizes').textContent=D.sizes.length;

  /* show content, hide empty-states */
  ['ov','cx','tl','dt'].forEach(p=>{
    const e=document.getElementById(p+'-empty');if(e)e.style.display='none';
    const c=document.getElementById(p+'-content');if(c)c.style.display='block';
  });

  /* compare tab: show/hide */
  const cmpBtn=document.getElementById('tab-compare-btn');
  cmpBtn.style.display=multi?'':'none';
  if(multi){
    document.getElementById('cmp-empty').style.display='none';
    document.getElementById('cmp-content').style.display='block';
    cmpBtn.textContent=D.algorithms[0]+' vs '+D.algorithms[1];
  }

  /* algo toggles: show only when multiple */
  ['ov-algo-toggle','cx-algo-toggle'].forEach(id=>{
    const el=document.getElementById(id);
    if(multi){
      el.style.display='';
      el.innerHTML=D.algorithms.map((a,i)=>'<button class="algo-btn'+(i===0?' active':'')+'" data-algo="'+a+'">'+a+'</button>').join('');
    } else {
      el.style.display='none';
      el.innerHTML='';
    }
  });
  ovAlgo=D.algorithms[0]; cxAlgo=D.algorithms[0];
  if(multi){
    setupToggle('ov-algo-toggle',a=>{ovAlgo=a;renderOverview();});
    setupToggle('cx-algo-toggle',a=>{cxAlgo=a;renderComplexity();});
  }

  /* reset dropdowns */
  const dfAlgo=document.getElementById('df-algo');
  dfAlgo.innerHTML='<option value="all">All</option>';
  D.algorithms.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a;dfAlgo.appendChild(o);});

  document.getElementById('cx-counter').innerHTML='';
  document.getElementById('cmp-counter').innerHTML='';
  document.getElementById('cmp-gen').innerHTML='';

  const dfGen=document.getElementById('df-gen');
  dfGen.innerHTML='<option value="all">All</option>';
  D.generators.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;dfGen.appendChild(o);});

  const dfSize=document.getElementById('df-size');
  dfSize.innerHTML='<option value="all">All</option>';
  D.sizes.forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent='N='+s;dfSize.appendChild(o);});

  /* reset timeline */
  resetTL();

  /* render all tabs */
  renderOverview();
  renderComplexity();
  renderTimeline();
  if(multi) renderCompare();
  renderData();
}
</script>
</body>
</html>"""


# =======================================================================
# HTTP SERVER
# =======================================================================

class DashboardHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = DASHBOARD_HTML.replace(
                "__PRESETS__", json.dumps(PRESETS, ensure_ascii=False)
            )
            content = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/run":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 1_000_000:
                self._json_error(413, "Request too large")
                return

            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                self._json_error(400, "Invalid JSON")
                return

            # Accept: { algorithms: [{name, code}, ...], sizes, trials }
            algo_list = body.get("algorithms", [])
            if not algo_list or not isinstance(algo_list, list):
                self._json_error(400, "Field 'algorithms' (array) is required")
                return
            if len(algo_list) > 10:
                self._json_error(400, "Maximum 10 algorithms")
                return

            algos: List[Tuple[str, str]] = []
            for i, entry in enumerate(algo_list):
                name = str(entry.get("name", "")).strip()
                code = str(entry.get("code", ""))
                if not name:
                    self._json_error(400, f"Algorithm #{i+1}: name is required")
                    return
                if not code.strip():
                    self._json_error(400, f"Algorithm #{i+1}: source code is required")
                    return
                algos.append((name, code))

            sizes = body.get("sizes", [5, 10, 20, 50])
            trials = int(body.get("trials", 3))
            trials = max(1, min(trials, 20))
            sizes = [int(s) for s in sizes if isinstance(s, (int, float)) and 1 <= s <= 10000]
            if not sizes:
                self._json_error(400, "At least one valid size is required")
                return

            try:
                data = run_dynamic_experiments(algos, sizes, trials)
                self._json_response(200, data)
            except Exception as exc:
                traceback.print_exc()
                self._json_error(400, str(exc))
        else:
            self.send_error(404)

    # --- helpers ---

    def _json_response(self, code: int, data: Any):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json_error(self, code: int, message: str):
        self._json_response(code, {"error": message})

    def log_message(self, fmt, *args):
        pass


# =======================================================================
# MAIN
# =======================================================================

def main():
    print("=" * 60)
    print("Interactive Pseudocode Dashboard")
    print("=" * 60)
    print()
    print("Open the dashboard, enter pseudocode for one or two")
    print("algorithms and click 'Run Experiments'.")
    print("Press '+' to add a second algorithm for comparison.")
    print()
    print(f"  Available generators: {', '.join(list_generators())}")
    print()

    host, port = "127.0.0.1", 8050
    server = HTTPServer((host, port), DashboardHandler)
    print(f"Dashboard: http://{host}:{port}")
    print("Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
