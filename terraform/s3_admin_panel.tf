# Admin Panel S3 Static Hosting with CloudFront
# ==============================================
# Hosts the admin panel HTML/JS/CSS on S3 with CloudFront CDN for HTTPS

# S3 Bucket for admin panel files
resource "aws_s3_bucket" "admin_panel" {
  bucket_prefix = "shorts-admin-panel-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "admin_panel_block" {
  bucket = aws_s3_bucket.admin_panel.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "admin_panel" {
  name                              = "admin-panel-oac"
  description                       = "OAC for admin panel S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "admin_panel" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  comment             = "Admin Panel CDN"
  price_class         = "PriceClass_100" # North America & Europe only (cheapest)

  origin {
    domain_name              = aws_s3_bucket.admin_panel.bucket_regional_domain_name
    origin_id                = "S3-admin-panel"
    origin_access_control_id = aws_cloudfront_origin_access_control.admin_panel.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-admin-panel"
    viewer_protocol_policy = "redirect-to-https"

    # Low TTL for development - easy updates
    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  # SPA routing - return index.html for 403/404 errors
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# S3 Bucket Policy - CloudFront access only
resource "aws_s3_bucket_policy" "admin_panel" {
  bucket = aws_s3_bucket.admin_panel.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.admin_panel.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.admin_panel.arn
          }
        }
      }
    ]
  })
}

# Upload admin panel files
resource "aws_s3_object" "admin_index" {
  bucket       = aws_s3_bucket.admin_panel.id
  key          = "index.html"
  source       = "${path.module}/../admin-panel/index.html"
  content_type = "text/html"
  etag         = filemd5("${path.module}/../admin-panel/index.html")
}

resource "aws_s3_object" "admin_styles" {
  bucket       = aws_s3_bucket.admin_panel.id
  key          = "styles.css"
  source       = "${path.module}/../admin-panel/styles.css"
  content_type = "text/css"
  etag         = filemd5("${path.module}/../admin-panel/styles.css")
}

resource "aws_s3_object" "admin_js" {
  bucket       = aws_s3_bucket.admin_panel.id
  key          = "app.js"
  source       = "${path.module}/../admin-panel/app.js"
  content_type = "application/javascript"
  etag         = filemd5("${path.module}/../admin-panel/app.js")
}
