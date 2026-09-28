mock_provider "coder" {}

run "defaults" {
  command = plan
  variables {
    agent_id = "test-agent"
    workdir  = "/workspace/project/"
  }
  assert {
    condition     = var.install_t3code && var.t3code_version == "latest" && local.workdir == "/workspace/project"
    error_message = "Installation defaults and directory normalization must be preserved."
  }
  assert {
    condition     = !var.public_access && coder_app.web[0].url == "http://localhost:3773" && coder_app.web[0].share == "owner" && coder_app.web[0].subdomain
    error_message = "Expose port 3773 through an owner-only subdomain app."
  }
  assert {
    condition     = strcontains(coder_app.pair[0].command, "t3 pair") && coder_app.pair[0].open_in == "slim-window"
    error_message = "Provide a pairing terminal."
  }
  assert {
    condition     = length(module.coder_utils.scripts) == 2
    error_message = "Run install then server startup."
  }
}

run "public_access_is_opt_in" {
  command = plan
  variables {
    agent_id      = "test-agent"
    workdir       = "/workspace"
    public_access = true
  }
  assert {
    condition     = coder_app.web[0].share == "public" && coder_app.web[0].subdomain && coder_app.web[0].url == "http://localhost:3773"
    error_message = "Public access must expose the existing subdomain app through Coder."
  }
  assert {
    condition     = coder_app.pair[0].share == "owner"
    error_message = "Generating pairing credentials must remain owner-only."
  }
}

run "custom_configuration" {
  command = plan
  variables {
    agent_id              = "test-agent"
    workdir               = "/"
    web_port              = 8080
    install_t3code        = false
    t3code_version        = "0.0.42"
    web_app_display_name  = "T3 Browser"
    pair_app_display_name = "Pair Browser"
    order                 = 10
    group                 = "AI"
    icon                  = "/custom.svg"
    pre_install_script    = "echo before"
    post_install_script   = "echo after"
  }
  assert {
    condition     = local.workdir == "/" && coder_app.web[0].url == "http://localhost:8080"
    error_message = "Preserve root workdir and custom port."
  }
  assert {
    condition     = coder_app.web[0].display_name == "T3 Browser" && coder_app.pair[0].display_name == "Pair Browser" && coder_app.pair[0].group == "AI" && coder_app.web[0].order == 10 && coder_app.web[0].icon == "/custom.svg"
    error_message = "Respect app presentation settings."
  }
  assert {
    condition     = length(module.coder_utils.scripts) == 4 && strcontains(local.install_script, "ARG_INSTALL_T3CODE='false'")
    error_message = "Support custom installation and hooks."
  }
}

run "install_only" {
  command = plan
  variables {
    agent_id      = "test-agent"
    workdir       = "/workspace"
    public_access = true
    enable_web    = false
    subdomain     = false
  }
  assert {
    condition     = length(coder_app.web) == 0 && length(coder_app.pair) == 0 && local.start_script == null && length(module.coder_utils.scripts) == 1
    error_message = "Install-only mode must omit both apps and server startup."
  }
}

run "invalid_port" {
  command = plan
  variables {
    agent_id = "test-agent"
    workdir  = "/workspace"
    web_port = 65536
  }
  expect_failures = [var.web_port]
}
run "fractional_port" {
  command = plan
  variables {
    agent_id = "test-agent"
    workdir  = "/workspace"
    web_port = 3773.5
  }
  expect_failures = [var.web_port]
}
run "empty_directory" {
  command = plan
  variables {
    agent_id = "test-agent"
    workdir  = " "
  }
  expect_failures = [var.workdir]
}
run "path_proxy_rejected" {
  command = plan
  variables {
    agent_id  = "test-agent"
    workdir   = "/workspace"
    subdomain = false
  }
  expect_failures = [var.subdomain]
}
