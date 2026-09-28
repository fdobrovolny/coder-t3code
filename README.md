# Coder T3 Code Module

Install and run [T3 Code](https://github.com/pingdotgg/t3code) in a Coder workspace, using the same Terraform module structure as [coder-opencode](https://github.com/fdobrovolny/coder-opencode).

- **T3 Code Web** opens the browser UI through Coder's app proxy, with owner-only access by default.
- **T3 Code Pair** opens a terminal and generates a fresh one-time browser pairing token.

## Usage

Reference a tagged release to keep module updates predictable:

```hcl
module "t3code" {
  source = "git::https://github.com/fdobrovolny/coder-t3code.git?ref=v0.2.0"

  agent_id = coder_agent.main.id
  workdir  = "/home/coder/project"
}
```

For local development, use `source = "../coder-t3code"`. If uploading a template with a local module source to Coder, include the module inside the template archive and adjust the relative path.

## Requirements

- Terraform 1.9 or newer and the Coder provider (2.13 or newer).
- A Linux workspace supported by T3 Code's standalone installer, with Bash, curl, tar, base64, `flock` (util-linux), and sha256sum or shasum. The standalone runtime does not require Node.js or npm.
- Coder's [wildcard access URL](https://coder.com/docs/admin/networking/wildcard-access-url). This module requires subdomain apps because T3 Code uses root-relative routes.
- At least one supported provider installed and authenticated in the workspace; see [T3 Code provider setup](https://github.com/pingdotgg/t3code/blob/main/docs/user/install.md). Provider installation and credentials are managed separately, for example in `pre_install_script` or your workspace image.

## First connection

1. Wait for workspace startup to finish.
2. Open **T3 Code Pair** and copy the value printed after `Token:`.
3. Open **T3 Code Web**. On that Coder app's origin, navigate to `/pair#token=<TOKEN>`, replacing `<TOKEN>` with the copied token. For example: `https://<your-coder-app-subdomain>/pair#token=<TOKEN>`.
4. Add your project directory in T3 Code's UI, or run `t3 project add /home/coder/project` in the workspace terminal.

The URL printed by `t3 pair` uses `127.0.0.1`, which refers to your browser's own machine. Replace that origin with the Coder app origin, preserving `/pair#token=...`. Pairing links are one-time credentials; generate another for each new browser/device. Keep tokens private. By default, Coder proxy authentication and T3 Code's own pairing both apply.

The module uses `t3 serve`, which does not open a browser or automatically register the working directory as a project. `workdir` sets the server's initial directory and is created during installation.

## Native clients and public access

Set `public_access = true` to allow desktop and mobile clients to reach the web UI and backend without a Coder login:

```hcl
module "t3code" {
  source = "git::https://github.com/fdobrovolny/coder-t3code.git?ref=v0.2.0"

  agent_id      = coder_agent.main.id
  workdir       = "/home/coder/project"
  public_access = true
}
```

This sets the web app's [Coder sharing level](https://registry.terraform.io/providers/coder/coder/latest/docs/resources/app) to `public`. T3 Code's own pairing and authentication still apply, and the pairing terminal remains owner-only. The default `false` requires the workspace owner's Coder login. This setting affects the entire web app, including its backend API; it does not create a separate backend endpoint.

Use a fresh pairing link with the HTTPS Coder app origin in place of `127.0.0.1`, as described above. The client must be able to resolve and reach that hostname, and any reverse proxy in front of Coder must allow access without an additional browser login. Your Coder deployment must permit public app sharing.

“Public” removes Coder's login requirement; it does not change network reachability. If the app hostname is reachable only over Tailscale, access remains limited by your tailnet rules. If that hostname is internet-accessible, anyone can reach the T3 endpoint, with T3 authentication protecting authenticated operations. The server continues listening on loopback behind Coder's proxy.

## Configuration

| Input | Default | Purpose |
| --- | --- | --- |
| `agent_id` | required | Coder agent ID |
| `workdir` | required | Server working directory |
| `t3code_version` | `latest` | Stable release on first installation, or an exact version such as `0.0.42` |
| `install_t3code` | `true` | Install T3 Code; set false for a preinstalled `t3` on PATH |
| `enable_web` | `true` | Start the server and create web and pairing apps |
| `public_access` | `false` | Allow web UI/backend access without a Coder login; T3 pairing still applies |
| `web_port` | `3773` | Loopback HTTP/WebSocket port |
| `subdomain` | `true` | Must be true when web support is enabled |
| `web_app_display_name` | `T3 Code Web` | Web app label |
| `pair_app_display_name` | `T3 Code Pair` | Pairing terminal label |
| `icon` | `/icon/terminal.svg` | App and startup script icon |
| `order`, `group` | `null` | Coder app ordering and grouping |
| `pre_install_script`, `post_install_script` | `null` | Custom Bash installation hooks |

`latest` preserves an existing installation. An explicit version pin installs that version when it differs from the installed one. Version changes take effect when the server is restarted; restart the workspace after changing a pin. When installation is disabled, the supplied binary's version is your responsibility.

The installer uses [T3 Code's official installation script](https://t3.codes/install.sh), which downloads and verifies a standalone release. It installs `t3` under `$HOME/.local/bin` and links it into `CODER_SCRIPT_BIN_DIR` for Coder terminal sessions. T3 Code stores its state under `$HOME/.t3` by default; persist this directory to retain projects and pairing sessions. This module supports one T3 Code instance per workspace user.

The server binds to `127.0.0.1`, starts in the background, and is checked through `/.well-known/t3/environment`. Startup is serialized with `flock`; repeated startup reuses the recorded live server. Startup fails on early process exit or after a 60-second readiness timeout.

Scripts and logs live under `$HOME/.coder-modules/fdobrovolny/t3code/`. Server output is in `logs/server.log`, with owner-only permissions because headless startup prints pairing credentials. The `scripts` output exposes ordered `coder exp sync` names for downstream startup dependencies, using [`coder-utils`](https://registry.coder.com/modules/coder/coder-utils).

Set `enable_web = false` for installation only. This omits both apps and the server startup script.

## Validation

```sh
terraform init -backend=false
terraform fmt -check
terraform validate
terraform test
python3 tests/test_scripts.py
```

Tests cover owner-only defaults, opt-in public access, pairing terminal privacy, app configuration, invalid inputs, install-only mode, pinned installation reuse, CLI linking, duplicate startup, occupied ports, early server failure, and log permissions. The shell tests use Terraform-rendered templates and isolated fake executables.

The standalone T3 Code 0.0.42 release was also checked locally for server startup, web UI delivery, environment discovery, and pairing-token generation. End-to-end access through a deployed Coder wildcard proxy still needs validation in your Coder installation.

## Attribution and license

Adapted from [fdobrovolny/coder-opencode](https://github.com/fdobrovolny/coder-opencode), itself derived from the [Coder Registry's coder-labs/opencode module](https://github.com/coder/registry/tree/main/registry/coder-labs/modules/opencode). Licensed under [Apache-2.0](LICENSE). T3 Code is a separate upstream project with its own license.
