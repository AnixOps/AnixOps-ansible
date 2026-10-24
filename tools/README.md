# tools/ — operator helper scripts | 运维辅助脚本

Standalone helpers that run on the operator's workstation, not on managed hosts.
Install their Python dependencies with `pip install -r requirements.txt`
(or `scripts/anixops.sh setup`). Every script prints usage with `--help`.

## generate_inventory.py

Renders `inventories/production/hosts.yml` from `inventories/production/servers-config.yml`,
filling host addresses from environment variables (`.env` locally, GitHub secrets in CI).
`python3 tools/generate_inventory.py local|github-actions [--output PATH] [--check]`.
`--check` exits 1 when the committed `hosts.yml` differs from the rendered output; this is the
inventory drift gate used by `make check-inventory` and `scripts/anixops.sh doctor`. Both modes
read `SSH_KEY_PATH` (default `~/.ssh/id_rsa`). Use `scripts/anixops.sh gen-inventory` to
regenerate the committed file with a diff preview.

## cloudflare_manager.py

Manages Cloudflare DNS records and the orange-cloud proxy flag for the project's domains:
create/update A and AAAA records, toggle proxying, and batch-apply a list of records. Reads
`CLOUDFLARE_API_TOKEN` (and optionally `CLOUDFLARE_ZONE_ID`) from the environment or `.env`.
Without arguments it starts an interactive menu; with `--help` it lists the batch sub-commands.
Changes are made against the live Cloudflare API, so run it with care.

## ssh_key_manager.py

Finds (or generates) the operator's SSH private key, validates its format, and uploads it as a
GitHub Actions secret (default name `SSH_PRIVATE_KEY`) using libsodium sealed boxes via PyNaCl,
which is what the GitHub API requires. `python3 tools/ssh_key_manager.py --key-file ~/.ssh/id_ed25519
--repo owner/repo --token ghp_...`; omit the options for the interactive wizard. The private key
never leaves the machine unencrypted.

## ssh_key_deployer.py

Pushes an SSH public key to one or many servers (IPv4 and IPv6) before Ansible can reach them,
using `ssh-copy-id` where available and an `scp` + `ssh` fallback otherwise (paramiko/scp).
Hosts can be typed interactively or read from `.env` host variables. Useful for bootstrapping a
freshly reinstalled host that still only accepts password authentication.

## secrets_uploader.py

Bulk-uploads the variables of a `.env` file to GitHub repository secrets so the workflows in
`.github/workflows/` can render the inventory. Supports include/exclude patterns, skips comments and
empty values, shows a dry-run summary before uploading, and asks for confirmation. Requires a GitHub
token with `repo` scope (`--token` or `GITHUB_TOKEN`).

## encode_ssl_cert.sh

Encodes a PEM certificate chain and its private key as single-line base64 for storage in `.env`
(`SSL_CERTIFICATE_PEM`, `SSL_CERTIFICATE_KEY_PEM`) or as CI secrets:
`tools/encode_ssl_cert.sh fullchain.pem privkey.pem [--write]`. With `--write` it updates the
variables in the project's `.env` in place after taking a timestamped backup of the file.
