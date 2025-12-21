"""Tests for text card content generation in ContentGenerator."""

import json
import pytest
from unittest.mock import Mock, patch
from social_media.content_generator import ContentGenerator


@pytest.fixture
def content_generator():
    """Create a ContentGenerator instance with mock config."""
    config = {
        "ai_influencer_settings": {
            "name": "Refiloe",
            "personality_traits": ["Authentic", "Practical", "Empowering"],
            "speaking_style": {
                "voice": "First person",
                "tone": "Conversational and engaging",
            },
        },
        "claude_api_key": "test-key",
        "model": "claude-3-5-sonnet-20241022",
    }
    return ContentGenerator(config)


class TestTextCardGeneration:
    """Test text card content generation methods."""

    def test_generate_quote_content(self, content_generator):
        """Test generating quote-type text card content."""
        mock_response = json.dumps({
            "type": "quote",
            "quote": "Your clients don't buy sessions. They buy transformation.",
            "attribution": "Refiloe",
            "caption": "This changed my approach to client conversations. 💪",
            "hashtags": ["#personaltrainer", "#fitnessbusiness", "#clientsuccess"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("quote")

            assert result["type"] == "quote"
            assert "quote" in result
            assert "attribution" in result
            assert "caption" in result
            assert "hashtags" in result
            assert len(result["quote"]) <= 150
            assert len(result["hashtags"]) > 0

    def test_generate_tip_content(self, content_generator):
        """Test generating tip-type text card content."""
        mock_response = json.dumps({
            "type": "tip",
            "header": "TIME SAVER",
            "tip": "Send automated session reminders 24 hours before appointments.",
            "subtitle": "Cuts no-shows by 70%",
            "caption": "This automation gave me back 5+ hours weekly. Try it!",
            "hashtags": ["#trainertools", "#adminautomation", "#trainerhacks"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("tip")

            assert result["type"] == "tip"
            assert "header" in result
            assert "tip" in result
            assert "subtitle" in result
            assert len(result["header"]) <= 20
            assert len(result["tip"]) <= 200
            assert len(result["subtitle"]) <= 80

    def test_generate_educational_content(self, content_generator):
        """Test generating educational-type text card content."""
        mock_response = json.dumps({
            "type": "educational",
            "title": "5 Signs a Client Will Ghost You",
            "points": [
                "They reschedule more than once in the first week",
                "They ask about refund policies before starting",
                "They don't respond to form check videos",
                "They're vague about their actual goals",
                "They compare your rates to big gym chains",
            ],
            "caption": "Learned this the hard way. Which one have you experienced?",
            "hashtags": ["#personaltrainer", "#clientmanagement", "#trainerlife"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("educational")

            assert result["type"] == "educational"
            assert "title" in result
            assert "points" in result
            assert len(result["title"]) <= 50
            assert 3 <= len(result["points"]) <= 5
            assert all(len(point) <= 60 for point in result["points"])

    def test_generate_motivation_content(self, content_generator):
        """Test generating motivation-type text card content."""
        mock_response = json.dumps({
            "type": "motivation",
            "statement": "You're building empires, one rep at a time.",
            "caption": "Every session builds your business. Keep going! 💪🔥",
            "hashtags": ["#trainermotivation", "#fitnessmindset", "#trainerlife"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("motivation")

            assert result["type"] == "motivation"
            assert "statement" in result
            assert len(result["statement"]) <= 100
            assert "caption" in result
            assert "hashtags" in result

    def test_random_content_type_selection(self, content_generator):
        """Test that content type is randomly selected when not specified."""
        mock_response = json.dumps({
            "type": "quote",
            "quote": "Test quote",
            "attribution": "Test",
            "caption": "Test caption",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content()

            # Should generate content (type will be one of the valid types)
            assert result["type"] in ["quote", "tip", "educational", "motivation"]

    def test_invalid_content_type_fallback(self, content_generator):
        """Test that invalid content type falls back to random selection."""
        mock_response = json.dumps({
            "type": "tip",
            "header": "TEST",
            "tip": "Test tip",
            "subtitle": "Test subtitle",
            "caption": "Test caption",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            # Use invalid content type
            result = content_generator.generate_text_card_content("invalid_type")

            # Should still generate content with a valid type
            assert result["type"] in ["quote", "tip", "educational", "motivation"]

    def test_empty_api_response(self, content_generator):
        """Test handling of empty API response."""
        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=""
        ):
            result = content_generator.generate_text_card_content("quote")

            # Should return empty dict on failure
            assert result == {}

    def test_invalid_json_response(self, content_generator):
        """Test handling of invalid JSON response."""
        with patch.object(
            content_generator, "_call_claude_with_retry", return_value="Not valid JSON"
        ):
            result = content_generator.generate_text_card_content("quote")

            # Should return empty dict on parse failure
            assert result == {}

    def test_missing_required_fields(self, content_generator):
        """Test validation rejects content missing required fields."""
        # Missing quote field
        mock_response = json.dumps({
            "type": "quote",
            "attribution": "Test",
            "caption": "Test caption",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("quote")

            # Should return empty dict when required field is missing
            assert result == {}

    def test_character_limits_enforced(self, content_generator):
        """Test that character limits are enforced through truncation."""
        # Quote exceeding 150 char limit
        long_quote = "A" * 200
        mock_response = json.dumps({
            "type": "quote",
            "quote": long_quote,
            "attribution": "Test",
            "caption": "Test caption",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("quote")

            # Should truncate to 150 chars
            assert len(result["quote"]) == 150

    def test_metadata_included(self, content_generator):
        """Test that metadata is added to generated content."""
        mock_response = json.dumps({
            "type": "quote",
            "quote": "Test quote",
            "attribution": "Test",
            "caption": "Test caption",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("quote")

            assert "metadata" in result
            assert result["metadata"]["content_type"] == "quote"
            assert result["metadata"]["ai_generated"] is True
            assert "generated_at" in result["metadata"]
            assert "model_used" in result["metadata"]

    def test_banned_words_filtered(self, content_generator):
        """Test that banned words are filtered from content."""
        mock_response = json.dumps({
            "type": "quote",
            "quote": "This problem gnaws at every trainer daily.",
            "attribution": "Test",
            "caption": "This issue gnaws at us all.",
            "hashtags": ["#test"],
        })

        with patch.object(
            content_generator, "_call_claude_with_retry", return_value=mock_response
        ):
            result = content_generator.generate_text_card_content("quote")

            # Banned word "gnaws" should be filtered out
            assert "gnaw" not in result["quote"].lower()
            assert "gnaw" not in result["caption"].lower()
