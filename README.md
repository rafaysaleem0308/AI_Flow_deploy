# 🧠 Dynamic Wumpus Logic Agent

A **Web-based Knowledge-Based Agent** that navigates a Wumpus World-style grid using **Propositional Logic** and **Resolution Refutation** to deduce safe cells in real time.

---

## 🌐 Live Demo

> Deployed on Vercel: *(add your live URL here after deployment)*

---

## 📸 Preview

The agent explores a dynamically-generated grid, inferring which cells are safe using a Propositional Logic Knowledge Base and Resolution Refutation algorithm.

- 🟢 **Green** — Provably Safe cell
- ⬛ **Gray** — Unknown/Unvisited cell
- 🔴 **Red** — Confirmed Hazard (Pit or Wumpus)
- **A** — Current Agent position

---

## 🚀 Features

### Environment
- **Dynamic Grid Sizing** — User defines grid dimensions (Rows × Columns, 3–12)
- **Random Hazard Placement** — Pits and a Wumpus are randomly placed each episode; the agent has no prior knowledge of their locations
- **Percept Generation:**
  - **Breeze** — received if the agent is in a cell adjacent to a Pit
  - **Stench** — received if the agent is in a cell adjacent to the Wumpus

### Inference Engine (Core AI)
- **Knowledge Base (KB)** — Maintains a Propositional Logic KB in Conjunctive Normal Form (CNF)
- **TELL** — When receiving percepts, encodes biconditional rules (e.g., `B_2,1 ⇔ P_2,2 ∨ P_3,1 ∨ P_1,1`) into the KB
- **ASK / Resolution Refutation** — Before moving to an unvisited cell, the agent queries the KB to prove the negation of the hazard (i.e., `¬P_r,c ∧ ¬W_r,c`) using automated clause resolution

### Web GUI
- **Real-Time Grid Visualization** — Cells colored by inferred safety status
- **Metrics Dashboard** — Displays:
  - Current **Percepts** at agent's location (Breeze / Stench)
  - Total **Inference Steps** taken by the Resolution algorithm
  - Current agent **Status**
- **Step Control** — Manually step the agent one move at a time

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask |
| AI Engine | Custom Propositional Logic + Resolution Refutation (from scratch) |
| Frontend | Vanilla HTML5 / CSS / JavaScript (served via Flask) |
| Deployment | Vercel (via WSGI adapter) |

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/rafaysaleem0308/AI_Flow_deploy.git
cd AI_Flow_deploy

# Install dependencies
pip install flask
```

### Run

```bash
python Q6.py
```

Then open your browser at: [http://localhost:5000](http://localhost:5000)

---

## 🧩 How It Works

### Resolution Refutation

The inference engine proves a query `Q` by:

1. Adding `¬Q` (negation of the query) to the KB
2. Converting all clauses to CNF
3. Repeatedly resolving pairs of clauses using the resolution rule
4. If an **empty clause** (contradiction) is derived → `Q` is **proven true**
5. If no new clauses can be derived → query cannot be proven (cell remains unknown)

### Biconditional Encoding

For each visited cell `(r, c)`, the KB encodes:

```
B_r,c ⇔ P_r1,c1 ∨ P_r2,c2 ∨ ...   (Breeze ↔ adjacent pit exists)
S_r,c ⇔ W_r1,c1 ∨ W_r2,c2 ∨ ...   (Stench ↔ adjacent Wumpus exists)
```

This is split into two CNF clauses:
- `¬B_r,c ∨ P_r1,c1 ∨ P_r2,c2`  
- `B_r,c ∨ ¬P_ri,ci`  (one per neighbor)

---

## 📂 Project Structure

```
AI_Flow_deploy/
├── Q6.py          # Main application (backend + embedded frontend)
└── README.md      # This file
```

---

## 🎓 Academic Context

**Course:** Artificial Intelligence  
**Assignment:** 6 — Coding Project  
**Topic:** Dynamic Wumpus Logic Agent using Propositional Logic and Resolution Refutation  

---

## 📝 License

This project is for educational purposes.
