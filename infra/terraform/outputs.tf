output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.main.id
}

output "neo4j_ip" {
  value = azurerm_container_group.neo4j.ip_address
}

output "blob_account_name" {
  value = azurerm_storage_account.blob.name
}

output "search_service_name" {
  value = azurerm_search_service.main.name
}

output "servicebus_namespace" {
  value = azurerm_servicebus_namespace.main.name
}
