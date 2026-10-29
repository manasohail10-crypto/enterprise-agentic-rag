# The two image stores (Step 14).
resource "aws_ecr_repository" "repo" {
  for_each = toset(["api", "ui"])

  name                 = "${var.project}-${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # "terraform destroy" also deletes the images inside, so nothing is left to pay for

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the newest 15 images in each repository (old images cost money).
resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each   = aws_ecr_repository.repo
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 15 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 15
      }
      action = { type = "expire" }
    }]
  })
}