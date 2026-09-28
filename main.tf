# Adapted from fdobrovolny/coder-opencode, derived from Coder Registry's coder-labs/opencode module.

terraform {
  required_version = ">= 1.9"

  required_providers {
    coder = {
      source  = "coder/coder"
      version = ">= 2.13"
    }
  }
}

variable "agent_id" {
  description = "The ID of a Coder agent."
  type        = string
}

variable "order" {
  description = "The order determines the position of the apps in the Coder UI. The lowest order is shown first and apps with equal order are sorted by name."
  type        = number
  default     = null
}

variable "group" {
  description = "The name of the Coder app group that both T3 Code apps belong to."
  type        = string
  default     = null
}

variable "icon" {
  description = "The icon to use for the T3 Code apps and scripts."
  type        = string
  default     = "/icon/terminal.svg"
}

variable "workdir" {
  description = "The project directory in which T3 Code runs. It is created during installation if it does not exist."
  type        = string

  validation {
    condition     = trimspace(var.workdir) != ""
    error_message = "workdir must not be empty."
  }
}

variable "web_app_display_name" {
  description = "Display name for the T3 Code web app."
  type        = string
  default     = "T3 Code Web"
}

variable "enable_web" {
  description = "Whether to create the T3 Code web app and start its server."
  type        = bool
  default     = true
}

variable "public_access" {
  description = "Allow access to the web UI and backend through the Coder app proxy without a Coder login. T3 Code pairing still applies. The pairing terminal remains owner-only."
  type        = bool
  default     = false
  nullable    = false
}

variable "pair_app_display_name" {
  description = "Display name for the T3 Code pairing terminal app."
  type        = string
  default     = "T3 Code Pair"
}

variable "web_port" {
  description = "Port on which the T3 Code web server listens."
  type        = number
  default     = 3773

  validation {
    condition     = var.web_port >= 1 && var.web_port <= 65535 && floor(var.web_port) == var.web_port
    error_message = "web_port must be between 1 and 65535."
  }
}

variable "subdomain" {
  description = "Whether the T3 Code web app uses a subdomain. T3 Code requires subdomain mode because it does not support path-prefixed URLs."
  type        = bool
  default     = true

  validation {
    condition     = !var.enable_web || var.subdomain
    error_message = "subdomain must be true because T3 Code uses root-relative asset, API, and WebSocket URLs. Configure Coder's wildcard access URL."
  }
}

variable "pre_install_script" {
  description = "Custom script to run before installing T3 Code."
  type        = string
  default     = null
}

variable "post_install_script" {
  description = "Custom script to run after installing T3 Code."
  type        = string
  default     = null
}

variable "install_t3code" {
  description = "Whether to install T3 Code."
  type        = bool
  default     = true
}

variable "t3code_version" {
  description = "The version of T3 Code to install."
  type        = string
  default     = "latest"
}

locals {
  workdir = var.workdir == "/" ? "/" : trimsuffix(var.workdir, "/")
  install_script = templatefile("${path.module}/scripts/install.sh.tftpl", {
    ARG_INSTALL_T3CODE = tostring(var.install_t3code)
    ARG_T3CODE_VERSION = base64encode(var.t3code_version)
    ARG_WORKDIR        = base64encode(local.workdir)
  })
  start_script = var.enable_web ? templatefile("${path.module}/scripts/start.sh.tftpl", {
    ARG_WORKDIR  = base64encode(local.workdir)
    ARG_WEB_PORT = tostring(var.web_port)
  }) : null
}

module "coder_utils" {
  source  = "registry.coder.com/coder/coder-utils/coder"
  version = "0.0.1"

  agent_id            = var.agent_id
  module_directory    = "$HOME/.coder-modules/fdobrovolny/t3code"
  display_name_prefix = "T3 Code"
  icon                = var.icon
  pre_install_script  = var.pre_install_script
  install_script      = local.install_script
  post_install_script = var.post_install_script
  start_script        = local.start_script
}

# T3 Code uses root-relative routes and cannot run behind Coder's path-based app proxy.
resource "coder_app" "web" {
  count = var.enable_web ? 1 : 0

  agent_id     = var.agent_id
  slug         = "t3code-web"
  display_name = var.web_app_display_name
  url          = "http://localhost:${var.web_port}"
  icon         = var.icon
  subdomain    = var.subdomain
  share        = var.public_access ? "public" : "owner"
  order        = var.order
  group        = var.group
  open_in      = "tab"

  healthcheck {
    url       = "http://localhost:${var.web_port}/.well-known/t3/environment"
    interval  = 3
    threshold = 20
  }
}

resource "coder_app" "pair" {
  count = var.enable_web ? 1 : 0

  agent_id     = var.agent_id
  slug         = "t3code-pair"
  share        = "owner"
  display_name = var.pair_app_display_name
  command      = <<-EOT
    #!/bin/bash
    set -e
    export PATH="$HOME/.local/bin:$PATH"
    cd "$(echo -n '${base64encode(local.workdir)}' | base64 -d)"
    echo "Use the token below at your Coder T3 Code Web URL: /pair#token=<TOKEN>"
    t3 pair
    read -r -p "Press Enter to close this terminal."
  EOT
  icon         = var.icon
  order        = var.order
  group        = var.group
  open_in      = "slim-window"
}

output "scripts" {
  description = "Ordered list of coder exp sync names produced by this module, in run order."
  value       = module.coder_utils.scripts
}
