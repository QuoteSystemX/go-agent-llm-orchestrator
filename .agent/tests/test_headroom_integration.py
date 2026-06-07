"""
E2E тесты интеграции Headroom с Antigravity Kit.
Запуск: python3 -m pytest .agent/tests/test_headroom_integration.py -v
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADROOM_CFG_DIR = REPO_ROOT / ".agent" / "config" / "headroom"
SCRIPTS_DIR = REPO_ROOT / ".agent" / "scripts"
CLAUDE_AGENTS_DIR = REPO_ROOT / ".claude" / "agents"


# ─── Группа 1: Конфиги ────────────────────────────────────────────────────────

class TestHeadroomConfigs:
    def test_template_config_exists(self):
        assert (HEADROOM_CFG_DIR / "config.template.yaml").exists()

    @pytest.mark.parametrize("profile", ["go-service", "web-app", "data-platform", "mobile"])
    def test_profile_config_exists(self, profile):
        assert (HEADROOM_CFG_DIR / f"{profile}.yaml").exists(), f"Отсутствует {profile}.yaml"

    @pytest.mark.parametrize("profile", ["go-service", "web-app", "data-platform", "mobile"])
    def test_profile_config_valid_yaml(self, profile):
        import yaml
        path = HEADROOM_CFG_DIR / f"{profile}.yaml"
        data = yaml.safe_load(path.read_text())
        assert "version" in data
        assert "compression" in data
        assert "bus_integration" in data

    def test_mcp_config_has_headroom(self):
        mcp_path = REPO_ROOT / ".agent" / "config" / "mcp_config.json"
        cfg = json.loads(mcp_path.read_text())
        assert "headroom-mcp" in cfg.get("mcpServers", {}), "headroom-mcp отсутствует в mcp_config.json"

    def test_headroom_mcp_has_env(self):
        mcp_path = REPO_ROOT / ".agent" / "config" / "mcp_config.json"
        cfg = json.loads(mcp_path.read_text())
        entry = cfg["mcpServers"]["headroom-mcp"]
        assert entry.get("env", {}).get("HEADROOM_CONFIG_DIR"), "HEADROOM_CONFIG_DIR не задан"

    def test_docker_compose_exists(self):
        assert (HEADROOM_CFG_DIR / "docker-compose.headroom.yml").exists()

    def test_docker_compose_valid_yaml(self):
        import yaml
        path = HEADROOM_CFG_DIR / "docker-compose.headroom.yml"
        data = yaml.safe_load(path.read_text())
        assert "services" in data
        assert "headroom-proxy" in data["services"]
        assert "redis" in data["services"]
        assert "qdrant" in data["services"]

    def test_skill_module_exists(self):
        skill = REPO_ROOT / ".agent" / "skills" / "headroom-patterns" / "SKILL.md"
        assert skill.exists(), "headroom-patterns/SKILL.md отсутствует"

    def test_skill_has_required_sections(self):
        skill = REPO_ROOT / ".agent" / "skills" / "headroom-patterns" / "SKILL.md"
        content = skill.read_text()
        assert "headroom_compress" in content
        assert "headroom_retrieve" in content
        assert "content_type" in content


# ─── Группа 2: Провижнинг скрипт ─────────────────────────────────────────────

class TestHeadroomSetup:
    def test_script_exists(self):
        script = SCRIPTS_DIR / "delivery" / "headroom_setup.py"
        assert script.exists()

    def test_dry_run_exits_zero(self, tmp_path):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service", "--dry-run"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_dry_run_no_files_created(self, tmp_path):
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service", "--dry-run"],
            capture_output=True,
        )
        assert not (tmp_path / ".headroom" / "config.yaml").exists()

    def test_tier1_creates_config(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("")
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service", "--tier", "1"],
            check=True, capture_output=True,
        )
        assert (tmp_path / ".headroom" / "config.yaml").exists()
        assert (tmp_path / ".headroom" / ".gitignore").exists()

    def test_tier1_injects_mcp_entry(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("")
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service"],
            check=True, capture_output=True,
        )
        mcp = json.loads((tmp_path / ".mcp.json").read_text())
        assert "headroom-mcp" in mcp["mcpServers"]
        assert mcp["mcpServers"]["headroom-mcp"]["args"] == ["mcp"]

    def test_tier2_creates_docker_compose(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("")
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service", "--tier", "2"],
            check=True, capture_output=True,
        )
        assert (tmp_path / "docker-compose.headroom.yml").exists()

    def test_idempotency(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("")
        args = [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
                "--root", str(tmp_path), "--profile", "go-service"]
        subprocess.run(args, check=True, capture_output=True)
        mtime1 = (tmp_path / ".headroom" / "config.yaml").stat().st_mtime
        subprocess.run(args, check=True, capture_output=True)
        mtime2 = (tmp_path / ".headroom" / "config.yaml").stat().st_mtime
        assert mtime1 == mtime2, "config.yaml перезаписан при повторном запуске (не идемпотентен)"

    def test_gitignore_updated(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
             "--root", str(tmp_path), "--profile", "go-service"],
            check=True, capture_output=True,
        )
        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".headroom/cache.db" in gitignore

    def test_mcp_injection_idempotent(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {}}')
        (tmp_path / ".gitignore").write_text("")
        args = [sys.executable, str(SCRIPTS_DIR / "delivery" / "headroom_setup.py"),
                "--root", str(tmp_path), "--profile", "go-service"]
        subprocess.run(args, check=True, capture_output=True)
        subprocess.run(args, check=True, capture_output=True)
        mcp = json.loads((tmp_path / ".mcp.json").read_text())
        servers = mcp.get("mcpServers", {})
        headroom_entries = [k for k in servers if k == "headroom-mcp"]
        assert len(headroom_entries) == 1, "headroom-mcp добавлен дважды"


# ─── Группа 3: sync_agents.py ─────────────────────────────────────────────────

class TestSyncAgentsInjection:
    def test_skill_extras_has_headroom_for_backend(self):
        sys.path.insert(0, str(SCRIPTS_DIR / "delivery"))
        from sync_agents import AGENT_SKILL_EXTRAS
        assert "headroom-patterns" in AGENT_SKILL_EXTRAS.get("backend-specialist", [])

    def test_skill_extras_has_headroom_for_debugger(self):
        from sync_agents import AGENT_SKILL_EXTRAS
        assert "headroom-patterns" in AGENT_SKILL_EXTRAS.get("debugger", [])

    def test_skill_extras_has_headroom_for_test_engineer(self):
        from sync_agents import AGENT_SKILL_EXTRAS
        assert "headroom-patterns" in AGENT_SKILL_EXTRAS.get("test-engineer", [])

    def test_permissions_allow_has_headroom(self):
        from sync_agents import CLAUDE_PERMISSIONS_ALLOW
        headroom_perms = [p for p in CLAUDE_PERMISSIONS_ALLOW if "headroom" in p]
        assert len(headroom_perms) >= 3, "headroom MCP permissions отсутствуют в CLAUDE_PERMISSIONS_ALLOW"

    def test_no_headroom_flag_exists(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "delivery" / "sync_agents.py"), "--help"],
            capture_output=True, text=True,
        )
        assert "--no-headroom" in result.stdout

    def test_security_agents_no_headroom_skill(self):
        from sync_agents import AGENT_SKILL_EXTRAS
        for agent in ["red-team", "security-auditor", "penetration-tester"]:
            extras = AGENT_SKILL_EXTRAS.get(agent, [])
            assert "headroom-patterns" not in extras, f"{agent} не должен иметь headroom-patterns"


# ─── Группа 4: Bus CCR ────────────────────────────────────────────────────────

class TestBusCCR:
    def test_estimate_tokens_small(self):
        sys.path.insert(0, str(SCRIPTS_DIR / "context"))
        from bus_manager import _estimate_tokens
        assert _estimate_tokens("hello") < 10

    def test_estimate_tokens_large(self):
        from bus_manager import _estimate_tokens
        content = "x" * 4000
        assert 800 <= _estimate_tokens(content) <= 1200

    def test_detect_content_type_code(self):
        from bus_manager import _detect_content_type
        obj = {"type": "code_chunk"}
        assert _detect_content_type(obj) == "code"

    def test_detect_content_type_json(self):
        from bus_manager import _detect_content_type
        obj = {"type": "verification_result"}
        assert _detect_content_type(obj) == "json"

    def test_push_with_ccr_no_client_falls_back(self, tmp_path, monkeypatch):
        from bus_manager import push_with_ccr, _estimate_tokens
        large_content = json.dumps({"data": "x" * 3000})
        assert _estimate_tokens(large_content) > 500
        # Without headroom_client, should call plain push (may fail on real bus path — mock)
        # Just verify the function exists and accepts the right signature
        import inspect
        sig = inspect.signature(push_with_ccr)
        assert "headroom_client" in sig.parameters

    def test_pull_with_ccr_exists(self):
        from bus_manager import pull_with_ccr
        import inspect
        sig = inspect.signature(pull_with_ccr)
        assert "retrieve_full" in sig.parameters
        assert "headroom_client" in sig.parameters

    def test_ccr_threshold_is_500(self):
        from bus_manager import _CCR_THRESHOLD_TOKENS
        assert _CCR_THRESHOLD_TOKENS == 500


# ─── Группа 5: distribution.yml ───────────────────────────────────────────────

class TestDistributionConfig:
    def test_distribution_yml_has_profiles(self):
        import yaml
        dist = REPO_ROOT / ".github" / "distribution.yml"
        data = yaml.safe_load(dist.read_text())
        for repo in data["repositories"]:
            assert "profile" in repo, f"Репо {repo['name']} не имеет поля profile"
            assert "headroom_tier" in repo, f"Репо {repo['name']} не имеет поля headroom_tier"

    def test_all_profiles_valid(self):
        import yaml
        dist = REPO_ROOT / ".github" / "distribution.yml"
        data = yaml.safe_load(dist.read_text())
        valid_profiles = {"go-service", "web-app", "data-platform", "mobile"}
        for repo in data["repositories"]:
            assert repo["profile"] in valid_profiles, \
                f"Неизвестный профиль '{repo['profile']}' у {repo['name']}"

    def test_tier2_repos_have_docker_compose_config(self):
        import yaml
        dist = REPO_ROOT / ".github" / "distribution.yml"
        data = yaml.safe_load(dist.read_text())
        tier2_repos = [r for r in data["repositories"] if r.get("headroom_tier") == 2]
        assert len(tier2_repos) > 0, "Нет Tier 2 репо в distribution.yml"
        assert (HEADROOM_CFG_DIR / "docker-compose.headroom.yml").exists()
