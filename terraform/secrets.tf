# Reference existing Secrets Manager secret (created manually with YouTube OAuth)
# This secret was created via AWS CLI with youtube_secret.json

data "aws_secretsmanager_secret" "youtube_oauth" {
  name = "shorts/youtube-oauth"
}

output "youtube_oauth_secret_arn" {
  value = data.aws_secretsmanager_secret.youtube_oauth.arn
}
