# A security group is a firewall in front of a server. Everything not listed here is blocked.

# ---------- the app server ----------
resource "aws_security_group" "app" {
  name        = "${var.project}-app-sg"
  description = "App server: SSH and the app pages, only from my IP"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  for_each = {
    ssh = 22
    api = 8000
    ui  = 8501
  }

  security_group_id = aws_security_group.app.id
  description       = "${each.key} from my IP"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

resource "aws_vpc_security_group_egress_rule" "app" {
  security_group_id = aws_security_group.app.id
  description       = "all outgoing traffic"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# ---------- the CI server (Jenkins + SonarQube) ----------
resource "aws_security_group" "ci" {
  name        = "${var.project}-ci-sg"
  description = "CI server: SSH, Jenkins and SonarQube from my IP, Jenkins webhook from GitHub"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "ci_me" {
  for_each = {
    ssh       = 22
    jenkins   = 8080
    sonarqube = 9000
  }

  security_group_id = aws_security_group.ci.id
  description       = "${each.key} from my IP"
  cidr_ipv4         = var.my_ip_cidr
  ip_protocol       = "tcp"
  from_port         = each.value
  to_port           = each.value
}

resource "aws_vpc_security_group_ingress_rule" "ci_github" {
  for_each = local.github_hook_cidrs

  security_group_id = aws_security_group.ci.id
  description       = "Jenkins webhook from GitHub"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 8080
  to_port           = 8080
}

resource "aws_vpc_security_group_egress_rule" "ci" {
  security_group_id = aws_security_group.ci.id
  description       = "all outgoing traffic"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}