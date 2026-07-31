terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  # The two rate-limiter implementations. Everything downstream (Lambda,
  # log groups, API routes, permissions) fans out from this map so the
  # naive and atomic paths stay structurally identical.
  implementations = {
    naive  = "handler.naive_check"
    atomic = "handler.atomic_check"
  }
}
