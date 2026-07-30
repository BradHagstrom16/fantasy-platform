# Origin Cloak — DigitalOcean Cloud Firewall Runbook

**Backlog item:** 2.6 (`docs/engineering-backlog-2026-07-21.md`) · **Decision record:** ADR-043
**Created:** 2026-07-30 · **This doc is living** — it is the runbook for the initial rollout AND for every future Cloudflare range refresh (§9).

## 1. Goal and evidence

Restrict inbound 80/443 on the production droplet (`104.131.28.136`) to Cloudflare's
published IP ranges, so direct-to-origin traffic can no longer bypass Cloudflare's
WAF/DDoS layer. This is defense-in-depth for the origin itself — rate limiting already
handles direct traffic correctly (backlog 2.5's realip config keys it by true peer IP).

Not theoretical: on 2026-07-30, within a 10-minute window of the 2.5 verification,
the access log showed scanners hitting the bare origin IP directly — `43.164.129.191`
got a 301+200 with referer `http://104.131.28.136:80`, and `112.140.195.13` got a 400.

## 2. Who does what

- **Agent** — all repo files, the verification probes (§6), the rollback-drill probes
  (§7), and diff-checking every chip list Brad pastes back **before** he clicks Create.
- **Brad** — every DigitalOcean dashboard click (the agent cannot reach the dashboard,
  and `sudo` on the droplet needs Brad's interactive TTY anyway).

## 3. Safety model — read before clicking anything

- **The SSH rule is the one step that cannot be gotten wrong.** A DO Cloud Firewall is
  default-deny inbound once attached. The create form pre-fills an SSH rule
  (TCP 22 from All IPv4 + All IPv6) — **verify that row exists before clicking Create
  Firewall** (§5, checkpoint). Without it, SSH is locked out and the agent cannot
  recover it (no sudo, no dashboard).
- **Rollback needs no SSH:** firewall page → **Droplets** tab → trash icon next to the
  droplet. Traffic restores because ufw underneath still allows everything (the cloud
  firewall is the narrower *outer* gate; effective policy is the intersection).
- **Break-glass:** the DO **Recovery Console** (droplet page → Access → Launch Recovery
  Console) works regardless of firewall rules.
- **UptimeRobot symptom:** `cccfantasy.com` going red while the droplet itself looks
  healthy is the signature of a stale or bad allowlist (Cloudflare can't reach the
  origin → visitors see 522s). **Detach the droplet first, debug second.**
- **`sudo ufw status` will still show `Nginx Full ALLOW Anywhere` forever.** Expected —
  ufw is deliberately untouched (ADR-043). Do not "fix" it; do not tighten ufw to
  match. Two independently-maintained allowlists = two ways to hard-block users.
- **Rule deletions in the DO UI are immediate, with no confirmation dialog.** Edit the
  firewall carefully; there is no undo besides re-entering the rule.
- **Union semantics:** if a second firewall is ever attached to the droplet, DO applies
  the union of all rules — a permissive second firewall silently un-cloaks the origin.
  Keep exactly one firewall on this droplet.

## 4. The Cloudflare range list (paste source)

Fetched 2026-07-30 from https://www.cloudflare.com/ips-v4 + /ips-v6 (15 IPv4 + 7 IPv6).
Test-locked: `tests/test_client_ip_keying.py::TestFirewallRunbookRangeSync` asserts this
block equals `CLOUDFLARE_RANGES`, which the existing locks tie to `deploy/nginx.conf`.
The droplet has no global IPv6 address (verified 2026-07-30), so the v6 entries are
currently inert — they are included so every mirror of this list stays byte-identical.

<!-- CF-RANGES-START -->
173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22
2400:cb00::/32
2606:4700::/32
2803:f800::/32
2405:b500::/32
2405:8100::/32
2a06:98c0::/29
2c0f:f248::/32
<!-- CF-RANGES-END -->

## 5. Task 1 (Brad): create the firewall

Everything happens in the **single create form** — never create a firewall with default
rules and edit it afterwards; the moment a default firewall attaches, 80/443 are blocked
entirely until the rules are added.

- [ ] **Step 1: Open the create form**

1. DigitalOcean dashboard → left sidebar **Networking** → **Firewalls** tab
2. Click **Create Firewall**
3. **Name:** `fantasy-platform-fw`

- [ ] **Step 2: CHECKPOINT — confirm the SSH rule exists**

Under **Inbound Rules**, the form pre-fills one row:
`SSH · TCP · 22 · All IPv4, All IPv6`

**Do not proceed until this row is present.** Leave it exactly as-is. This row is what
keeps SSH reachable after the firewall attaches.

- [ ] **Step 3: Add the HTTP rule (port 80, Cloudflare only)**

1. Under **Inbound Rules**, open the **New rule** dropdown → select **HTTP**
   (fills in TCP/80 with sources `All IPv4, All IPv6`)
2. Click into the row's **Sources** field and **delete the `All IPv4` and `All IPv6`
   chips** — this is the critical step: leaving either chip makes the cloak a silent
   no-op
3. Paste the 22 ranges from §4 into the Sources field. Try pasting the whole list at
   once — if the field doesn't tokenize them into separate chips, enter them one per
   line, pressing Enter after each
4. **Expected result: exactly 22 chips, no `All IPv4`/`All IPv6` chip present**
5. Copy the chip list and paste it back to the agent for a diff-check

- [ ] **Step 4: Add the HTTPS rule (port 443, Cloudflare only)**

Repeat Step 3 with **New rule → HTTPS** (TCP/443). Same 22 chips, same paste-back.

- [ ] **Step 5: Leave Outbound Rules untouched**

The form pre-fills allow-all outbound (ICMP, all TCP, all UDP to all destinations).
Leave all three rows exactly as-is — they carry the droplet's outbound traffic to
Managed Postgres (:25060), Brevo SMTP (:2525), and every vendor API the sync timers
call. The firewall is stateful, so replies to these connections need no inbound holes.

- [ ] **Step 6: Apply to the droplet**

Under **Apply to Droplets**, type `fantasy-platform` and select the droplet
(confirm the row shows `104.131.28.136`).

- [ ] **Step 7: Pre-create checklist, then create**

Verify all four before clicking:
1. Inbound: exactly **3 rows** — SSH (22, All IPv4+IPv6), HTTP (80, 22 chips),
   HTTPS (443, 22 chips)
2. Outbound: **3 default rows**, untouched
3. Droplets: exactly **1** (`fantasy-platform`)
4. The agent has confirmed both pasted chip lists match the pinned ranges

Click **Create Firewall**. The rules enforce as soon as the firewall attaches.

## 6. Task 2 (agent): verification probes

Reference before-state (captured 2026-07-30 20:20 UTC, pre-firewall):
bare-IP http → `HTTP/1.1 301` with `Server: nginx/1.24.0 (Ubuntu)`; bare-IP https
(`-k`) → `HTTP/2 200`; `https://cccfantasy.com/` → `HTTP/2 200`, `server: cloudflare`.

After Create, run (allow up to ~60s for propagation before declaring failure — DO does
not document the timing):

```bash
curl -sI -m 10 http://104.131.28.136/ ; echo "exit=$?"      # expect: no output, exit=28
curl -skI -m 10 https://104.131.28.136/ ; echo "exit=$?"    # expect: no output, exit=28
curl -sI -m 10 https://cccfantasy.com/ | head -3            # expect: HTTP/2 200, server: cloudflare
ssh -o BatchMode=yes deploy@104.131.28.136 'echo ssh-ok'    # expect: ssh-ok
ssh -o BatchMode=yes deploy@104.131.28.136 \
  "ss -tn state established '( dport = :25060 )' | head -3" # expect: rows → outbound DB alive
```

Reading the probe results: **exit=28 (timeout) is the success signature** — the packet
was *dropped* at DO's network layer. A "connection refused" instead means the packet
reached the droplet and nginx is down — a different problem; don't touch the firewall.

## 7. Task 3 (both, recommended): rollback drill

Prove the emergency lever once, calmly, before it's ever needed in anger — and measure
the one number DO doesn't publish (detach-to-restore latency):

1. **Brad:** firewall page → **Droplets** tab → trash icon → remove the droplet
2. **Agent:** probe `curl -sI -m 5 http://104.131.28.136/` in a loop; record how long
   until it returns `301` again
3. **Brad:** **Add Droplets** → re-attach `fantasy-platform`
4. **Agent:** confirm the probe times out again (exit=28) and `https://cccfantasy.com`
   still returns 200

## 8. Rollback (real emergencies)

- **Restore traffic:** firewall page → **Droplets** tab → trash icon next to
  `fantasy-platform`. No SSH needed; ufw still allows everything, so service restores
  as soon as DO propagates the detach (latency measured in §7).
- **Remove entirely:** firewall page → **More** menu → **Destroy** → **Confirm**
  (droplets are never affected by destroying a firewall).

## 9. Range-refresh recipe (when Cloudflare changes its published ranges)

A stale allowlist here **hard-blocks legitimate Cloudflare traffic** (users see 522s) —
unlike the realip list, which fails soft. Refresh **all four places together**:

1. Fetch: `curl -s https://www.cloudflare.com/ips-v4 https://www.cloudflare.com/ips-v6`
2. `deploy/nginx.conf` — the `set_real_ip_from` block (recipe in its realip comment;
   reinstall per that file's header)
3. `tests/test_client_ip_keying.py` — `CLOUDFLARE_RANGES`
4. This doc — the §4 marker block
   (2–4 are equality-locked by pytest; a partial refresh fails CI)
5. **The dashboard** — firewall → **Rules** tab → edit the HTTP rule's sources → update
   chips → save → repeat for HTTPS. The live firewall is the one mirror no test can
   see; it only changes when someone performs this step.
6. Re-run the §6 probes.

## 10. Troubleshooting

| Symptom | Likely cause | Lever |
|---|---|---|
| UptimeRobot red / visitors see 522, droplet healthy | Stale or mistyped allowlist blocking Cloudflare | Detach droplet (§8), then fix chips and re-attach |
| SSH refused/timing out | SSH rule missing or edited | DO Recovery Console (§3); re-add `TCP 22 All IPv4+IPv6` in dashboard |
| Bare-IP probes suddenly return 301 again / scanners reappear in access log | Firewall detached, destroyed, or a second permissive firewall attached (union semantics) | Firewalls page: confirm exactly one firewall, attached, rules intact |
| Bare-IP probe says "connection refused" (not timeout) | nginx down — packet reached the droplet | App-side debugging; the firewall is not the problem |
| Emails/DB/API syncs failing after firewall work | Outbound rules were edited | Restore allow-all outbound (ICMP + all TCP + all UDP) |
