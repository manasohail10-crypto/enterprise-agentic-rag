variable "region" {
  description = "AWS region. ap-south-1 is Mumbai."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "A short name used in all resource names."
  type        = string
  default     = "enterprise-rag"
}

variable "my_ip_cidr" {
  description = "YOUR public IP with /32 at the end, for example 203.0.113.25/32. Only this address can reach the servers. Find it at https://checkip.amazonaws.com"
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0)) && var.my_ip_cidr != "0.0.0.0/0"
    error_message = "Use your own IP like 203.0.113.25/32. 0.0.0.0/0 (the whole internet) is not allowed."
  }
}

variable "key_name" {
  description = "The name of the EC2 key pair you made in Step 13 (rag-key)."
  type        = string
  default     = "rag-key"
}

variable "github_repo" {
  description = "Your GitHub repository as owner/name. Used for the OIDC role and for cloning the Jenkins files."
  type        = string
  default     = "manasohail10-crypto/enterprise-agentic-rag"
}

variable "git_branch" {
  description = "The branch the CI server clones (it must contain the jenkins/ folder)."
  type        = string
  default     = "main"
}

variable "app_instance_type" {
  description = "Size of the server that runs the app. t3.medium has 4 GB memory."
  type        = string
  default     = "t3.medium"
}

variable "create_app_server" {
  description = "Make the app server (Step 13). Set false if you do not need it any more."
  type        = bool
  default     = true
}

variable "create_ci_server" {
  description = "Make the CI server with Jenkins and SonarQube (Step 16)."
  type        = bool
  default     = true
}

variable "ci_instance_type" {
  description = "Size of the CI server. SonarQube needs about 4 GB, Jenkins about 1 GB, so use 8 GB: t3.large."
  type        = string
  default     = "t3.large"
}

variable "create_github_oidc_provider" {
  description = "AWS allows only ONE GitHub OIDC provider per account. Set false if one already exists (for example from Step 14)."
  type        = bool
  default     = true
}