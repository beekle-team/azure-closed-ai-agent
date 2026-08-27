resource "azurerm_container_app_environment" "main" {
  name                           = "${var.name_prefix}-cae"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.app.id
  internal_load_balancer_enabled = true
}

locals {
  agent_image = var.agent_image != "" ? var.agent_image : "${azurerm_container_registry.main.login_server}/closed-agent:latest"
  admin_image = var.admin_image != "" ? var.admin_image : "${azurerm_container_registry.main.login_server}/closed-admin:latest"
}

resource "azurerm_container_app" "admin" {
  name                         = "${var.name_prefix}-admin"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  template {
    container {
      name   = "admin"
      image  = local.admin_image
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  ingress {
    external_enabled = false
    target_port      = 80
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

resource "azurerm_container_app" "agent" {
  name                         = "${var.name_prefix}-agent"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name  = "search-key"
    value = azurerm_search_service.main.primary_key
  }

  template {
    container {
      name   = "agent"
      image  = local.agent_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = "production"
      }

      env {
        name  = "AUTH_MODE"
        value = "entra"
      }

      env {
        name  = "AZURE_TENANT_ID"
        value = var.azure_tenant_id
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.azure_client_id
      }

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }

      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = "https://${azurerm_search_service.main.name}.search.windows.net"
      }

      env {
        name        = "AZURE_SEARCH_API_KEY"
        secret_name = "search-key"
      }

      env {
        name  = "AZURE_SEARCH_INDEX"
        value = "corpus"
      }
    }
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "auto"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

resource "azurerm_container_group" "neo4j" {
  name                = "${var.name_prefix}-neo4j"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  ip_address_type     = "Private"
  subnet_ids          = [azurerm_subnet.aci.id]

  container {
    name   = "neo4j"
    image  = "neo4j:5.26-community"
    cpu    = 1
    memory = 2

    ports {
      port     = 7687
      protocol = "TCP"
    }

    environment_variables = {
      NEO4J_AUTH = "neo4j/${var.neo4j_password}"
    }
  }
}
