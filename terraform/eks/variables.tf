variable "region" {
  description = "AWS region. ap-south-1 is Mumbai."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "A short name used in resource names."
  type        = string
  default     = "enterprise-rag"
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "enterprise-rag-eks"
}

variable "kubernetes_version" {
  description = "Kubernetes version of the EKS cluster."
  type        = string
  default     = "1.35"
}

variable "my_ip_cidr" {
  description = "YOUR public IP with /32, for example 203.0.113.25/32. Only this address can talk to the cluster API."
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0)) && var.my_ip_cidr != "0.0.0.0/0"
    error_message = "Use your own IP like 203.0.113.25/32. 0.0.0.0/0 (the whole internet) is not allowed."
  }
}

variable "node_instance_type" {
  description = "Size of each worker computer. The API image is big and needs memory, so use t3.large (8 GB)."
  type        = string
  default     = "t3.large"
}

variable "node_desired_size" {
  description = "How many worker computers to start with."
  type        = number
  default     = 2
}