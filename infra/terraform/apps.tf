resource "azurerm_container_app_environment" "main" {
  name                           = "${var.name_prefix}-cae"
  location                       = azurerm_resource_group.main.location
  resource_group_name            = azurerm_resource_group.main.name
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.main.id
  infrastructure_subnet_id       = azurerm_subnet.app.id
  internal_load_balancer_enabled = true
}

resource "azurerm_storage_share" "agent_data" {
  name               = "agent-data"
  storage_account_id = azurerm_storage_account.blob.id
  quota              = 10
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

  secret {
    name  = "openai-key"
    value = azurerm_cognitive_account.openai.primary_access_key
  }

  secret {
    name  = "storage-connection"
    value = azurerm_storage_account.blob.primary_connection_string
  }

  secret {
    name  = "servicebus-connection"
    value = azurerm_servicebus_namespace.main.default_primary_connection_string
  }

  secret {
    name  = "neo4j-password"
    value = var.neo4j_password
  }

  secret {
    name  = "postgres-url"
    value = "postgresql://${var.postgres_admin_login}:${var.postgres_admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/closed_agent"
  }

  secret {
    name  = "webhook-secret"
    value = var.channel_webhook_secret
  }

  secret {
    name  = "storage-key"
    value = azurerm_storage_account.blob.primary_access_key
  }

  storage {
    name         = "agentdata"
    account_name = azurerm_storage_account.blob.name
    access_key   = azurerm_storage_account.blob.primary_access_key
    share_name   = azurerm_storage_share.agent_data.name
    access_mode  = "ReadWrite"
  }

  template {
    volume {
      name         = "agent-data"
      storage_name = "agentdata"
      storage_type = "AzureFile"
    }

    container {
      name   = "agent"
      image  = local.agent_image
      cpu    = 0.5
      memory = "1Gi"

      volume_mounts {
        name = "agent-data"
        path = "/app/data"
      }

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
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "openai-key"
      }

      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = var.openai_deployment_name
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

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "AZURE_BLOB_CONTAINER"
        value = "corpus"
      }

      env {
        name        = "AZURE_SERVICEBUS_CONNECTION_STRING"
        secret_name = "servicebus-connection"
      }

      env {
        name  = "AZURE_SERVICEBUS_QUEUE"
        value = "ingest"
      }

      env {
        name  = "NEO4J_URI"
        value = "bolt://${azurerm_container_group.neo4j.ip_address}:7687"
      }

      env {
        name  = "NEO4J_USER"
        value = "neo4j"
      }

      env {
        name        = "NEO4J_PASSWORD"
        secret_name = "neo4j-password"
      }

      env {
        name        = "DATABASE_URL"
        secret_name = "postgres-url"
      }

      env {
        name        = "CHANNEL_WEBHOOK_SECRET"
        secret_name = "webhook-secret"
      }

      env {
        name  = "DATA_DIR"
        value = "/app/data"
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
