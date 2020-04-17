provider "aws" {
  region  = "us-east-1"
  version = "~> 2.47"
}

resource "aws_sqs_queue" "terraform_queue" {
  name_prefix               = "terraform-example-queue"
  delay_seconds             = 90
  max_message_size          = 2048
  message_retention_seconds = 86400
  receive_wait_time_seconds = 10
  tags = {
    Environment = "production"
  }
}

output "this_sqs_queue_id" {
  description = "The URL for the created Amazon SQS queue"
  value = aws_sqs_queue.terraform_queue.id
}
