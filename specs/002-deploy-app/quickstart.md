# Operator Runbook: Deploy the Clinic Scheduling App

This is the step-by-step guide an operator follows to take a **fresh Linux server** to a **live,
HTTPS-secured, healthy** production instance — and to back it up, restore it, and update it. You do
**not** need prior DevOps or container experience. Every step ends with a **✅ Verify** check; do not
proceed until it passes. Each step also lists **⚠ If it fails** remedies.

> Target time to live: under 60 minutes (SC-001). Work top-to-bottom.

---

## What you need before starting (Dependencies)

- A **domain name** you control with editable DNS (e.g. `clinic.example.com`).
- A **fresh Linux VM** (Ubuntu 22.04 or 24.04 LTS), with a public IP and ports **80**, **443**,
  and **22 (SSH)** open inbound.
- SSH access to that server as a user with `sudo`.
- The application source (this repository).

---

## Step 0 — Choose a server (free option for the first clinic)

This runbook runs on **any** single Ubuntu VM. For a **free** initial deploy of one clinic, the
recommended host is the **Oracle Cloud "Always Free" Ampere A1 (ARM) VM** — it is the only free tier
that runs this stack as designed (a real VM with self-hosted PostgreSQL 16 + `btree_gist`, the
extension behind the no-double-booking guarantee). A free **2 OCPU / 12 GB RAM / 200 GB** ARM
instance is far more than this pilot needs (~4 GB).

- Pick a region with low latency to your clinics (EU — Frankfurt/Amsterdam — or Jeddah/UAE are
  closest to Egypt). ARM capacity can be scarce at signup; retry or choose a less-busy region.
- **Avoid free PaaS tiers (Render/Railway free) for a real clinic**: their free Postgres expires
  (~30 days = data loss) and web services sleep on idle — unacceptable for live patient data.
- **Off-box backups are mandatory here**: Oracle may reclaim *idle* Always-Free instances, so keep
  the encrypted `*.dump.age` artifacts and the `age` private key on another machine (Step 8).

> **Oracle-specific gotchas** (handled in the steps below):
> - Oracle VMs are **ARM (aarch64)** → build images for `linux/arm64` (Step 4). All base images
>   used here (`postgres:16`, `caddy:2`, Python) have ARM builds.
> - Oracle **blocks ports 80/443 by default** in two places — the cloud **Security List/NSG** *and*
>   the instance's local `iptables` (Step 5). Both must be opened or HTTPS will hang.

When the pilot grows or you want to stop self-administering, move to a ~€4–5/mo Hetzner VM — the
same Compose stack, no changes.

---

## Step 1 — Provision the server (install Docker)

SSH into the server, then install Docker Engine + the Compose plugin and enable it on boot:

```bash
sudo apt-get update
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"    # log out/in once so docker runs without sudo
```

Also install `age` (for encrypted backups) and `git`:

```bash
sudo apt-get install -y age git
```

**✅ Verify**

```bash
docker --version && docker compose version && age --version && git --version
```

All four print a version. `docker run --rm hello-world` prints a success message.

**⚠ If it fails**
- *`docker: permission denied`* → you haven't re-logged in after `usermod`. Log out and back in, or
  run `newgrp docker`.
- *`docker compose: not found`* → the Compose **plugin** didn't install; re-run the Docker install
  script (`get.docker.com` bundles it) — do not install the old `docker-compose` v1 binary.

---

## Step 2 — Point your domain at the server

In your DNS provider, create an **A record** for your domain (e.g. `clinic.example.com`) pointing to
the server's public IPv4 address (and an **AAAA** record if you have IPv6).

**✅ Verify** — from your laptop (not the server):

```bash
dig +short clinic.example.com      # must print your server's public IP
```

**⚠ If it fails**
- *No output or wrong IP (DNS not propagated)* → propagation can take minutes to a couple of hours.
  Wait and re-check. **Do not request a certificate (Step 5) until this resolves** — certificate
  issuance will fail if the domain doesn't yet point to the server (edge case: domain/DNS not
  propagated).

---

## Step 3 — Get the code and create your secrets file

On the server:

```bash
sudo mkdir -p /srv/clinic/backups && sudo chown -R "$USER" /srv/clinic
git clone <YOUR_REPO_URL> /srv/clinic/app
cd /srv/clinic/app/deploy
cp .env.example .env
```

Generate strong secrets and an `age` key for backups:

```bash
# session secret (>= 16 chars) and DB password
echo "SESSION_SECRET=$(openssl rand -base64 48 | tr -d '\n')"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)"

# backup encryption key — SAVE the private key somewhere safe and OFF the server
age-keygen -o /srv/clinic/backup-key.txt        # prints the public key (age1...)
```

Edit `deploy/.env` and set, at minimum:

```
DOMAIN=clinic.example.com
POSTGRES_PASSWORD=<the generated password>
DATABASE_URL=postgresql+psycopg://postgres:<the generated password>@db:5432/clinic
SESSION_SECRET=<the generated session secret>
COOKIE_SECURE=true
SUPERADMIN_EMAIL=you@example.com
SUPERADMIN_PASSWORD=<a temporary password, 12+ chars>
BACKUP_AGE_RECIPIENT=<the age1... public key printed above>
```

**✅ Verify**

```bash
git -C /srv/clinic/app check-ignore deploy/.env   # prints "deploy/.env" → it is gitignored
test $(grep -c . deploy/.env) -ge 8 && echo "env populated"
```

`.env` is ignored by git (so secrets are never committed — FR-003/SC-007) and has your values.

**⚠ If it fails**
- *`check-ignore` prints nothing* → `.env` is **not** ignored. Stop. Confirm the root `.gitignore`
  contains `.env` and `.env.*` before continuing; never `git add` this file.
- *Weak/placeholder secret* → the app will refuse to start later (by design). Use the generated
  values, not the dev defaults.

---

## Step 4 — Build and start the stack

From `/srv/clinic/app/deploy`:

```bash
docker compose build
docker compose up -d
```

> **On an Oracle/ARM (aarch64) VM**: the images build natively for ARM — no flag needed when you
> build *on* the server (as above). Only if you build on an x86 machine and push to an ARM host do
> you need `docker build --platform linux/arm64 …`. Confirm the host arch with `uname -m` → `aarch64`.

On first start the backend automatically runs database migrations (`alembic upgrade head`),
creating the schema, the `btree_gist` extension, the no-double-booking exclusion constraint, and the
tenant-isolation backstops — no manual SQL (FR-004).

**✅ Verify**

```bash
docker compose ps          # caddy, backend, db all "running"/"healthy"
docker compose logs backend | grep -i "Application startup complete"
```

`db` shows `healthy`, and the backend log shows Alembic running migrations then uvicorn startup.

**⚠ If it fails**
- *Backend keeps restarting with a config error* → a missing/short `SESSION_SECRET` or a malformed
  `DATABASE_URL` (must start `postgresql+psycopg://`). Fix `.env`, then `docker compose up -d`.
- *Migration fails mid-deploy* → the backend exits and does **not** serve a half-upgraded schema.
  Read `docker compose logs backend`, fix the cause, and re-run `docker compose up -d` (migrations
  are idempotent). If needed, restore the last good backup (Step 8) before retrying.
- *`db` unhealthy* → wrong `POSTGRES_PASSWORD` vs `DATABASE_URL`; make them match and recreate:
  `docker compose down && docker compose up -d`.

---

## Step 5 — Confirm HTTPS is live with a valid certificate

Caddy automatically obtains a Let's Encrypt certificate for your `DOMAIN` on first request and
redirects HTTP→HTTPS.

> **Oracle Cloud first**: open ports 80/443 in **both** places, or this step will hang:
> 1. **Cloud firewall** — in the OCI console, add **Ingress rules** to the subnet's *Security List*
>    (or the instance's *NSG*) allowing TCP **80** and **443** from `0.0.0.0/0`.
> 2. **Instance firewall** — Oracle Ubuntu images ship restrictive `iptables`:
>    ```bash
>    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
>    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
>    sudo netfilter-persistent save        # persist across reboots
>    ```

**✅ Verify** — from your laptop:

```bash
curl -I https://clinic.example.com/api/v1/health   # HTTP/2 200, valid TLS (no -k needed)
curl -I http://clinic.example.com                  # 308/301 redirect to https://
```

Open `https://clinic.example.com` in a browser: it loads with a padlock and **no security warning**
(SC-003).

**⚠ If it fails (certificate issuance)**
- *Cert error / connection refused on 443* → check `docker compose logs caddy`. Common causes:
  - **DNS not pointing here** → re-do Step 2's verify.
  - **Ports 80/443 blocked** → open them in the cloud firewall/security group. ACME needs port 80.
  - **Rate limit** (after many retries) → wait an hour before retrying; Let's Encrypt limits issuance.
- Caddy retries automatically once the cause is fixed — re-run the verify after a minute.

---

## Step 6 — Create the first administrator (bootstrap)

Create the platform super-admin so you can sign in immediately (FR-005). This reads
`SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` from `.env`:

```bash
docker compose exec backend python -m src.scripts.seed_superadmin
```

**✅ Verify** — it prints `Super-admin created: you@example.com (must change password on first
login)`. In the browser, sign in at `https://clinic.example.com` with those credentials; you are
prompted to change the password on first login.

**⚠ If it fails**
- *`SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD must be set`* → they're missing from `.env`; add them
  and re-run (the command is idempotent — safe to run again).
- *"already exists"* → the admin is already created; just log in.

---

## Step 7 — Smoke-test the live system (behavior gates)

Confirm the production instance still enforces every gate (FR-010, SC-003, SC-006). In the browser,
signed in as an admin:

1. Provision a center and a center-admin; sign in and **create one appointment** → it saves and is
   still visible after a page reload.
2. **Double-booking**: have two reception users try to book the same doctor/slot at once → exactly
   one succeeds; the other gets a clear "slot taken" message (never both).
3. **Cross-center isolation**: signed in as Center A, attempt to view Center B's data (e.g. by URL)
   → access is denied and no Center B data is shown.

**✅ Verify** — all three behave as above. Health stays green:
`curl -s https://clinic.example.com/api/v1/health` → `{"status":"ok","database":"up"}`.

**⚠ If it fails** — if a double-booking or cross-center read ever succeeds, **stop and do not go
live**; this is a release-blocking gate failure. Capture `docker compose logs backend` and escalate.

---

## Step 8 — Set up encrypted backups

Take an encrypted backup and confirm it exists (FR-008):

```bash
cd /srv/clinic/app/deploy
./ops/backup.sh        # writes /srv/clinic/backups/clinic-<UTC>.dump.age and prints the path
```

Schedule a daily backup with cron:

```bash
( crontab -l 2>/dev/null; echo "30 2 * * * cd /srv/clinic/app/deploy && ./ops/backup.sh" ) | crontab -
```

**✅ Verify**

```bash
ls -lh /srv/clinic/backups/           # a non-empty *.dump.age file
crontab -l | grep backup.sh           # the daily job is listed
```

**⚠ If it fails**
- *`backup.sh` aborts on the recipient* → `BACKUP_AGE_RECIPIENT` in `.env` must be the `age1...`
  **public** key from Step 3.
- Keep the **private** key (`backup-key.txt`) off the server in a safe place — without it backups
  cannot be restored.

### Restore drill (prove recovery — SC-004)

Periodically prove you can recover onto a clean instance:

```bash
./ops/restore.sh /srv/clinic/backups/clinic-<UTC>.dump.age
```

**✅ Verify** — after restore, appointment/account/audit counts match the source; staff data is
intact. (Practice this on a throwaway server, not production.)

**⚠ If it fails**
- *`age: no identity found`* → you must provide the correct private key (`backup-key.txt`) matching the public key used during backup.
- *`pg_restore: error`* → the target database must be clean/empty before restoring.

---

## Step 9 — Confirm reboot survival

```bash
sudo reboot
```

Wait ~1 minute, then from your laptop:

**✅ Verify**

```bash
curl -s https://clinic.example.com/api/v1/health   # {"status":"ok","database":"up"}
```

The stack came back automatically with no manual action (FR-007, SC-008).

**⚠ If it fails** — Docker isn't enabled on boot. Run `sudo systemctl enable docker` and reboot
again.

---

## Step 10 — Updating to a new version (when needed)

To deploy a new application version while preserving all data (FR-009, SC-005):

```bash
cd /srv/clinic/app/deploy
./ops/backup.sh                 # 1. always back up first
git -C /srv/clinic/app pull     # 2. get the new version
docker compose build            # 3. build new images
docker compose up -d            # 4. recreate; migrations auto-apply, data volume preserved
```

**✅ Verify**

```bash
docker compose ps                                   # all healthy
curl -s https://clinic.example.com/api/v1/health    # ok
```

Existing appointments/accounts are still present; downtime was under a few minutes.

**⚠ If it fails**
- *Migration error on the new version* → the new backend won't serve. Restore the pre-update backup
  (Step 8) and re-deploy the previous commit:
  `git -C /srv/clinic/app checkout <previous-commit> && docker compose up -d --build`.

---

## Day-to-day operations reference

| Task | Command (from `deploy/`) |
|------|--------------------------|
| View app logs (PHI-redacted) | `docker compose logs -f backend` |
| Check status / health | `docker compose ps` · `curl -s https://<DOMAIN>/api/v1/health` |
| Stop / start | `docker compose stop` · `docker compose up -d` |
| Backup now | `./ops/backup.sh` |
| Restore | `./ops/restore.sh <artifact>` |
| Update | see Step 10 |

When the app is briefly unavailable (e.g. during an update), visitors see a plain maintenance page,
not a technical error (FR-015). Application logs never contain patient identifiers or secrets
(FR-013).
