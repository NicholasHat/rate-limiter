variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "rate-limiter"
}

variable "bucket_capacity" {
  description = "Maximum tokens a client's bucket can hold"
  type        = number
  default     = 10
}

variable "refill_rate_per_second" {
  description = "Tokens added back to a bucket per second (lazy refill)"
  type        = number
  default     = 1
}

variable "window_seconds" {
  description = "Sliding window length in seconds; the limit per window is bucket_capacity"
  type        = number
  default     = 10
}

variable "cas_backoff" {
  description = "CAS retry backoff strategy for the atomic path: jitter or none"
  type        = string
  default     = "jitter"
}
