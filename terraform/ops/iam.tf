locals {
  repo_arns = [for repo in aws_ecr_repository.repo : repo.arn]
}

# ---------- what "push to our two ECR repositories" means ----------
data "aws_iam_policy_document" "ecr_push" {
  statement {
    sid       = "LoginToEcr"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PushToOurRepositoriesOnly"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = local.repo_arns
  }
}

resource "aws_iam_policy" "ecr_push" {
  name   = "${var.project}-ecr-push"
  policy = data.aws_iam_policy_document.ecr_push.json
}

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# ---------- the app server role: can pull images ----------
resource "aws_iam_role" "app" {
  name               = "${var.project}-app-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

resource "aws_iam_role_policy_attachment" "app" {
  for_each = {
    ecr_read = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
    ssm      = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  role       = aws_iam_role.app.name
  policy_arn = each.value
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project}-app-profile"
  role = aws_iam_role.app.name
}

# ---------- the CI server role: can push images (so Jenkins needs no AWS password) ----------
resource "aws_iam_role" "ci" {
  name               = "${var.project}-ci-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

resource "aws_iam_role_policy_attachment" "ci" {
  for_each = {
    ecr_push = aws_iam_policy.ecr_push.arn
    ssm      = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  role       = aws_iam_role.ci.name
  policy_arn = each.value
}

resource "aws_iam_instance_profile" "ci" {
  name = "${var.project}-ci-profile"
  role = aws_iam_role.ci.name
}

# ---------- GitHub Actions: push to ECR with a short-lived token (OIDC) ----------
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

locals {
  github_oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : "arn:aws:iam::${data.aws_caller_identity.me.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Only our repository, and only the main branch or a version tag, can use this role.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:ref:refs/heads/main",
        "repo:${var.github_repo}:ref:refs/tags/v*",
      ]
    }
  }
}

resource "aws_iam_role" "github" {
  name               = "${var.project}-github-ecr-push"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

resource "aws_iam_role_policy_attachment" "github" {
  role       = aws_iam_role.github.name
  policy_arn = aws_iam_policy.ecr_push.arn
}