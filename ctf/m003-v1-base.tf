# M003 v1-base - Base CTF Scenario
# Service Principal Secret-Based Privilege Escalation

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "ctf" {
  name     = "rg-ctf-m003-v1"
  location = "eastus"

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v1-base"
    environment  = "ctf"
  }
}

resource "azurerm_virtual_network" "target" {
  name                = "vnet-ctf-m003-target"
  location            = azurerm_resource_group.ctf.location
  resource_group_name = azurerm_resource_group.ctf.name
  address_space       = ["10.0.0.0/16"]

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v1-base"
    ctf_role     = "target"
  }
}

resource "azurerm_subnet" "target" {
  name                 = "subnet-ctf-m003-target"
  resource_group_name  = azurerm_resource_group.ctf.name
  virtual_network_name = azurerm_virtual_network.target.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "target" {
  name                = "nsg-ctf-m003-target"
  location            = azurerm_resource_group.ctf.location
  resource_group_name = azurerm_resource_group.ctf.name

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v1-base"
    ctf_role     = "target"
  }
}

output "resource_group_name" {
  value = azurerm_resource_group.ctf.name
}

output "vnet_id" {
  value = azurerm_virtual_network.target.id
}
