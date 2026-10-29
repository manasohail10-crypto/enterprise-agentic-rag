# ---------- the app server (Step 13) ----------
resource "aws_instance" "app" {
  count = var.create_app_server ? 1 : 0

  ami                         = data.aws_ssm_parameter.ubuntu.value
  instance_type               = var.app_instance_type
  key_name                    = var.key_name
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = true

  # replace(..., "\r", "") removes Windows line endings, which would break a Linux script.
  user_data                   = replace(file("${path.module}/scripts/install-docker.sh"), "\r", "")
  user_data_replace_on_change = true

  # IMDSv2 only (safer). Hop limit 2 lets containers on the server use the server role too.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "${var.project}-app"
  }
}

# ---------- the CI server (Step 16): Jenkins + SonarQube ----------
resource "aws_instance" "ci" {
  count = var.create_ci_server ? 1 : 0

  ami                         = data.aws_ssm_parameter.ubuntu.value
  instance_type               = var.ci_instance_type
  key_name                    = var.key_name
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.ci.id]
  iam_instance_profile        = aws_iam_instance_profile.ci.name
  associate_public_ip_address = true

  user_data = replace(templatefile("${path.module}/scripts/ci-bootstrap.sh", {
    repo_url   = "https://github.com/${var.github_repo}.git"
    git_branch = var.git_branch
    region     = var.region
  }), "\r", "")
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2 # Jenkins runs in a container and must reach the server role
  }

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "${var.project}-ci"
  }
}

# A fixed public address for the CI server, so the GitHub webhook URL does not change when you stop and start it.
resource "aws_eip" "ci" {
  count    = var.create_ci_server ? 1 : 0
  domain   = "vpc"
  instance = aws_instance.ci[0].id
}