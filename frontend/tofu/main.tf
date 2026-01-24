# Used to ensure the ACR name is unique
resource "random_string" "unique" {
  length  = 6
  special = false
  upper   = false
}

# Create a resource group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

# Create an Azure Container Registry
resource "azurerm_container_registry" "main" {
  name                = "${var.acr_name_prefix}${random_string.unique.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
}

# Create an Azure Kubernetes Service cluster
resource "azurerm_kubernetes_cluster" "main" {
  name                = var.aks_cluster_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = var.aks_cluster_name

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_DS2_v2"
  }

  identity {
    type = "SystemAssigned"
  }

  # Grant the AKS cluster pull access to the ACR
  role_based_access_control_enabled = true

  network_profile {
    network_plugin = "azure"
    service_cidr = "10.0.0.0/16"
    dns_service_ip = "10.0.0.10"
    docker_bridge_cidr = "172.17.0.1/16"
  }
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}
