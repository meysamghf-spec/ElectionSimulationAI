#!/usr/bin/env python3
"""Check a rendered Compose config for published ports and networks. Does not print the config."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any


def _networks(service: Mapping[str, Any]) -> set[str]:
    raw = service.get("networks") or {}
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if isinstance(raw, dict):
        return {str(item) for item in raw}
    return set()


def _published(service: Mapping[str, Any]) -> list[dict[str, Any]]:
    ports = service.get("ports") or []
    return [port for port in ports if isinstance(port, dict)]


def compose_problems(config: Mapping[str, Any], mode: str) -> list[str]:
    services = config.get("services") or {}
    if not isinstance(services, dict):
        return ["Compose config has no services."]
    problems: list[str] = []
    if mode == "production":
        problems.extend(_production_problems(config, services))
    elif mode == "development":
        problems.extend(_development_problems(services))
    else:
        problems.append("mode must be production or development.")
    return problems


def _production_problems(config: Mapping[str, Any], services: Mapping[str, Any]) -> list[str]:
    """Production sits behind ONE shared Caddy on the server. Nothing here may publish a host port."""

    problems: list[str] = []
    api = services.get("api")
    web = services.get("web")
    db = services.get("db")
    shared_db = isinstance(api, dict) and "shareddb" in _networks(api)
    required = ("api", "web") if shared_db else ("db", "api", "web")
    for name in required:
        if name not in services:
            problems.append(f"Production config is missing the {name} service.")
    if "caddy" in services:
        problems.append("Production must not bundle Caddy. The server's shared Caddy is the only proxy.")
    for name, service in services.items():
        if not isinstance(service, dict):
            continue
        for port in _published(service):
            published = str(port.get("published"))
            problems.append(f"{name} publishes host port {published}. Production must not publish any host port.")
    if isinstance(db, dict) and _networks(db) != {"data"}:
        problems.append("db must be attached only to the data network.")
    if isinstance(api, dict):
        expected = {"internal", "shareddb"} if shared_db else {"data", "internal"}
        if _networks(api) != expected:
            problems.append(f"api must be attached only to the {' and '.join(sorted(expected))} networks.")
    if isinstance(web, dict) and _networks(web) != {"internal", "proxy"}:
        problems.append("web must be attached to the internal and proxy networks.")
    if isinstance(web, dict) and _network_ip(web, "internal") != "172.28.10.10":
        problems.append("web must use internal address 172.28.10.10 so the API can trust that host only.")
    networks = config.get("networks") or {}
    if not isinstance(networks, dict):
        networks = {}
    internal = networks.get("internal")
    subnets: list[str] = []
    if isinstance(internal, dict):
        ipam = internal.get("ipam") or {}
        configs = ipam.get("config") if isinstance(ipam, dict) else None
        if isinstance(configs, list):
            subnets = [str(item.get("subnet")) for item in configs if isinstance(item, dict)]
    if "172.28.10.0/24" not in subnets:
        problems.append("The internal network must use subnet 172.28.10.0/24.")
    data = networks.get("data")
    if not shared_db and not (isinstance(data, dict) and data.get("internal") is True):
        problems.append("The data network must be internal (no outside route).")
    proxy = networks.get("proxy")
    if not (isinstance(proxy, dict) and proxy.get("external") is True):
        problems.append("The proxy network must be external, shared with the server's Caddy.")
    if isinstance(api, dict):
        environment = api.get("environment") or {}
        trusted = _env_value(environment, "TRUSTED_PROXY_CIDRS")
        if trusted != "172.28.10.10/32":
            problems.append("api TRUSTED_PROXY_CIDRS must be 172.28.10.10/32, the web container address.")
        if _env_value(environment, "ENVIRONMENT") != "production":
            problems.append("api ENVIRONMENT must be production.")
        if _env_value(environment, "ALLOW_REGISTRATION") != "false":
            problems.append("api ALLOW_REGISTRATION must be false.")
    return problems


def _development_problems(services: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if "caddy" in services:
        problems.append("The development stack must not start Caddy.")
    published_targets: set[str] = set()
    for name, service in services.items():
        if not isinstance(service, dict):
            continue
        for port in _published(service):
            host_ip = str(port.get("host_ip") or "")
            published = str(port.get("published"))
            published_targets.add(str(port.get("target")))
            if host_ip != "127.0.0.1":
                problems.append(f"{name} publishes {published} on {host_ip or 'all interfaces'}.")
    for target in ("3000", "8000", "5432"):
        if target not in published_targets:
            problems.append(f"Development config must publish target port {target} on 127.0.0.1.")
    return problems


def _network_ip(service: Mapping[str, Any], network: str) -> str:
    raw = service.get("networks") or {}
    if isinstance(raw, dict):
        spec = raw.get(network) or {}
        if isinstance(spec, dict):
            return str(spec.get("ipv4_address") or "")
    return ""


def _env_value(environment: object, name: str) -> str:
    if isinstance(environment, dict):
        value = environment.get(name)
        return "" if value is None else str(value)
    if isinstance(environment, list):
        prefix = f"{name}="
        for item in environment:
            if isinstance(item, str) and item.startswith(prefix):
                return item[len(prefix) :]
    return ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("Usage: check_compose_config.py CONFIG.json production|development", file=sys.stderr)
        return 2
    path, mode = args
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config, dict):
        print("Compose config must be a JSON object.", file=sys.stderr)
        return 1
    problems = compose_problems(config, mode)
    if problems:
        print(f"{mode} Compose configuration is not acceptable:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print(f"{mode} Compose port and network checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
