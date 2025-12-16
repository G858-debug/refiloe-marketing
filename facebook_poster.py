"""
Facebook Poster Module for Refiloe Social Media Automation

This module handles posting content to Facebook pages and groups using the Facebook Graph API.
It integrates with the social media database to manage posts and provides comprehensive
error handling and analytics.

Author: Refiloe AI Assistant
Created: 2024
"""

import os
import time
import requests
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz
from utils.logger import log_info, log_error, log_warning
from social_media.database import SocialMediaDatabase


class FacebookPoster:
    """
    Facebook Poster class for automated content posting to Facebook pages and groups.
    
    This class handles:
    - Posting content to Facebook pages
    - Uploading images to Facebook
    - Posting to Facebook groups (future feature)
    - Fetching post analytics
    - Error handling and retry logic
    """
    
    def __init__(self, page_access_token: str, page_id: str, supabase_client=None):
        """
        Initialize Facebook API connection.
        
        Args:
            page_access_token: Facebook Page Access Token
            page_id: Facebook Page ID
            supabase_client: Optional Supabase client for database operations
        """
        self.page_access_token = page_access_token
        self.page_id = page_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self.database = SocialMediaDatabase(supabase_client) if supabase_client else None
        
        # Load configuration
        self.config = self._load_config()
        
        # Rate limiting settings
        self.rate_limit_delay = 1  # seconds between requests
        self.max_retries = 3
        
        log_info(f"FacebookPoster initialized for page {page_id}")
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            log_error(f"Failed to load config: {e}")
            return {}
    
    def post_to_page(self, post_data: Dict) -> Dict:
        """
        Post content to Facebook Page.

        Args:
            post_data: Dictionary containing:
                - content_text: The text content to post
                - image_ids: Optional list of Facebook image IDs
                - video_url: Optional video URL from HeyGen
                - scheduled_time: Optional scheduled posting time

        Returns:
            Dictionary with success status, post_id, and error message
        """
        try:
            log_info(f"Posting to Facebook page {self.page_id}")

            # Validate required data
            if not post_data.get('content_text'):
                return {
                    'success': False,
                    'post_id': None,
                    'error': 'No content text provided'
                }

            # Check if this is a video post
            if post_data.get('video_url'):
                log_info("Detected video URL, posting as video")
                return self._post_video(post_data)

            # Prepare post parameters for text/image post
            post_params = {
                'message': post_data['content_text'],
                'access_token': self.page_access_token
            }

            # Add images if provided
            if post_data.get('image_ids'):
                post_params['attached_media'] = post_data['image_ids']

            # Add scheduled time if provided
            if post_data.get('scheduled_time'):
                post_params['scheduled_publish_time'] = int(
                    post_data['scheduled_time'].timestamp()
                )
                post_params['published'] = False

            # Make API request
            url = f"{self.base_url}/{self.page_id}/feed"
            response = self._make_api_request('POST', url, data=post_params)

            if response.get('id'):
                log_info(f"Successfully posted to Facebook: {response['id']}")
                return {
                    'success': True,
                    'post_id': response['id'],
                    'error': None
                }
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                log_error(f"Failed to post to Facebook: {error_msg}")
                return {
                    'success': False,
                    'post_id': None,
                    'error': error_msg
                }

        except Exception as e:
            log_error(f"Exception in post_to_page: {e}")
            return {
                'success': False,
                'post_id': None,
                'error': str(e)
            }
    
    def upload_image(self, image_path: str) -> str:
        """
        Upload image to Facebook and return the image ID.
        
        Args:
            image_path: Path to the image file (local or Supabase URL)
        
        Returns:
            Facebook image ID for use in posts
        """
        try:
            log_info(f"Uploading image: {image_path}")
            
            # Download image if it's a URL
            if image_path.startswith('http'):
                image_data = self._download_image(image_path)
            else:
                # Read local file
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            
            # Prepare upload parameters
            files = {'source': image_data}
            data = {'access_token': self.page_access_token}
            
            # Upload to Facebook
            url = f"{self.base_url}/{self.page_id}/photos"
            response = self._make_api_request('POST', url, files=files, data=data)
            
            if response.get('id'):
                log_info(f"Image uploaded successfully: {response['id']}")
                return response['id']
            else:
                error_msg = response.get('error', {}).get('message', 'Upload failed')
                log_error(f"Image upload failed: {error_msg}")
                raise Exception(f"Image upload failed: {error_msg}")
                
        except Exception as e:
            log_error(f"Exception in upload_image: {e}")
            raise e
    
    def _download_image(self, url: str) -> bytes:
        """Download image from URL."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            log_error(f"Failed to download image from {url}: {e}")
            raise e

    def _post_video(self, post_data: Dict) -> Dict:
        """
        Post video to Facebook Page as UNPUBLISHED DRAFT.

        Videos are posted as drafts so background music can be added
        manually in Creator Studio before publishing.

        Args:
            post_data: Dictionary containing:
                - content_text: The text content/description for the video
                - video_url: URL of the video (from HeyGen or other source)
                - post_as_draft: If True (default for videos), post as unpublished

        Returns:
            Dictionary with success status, post_id, and error message
        """
        try:
            video_url = post_data.get('video_url')
            post_as_draft = post_data.get('post_as_draft', True)  # Default to draft for videos

            log_info(f"Posting video to Facebook page from URL: {video_url}")
            log_info(f"Post as draft (unpublished): {post_as_draft}")

            # Prepare video post parameters
            video_params = {
                'description': post_data.get('content_text', ''),
                'file_url': video_url,
                'access_token': self.page_access_token,
                'published': not post_as_draft,  # False = draft/unpublished
            }

            # Make API request to videos endpoint
            url = f"{self.base_url}/{self.page_id}/videos"
            response = self._make_api_request('POST', url, data=video_params)

            if response.get('id'):
                status_msg = "as DRAFT (unpublished)" if post_as_draft else "as PUBLISHED"
                log_info(f"Successfully posted video to Facebook {status_msg}: {response['id']}")
                return {
                    'success': True,
                    'post_id': response['id'],
                    'is_draft': post_as_draft,
                    'error': None
                }
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                log_error(f"Failed to post video to Facebook: {error_msg}")
                return {
                    'success': False,
                    'post_id': None,
                    'is_draft': post_as_draft,
                    'error': error_msg
                }

        except Exception as e:
            log_error(f"Exception in _post_video: {e}")
            return {
                'success': False,
                'post_id': None,
                'error': str(e)
            }

    def post_approved_content(self, post_record: Dict) -> Dict:
        """
        Post approved content to Facebook, handling videos, images, or text.

        This method is specifically designed for posting content that has been
        approved through the approval workflow.

        Args:
            post_record: Database record of the approved post containing:
                - id: Post UUID
                - content_text: The text content
                - video_url: Optional video URL from HeyGen
                - image_ids: Optional list of image URLs

        Returns:
            Dictionary with success status, post_id, and error message
        """
        try:
            post_id = post_record.get('id')
            log_info(f"Posting approved content for post {post_id}")

            # Prepare post data
            post_data = {
                'content_text': post_record.get('content_text', ''),
            }

            # Check for video URL first (videos take priority over images)
            if post_record.get('video_url'):
                log_info(f"Posting as video: {post_record['video_url']}")
                post_data['video_url'] = post_record['video_url']
            # Otherwise check for images
            elif post_record.get('image_ids'):
                log_info(f"Posting with images")
                # If image_ids are URLs, we need to upload them first
                image_urls = post_record.get('image_ids', [])
                if image_urls and isinstance(image_urls, list):
                    uploaded_ids = []
                    for img_url in image_urls:
                        try:
                            fb_image_id = self.upload_image(img_url)
                            uploaded_ids.append({'media_fbid': fb_image_id})
                        except Exception as img_error:
                            log_warning(f"Failed to upload image {img_url}: {img_error}")

                    if uploaded_ids:
                        post_data['image_ids'] = uploaded_ids

            # Post to Facebook
            result = self.post_to_page(post_data)

            # Update database if successful
            if result['success'] and self.database:
                self.database.mark_post_published(post_id, result['post_id'])
                log_info(f"Updated database with Facebook post ID: {result['post_id']}")

            return result

        except Exception as e:
            log_error(f"Exception in post_approved_content: {e}")
            return {
                'success': False,
                'post_id': None,
                'error': str(e)
            }
    
    def post_to_group(self, group_id: str, post_data: Dict) -> Dict:
        """
        Post to Facebook Group (Future feature).
        
        Currently disabled as per configuration. Groups require different
        permissions and approval processes.
        
        Args:
            group_id: Facebook Group ID
            post_data: Post content data
        
        Returns:
            Dictionary with success status and error message
        """
        log_warning("Group posting is currently disabled in configuration")
        return {
            'success': False,
            'post_id': None,
            'error': 'Group posting is disabled. Focus on page growth first.'
        }
    
    def get_post_insights(self, post_id: str) -> Dict:
        """
        Fetch analytics for a published post.
        
        Args:
            post_id: Facebook post ID
        
        Returns:
            Dictionary containing post analytics data
        """
        try:
            log_info(f"Fetching insights for post: {post_id}")
            
            # Request insights data
            url = f"{self.base_url}/{post_id}/insights"
            params = {
                'metric': 'post_impressions,post_engaged_users,post_reactions_by_type_total,post_comments,post_shares',
                'access_token': self.page_access_token
            }
            
            response = self._make_api_request('GET', url, params=params)
            
            if response.get('data'):
                # Process insights data
                insights = self._process_insights_data(response['data'])
                log_info(f"Retrieved insights for post {post_id}")
                return insights
            else:
                log_warning(f"No insights data available for post {post_id}")
                return {}
                
        except Exception as e:
            log_error(f"Exception in get_post_insights: {e}")
            return {}
    
    def _process_insights_data(self, raw_data: List[Dict]) -> Dict:
        """Process raw insights data into structured format."""
        insights = {
            'impressions': 0,
            'engaged_users': 0,
            'reactions': {},
            'comments': 0,
            'shares': 0,
            'engagement_rate': 0
        }
        
        for metric in raw_data:
            metric_name = metric.get('name', '')
            values = metric.get('values', [])
            
            if values and len(values) > 0:
                value = values[0].get('value', 0)
                
                if metric_name == 'post_impressions':
                    insights['impressions'] = value
                elif metric_name == 'post_engaged_users':
                    insights['engaged_users'] = value
                elif metric_name == 'post_reactions_by_type_total':
                    insights['reactions'] = value
                elif metric_name == 'post_comments':
                    insights['comments'] = value
                elif metric_name == 'post_shares':
                    insights['shares'] = value
        
        # Calculate engagement rate
        if insights['impressions'] > 0:
            insights['engagement_rate'] = (
                insights['engaged_users'] / insights['impressions']
            ) * 100
        
        return insights
    
    def delete_post(self, post_id: str) -> bool:
        """
        Delete a post (for cleanup/testing).
        
        Args:
            post_id: Facebook post ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Deleting post: {post_id}")
            
            url = f"{self.base_url}/{post_id}"
            params = {'access_token': self.page_access_token}
            
            response = self._make_api_request('DELETE', url, params=params)
            
            if response.get('success'):
                log_info(f"Post {post_id} deleted successfully")
                return True
            else:
                log_error(f"Failed to delete post {post_id}")
                return False
                
        except Exception as e:
            log_error(f"Exception in delete_post: {e}")
            return False
    
    def _make_api_request(self, method: str, url: str, **kwargs) -> Dict:
        """
        Make API request with retry logic and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            url: API endpoint URL
            **kwargs: Additional request parameters
        
        Returns:
            API response as dictionary
        """
        for attempt in range(self.max_retries):
            try:
                # Rate limiting
                if attempt > 0:
                    time.sleep(self.rate_limit_delay * attempt)
                
                # Make request
                response = requests.request(method, url, timeout=30, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    log_warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                # Handle token expiration
                if response.status_code == 401:
                    log_error("Facebook access token expired or invalid")
                    raise Exception("Access token expired")
                
                # Handle other errors
                response.raise_for_status()
                
                # Return JSON response
                return response.json()
                
            except requests.exceptions.RequestException as e:
                log_error(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise e
        
        raise Exception("Max retries exceeded")
    
    def get_page_info(self) -> Dict:
        """
        Get basic information about the Facebook page.
        
        Returns:
            Dictionary with page information
        """
        try:
            url = f"{self.base_url}/{self.page_id}"
            params = {
                'fields': 'name,id,category,followers_count',
                'access_token': self.page_access_token
            }
            
            response = self._make_api_request('GET', url, params=params)
            return response
            
        except Exception as e:
            log_error(f"Exception in get_page_info: {e}")
            return {}
    
    def validate_credentials(self) -> bool:
        """
        Validate Facebook credentials by making a test API call.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            page_info = self.get_page_info()
            if page_info.get('id'):
                log_info("Facebook credentials validated successfully")
                return True
            else:
                log_error("Facebook credentials validation failed")
                return False
        except Exception as e:
            log_error(f"Facebook credentials validation error: {e}")
            return False

    def get_post_comments(self, post_id: str, limit: int = 100) -> List[Dict]:
        """
        Fetch comments for a specific Facebook post.

        Args:
            post_id: Facebook post ID
            limit: Maximum number of comments to fetch (default: 100)

        Returns:
            List of comment dictionaries with comment data
        """
        try:
            log_info(f"Fetching comments for post: {post_id}")

            url = f"{self.base_url}/{post_id}/comments"
            params = {
                'fields': 'id,message,from,created_time,like_count,comment_count',
                'limit': limit,
                'access_token': self.page_access_token
            }

            response = self._make_api_request('GET', url, params=params)

            if response.get('data'):
                comments = response['data']
                log_info(f"Retrieved {len(comments)} comments for post {post_id}")
                return comments
            else:
                log_info(f"No comments found for post {post_id}")
                return []

        except Exception as e:
            log_error(f"Exception in get_post_comments: {e}")
            return []

    def reply_to_comment(self, comment_id: str, message: str) -> bool:
        """
        Reply to a Facebook comment.

        Args:
            comment_id: Facebook comment ID to reply to
            message: Reply message text

        Returns:
            True if reply was posted successfully, False otherwise
        """
        try:
            log_info(f"Posting reply to comment: {comment_id}")

            url = f"{self.base_url}/{comment_id}/comments"
            data = {
                'message': message,
                'access_token': self.page_access_token
            }

            response = self._make_api_request('POST', url, data=data)

            if response.get('id'):
                log_info(f"Successfully posted reply: {response['id']}")
                return True
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error')
                log_error(f"Failed to post reply: {error_msg}")
                return False

        except Exception as e:
            log_error(f"Exception in reply_to_comment: {e}")
            return False


# Example usage and testing functions
def test_facebook_poster():
    """Test function for Facebook poster functionality."""
    # Get credentials from environment
    page_access_token = os.getenv('PAGE_ACCESS_TOKEN')
    page_id = os.getenv('PAGE_ID')
    
    if not page_access_token or not page_id:
        log_error("Missing Facebook credentials in environment variables")
        return
    
    # Initialize poster
    poster = FacebookPoster(page_access_token, page_id)
    
    # Validate credentials
    if not poster.validate_credentials():
        log_error("Invalid Facebook credentials")
        return
    
    # Test posting
    test_post = {
        'content_text': 'Test post from Refiloe AI Assistant! 🚀',
        'image_ids': []  # No images for test
    }
    
    result = poster.post_to_page(test_post)
    if result['success']:
        log_info(f"Test post successful: {result['post_id']}")
    else:
        log_error(f"Test post failed: {result['error']}")


if __name__ == "__main__":
    test_facebook_poster()
