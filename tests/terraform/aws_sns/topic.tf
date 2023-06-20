provider "aws" {
  region = "us-east-1"
}

resource "aws_sns_topic" "user_updates" {
  name_prefix = "user-updates-topic"
}
