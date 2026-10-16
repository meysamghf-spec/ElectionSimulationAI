"""Source and rendered Compose checks for the single-VM deployment."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    path = ROOT / "scripts" / "check_compose_config.py"
    spec = importlib.util.spec_from_file_location("check_compose_config", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_compose_source_publishes_no_ports_and_has_no_caddy() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'profiles: ["production"]' in text
    assert "ports:" not in text
    assert "caddy:" not in text.replace("name: ${PROXY_NETWORK:-caddy}", "")
    assert "deploy/caddy.Dockerfile" not in text
    assert "external: true" in text
    assert "electionsim-web" in text
    assert "internal: true" in text
    assert "172.28.10.10/32" in text
    assert "/api/v1/ready" in text
    assert "${POSTGRES_PASSWORD:-}" in text
    assert "SITE_ADDRESS:?" in text
    shared = (ROOT / "docker-compose.shared-db.yml").read_text(encoding="utf-8")
    assert "ports:" not in shared
    assert "DATABASE_URL:?" in shared
    dev = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:8000:8000" in dev
    assert "127.0.0.1:3000:3000" in dev
    assert "127.0.0.1:5432:5432" in dev
    assert "0.0.0.0:" not in dev
    assert "caddy" not in dev


def test_bundled_caddy_is_gone_and_shared_snippet_is_safe() -> None:
    assert not (ROOT / "deploy" / "caddy.Dockerfile").exists()
    assert not (ROOT / "deploy" / "Caddyfile").exists()
    text = (ROOT / "deploy" / "Caddyfile.shared.example").read_text(encoding="utf-8")
    assert "reverse_proxy electionsim-web:3000" in text
    assert "header_up X-Forwarded-For {remote_host}" in text
    assert "header_up X-Real-IP {remote_host}" in text
    web = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "fetch('http://127.0.0.1:3000/health')" in web
    assert (ROOT / "DEPLOY.md").exists()


def test_env_example_has_no_real_secrets() -> None:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line and not line.lstrip().startswith("#"))
    for name in ("POSTGRES_PASSWORD", "API_TOKEN", "INITIAL_ADMIN_PASSWORD", "LLM_API_KEY", "CREATE_USER_PASSWORD"):
        assert name in values
        assert values[name] in {"", "change-me-local-only"}


def test_backup_scripts_use_a_scratch_database_and_do_not_print_passwords() -> None:
    backup = (ROOT / "deploy" / "backup.sh").read_text(encoding="utf-8")
    restore = (ROOT / "deploy" / "restore-scratch.sh").read_text(encoding="utf-8")
    assert "pg_dump -U election -d election" in backup
    assert "POSTGRES_PASSWORD" not in backup
    assert "off the VM" in backup
    assert "election_restore_check" in restore
    assert "DROP DATABASE election_restore_check" in restore
    assert "pg_restore" in restore
    assert "POSTGRES_PASSWORD" not in restore
    assert "*.dump" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def _production_example() -> dict:
    return {
        "networks": {
            "internal": {"ipam": {"config": [{"subnet": "172.28.10.0/24"}]}},
            "data": {"internal": True},
            "proxy": {"external": True, "name": "caddy"},
        },
        "services": {
            "db": {"networks": ["data"]},
            "api": {
                "networks": ["data", "internal"],
                "environment": {
                    "TRUSTED_PROXY_CIDRS": "172.28.10.10/32",
                    "ENVIRONMENT": "production",
                    "ALLOW_REGISTRATION": "false",
                },
            },
            "web": {"networks": {"internal": {"ipv4_address": "172.28.10.10"}, "proxy": {}}},
        },
    }


def test_rendered_compose_examples() -> None:
    checker = _load_checker()
    production = _production_example()
    assert checker.compose_problems(production, "production") == []

    shared = _production_example()
    del shared["services"]["db"]
    shared["services"]["api"]["networks"] = ["internal", "shareddb"]
    assert checker.compose_problems(shared, "production") == []

    with_caddy = _production_example()
    with_caddy["services"]["caddy"] = {"ports": [{"published": "443", "target": 443}]}
    problems = "\n".join(checker.compose_problems(with_caddy, "production"))
    assert "must not bundle Caddy" in problems
    assert "443" in problems

    leaked = _production_example()
    leaked["services"]["db"]["ports"] = [{"published": "5432", "target": 5432, "host_ip": "0.0.0.0"}]
    assert "5432" in "\n".join(checker.compose_problems(leaked, "production"))

    open_data = _production_example()
    open_data["networks"]["data"] = {}
    assert any("data network" in p for p in checker.compose_problems(open_data, "production"))

    development = {
        "services": {
            "db": {"ports": [{"published": "5432", "target": 5432, "host_ip": "127.0.0.1"}]},
            "api": {"ports": [{"published": "8000", "target": 8000, "host_ip": "127.0.0.1"}]},
            "web": {"ports": [{"published": "3000", "target": 3000, "host_ip": "127.0.0.1"}]},
        }
    }
    assert checker.compose_problems(development, "development") == []
    public_dev = {
        "services": {
            "api": {"ports": [{"published": "8000", "target": 8000}]},
            "web": {"ports": [{"published": "3000", "target": 3000, "host_ip": "127.0.0.1"}]},
            "db": {"ports": [{"published": "5432", "target": 5432, "host_ip": "127.0.0.1"}]},
        }
    }
    assert any("all interfaces" in problem for problem in checker.compose_problems(public_dev, "development"))
