
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock environment variables before importing handler
os.environ['METRICS_TABLE_NAME'] = 'test_metrics'
os.environ['AWS_REGION_NAME'] = 'us-east-1'
os.environ['S3_BUCKET_NAME'] = 'test-bucket'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'

# Mock boto3
sys.modules['boto3'] = MagicMock()

# Mock script_gen and script_pipeline
sys.modules['script_gen'] = MagicMock()
sys.modules['script_gen'].SAMPLE_TOPICS = [  # pyre-ignore[16]
    {"topic": "Topic A", "era": "ancient"},
    {"topic": "Topic B", "era": "medieval"},
    {"topic": "Topic C", "era": "modern"},
    {"topic": "Unique Topic", "era": "future"}
]

sys.modules['script_pipeline'] = MagicMock()
sys.modules['stock_fetcher'] = MagicMock()
sys.modules['tts'] = MagicMock()
sys.modules['video_composer'] = MagicMock()
sys.modules['music_fetcher'] = MagicMock()
sys.modules['copyright_safety'] = MagicMock()
sys.modules['youtube_analytics'] = MagicMock()
sys.modules['story_music_matcher'] = MagicMock()

# Import handler
import handler  # pyre-ignore[21]

class TestRetryLogic(unittest.TestCase):
    
    def setUp(self):
        # Reset mocks
        handler.get_recent_video_topics = MagicMock()
        handler.generate_script_with_fallback = MagicMock()
        handler.select_random_topic_data = MagicMock()
        
        # Configure the module mock directly because handler imports it inside the function
        sys.modules['story_music_matcher'].get_music_category_for_script.return_value = ("epic", 0.9)
        
        # Explicitly mock boto3 on the handler module to insure we control it
        handler.boto3 = MagicMock()
        mock_s3_instance = MagicMock()
        mock_s3_instance.generate_presigned_url.return_value = "http://test-url"
        handler.boto3.client.return_value = mock_s3_instance
        
    def test_is_similar(self):
        past = ["Fatih Sultan Mehmet", "Napoleon Bonaparte"]
        self.assertTrue(handler.is_similar("Fatih", past))
        self.assertTrue(handler.is_similar("Napoleon", past))
        self.assertFalse(handler.is_similar("Atatürk", past))
        
    def test_retry_loop_success(self):
        """Test that loop retries on fallback and succeeds on good script."""
        # Setup
        handler.get_recent_video_topics.return_value = []
        
        # Mock random selection
        # Attempt 1: "Apple" (will fail generation)
        # Attempt 2: "Banana" (will succeed)
        handler.select_random_topic_data.side_effect = [
            {"topic": "Apple", "era": "ancient"},
            {"topic": "Banana", "era": "modern"},
            {"topic": "Cherry", "era": "future"} # Extra in case
        ]
        
        # Mock generation
        # Attempt 1: Fails (fallback used)
        # Attempt 2: Succeeds
        handler.generate_script_with_fallback.side_effect = [
            {
                "title": "Apple Video", 
                "fallback_used": True, 
                "pipeline_warnings": ["FALLBACK_USED"],
                "voiceover_text": "Apple text",
                "mood": "documentary",
                "segments": [],
                "era": "ancient",
                "safe_title": "Apple_Video"
            },
            {
                "title": "Banana Video", 
                "fallback_used": False,
                "voiceover_text": "Banana text",
                "mood": "documentary",
                "segments": [],
                "era": "modern",
                "safe_title": "Banana_Video"
            }
        ]
        
        # Mock downstream functions to avoid errors
        handler.fetch_videos_by_segments = MagicMock(return_value=["clip.mp4"])
        handler.generate_voiceover = MagicMock(return_value="audio.mp3")
        handler.generate_historical_music = MagicMock(return_value={"path": "music.mp3"})
        handler.compose_video = MagicMock(return_value="final.mp4")
        
        # Run
        event = {"use_pipeline": True} # Random mode
        with patch('json.dumps', return_value='{}'):
            response = handler.lambda_handler(event, None)
        
        # Verify
        self.assertEqual(handler.generate_script_with_fallback.call_count, 2)
        self.assertEqual(response['statusCode'], 200)
        # Cannot check body content because json.dumps is mocked to return '{}'
        
    def test_diversity_check(self):
        """Test that similar topics are skipped."""
        handler.get_recent_video_topics.return_value = ["Apple Pie"]
        
        # Generator that returns:
        # 1. "Apple Pie" (Duplicate - exact)
        # 2. "Orange" (Unique)
        handler.select_random_topic_data.side_effect = [
            {"topic": "Apple Pie", "era": "ancient"}, # Exact match
            {"topic": "Orange", "era": "medieval"}, # Unique
            {"topic": "Grape", "era": "modern"}
        ]
        
        handler.generate_script_with_fallback.return_value = {
            "title": "Orange Video", 
            "fallback_used": False,
            "voiceover_text": "Orange text",
            "mood": "documentary",
            "segments": [],
            "era": "medieval",
            "safe_title": "Orange_Video"
        }
        
        # Mock downstream
        handler.fetch_videos_by_segments = MagicMock(return_value=["clip.mp4"])
        handler.generate_voiceover = MagicMock(return_value="audio.mp3")
        handler.generate_historical_music = MagicMock(return_value={"path": "music.mp3"})
        handler.compose_video = MagicMock(return_value="final.mp4")
        
        # Run
        with patch('json.dumps', return_value='{}'):
            handler.lambda_handler({}, None)
        
        # Verify
        # Should have called select_random_topic_data twice (first one rejected)
        self.assertEqual(handler.select_random_topic_data.call_count, 2)
        # Generate should be called ONCE with Orange
        handler.generate_script_with_fallback.assert_called_once()
        _, kwargs = handler.generate_script_with_fallback.call_args
        self.assertEqual(kwargs['topic'], "Orange")

if __name__ == '__main__':
    unittest.main()
