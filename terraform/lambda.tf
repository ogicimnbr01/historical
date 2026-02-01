# Lambda Function for Video Generation
resource "aws_lambda_function" "video_generator" {
  function_name = "youtube-shorts-video-generator"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300  # 5 minutes
  memory_size   = 3008 # 3GB for video processing

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  layers = [
    aws_lambda_layer_version.ffmpeg_layer.arn,
    aws_lambda_layer_version.python_deps.arn
  ]

  environment {
    variables = {
      S3_BUCKET_NAME     = aws_s3_bucket.videos.id
      SNS_TOPIC_ARN      = aws_sns_topic.video_ready.arn
      AWS_REGION_NAME    = var.aws_region
      PEXELS_API_KEY     = var.pexels_api_key
    }
  }

  ephemeral_storage {
    size = 5120 # 5GB for video processing
  }
}

# Lambda Layer for FFmpeg
resource "aws_lambda_layer_version" "ffmpeg_layer" {
  layer_name          = "ffmpeg-layer"
  description         = "FFmpeg binary for video processing"
  compatible_runtimes = ["python3.11"]
  
  s3_bucket = aws_s3_bucket.videos.id
  s3_key    = "layers/ffmpeg-layer.zip"
  
  depends_on = [aws_s3_object.ffmpeg_layer]
}

resource "aws_s3_object" "ffmpeg_layer" {
  bucket = aws_s3_bucket.videos.id
  key    = "layers/ffmpeg-layer.zip"
  source = "${path.module}/../lambda/layer/ffmpeg-layer.zip"
  etag   = filemd5("${path.module}/../lambda/layer/ffmpeg-layer.zip")
}

# Python dependencies layer
resource "aws_lambda_layer_version" "python_deps" {
  layer_name          = "python-deps-layer"
  description         = "Python dependencies: requests"
  compatible_runtimes = ["python3.11"]
  
  s3_bucket = aws_s3_bucket.videos.id
  s3_key    = "layers/python-deps.zip"
  
  depends_on = [aws_s3_object.python_deps]
}

resource "aws_s3_object" "python_deps" {
  bucket = aws_s3_bucket.videos.id
  key    = "layers/python-deps.zip"
  source = "${path.module}/../lambda/layer/python-deps.zip"
  etag   = filemd5("${path.module}/../lambda/layer/python-deps.zip")
}

# Package Lambda code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/video_creator"
  output_path = "${path.module}/../lambda/video_creator.zip"
}
