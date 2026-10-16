# Deploying ElectionSimulationAI on an Iranian VPS

**خلاصهٔ فارسی:** این برنامه روی یک سرور مجازی ایرانی با Docker Compose اجرا می‌شود و پشت **یک Caddy مشترک** (برای همهٔ پلتفرم‌ها) روی یک زیردامنه مثل `election.example.ir` قرار می‌گیرد. این پروژه هیچ پورتی را روی سرور باز نمی‌کند؛ فقط Caddy مشترک پورت‌های ۸۰ و ۴۴۳ را باز می‌کند. پایگاه داده یا داخل همین پروژه است (پیش‌فرض) یا Postgres مشترک سرور. رمزها فقط در فایل `.env` روی سرور نگه داشته می‌شوند. همهٔ نتایج سامانه «شبیه‌سازی فرضی» هستند و این موضوع در بالای همهٔ صفحه‌ها نمایش داده می‌شود. زبان پیش‌فرض رابط کاربری انگلیسی است و با دکمهٔ «فارسی» در بالای صفحه به فارسی (راست‌به‌چپ) تغییر می‌کند و انتخاب کاربر در مرورگر ذخیره می‌شود.

The rest of this guide is in English so commands can be copied exactly.

## 0. What you need

| Item | Notes |
|---|---|
| Iranian VPS | Ubuntu 22.04/24.04 or Debian 12, at least 2 vCPU / 4 GB RAM for all five platforms (1 GB is enough for this app alone). Add 4 GB swap if RAM is tight. |
| Domain | One `.ir` domain from nic.ir. This app uses one subdomain, e.g. `election.example.ir`. |
| DNS | An `A` record `election` → the VPS public IPv4. |
| Docker | Docker Engine with the Compose plugin (`docker compose version`). |

## 1. Prepare the server (once, shared by every platform)

```bash
# Docker (Iranian mirrors are used below if download.docker.com is blocked)
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 || sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

# Swap (skip if the VPS already has it)
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Firewall: only SSH, HTTP, HTTPS
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

### Docker Hub / PyPI / npm from Iran

Docker Hub refuses pulls from Iranian IP addresses, and PyPI/npm can be slow or blocked. Use an Iranian mirror. These were listed in provider documentation on 16 Oct 2026; check that they still work before relying on them:

```bash
# Docker Hub mirror for the whole daemon (back up any existing daemon.json first)
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true
echo '{ "registry-mirrors": ["https://docker.arvancloud.ir", "https://docker-mirror.liara.ir", "https://hub.hamdocker.ir"] }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
docker info | grep -A3 "Registry Mirrors"
```

For Python and npm packages used during the image build, set these in `.env` (step 3):

```
PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
NPM_REGISTRY=https://package-mirror.liara.ir/repository/npm/
```

A mirror is a third party. If you prefer, build the images in GitHub Actions or on another machine, `docker save` them, copy them to the VPS with `scp`, and `docker load` them there.

### Shared network and shared Caddy (once per server)

Every platform joins one external Docker network named `caddy`. One Caddy container is the only thing that listens on ports 80 and 443 and gets HTTPS certificates for all subdomains.

```bash
docker network create caddy
sudo mkdir -p /srv/caddy && cd /srv/caddy
cat > docker-compose.yml <<'YAML'
services:
  caddy:
    image: caddy:2-alpine
    container_name: caddy
    restart: unless-stopped
    ports: ["80:80", "443:443", "443:443/udp"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks: [caddy]
networks:
  caddy:
    external: true
volumes:
  caddy_data:
  caddy_config:
YAML
printf '{\n\temail you@example.com\n}\n\n' > Caddyfile
```

Append this app's site block (a copy is in `deploy/Caddyfile.shared.example`), replacing the hostname:

```
election.example.ir {
	encode gzip
	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		X-Frame-Options DENY
		-Server
	}
	reverse_proxy electionsim-web:3000 {
		header_up X-Forwarded-For {remote_host}
		header_up X-Real-IP {remote_host}
		health_uri /health
		health_interval 30s
	}
}
```

```bash
docker compose up -d                                          # first time
docker exec caddy caddy reload --config /etc/caddy/Caddyfile  # after each edit
```

Caddy gets the certificate from Let's Encrypt automatically once DNS points at the VPS. If Let's Encrypt is unreachable from the VPS, ask the hosting provider for a certificate (or use ArvanCloud's CDN with its certificate in front of the server) and configure `tls /path/cert.pem /path/key.pem` in the site block.

## 2. Get the code

```bash
sudo mkdir -p /srv/electionsim && sudo chown "$USER" /srv/electionsim
git clone https://github.com/meysamghf-spec/ElectionSimulationAI.git /srv/electionsim
cd /srv/electionsim
```

(A private repository needs a read-only deploy key or token. Copying a zip of the repository also works.)

## 3. Configure secrets in `.env`

Secrets live only in `/srv/electionsim/.env` on the server. It is git-ignored. Never commit it.

```bash
cp .env.example .env
chmod 600 .env
openssl rand -base64 36 | tr -d '/+=@:?#'   # run once per secret and paste the result
```

Set at least:

```
SITE_ADDRESS=election.example.ir
AUTH_MODE=accounts
POSTGRES_PASSWORD=<long random value, no @ : / ? #>
INITIAL_ADMIN_EMAIL=you@example.com
INITIAL_ADMIN_PASSWORD=<long random value>
# optional Iranian mirrors, see step 1
PIP_INDEX_URL=
NPM_REGISTRY=
DEFAULT_LOCALE=en        # or fa to show Persian to first-time visitors
```

Leave `LLM_API_KEY` empty. The built-in deterministic parser works without any AI provider, and OpenAI-style providers are not reachable from Iran. If you later use an Iranian OpenAI-compatible provider, set `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.

Check the configuration without printing secrets:

```bash
set -a; . ./.env; set +a
ENVIRONMENT=production DATABASE_URL="postgresql+psycopg://election:${POSTGRES_PASSWORD}@db:5432/election" \
  CORS_ORIGINS="https://${SITE_ADDRESS}" TRUSTED_PROXY_CIDRS=172.28.10.10/32 API_INTERNAL_URL=http://api:8000 \
  python3 deploy/check_production_env.py
```

(Needs Python with `pydantic-settings` installed. You can skip it: the API also refuses to start in production with weak settings.)

## 4. Start

Bundled database (simplest):

```bash
docker compose --profile production up -d --build
docker compose --profile production ps
```

Shared PostgreSQL instead (one Postgres container for all platforms, attached to an external network `postgres`, no published port):

```bash
# once, in the shared Postgres container:
docker exec -it postgres psql -U postgres -c "CREATE ROLE electionsim LOGIN PASSWORD '<long password>';" \
  -c "CREATE DATABASE electionsim OWNER electionsim;"
# in .env:
#   DATABASE_URL=postgresql+psycopg://electionsim:<long password>@postgres:5432/electionsim
#   SHARED_DB_NETWORK=postgres
docker compose -f docker-compose.yml -f docker-compose.shared-db.yml --profile production up -d --build
```

What runs where:

| Container | Networks | Host ports |
|---|---|---|
| `db` (bundled mode only) | `data` (internal, no internet) | none |
| `api` (FastAPI) | `data` + `internal` (or `internal` + shared `postgres`) | none |
| `web` (Next.js) | `internal` (fixed IP 172.28.10.10) + shared `caddy` as `electionsim-web` | none |

Only the shared Caddy publishes ports. The API trusts `X-Forwarded-For` only from the web container's fixed address. If another project on the server already uses subnet `172.28.10.0/24`, change that project. This app's tests expect this subnet.

## 5. First sign-in

1. Open `https://election.example.ir`, then sign in with `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`.
2. Remove `INITIAL_ADMIN_PASSWORD` from `.env`, set `EXISTING_USERS=true`, and run `docker compose --profile production up -d` again.
3. Add more users without public signup: `docker compose --profile production exec -e CREATE_USER_EMAIL=a@b.ir -e CREATE_USER_PASSWORD='…' api python -m app.auth.cli`.

Public self-registration is disabled on purpose. There is no email verification or password reset (no SMTP).

## 6. Health checks and monitoring

| URL | Meaning |
|---|---|
| `https://election.example.ir/health` | 200 `{"status":"ok","web":"ok","api":"ok"}` when the site, API, and database are up; 503 otherwise. Use it for uptime monitors. |
| `http://api:8000/health` (inside Docker) | API + database check. |
| `/api/v1/health`, `/api/v1/ready` | API liveness and readiness (also used by the container health checks). |

```bash
docker compose --profile production logs -f --tail=100 api web
```

## 7. Updates, backups, rollback

```bash
cd /srv/electionsim && git pull && docker compose --profile production up -d --build
deploy/backup.sh                       # bundled db: writes /var/backups/electionsim/election-*.dump
deploy/restore-scratch.sh <dump>       # proves a dump restores, without touching the live db
```

Copy dumps off the VPS. For a shared Postgres, back up from the shared container with `pg_dump -U electionsim -d electionsim -Fc`. The timer files in `deploy/` run the backup daily (see `docs/backup.md`).

Rollback: `git checkout <previous tag or commit>` and run `up -d --build` again. Migrations only add tables, so no data is lost.

## 8. Content and legal notes

- Every page shows a fixed banner (Persian and English): results are hypothetical simulations, not official results, polls, or real predictions. Every export and API result carries `"hypothetical": true`.
- Use hypothetical candidates and regions only. Do not present outputs as forecasts of any real Iranian election.
- The interface is English (LTR) by default with a فارسی (Persian, RTL) toggle in the header; the choice is saved in the browser. The detailed configuration editor, results dashboard, and import screens are still in English in both modes.
