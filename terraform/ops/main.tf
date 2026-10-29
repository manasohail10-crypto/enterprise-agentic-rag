data "aws_caller_identity" "me" {}

# We use the default VPC (a network every AWS account already has). No NAT gateway is needed, so no extra cost.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# The newest Ubuntu 24.04 LTS image. Canonical (the maker of Ubuntu) publishes its ID here.
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

# GitHub publishes the IP addresses its webhooks come from. We let ONLY these addresses reach Jenkins port 8080.
data "http" "github_meta" {
  url = "https://api.github.com/meta"

  request_headers = {
    Accept = "application/vnd.github+json"
  }
}

locals {
  subnet_id = sort(data.aws_subnets.default.ids)[0]

  # Only IPv4 addresses (the ones without a colon).
  github_hook_cidrs = toset([
    for cidr in jsondecode(data.http.github_meta.response_body).hooks : cidr if !strcontains(cidr, ":")
  ])

  registry = "${data.aws_caller_identity.me.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}