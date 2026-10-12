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


def test_production_compose_source_publishes_only_the_proxy() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'profiles: ["production"]' in text
    assert '"80:80"' in text
    assert '"443:443"' in text
    assert "8000:8000" not in text
    assert "5432:5432" not in text
    assert "3000:3000" not in text
    assert "172.28.10.10/32" in text
    assert "172.28.10.10" in text
    assert "/api/v1/ready" in text
    assert "caddy_data:/data" in text
    dev = (ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:8000:8000" in dev
    assert "127.0.0.1:3000:3000" in dev
    assert "127.0.0.1:5432:5432" in dev
    assert "0.0.0.0:" not in dev
    assert "caddy" not in dev


def test_caddy_replaces_forwarded_headers_and_has_no_baked_domain() -> None:
    text = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "{$SITE_ADDRESS}" in text
    assert "{$ACME_EMAIL}" in text
    assert "header_up X-Forwarded-For {remote_host}" in text
    assert "header_up X-Real-IP {remote_host}" in text
    assert "example.com" not in text
    dockerfile = (ROOT / "deploy" / "caddy.Dockerfile").read_text(encoding="utf-8")
    assert "wget" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    web = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "fetch('http://127.0.0.1:3000/')" in web


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


def test_rendered_compose_examples() -> None:
    checker = _load_checker()
    production = {
        "networks": {"internal": {"ipam": {"config": [{"subnet": "172.28.10.0/24"}]}}},
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
            "web": {"networks": {"internal": {"ipv4_address": "172.28.10.10"}, "edge": {}}},
            "caddy": {
                "networks": ["edge"],
                "ports": [
                    {"published": "80", "target": 80},
                    {"published": "443", "target": 443},
                ],
            },
        },
    }
    assert checker.compose_problems(production, "production") == []
    leaked = {
        "services": {
            "api": {"ports": [{"published": "8000", "target": 8000, "host_ip": "0.0.0.0"}]},
        }
    }
    leaked_text = "\n".join(checker.compose_problems(leaked, "production"))
    assert "8000" in leaked_text
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
