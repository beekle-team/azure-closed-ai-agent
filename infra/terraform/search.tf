resource "azurerm_storage_account" "blob" {
  name                            = "${var.name_prefix}blob"
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "corpus" {
  name                  = "corpus"
  storage_account_id    = azurerm_storage_account.blob.id
  container_access_type = "private"
}

resource "azurerm_private_endpoint" "blob" {
  name                = "${var.name_prefix}-blob-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.pe.id

  private_service_connection {
    name                           = "${var.name_prefix}-blob-psc"
    private_connection_resource_id = azurerm_storage_account.blob.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_search_service" "main" {
  name                          = "${var.name_prefix}-srch"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  sku                           = "basic"
  public_network_access_enabled = false
  local_authentication_enabled  = true
}

resource "azurerm_private_endpoint" "search" {
  name                = "${var.name_prefix}-srch-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.pe.id

  private_service_connection {
    name                           = "${var.name_prefix}-srch-psc"
    private_connection_resource_id = azurerm_search_service.main.id
    subresource_names              = ["searchService"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "search"
    private_dns_zone_ids = [azurerm_private_dns_zone.search.id]
  }
}

resource "azurerm_servicebus_namespace" "main" {
  name                          = "${var.name_prefix}-bus"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  sku                           = "Premium"
  capacity                      = 1
  public_network_access_enabled = false
}

resource "azurerm_servicebus_queue" "ingest" {
  name         = "ingest"
  namespace_id = azurerm_servicebus_namespace.main.id
}

resource "azurerm_private_endpoint" "servicebus" {
  name                = "${var.name_prefix}-bus-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.pe.id

  private_service_connection {
    name                           = "${var.name_prefix}-bus-psc"
    private_connection_resource_id = azurerm_servicebus_namespace.main.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "servicebus"
    private_dns_zone_ids = [azurerm_private_dns_zone.servicebus.id]
  }
}
