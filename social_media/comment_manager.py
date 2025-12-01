"""
Facebook Comment Auto-Reply Manager for Refiloe

This module handles automated AI-powered responses to Facebook comments using Claude.
It categorizes comments, generates contextual replies in Refiloe's voice, and manages
the comment interaction lifecycle.

Author: Refiloe AI Assistant
Created: 2025-12-01
"""

import os
import uuid
import yaml
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pytz
import anthropic
from utils.logger import log_info, log_error, log_warning


class CommentManager:
    """
    Manages Facebook comment interactions with AI-powered auto-replies.

    Features:
    - Fetches new comments from Facebook posts
    - Analyzes comments using Claude AI to categorize intent
    - Generates contextual replies in Refiloe's personality
    - Posts replies back to Facebook
    - Flags sensitive comments for human review
    - Tracks daily reply limits and rate limiting
    """

    def __init__(self, supabase_client, facebook_poster, config: Dict = None):
        """
        Initialize the Comment Manager.

        Args:
            supabase_client: Supabase client for database operations
            facebook_poster: FacebookPoster instance for API calls
            config: Optional configuration dictionary (loaded from config.yaml if not provided)
        """
        self.db = supabase_client
        self.facebook = facebook_poster
        self.sa_tz = pytz.timezone('Africa/Johannesburg')

        # Load configuration
        self.config = config or self._load_config()
        self.comment_config = self.config.get('comment_automation', {})

        # Initialize Anthropic client
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.anthropic_api_key:
            log_warning("ANTHROPIC_API_KEY not found - AI features will be disabled")
            self.anthropic_client = None
        else:
            self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)

        # Refiloe personality traits
        self.refiloe_personality = self.config.get('ai_influencer_settings', {})

        # Track daily reply count
        self.daily_reply_count = 0
        self.last_check_date = None

        log_info("CommentManager initialized")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            log_error(f"Failed to load config: {e}")
            return {}

    def fetch_new_comments(self, since_hours: int = 24) -> List[Dict]:
        """
        Fetch new comments from recent posts that haven't been processed yet.

        Args:
            since_hours: Number of hours to look back for comments (default: 24)

        Returns:
            List of comment dictionaries with post context
        """
        try:
            # Get recent published posts
            cutoff_time = datetime.now(self.sa_tz) - timedelta(hours=since_hours)

            result = self.db.table('social_posts').select(
                'id', 'facebook_post_id', 'caption_text', 'content_theme', 'published_time'
            ).eq('status', 'published').not_.is_('facebook_post_id', 'null').gte(
                'published_time', cutoff_time.isoformat()
            ).execute()

            if not result.data:
                log_info("No recent posts found to check for comments")
                return []

            all_comments = []

            # Fetch comments for each post
            for post in result.data:
                facebook_post_id = post['facebook_post_id']

                # Get comments from Facebook
                fb_comments = self.facebook.get_post_comments(facebook_post_id)

                # Filter out already processed comments
                for comment in fb_comments:
                    if not self._is_comment_processed(comment['id']):
                        comment['post_id'] = post['id']
                        comment['post_context'] = {
                            'caption': post['caption_text'],
                            'theme': post['content_theme']
                        }
                        all_comments.append(comment)

            log_info(f"Fetched {len(all_comments)} new comments")
            return all_comments

        except Exception as e:
            log_error(f"Error fetching comments: {e}")
            return []

    def _is_comment_processed(self, facebook_comment_id: str) -> bool:
        """Check if a comment has already been processed."""
        try:
            result = self.db.table('comment_interactions').select('id').eq(
                'facebook_comment_id', facebook_comment_id
            ).execute()

            return bool(result.data)
        except Exception as e:
            log_error(f"Error checking comment status: {e}")
            return False

    def analyze_comment(self, comment_text: str, post_context: Dict = None) -> Tuple[str, float]:
        """
        Use Claude to analyze and categorize a comment.

        Args:
            comment_text: The comment text to analyze
            post_context: Optional context about the post (caption, theme)

        Returns:
            Tuple of (category, sentiment_score)
            Categories: 'question', 'positive', 'negative', 'spam', 'engagement'
            Sentiment score: -1.0 (very negative) to 1.0 (very positive)
        """
        if not self.anthropic_client:
            log_warning("Anthropic client not available - using basic categorization")
            return self._basic_categorization(comment_text)

        try:
            context_info = ""
            if post_context:
                context_info = f"\n\nPost context:\nCaption: {post_context.get('caption', 'N/A')}\nTheme: {post_context.get('theme', 'N/A')}"

            prompt = f"""Analyze this Facebook comment and categorize it into ONE of these categories:

- 'question': The commenter is asking for information or advice
- 'positive': Praise, thanks, encouragement, or agreement
- 'negative': Complaint, criticism, or disagreement
- 'spam': Promotional content, irrelevant content, or blatant spam
- 'engagement': Simple reaction (emoji, "Nice!", "Love this", short supportive phrase)

Also provide a sentiment score from -1.0 (very negative) to 1.0 (very positive).

Comment: "{comment_text}"{context_info}

Respond ONLY with a JSON object in this exact format:
{{"category": "one_of_five_categories", "sentiment_score": 0.0, "reasoning": "brief explanation"}}"""

            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract JSON from response
            import json
            import re
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                category = result.get('category', 'engagement')
                sentiment_score = float(result.get('sentiment_score', 0.0))

                # Validate category
                valid_categories = ['question', 'positive', 'negative', 'spam', 'engagement']
                if category not in valid_categories:
                    category = 'engagement'

                log_info(f"Comment categorized as '{category}' (sentiment: {sentiment_score})")
                return category, sentiment_score
            else:
                log_warning("Could not parse Claude response, using basic categorization")
                return self._basic_categorization(comment_text)

        except Exception as e:
            log_error(f"Error analyzing comment with Claude: {e}")
            return self._basic_categorization(comment_text)

    def _basic_categorization(self, comment_text: str) -> Tuple[str, float]:
        """Basic keyword-based categorization fallback."""
        text_lower = comment_text.lower()

        # Check for questions
        if any(q in text_lower for q in ['?', 'how', 'what', 'when', 'where', 'why', 'can you', 'could you']):
            return 'question', 0.3

        # Check for positive sentiment
        positive_words = ['thanks', 'thank you', 'love', 'great', 'awesome', 'amazing', 'helpful', 'excellent']
        if any(word in text_lower for word in positive_words):
            return 'positive', 0.8

        # Check for negative sentiment
        negative_words = ['hate', 'terrible', 'awful', 'worst', 'bad', 'disappointed', 'scam', 'fraud']
        if any(word in text_lower for word in negative_words):
            return 'negative', -0.7

        # Check for spam
        spam_indicators = ['buy now', 'click here', 'discount', 'limited offer', 'dm me', 'check my profile']
        if any(indicator in text_lower for indicator in spam_indicators):
            return 'spam', 0.0

        # Default to engagement
        return 'engagement', 0.5

    def generate_reply(self, comment_text: str, category: str, post_context: Dict = None) -> str:
        """
        Generate a contextual reply using Claude in Refiloe's voice.

        Args:
            comment_text: The original comment text
            category: The comment category
            post_context: Optional context about the post

        Returns:
            Generated reply text (under 200 characters with emojis)
        """
        if not self.anthropic_client:
            log_warning("Anthropic client not available - using template reply")
            return self._template_reply(category)

        try:
            # Build personality description
            personality_traits = self.refiloe_personality.get('personality_traits', [])
            speaking_style = self.refiloe_personality.get('speaking_style', {})

            personality_desc = f"""Personality traits: {', '.join(personality_traits)}
Speaking style: {speaking_style.get('tone', 'Conversational and supportive')}
Voice: {speaking_style.get('voice', 'First person')}"""

            context_info = ""
            if post_context:
                context_info = f"\n\nOriginal post was about: {post_context.get('theme', 'fitness/training')}"

            prompt = f"""You are Refiloe, an AI assistant for personal trainers. Generate a reply to this Facebook comment.

{personality_desc}

Comment type: {category}
Comment: "{comment_text}"{context_info}

Guidelines:
- Be friendly, helpful, and encouraging
- Keep it under 200 characters (including emojis)
- Use 1-2 relevant emojis maximum
- Sound natural and conversational
- For questions: provide helpful guidance
- For positive comments: show appreciation
- For engagement: be warm and relatable

Generate ONLY the reply text, nothing else:"""

            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            reply_text = message.content[0].text.strip()

            # Ensure it's under 200 characters
            if len(reply_text) > 200:
                reply_text = reply_text[:197] + "..."

            log_info(f"Generated reply: {reply_text}")
            return reply_text

        except Exception as e:
            log_error(f"Error generating reply with Claude: {e}")
            return self._template_reply(category)

    def _template_reply(self, category: str) -> str:
        """Fallback template replies when AI is unavailable."""
        templates = {
            'question': "Great question! Let me help you with that. DM me for more details! 💪",
            'positive': "Thank you so much! Your support means everything! ❤️",
            'engagement': "Love your energy! Thanks for being part of the community! 🙌",
            'negative': "I appreciate your feedback and want to make this right. Let's chat!",
            'spam': ""  # Don't reply to spam
        }
        return templates.get(category, "Thanks for your comment! 😊")

    def should_auto_reply(self, category: str) -> bool:
        """
        Determine if a comment should receive an auto-reply.

        Args:
            category: Comment category

        Returns:
            True if should auto-reply, False otherwise
        """
        # Check if automation is enabled
        if not self.comment_config.get('enabled', True):
            return False

        # Check daily limit
        max_daily = self.comment_config.get('max_daily_replies', 50)
        if self.daily_reply_count >= max_daily:
            log_warning(f"Daily reply limit reached ({max_daily})")
            return False

        # Check category settings
        auto_reply_categories = self.comment_config.get('auto_reply_categories', ['question', 'positive', 'engagement'])
        return category in auto_reply_categories

    def post_reply(self, comment_id: str, reply_text: str) -> bool:
        """
        Post a reply to a Facebook comment.

        Args:
            comment_id: Facebook comment ID
            reply_text: Reply text to post

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add delay to appear more human
            import time
            delay = self.comment_config.get('reply_delay_seconds', 30)
            time.sleep(delay)

            # Post reply via Facebook
            success = self.facebook.reply_to_comment(comment_id, reply_text)

            if success:
                self.daily_reply_count += 1
                log_info(f"Posted reply to comment {comment_id}")

            return success

        except Exception as e:
            log_error(f"Error posting reply: {e}")
            return False

    def process_comment(self, comment: Dict) -> Dict:
        """
        Process a single comment: analyze, generate reply, and store in database.

        Args:
            comment: Comment dictionary with text, author, post_id, etc.

        Returns:
            Processing result dictionary
        """
        try:
            comment_text = comment['message']
            comment_id = comment['id']
            post_id = comment.get('post_id')
            post_context = comment.get('post_context')

            log_info(f"Processing comment {comment_id}")

            # Analyze comment
            category, sentiment_score = self.analyze_comment(comment_text, post_context)

            # Check if should flag for review
            flag_categories = self.comment_config.get('flag_for_review', ['negative'])
            flagged = category in flag_categories

            # Determine if should auto-reply
            should_reply = self.should_auto_reply(category)

            reply_text = None
            replied_at = None

            if should_reply and category not in self.comment_config.get('ignore', ['spam']):
                # Generate reply
                reply_text = self.generate_reply(comment_text, category, post_context)

                # Post reply
                if self.post_reply(comment_id, reply_text):
                    replied_at = datetime.now(self.sa_tz)

            # Save to database
            interaction_id = str(uuid.uuid4())
            interaction_data = {
                'id': interaction_id,
                'facebook_comment_id': comment_id,
                'post_id': post_id,
                'comment_text': comment_text,
                'comment_author': comment.get('from', {}).get('name', 'Unknown'),
                'comment_author_id': comment.get('from', {}).get('id', ''),
                'category': category,
                'reply_text': reply_text,
                'replied_at': replied_at.isoformat() if replied_at else None,
                'flagged_for_review': flagged,
                'sentiment_score': sentiment_score,
                'created_at': datetime.now(self.sa_tz).isoformat(),
                'updated_at': datetime.now(self.sa_tz).isoformat()
            }

            result = self.db.table('comment_interactions').insert(interaction_data).execute()

            if result.data:
                log_info(f"Saved comment interaction {interaction_id}")
                return {
                    'success': True,
                    'interaction_id': interaction_id,
                    'category': category,
                    'replied': replied_at is not None,
                    'flagged': flagged
                }
            else:
                log_error("Failed to save comment interaction")
                return {'success': False, 'error': 'Database save failed'}

        except Exception as e:
            log_error(f"Error processing comment: {e}")
            return {'success': False, 'error': str(e)}

    def process_new_comments(self) -> Dict:
        """
        Main entry point: fetch and process all new comments.

        Returns:
            Summary of processing results
        """
        try:
            # Reset daily counter if new day
            today = datetime.now(self.sa_tz).date()
            if self.last_check_date != today:
                self.daily_reply_count = 0
                self.last_check_date = today

            log_info("Starting comment processing cycle")

            # Fetch new comments
            comments = self.fetch_new_comments()

            if not comments:
                log_info("No new comments to process")
                return {
                    'total_comments': 0,
                    'processed': 0,
                    'replied': 0,
                    'flagged': 0
                }

            # Process each comment
            results = {
                'total_comments': len(comments),
                'processed': 0,
                'replied': 0,
                'flagged': 0,
                'errors': 0
            }

            for comment in comments:
                result = self.process_comment(comment)

                if result['success']:
                    results['processed'] += 1
                    if result.get('replied'):
                        results['replied'] += 1
                    if result.get('flagged'):
                        results['flagged'] += 1
                else:
                    results['errors'] += 1

            log_info(f"Comment processing complete: {results}")
            return results

        except Exception as e:
            log_error(f"Error in process_new_comments: {e}")
            return {'error': str(e)}

    def get_flagged_comments(self, limit: int = 50) -> List[Dict]:
        """
        Get comments flagged for human review.

        Args:
            limit: Maximum number of comments to return

        Returns:
            List of flagged comment interactions
        """
        try:
            result = self.db.table('comment_interactions').select(
                '*'
            ).eq('flagged_for_review', True).order(
                'created_at', desc=True
            ).limit(limit).execute()

            return result.data if result.data else []

        except Exception as e:
            log_error(f"Error fetching flagged comments: {e}")
            return []
