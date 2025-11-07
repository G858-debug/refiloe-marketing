"""Reusable templates for common social media post types.

This module provides structured templates for different categories of social media
content, each with guidelines for hooks, body content, avatar styles, hashtags,
and optimal posting times. Templates are designed to streamline content creation
while maintaining consistency across the fitness coaching brand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PostTemplate:
    """Structured template for a social media post.

    Attributes:
        name: Template identifier
        category: Post category (pain_point, success_story, educational, engagement)
        hook_structure: Guidelines for creating an attention-grabbing title/hook
        body_guidelines: Content structure and messaging guidelines
        avatar_style: Recommended avatar presentation style for video generation
        hashtags: Suggested hashtags for the post
        optimal_posting_time: Best time(s) to post for maximum engagement
        tone: Voice and tone guidelines (e.g., empathetic, celebratory, informative)
        call_to_action: Suggested CTAs for the post
    """

    name: str
    category: str
    hook_structure: str
    body_guidelines: List[str]
    avatar_style: str
    hashtags: List[str]
    optimal_posting_time: str
    tone: str = "professional"
    call_to_action: Optional[str] = None


# ============================================================================
# PAIN POINT POSTS
# ============================================================================

PAIN_POINT_TEMPLATES: Dict[str, PostTemplate] = {
    "that_moment_when": PostTemplate(
        name="that_moment_when",
        category="pain_point",
        hook_structure=(
            "Start with 'That moment when...' followed by a specific, relatable "
            "trainer struggle. Keep it under 10 words for maximum impact."
        ),
        body_guidelines=[
            "Open with the relatable pain point that resonates emotionally",
            "Acknowledge the frustration or challenge (empathy first)",
            "Pivot to a practical solution or mindset shift",
            "End with hope or a clear action step",
            "Keep total length 150-200 characters for Instagram/Twitter optimization",
        ],
        avatar_style="CLOSEUP_EMPATHETIC",
        hashtags=[
            "#TrainerLife",
            "#FitnessCoach",
            "#PersonalTrainerProblems",
            "#FitnessEntrepreneur",
            "#TrainerTips",
        ],
        optimal_posting_time="Tuesday-Thursday, 7-9 AM or 6-8 PM",
        tone="empathetic and relatable",
        call_to_action="Comment below if you've experienced this! 👇",
    ),
    "pov_trainer": PostTemplate(
        name="pov_trainer",
        category="pain_point",
        hook_structure=(
            "Use 'POV: You're a trainer and...' format to set up a specific scenario. "
            "Make it hyper-specific to increase relatability."
        ),
        body_guidelines=[
            "Set the scene with vivid, specific details",
            "Build tension or highlight the challenge",
            "Show the internal monologue or decision point",
            "Resolve with either humor, solution, or solidarity",
            "Use conversational language and contractions",
        ],
        avatar_style="FULLBODY_DEMONSTRATIVE",
        hashtags=[
            "#POV",
            "#TrainerLife",
            "#FitnessBusiness",
            "#GymOwner",
            "#PersonalTrainer",
            "#FitnessReality",
        ],
        optimal_posting_time="Monday, Wednesday, Friday, 8-10 AM",
        tone="humorous yet authentic",
        call_to_action="Tag a trainer who gets it! 😂",
    ),
    "struggle_to_solution": PostTemplate(
        name="struggle_to_solution",
        category="pain_point",
        hook_structure=(
            "Lead with a common struggle statement: 'Struggling with [X]?' or "
            "'[X] is the #1 problem trainers face.' Make it urgent and specific."
        ),
        body_guidelines=[
            "State the problem clearly in the first sentence",
            "Validate why this problem is significant (statistics/emotions)",
            "Present 2-3 concrete, actionable solutions",
            "Use bullet points or numbered lists for clarity",
            "End with encouragement and next steps",
        ],
        avatar_style="PROFESSIONAL_CLOSEUP",
        hashtags=[
            "#FitnessTips",
            "#TrainerHacks",
            "#ProblemSolved",
            "#FitnessAdvice",
            "#TrainerSupport",
        ],
        optimal_posting_time="Tuesday, Thursday, 12-2 PM",
        tone="solution-oriented and supportive",
        call_to_action="Save this for when you need it! 📌 Which tip will you try first?",
    ),
}


# ============================================================================
# SUCCESS STORY POSTS
# ============================================================================

SUCCESS_STORY_TEMPLATES: Dict[str, PostTemplate] = {
    "client_transformation": PostTemplate(
        name="client_transformation",
        category="success_story",
        hook_structure=(
            "Start with the dramatic result: '[Name] lost X lbs / gained Y strength / "
            "achieved Z milestone.' Lead with the outcome, then tell the story."
        ),
        body_guidelines=[
            "Open with the powerful end result (hook)",
            "Describe the starting point (where they were)",
            "Highlight 2-3 key turning points in the journey",
            "Share specific strategies or mindset shifts used",
            "Give credit to client's hard work and dedication",
            "End with current status and future goals",
            "Include a quote from the client if possible",
        ],
        avatar_style="CONFIDENT_SWIMWEAR_FULLBODY",
        hashtags=[
            "#TransformationTuesday",
            "#ClientSuccess",
            "#FitnessResults",
            "#BeforeAndAfter",
            "#PersonalTrainerSuccess",
            "#RealResults",
        ],
        optimal_posting_time="Tuesday (Transformation Tuesday), 9-11 AM",
        tone="celebratory and inspiring",
        call_to_action="Drop a 🔥 to celebrate [Name]'s incredible journey!",
    ),
    "milestone_achievement": PostTemplate(
        name="milestone_achievement",
        category="success_story",
        hook_structure=(
            "Announce the milestone immediately: 'MAJOR WIN:' or 'MILESTONE ALERT:' "
            "followed by the specific achievement. Use emojis for visual impact."
        ),
        body_guidelines=[
            "Announce the milestone with energy and excitement",
            "Provide context: what made this milestone significant",
            "Share the timeline (how long it took)",
            "Mention obstacles overcome along the way",
            "Highlight the lesson or takeaway",
            "Acknowledge everyone who contributed",
        ],
        avatar_style="CELEBRATORY_FULLBODY",
        hashtags=[
            "#MilestoneMonday",
            "#GoalAchieved",
            "#FitnessGoals",
            "#SuccessStory",
            "#TrainerWin",
            "#CelebrateSuccess",
        ],
        optimal_posting_time="Monday (Milestone Monday), 10 AM-12 PM",
        tone="proud and energetic",
        call_to_action="What's your next big milestone? Tell me below! ⬇️",
    ),
    "before_after_narrative": PostTemplate(
        name="before_after_narrative",
        category="success_story",
        hook_structure=(
            "Create contrast: 'BEFORE: [struggle/situation] → AFTER: [achievement/new reality]' "
            "Format for immediate visual/emotional impact."
        ),
        body_guidelines=[
            "Use clear BEFORE/AFTER structure",
            "BEFORE section: describe physical and emotional state",
            "Include specific details (measurements, feelings, limitations)",
            "AFTER section: current state with specific improvements",
            "THE JOURNEY: highlight 3-4 key changes made",
            "Include timeline and sustainable approach emphasis",
            "End with what's next or maintaining the success",
        ],
        avatar_style="CONFIDENT_SWIMWEAR_FULLBODY",
        hashtags=[
            "#BeforeAndAfter",
            "#TransformationStory",
            "#FitnessJourney",
            "#ProgressNotPerfection",
            "#RealTransformation",
        ],
        optimal_posting_time="Tuesday, Friday, 8-10 AM",
        tone="inspiring and honest",
        call_to_action="Double-tap if this inspires you to start YOUR journey! 💪",
    ),
}


# ============================================================================
# EDUCATIONAL POSTS
# ============================================================================

EDUCATIONAL_TEMPLATES: Dict[str, PostTemplate] = {
    "myth_busting": PostTemplate(
        name="myth_busting",
        category="educational",
        hook_structure=(
            "Lead with 'MYTH:' or 'Stop believing...' or 'The truth about [X]' "
            "Call out the myth directly and create curiosity."
        ),
        body_guidelines=[
            "State the myth clearly and boldly",
            "Explain why people believe it (validate the confusion)",
            "Present the TRUTH with evidence or expert reasoning",
            "Explain the practical implications",
            "Provide the correct approach or alternative",
            "Use simple language to explain complex concepts",
        ],
        avatar_style="PROFESSIONAL_CLOSEUP",
        hashtags=[
            "#FitnessMyths",
            "#FitnessFacts",
            "#TrainerTruth",
            "#MythBusting",
            "#FitnessEducation",
            "#KnowledgeIsPower",
        ],
        optimal_posting_time="Monday, Wednesday, 1-3 PM",
        tone="authoritative yet approachable",
        call_to_action="Share this with someone who needs to hear it! What other myths should I bust?",
    ),
    "quick_tips": PostTemplate(
        name="quick_tips",
        category="educational",
        hook_structure=(
            "Number it: '3 Quick Tips to [achieve X]' or '5 Things Every Trainer Should Know' "
            "Promise quick, actionable value upfront."
        ),
        body_guidelines=[
            "Use numbered list format (3-5 tips maximum)",
            "Each tip should be one clear, actionable point",
            "Keep each tip to 1-2 sentences",
            "Use action verbs: 'Start with...', 'Try...', 'Focus on...'",
            "Include why each tip matters (brief explanation)",
            "End with encouragement to implement",
        ],
        avatar_style="FITNESS_FULLBODY",
        hashtags=[
            "#FitnessTips",
            "#QuickTips",
            "#TrainerAdvice",
            "#HealthTips",
            "#WorkoutTips",
            "#FitnessHacks",
        ],
        optimal_posting_time="Daily, 7-9 AM or 5-7 PM",
        tone="helpful and energetic",
        call_to_action="Save this for later! 💾 Which tip resonates most with you?",
    ),
    "how_to_guide": PostTemplate(
        name="how_to_guide",
        category="educational",
        hook_structure=(
            "Start with 'How to [achieve specific outcome]' or 'The complete guide to [X]' "
            "Be specific about the outcome they'll achieve."
        ),
        body_guidelines=[
            "Open with why this matters (the problem it solves)",
            "Break down into clear, sequential steps",
            "Use step numbers or bullet points",
            "Include pro tips or common pitfalls to avoid",
            "Provide context for when/how to use this",
            "End with expected results or next level tips",
            "Make it actionable within 24 hours",
        ],
        avatar_style="DEMONSTRATIVE_FULLBODY",
        hashtags=[
            "#HowTo",
            "#FitnessGuide",
            "#TrainerEducation",
            "#StepByStep",
            "#LearnWithMe",
            "#FitnessKnowledge",
        ],
        optimal_posting_time="Tuesday, Thursday, 11 AM-1 PM",
        tone="instructive and thorough",
        call_to_action="Bookmark this guide! 📚 Questions? Drop them below!",
    ),
}


# ============================================================================
# ENGAGEMENT POSTS
# ============================================================================

ENGAGEMENT_TEMPLATES: Dict[str, PostTemplate] = {
    "question_prompts": PostTemplate(
        name="question_prompts",
        category="engagement",
        hook_structure=(
            "Ask a compelling question: 'What's your biggest [X]?' or "
            "'Hot take: [controversial opinion]—agree or disagree?' Make it provocative."
        ),
        body_guidelines=[
            "Lead with the question in the first line",
            "Provide context or your own answer to model responses",
            "Keep it open-ended to encourage discussion",
            "Ask about experiences, opinions, or preferences",
            "Use emojis to make multiple-choice options visual",
            "Avoid yes/no questions—seek stories and details",
        ],
        avatar_style="CONVERSATIONAL_CLOSEUP",
        hashtags=[
            "#LetsTalk",
            "#TrainerCommunity",
            "#FitnessDiscussion",
            "#YourOpinion",
            "#EngageWithMe",
        ],
        optimal_posting_time="Wednesday, Friday, 6-8 PM",
        tone="curious and conversational",
        call_to_action="I'll respond to every comment! 💬 Go!",
    ),
    "poll_ideas": PostTemplate(
        name="poll_ideas",
        category="engagement",
        hook_structure=(
            "Frame the poll: 'Quick poll:' or 'Settle this debate:' or 'Which one are you?' "
            "Make the options clear and distinct."
        ),
        body_guidelines=[
            "State the poll question clearly",
            "Provide 2-4 distinct options",
            "Use emojis or letters (A/B/C) to identify choices",
            "Add brief context if needed",
            "Share why you're asking or what you'll do with results",
            "Keep it light and fun, not heavy or controversial",
        ],
        avatar_style="FRIENDLY_CLOSEUP",
        hashtags=[
            "#Poll",
            "#YourVote",
            "#TrainerPoll",
            "#WeightIn",
            "#FitnessOpinion",
        ],
        optimal_posting_time="Monday, Thursday, 12-2 PM",
        tone="playful and inclusive",
        call_to_action="Vote below! 🗳️ Can't wait to see the results!",
    ),
    "call_to_action": PostTemplate(
        name="call_to_action",
        category="engagement",
        hook_structure=(
            "Direct command or invitation: 'Tag a friend who...' or 'Share if you...' or "
            "'Drop a [emoji] if you agree' Make the action crystal clear."
        ),
        body_guidelines=[
            "State the desired action in the first sentence",
            "Explain why they should take action (benefit/reason)",
            "Keep the barrier to action LOW (simple comment/tag/share)",
            "Make it specific: not just 'comment' but 'comment your favorite...'",
            "Create urgency or exclusivity when appropriate",
            "Acknowledge and thank participants",
        ],
        avatar_style="MOTIVATIONAL_FULLBODY",
        hashtags=[
            "#TakeAction",
            "#JoinMe",
            "#GetInvolved",
            "#FitnessCommunity",
            "#EngageNow",
        ],
        optimal_posting_time="Daily, 8-10 AM",
        tone="motivating and direct",
        call_to_action="Do it now! ⏰ I'm watching the comments!",
    ),
}


# ============================================================================
# TEMPLATE REGISTRY AND HELPERS
# ============================================================================

ALL_TEMPLATES: Dict[str, PostTemplate] = {
    **PAIN_POINT_TEMPLATES,
    **SUCCESS_STORY_TEMPLATES,
    **EDUCATIONAL_TEMPLATES,
    **ENGAGEMENT_TEMPLATES,
}


def get_template(template_name: str) -> Optional[PostTemplate]:
    """Retrieve a template by name.

    Args:
        template_name: The identifier for the template

    Returns:
        PostTemplate if found, None otherwise
    """
    return ALL_TEMPLATES.get(template_name)


def get_templates_by_category(category: str) -> List[PostTemplate]:
    """Retrieve all templates for a specific category.

    Args:
        category: One of 'pain_point', 'success_story', 'educational', 'engagement'

    Returns:
        List of PostTemplate objects matching the category
    """
    return [
        template for template in ALL_TEMPLATES.values()
        if template.category == category
    ]


def list_all_template_names() -> List[str]:
    """Get a list of all available template names.

    Returns:
        List of template identifier strings
    """
    return list(ALL_TEMPLATES.keys())


def get_template_summary() -> Dict[str, int]:
    """Get a count of templates by category.

    Returns:
        Dictionary mapping category names to template counts
    """
    summary: Dict[str, int] = {}
    for template in ALL_TEMPLATES.values():
        summary[template.category] = summary.get(template.category, 0) + 1
    return summary


__all__ = [
    "PostTemplate",
    "PAIN_POINT_TEMPLATES",
    "SUCCESS_STORY_TEMPLATES",
    "EDUCATIONAL_TEMPLATES",
    "ENGAGEMENT_TEMPLATES",
    "ALL_TEMPLATES",
    "get_template",
    "get_templates_by_category",
    "list_all_template_names",
    "get_template_summary",
]
