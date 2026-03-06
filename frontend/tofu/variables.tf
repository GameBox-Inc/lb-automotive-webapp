variable "resource_group_name" {
  description = "The name of the Azure Resource Group."
  type        = string
  default     = "lb-automotive-rg"
}

variable "location" {
  description = "The Azure region where resources will be created."
  type        = string
  default     = "East US"
}

variable "acr_name_prefix" {
  description = "The prefix for the Azure Container Registry name. A random string will be appended for uniqueness."
  type        = string
  default     = "lbautomotiveacr"
}

variable "aks_cluster_name" {
  description = "The name of the AKS cluster."
  type        = string
  default     = "lb-automotive-aks"
}

variable "app_image_name" {
  description = "The name of the Docker image for the application."
  type        = string
  default     = "lb-automotive-dashboard"
}
