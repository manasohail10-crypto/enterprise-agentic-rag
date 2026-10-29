data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

# ---------- the network ----------
# Public subnets only and NO NAT gateway (a NAT gateway costs about 1 dollar per day).
# The worker computers get public addresses so they can pull images, but the security rules
# that EKS creates block all traffic coming in from the internet.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.7.3"

  name = "${var.cluster_name}-vpc"
  cidr = "10.20.0.0/16"
  azs  = local.azs

  public_subnets          = ["10.20.0.0/24", "10.20.1.0/24"]
  map_public_ip_on_launch = true

  enable_nat_gateway   = false
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
}

# ---------- the cluster ----------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.29.0"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

  # The cluster API (the "front door" for kubectl) is reachable ONLY from your IP.
  endpoint_public_access       = true
  endpoint_public_access_cidrs = [var.my_ip_cidr]
  endpoint_private_access      = true

  # You (the person who runs terraform apply) become cluster admin.
  enable_cluster_creator_admin_permissions = true

  # Control-plane logs cost money in CloudWatch. Off for this learning project.
  enabled_log_types = []

  addons = {
    coredns                = {}
    kube-proxy             = {}
    eks-pod-identity-agent = { before_compute = true }
    vpc-cni                = { before_compute = true }

    # Gives the database a real disk (an EBS volume). It uses Pod Identity, so no AWS key is stored anywhere.
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  eks_managed_node_groups = {
    main = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"

      min_size     = 1
      max_size     = 3
      desired_size = var.node_desired_size

      # The API image is about 2.8 GB. Give each worker enough disk.
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size = 40
            volume_type = "gp3"
            encrypted   = true
          }
        }
      }
    }
  }
}

# ---------- permission for the EBS disk driver ----------
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${var.cluster_name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}