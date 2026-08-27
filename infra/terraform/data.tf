resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.name_prefix}-law"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "${var.name_prefix}-id"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_cognitive_account" "openai" {
  name                          = "${var.name_prefix}-aoai"
  location                      = var.openai_location
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.name_prefix}-aoai"
  public_network_access_enabled = false

  network_acls {
    default_action = "Deny"
  }
}

resource "azurerm_cognitive_deployment" "chat" {
  name                 = var.openai_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = 10
  }
}

resource "azurerm_private_endpoint" "openai" {
  name                = "${var.name_prefix}-aoai-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.pe.id

  private_service_connection {
    name                           = "${var.name_prefix}-aoai-psc"
    private_connection_resource_id = azurerm_cognitive_account.openai.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "openai"
    private_dns_zone_ids = [azurerm_private_dns_zone.openai.id]
  }
}

resource "azurerm_key_vault" "main" {
  name                       = "${var.name_prefix}-kv"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = azurerm_user_assigned_identity.app.tenant_id
  sku_name                   = "standard"
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
  enable_rbac_authorization  = true
  public_network_access_enabled = false
}

resource "azurerm_private_endpoint" "vault" {
  name                = "${var.name_prefix}-kv-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.pe.id

  private_service_connection {
    name                           = "${var.name_prefix}-kv-psc"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "vault"
    private_dns_zone_ids = [azurerm_private_dns_zone.vault.id]
  }
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${var.name_prefix}-pg"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = "16"
  administrator_login           = var.postgres_admin_login
  administrator_password        = var.postgres_admin_password
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  public_network_access_enabled = false
  delegated_subnet_id           = azurerm_subnet.postgres.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgres.id
  zone                          = "1"

  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgres]
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = "closed_agent"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
