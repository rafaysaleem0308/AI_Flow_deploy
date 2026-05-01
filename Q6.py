import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from flask import Flask, jsonify, render_template_string, request


Clause = frozenset[str]


def make_lit(symbol: str, positive: bool = True) -> str:
    return symbol if positive else f"~{symbol}"


def negate_lit(lit: str) -> str:
    return lit[1:] if lit.startswith("~") else f"~{lit}"


def key(r: int, c: int) -> str:
    return f"{r}_{c}"


def pit_sym(r: int, c: int) -> str:
    return f"P_{key(r, c)}"


def wumpus_sym(r: int, c: int) -> str:
    return f"W_{key(r, c)}"


def breeze_sym(r: int, c: int) -> str:
    return f"B_{key(r, c)}"


def stench_sym(r: int, c: int) -> str:
    return f"S_{key(r, c)}"


class KnowledgeBase:
    def __init__(self) -> None:
        self.clauses: List[Clause] = []

    def add_clause(self, literals: Set[str]) -> None:
        self.clauses.append(frozenset(literals))

    def add_fact(self, symbol: str, value: bool) -> None:
        self.add_clause({make_lit(symbol, positive=value)})

    def add_biconditional_to_or(self, lhs_symbol: str, rhs_symbols: List[str]) -> None:
        # lhs <-> (r1 v r2 v ...)
        self.add_clause({make_lit(lhs_symbol, positive=False), *rhs_symbols})
        for rhs in rhs_symbols:
            self.add_clause({lhs_symbol, negate_lit(rhs)})

    def resolution_refutation(
        self,
        query_symbol: str,
        query_positive: bool,
        max_generated: int = 1500,
    ) -> Tuple[bool, int]:
        # Prove KB |= query by checking UNSAT(KB U {~query}).
        support = frozenset({make_lit(query_symbol, positive=not query_positive)})
        clauses: Set[Clause] = set(self.clauses)
        clauses.add(support)

        generated = 0
        pending: Set[Clause] = set()

        while True:
            clause_list = list(clauses)
            for i in range(len(clause_list)):
                for j in range(i + 1, len(clause_list)):
                    for resolvent in self._resolve_pair(clause_list[i], clause_list[j]):
                        generated += 1
                        if not resolvent:
                            return True, generated
                        pending.add(resolvent)
                        if generated >= max_generated:
                            return False, generated

            if pending.issubset(clauses):
                return False, generated

            clauses.update(pending)

    @staticmethod
    def _resolve_pair(c1: Clause, c2: Clause) -> Set[Clause]:
        out: Set[Clause] = set()
        for lit in c1:
            comp = negate_lit(lit)
            if comp not in c2:
                continue

            merged = set(c1.union(c2))
            merged.discard(lit)
            merged.discard(comp)

            # Ignore tautological clauses.
            if any(negate_lit(x) in merged for x in merged):
                continue
            out.add(frozenset(merged))
        return out


@dataclass
class AgentState:
    row: int
    col: int


class WumpusWorld:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.start = (0, 0)

        self.pits: Set[Tuple[int, int]] = set()
        self.wumpus: Optional[Tuple[int, int]] = None

        self.agent = AgentState(0, 0)
        self.visited: Set[Tuple[int, int]] = {(0, 0)}
        self.safe: Set[Tuple[int, int]] = {(0, 0)}
        self.confirmed_hazards: Set[Tuple[int, int]] = set()

        self.kb = KnowledgeBase()
        self.rule_cells: Set[Tuple[int, int]] = set()
        self.query_cache: Dict[Tuple[str, bool, int], bool] = {}

        self.total_inference_steps = 0
        self.last_percepts: List[str] = []
        self.last_status = "Episode initialized"
        self.game_over = False

        self._initialize_random_hazards()
        self._seed_static_rules()
        self._tell_current_percepts()
        self._infer_frontier_knowledge()

    def _initialize_random_hazards(self) -> None:
        cells = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (r, c) != self.start
        ]
        random.shuffle(cells)

        pit_count = max(1, (self.rows * self.cols) // 7)
        self.pits = set(cells[:pit_count])

        available = [cell for cell in cells if cell not in self.pits]
        self.wumpus = available[0] if available else None

    def _seed_static_rules(self) -> None:
        self.kb.add_fact(pit_sym(*self.start), False)
        self.kb.add_fact(wumpus_sym(*self.start), False)

    def _ensure_local_rules(self, r: int, c: int) -> None:
        cell = (r, c)
        if cell in self.rule_cells:
            return

        neighbors = self.neighbors(r, c)
        pit_neighbors = [pit_sym(nr, nc) for nr, nc in neighbors]
        w_neighbors = [wumpus_sym(nr, nc) for nr, nc in neighbors]

        self.kb.add_biconditional_to_or(breeze_sym(r, c), pit_neighbors)
        self.kb.add_biconditional_to_or(stench_sym(r, c), w_neighbors)
        self.rule_cells.add(cell)

    def neighbors(self, r: int, c: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                out.append((nr, nc))
        return out

    def _tell_current_percepts(self) -> None:
        r, c = self.agent.row, self.agent.col
        self._ensure_local_rules(r, c)

        neighbors = self.neighbors(r, c)
        breeze = any((nr, nc) in self.pits for nr, nc in neighbors)
        stench = any((nr, nc) == self.wumpus for nr, nc in neighbors)

        self.kb.add_fact(breeze_sym(r, c), breeze)
        self.kb.add_fact(stench_sym(r, c), stench)
        self.query_cache.clear()

        labels: List[str] = []
        if breeze:
            labels.append("Breeze")
        if stench:
            labels.append("Stench")
        if not labels:
            labels.append("None")
        self.last_percepts = labels

    def _is_provably(self, symbol: str, value: bool) -> bool:
        cache_key = (symbol, value, len(self.kb.clauses))
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]

        proven, steps = self.kb.resolution_refutation(symbol, query_positive=value)
        self.total_inference_steps += steps
        self.query_cache[cache_key] = proven
        return proven

    def _frontier_cells(self) -> Set[Tuple[int, int]]:
        frontier: Set[Tuple[int, int]] = set()
        for vr, vc in self.visited:
            for cell in self.neighbors(vr, vc):
                if cell not in self.visited:
                    frontier.add(cell)
        return frontier

    def _evaluate_cell(self, cell: Tuple[int, int]) -> None:
        r, c = cell
        no_pit = self._is_provably(pit_sym(r, c), False)
        no_wumpus = self._is_provably(wumpus_sym(r, c), False)
        if no_pit and no_wumpus:
            self.safe.add(cell)

        yes_pit = self._is_provably(pit_sym(r, c), True)
        yes_wumpus = self._is_provably(wumpus_sym(r, c), True)
        if yes_pit or yes_wumpus:
            self.confirmed_hazards.add(cell)

    def _infer_frontier_knowledge(self) -> None:
        self.safe.update(self.visited)
        for cell in self._frontier_cells():
            self._evaluate_cell(cell)

    def _adjacent_unvisited(self) -> List[Tuple[int, int]]:
        r, c = self.agent.row, self.agent.col
        return [cell for cell in self.neighbors(r, c) if cell not in self.visited]

    def step(self) -> None:
        if self.game_over:
            self.last_status = "Episode already finished"
            return

        candidates = self._adjacent_unvisited()
        for cell in candidates:
            self._evaluate_cell(cell)

        safe_choices = [
            cell
            for cell in candidates
            if cell in self.safe and cell not in self.confirmed_hazards
        ]

        if not safe_choices:
            self.last_status = "No provably safe adjacent move"
            return

        nr, nc = safe_choices[0]
        self.agent = AgentState(nr, nc)
        self.visited.add((nr, nc))

        if (nr, nc) in self.pits:
            self.last_status = "Agent fell into a pit"
            self.game_over = True
            return

        if self.wumpus and (nr, nc) == self.wumpus:
            self.last_status = "Agent encountered the Wumpus"
            self.game_over = True
            return

        self.last_status = f"Moved to ({nr}, {nc})"
        self._tell_current_percepts()
        self._infer_frontier_knowledge()

    def to_payload(self) -> Dict:
        grid: List[List[Dict]] = []
        for r in range(self.rows):
            row: List[Dict] = []
            for c in range(self.cols):
                row.append(
                    {
                        "r": r,
                        "c": c,
                        "agent": (r, c) == (self.agent.row, self.agent.col),
                        "visited": (r, c) in self.visited,
                        "safe": (r, c) in self.safe,
                        "hazard": (r, c) in self.confirmed_hazards,
                    }
                )
            grid.append(row)

        return {
            "rows": self.rows,
            "cols": self.cols,
            "grid": grid,
            "percepts": self.last_percepts,
            "inference_steps": self.total_inference_steps,
            "status": self.last_status,
            "game_over": self.game_over,
        }


app = Flask(__name__)
WORLD: Optional[WumpusWorld] = None


HTML = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Dynamic Wumpus Logic Agent</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --unknown: #99a4b2;
      --safe: #2f9e44;
      --hazard: #d63324;
      --text: #1f2937;
      --accent: #0ea5e9;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Segoe UI, Tahoma, Geneva, Verdana, sans-serif;
      background: radial-gradient(circle at 10% 15%, #ffffff 0%, var(--bg) 60%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 18px;
    }
    .app {
      width: min(980px, 100%);
      background: var(--panel);
      border-radius: 14px;
      box-shadow: 0 12px 30px rgba(20, 32, 50, 0.15);
      padding: 18px;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 16px;
    }
    .controls { display: grid; gap: 12px; align-content: start; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    input, button {
      width: 100%;
      padding: 10px;
      border-radius: 10px;
      border: 1px solid #c8d2df;
      font-size: 14px;
    }
    button {
      background: var(--accent);
      border: none;
      color: white;
      font-weight: 600;
      cursor: pointer;
    }
    .metrics {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 10px;
      display: grid;
      gap: 6px;
      font-size: 14px;
    }
    .legend { display: flex; gap: 8px; flex-wrap: wrap; font-size: 12px; }
    .tag { border-radius: 999px; color: #fff; padding: 2px 8px; }
    .unknown { background: var(--unknown); }
    .safe { background: var(--safe); }
    .hazard { background: var(--hazard); }
    .grid { display: grid; gap: 6px; align-content: start; }
    .cell {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: 700;
      font-size: 12px;
      border: 1px solid rgba(0,0,0,0.08);
    }
    @media (max-width: 860px) {
      .app { grid-template-columns: 1fr; }
      .cell { width: 34px; height: 34px; }
    }
  </style>
</head>
<body>
  <div class=\"app\">
    <div class=\"controls\">
      <h1 style=\"margin:0;font-size:1.15rem\">Dynamic Wumpus Logic Agent</h1>
      <div class=\"row\">
        <input id=\"rows\" type=\"number\" min=\"3\" max=\"12\" value=\"6\" />
        <input id=\"cols\" type=\"number\" min=\"3\" max=\"12\" value=\"6\" />
      </div>
      <button onclick=\"newEpisode()\">New Episode</button>
      <button onclick=\"stepAgent()\">Step Agent</button>
      <div class=\"metrics\">
        <div><strong>Status:</strong> <span id=\"status\">-</span></div>
        <div><strong>Percepts:</strong> <span id=\"percepts\">-</span></div>
        <div><strong>Total Inference Steps:</strong> <span id=\"steps\">0</span></div>
      </div>
      <div class=\"legend\">
        <span class=\"tag unknown\">Unknown</span>
        <span class=\"tag safe\">Safe</span>
        <span class=\"tag hazard\">Confirmed Hazard</span>
      </div>
      <div style=\"font-size:13px\">Agent position is marked with A.</div>
    </div>
    <div><div id=\"grid\" class=\"grid\"></div></div>
  </div>

  <script>
    function colorFor(cell) {
      if (cell.hazard) return getComputedStyle(document.documentElement).getPropertyValue('--hazard').trim();
      if (cell.safe || cell.visited) return getComputedStyle(document.documentElement).getPropertyValue('--safe').trim();
      return getComputedStyle(document.documentElement).getPropertyValue('--unknown').trim();
    }

    function render(data) {
      const grid = document.getElementById('grid');
      const size = window.innerWidth <= 860 ? 34 : 40;
      grid.style.gridTemplateColumns = `repeat(${data.cols}, ${size}px)`;
      grid.innerHTML = '';

      data.grid.forEach(row => {
        row.forEach(cell => {
          const d = document.createElement('div');
          d.className = 'cell';
          d.style.background = colorFor(cell);
          d.textContent = cell.agent ? 'A' : '';
          grid.appendChild(d);
        });
      });

      document.getElementById('status').textContent = data.status;
      document.getElementById('percepts').textContent = data.percepts.join(', ');
      document.getElementById('steps').textContent = data.inference_steps;
    }

    async function newEpisode() {
      const rows = parseInt(document.getElementById('rows').value, 10);
      const cols = parseInt(document.getElementById('cols').value, 10);
      const response = await fetch('/api/new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows, cols })
      });
      render(await response.json());
    }

    async function stepAgent() {
      const response = await fetch('/api/step', { method: 'POST' });
      render(await response.json());
    }

    newEpisode();
  </script>
</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(HTML)


@app.post("/api/new")
def api_new():
    global WORLD
    payload = request.get_json(silent=True) or {}
    rows = max(3, min(int(payload.get("rows", 6)), 12))
    cols = max(3, min(int(payload.get("cols", 6)), 12))

    WORLD = WumpusWorld(rows, cols)
    return jsonify(WORLD.to_payload())


@app.post("/api/step")
def api_step():
    global WORLD
    if WORLD is None:
        WORLD = WumpusWorld(6, 6)
    WORLD.step()
    return jsonify(WORLD.to_payload())


if __name__ == "__main__":
    app.run(debug=True)
