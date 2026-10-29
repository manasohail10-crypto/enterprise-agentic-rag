output "ecr_registry" {
  description = "Put this in deploy/eks/kustomization.yaml (newName) and in the Jenkinsfile."
  value       = local.registry
}

output "ecr_repositories" {
  value = { for key, repo in aws_ecr_repository.repo : key => repo.repository_url }
}

output "github_actions_role_arn" {
  description = "GitHub repository variable AWS_ROLE_ARN (Settings > Secrets and variables > Actions > Variables)."
  value       = aws_iam_role.github.arn
}

output "app_server_ip" {
  value = var.create_app_server ? aws_instance.app[0].public_ip : null
}

output "app_server_ssh" {
  value = var.create_app_server ? "ssh -i $env:USERPROFILE\\.ssh\\${var.key_name}.pem ubuntu@${aws_instance.app[0].public_ip}" : null
}

output "ci_server_ip" {
  value = var.create_ci_server ? aws_eip.ci[0].public_ip : null
}

output "ci_server_ssh" {
  value = var.create_ci_server ? "ssh -i $env:USERPROFILE\\.ssh\\${var.key_name}.pem ubuntu@${aws_eip.ci[0].public_ip}" : null
}

output "jenkins_url" {
  value = var.create_ci_server ? "http://${aws_eip.ci[0].public_ip}:8080" : null
}

output "sonarqube_url" {
  value = var.create_ci_server ? "http://${aws_eip.ci[0].public_ip}:9000" : null
}

output "github_webhook_url" {
  description = "GitHub repo > Settings > Webhooks > Payload URL"
  value       = var.create_ci_server ? "http://${aws_eip.ci[0].public_ip}:8080/github-webhook/" : null
}