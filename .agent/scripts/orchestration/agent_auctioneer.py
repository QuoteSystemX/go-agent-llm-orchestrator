
# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import json
import sys
from pathlib import Path


def parse_frontmatter(content):
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    
    fm_text = parts[1]
    body = parts[2]
    fm = {}
    for line in fm_text.strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm, body

def load_matrix():
    """
    Динамически собирает матрицу агентов, сканируя папку .agent/agents/
    """
    agents_dir = Path(".agent/agents")
    matrix = {"agents": []}
    
    if not agents_dir.exists():
        return matrix

    for agent_file in agents_dir.rglob("*.md"):
        try:
            content = agent_file.read_text(encoding="utf-8")
            fm, _ = parse_frontmatter(content)
            
            if not fm:
                continue
                
            # Извлекаем домены из frontmatter (строка через запятую)
            domains = [d.strip() for d in fm.get("domains", "").split(",") if d.strip()]
            
            # Добавляем агента в матрицу
            matrix["agents"].append({
                "id": agent_file.stem,
                "domains": domains,
                "description": fm.get("description", "No description provided."),
                "skills": [s.strip() for s in fm.get("skills", "").split(",") if s.strip()]
            })
        except Exception as e:
            print(f"⚠️ Error parsing {agent_file}: {e}")
            
    return matrix

def find_candidates(task_description):
    """
    Поиск кандидатов на основе динамической матрицы.
    """
    matrix = load_matrix()
    candidates = []
    task_lower = task_description.lower()
    
    for agent in matrix["agents"]:
        match_score = 0
        matched_indicators = []
        
        # 1. Прямое совпадение доменов (+1 за каждый)
        for domain in agent["domains"]:
            if domain.lower() in task_lower:
                match_score += 1
                matched_indicators.append(f"domain:{domain}")
        
        # 2. Совпадение по навыкам (SKILLS) (+2 за каждый, т.к. это точнее)
        for skill in agent.get("skills", []):
            # Проверяем как полное имя скилла, так и его части (например, 'go' в 'go-patterns')
            skill_clean = skill.lower().replace("-", " ")
            if skill.lower() in task_lower or skill_clean in task_lower:
                match_score += 2
                matched_indicators.append(f"skill:{skill}")
        
        # 3. Совпадение по ID агента (если задача явно для него) (+3)
        if agent["id"].lower() in task_lower:
            match_score += 3
            matched_indicators.append(f"identity:{agent['id']}")

        if match_score > 0:
            candidates.append({
                "id": agent["id"],
                "score": match_score,
                "indicators": matched_indicators,
                "description": agent["description"]
            })
            
    # Сортируем по релевантности
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

def run_auction(session_id, role, subtask_desc):
    """
    Имитация процесса торгов. 
    Принимает роль и описание подзадачи, возвращает лучшего кандидата.
    """
    print(f"📢 Auction started for role: [{role}]")
    print(f"📝 Subtask: {subtask_desc}")
    
    candidates = find_candidates(subtask_desc)
    
    if not candidates:
        # Fallback на orchestrator, если никто не подходит
        print("⚠️ No direct domain matches. Assigning default agent: orchestrator.")
        return {"id": "orchestrator", "status": "assigned_fallback"}

    print(f"👥 Candidates found: {[c['id'] for c in candidates]}")
    
    # Если кандидатов несколько, помечаем для Арены (Phase 3)
    if len(candidates) > 1:
        print(f"⚔️ Conflict detected! Candidates {candidates[0]['id']} and {candidates[1]['id']} will enter The Arena.")
        return {
            "id": "PENDING_ARENA",
            "candidates": [c["id"] for c in candidates],
            "role": role
        }
    
    winner = candidates[0]
    print(f"🏆 Winner: {winner['id']} (Score: {winner['score']})")
    return {"id": winner["id"], "status": "assigned_via_auction"}

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: agent_auctioneer.py <session_id> <role> <subtask_desc>")
        sys.exit(1)
        
    session_id = sys.argv[1]
    role = sys.argv[2]
    subtask_desc = sys.argv[3]
    
    result = run_auction(session_id, role, subtask_desc)
    print(json.dumps(result, indent=2))
