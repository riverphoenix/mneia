# Safety & Permissions

mneia includes a safety framework that classifies operations by risk level and requires appropriate authorization before execution.

## Risk Levels

| Level | Description | Approval |
|-------|-------------|----------|
| **LOW** | Read-only operations (search, stats, graph queries) | Auto-approved |
| **MEDIUM** | Web scraping, connector sync, entity extraction | Requires consent |
| **HIGH** | Live audio capture, bulk operations | Requires explicit approval |
| **CRITICAL** | Data purge, memory deletion | Always prompts |

## How It Works

Operations are decorated with `@requires_permission` which checks the `PermissionRegistry` before execution:

1. **LOW** risk operations run without prompting (configurable via `safety.auto_approve_low_risk`)
2. **MEDIUM** and **HIGH** operations check for a valid grant in the permissions database
3. **CRITICAL** operations always prompt, regardless of grants
4. **Blocked** operations in `safety.blocked_operations` are never allowed

## Managing Permissions

### Grant a Permission

```bash
mneia permission grant live_audio_capture
mneia permission grant web_scraping
```

Grants expire after `safety.approval_ttl_hours` (default: 24 hours).

### Revoke a Permission

```bash
mneia permission revoke live_audio_capture
```

### List Permissions

```bash
mneia permission list
```

Shows all active grants with their expiry times.

## Daemon Behavior

When the daemon encounters an operation that requires approval but has no grant:
- The operation is skipped with a warning log
- Other agents continue running normally
- No data is lost — the operation can be retried after granting permission

## Configuration

```bash
# Auto-approve all LOW risk operations (default: true)
mneia config set safety.auto_approve_low_risk true

# Set approval expiry time in hours (default: 24)
mneia config set safety.approval_ttl_hours 48

# Block specific operations entirely
# (edit config.json directly for list values)
```

## Permissions Database

Approvals are stored in `~/.mneia/data/permissions.db` with:
- Operation name
- Risk level
- Grant timestamp
- Expiry timestamp (based on TTL)
- Grant source (cli, daemon, etc.)

Expired approvals are automatically cleaned up.
