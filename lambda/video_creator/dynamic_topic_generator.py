"""
Dynamic Topic Generator - Autonomous Content Discovery
======================================================
LLM-based topic generation with diversity enforcement through:
1. History Injection (blacklist)
2. Constraint Roulette (random era/region/theme)
3. Micro-Detail Focus (obscurity bias)

Eliminates manual topic bucket management.
"""

import json
import random
import os
from typing import List, Optional, Dict
try:
    import boto3  # pyre-ignore[21]
    from pydantic import BaseModel, Field, ValidationError  # pyre-ignore[21]
except ImportError:
    boto3 = None
    BaseModel = None
    Field = None
    ValidationError = None

# ============================================================================
# PYDANTIC SCHEMA
# ============================================================================

if BaseModel and Field:
    class DynamicTopic(BaseModel):
        """Schema for LLM-generated topics."""
        title: str = Field(..., description="Viral, scroll-stopping title")
        wiki_entity: str = Field(..., description="Exact Wikipedia page name")
        era: str = Field(..., description="Historical era")
        figure: str = Field(..., description="Central historical figure or object")
        category: str = Field(..., description="Content category")
        obscurity_score: int = Field(..., ge=1, le=10, description="4-6: mainstream+angle, 7-10: obscure")
else:
    # Fallback if pydantic not available
    DynamicTopic = None

# ============================================================================
# CONSTRAINT ROULETTE POOLS
# ============================================================================

ERAS = [
    "ancient", "medieval", "ottoman_empire", "early_modern", 
    "19th_century", "ww1_ww2", "cold_war", "modern"
]

REGIONS = [
    "Asia", "Africa", "South America", "Europe", 
    "Middle East", "North America", "Oceania"
]

THEMES = [
    "bizarre medical ritual", "failed military operation", "elite scandal",
    "unusual punishment", "forgotten invention", "diplomatic betrayal",
    "strange diet/food history", "animal involved in war", "heist/theft",
    "architectural mystery", "assassination plot", "survival story",
    "religious controversy", "scientific accident", "royal intrigue"
]

# ============================================================================
# BEDROCK CLIENT HELPER (adapted from script_pipeline.py)
# ============================================================================

def get_bedrock_client(region_name: Optional[str] = None):
    """Initialize Bedrock client with region."""
    if not boto3:
        raise ImportError("boto3 not available")
    region = region_name or os.environ.get('AWS_REGION_NAME', 'us-east-1')
    return boto3.client('bedrock-runtime', region_name=region)


def invoke_bedrock(client, prompt: str, temperature: float = 0.8, max_tokens: int = 600) -> str:
    """
    Call Bedrock Claude model (adapted from script_pipeline.py pattern).
    
    Args:
        client: Bedrock runtime client
        prompt: The prompt to send
        temperature: Creativity level (0.8 for topic generation)
        max_tokens: Max response length
        
    Returns:
        Raw text response from Claude
    """
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body)
    )
    
    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']


# ============================================================================
# DYNAMIC TOPIC GENERATOR
# ============================================================================

def generate_dynamic_topic(
    past_entities: List[str],
    region_name: Optional[str] = None,
    category_weights: Optional[Dict[str, float]] = None
) -> Optional[dict]:
    """
    Generate a unique topic using LLM with diversity constraints.
    
    Args:
        past_entities: Last 50 wiki_entity values (blacklist)
        region_name: AWS region for Bedrock
        category_weights: Optional autopilot category preferences
        
    Returns:
        dict with keys: title, wiki_entity, era, figure, category, obscurity_score
        None if generation fails
    """
    # Spin the roulette
    chosen_era = random.choice(ERAS)
    chosen_region = random.choice(REGIONS)
    chosen_theme = random.choice(THEMES)
    
    # Format blacklist
    blacklist_str = "\n".join([f"- {entity}" for entity in past_entities[-50:]]) if past_entities else "None yet."
    
    # Build master prompt
    prompt = f"""You are an elite YouTube Shorts producer generating highly viral history content.
Your task is to find a fascinating historical topic and output ONLY valid JSON.

🚫 BLACKLIST - DO NOT USE THESE WIKI ENTITIES OR TOPICS (We already covered them):
{blacklist_str}

🎯 MANDATORY CONSTRAINTS FOR THIS RUN:
- Target Era: {chosen_era}
- Target Region: {chosen_region}
- Required Theme: {chosen_theme}

💡 OBSCURITY BIAS & MICRO-DETAILS (CRITICAL):
You CAN use mainstream historical events (like WWII, Roman Empire, Ottoman Empire), BUT you MUST NOT tell the main story.
Focus ONLY on a highly bizarre, forgotten, or shocking micro-detail hidden within that major event.

Examples:
- Bad: "The Fall of Constantinople"  Good: "The 60-meter chain that failed"
- Bad: "Gladiators in Ancient Rome"  Good: "Why Roman gladiators drank blood and ash"
- Bad: "WWII deception tactics"  Good: "The exploding chocolate bar that fooled Hitler"

Your Obscurity Score must be between 4 and 10:
- 4-6: Mainstream event + bizarre angle (acceptable)
- 7-10: Truly obscure/unknown event (ideal)

CRITICAL: The wiki_entity MUST be the exact Wikipedia page name that will return valid results.
For micro-details, choose the Wikipedia page most relevant to your specific angle.

Respond ONLY with valid JSON. No markdown blocks, no intro, no outro:
{{
  "title": "...",
  "wiki_entity": "...",
  "era": "...",
  "figure": "...",
  "category": "...",
  "obscurity_score": 8
}}
"""
    
    try:
        # Get Bedrock client
        client = get_bedrock_client(region_name)
        
        # LLM call
        raw_response = invoke_bedrock(client, prompt, temperature=0.8, max_tokens=600)
        
        # Clean JSON (remove markdown blocks if present)
        clean_json = raw_response.replace("```json", "").replace("```", "").strip()
        topic_dict = json.loads(clean_json)
        
        # Validate with Pydantic
        if DynamicTopic and ValidationError:
            validated_topic = DynamicTopic(**topic_dict)
            result = validated_topic.dict() if hasattr(validated_topic, 'dict') else validated_topic.model_dump()
        else:
            # Fallback if pydantic not available
            result = topic_dict
        
        print(f"🎯 Dynamic Topic Generated: '{result['title']}' (Entity: {result['wiki_entity']}, Score: {result.get('obscurity_score', 'N/A')})")
        print(f"   Constraints: {chosen_era} × {chosen_region} × {chosen_theme}")
        
        return result
        
    except ValidationError as e:
        print(f"❌ Pydantic Validation Failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ LLM did not return valid JSON: {e}")
        print(f"   Raw output: {raw_response[:200]}...")
        return None
    except Exception as e:
        print(f"❌ Error generating dynamic topic: {e}")
        return None


# ============================================================================
# HELPER: Get Recent Wiki Entities from DynamoDB
# ============================================================================

def get_recent_wiki_entities(limit: int = 50, region_name: Optional[str] = None) -> List[str]:
    """
    Fetch wiki_entity values from recent videos in DynamoDB.
    
    Args:
        limit: Number of recent videos to check
        region_name: AWS region
        
    Returns:
        List of wiki_entity strings
    """
    if not boto3:
        return []
    
    try:
        region = region_name or os.environ.get('AWS_REGION_NAME', 'us-east-1')
        table_name = os.environ.get('METRICS_TABLE_NAME', 'shorts_video_metrics')
        
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table = dynamodb.Table(table_name)
        
        # Query recent videos
        response = table.scan(
            Limit=limit,
            ProjectionExpression='metadata'
        )
        
        entities = []
        for item in response.get('Items', []):
            metadata = item.get('metadata', {})
            
            # Try multiple possible keys
            wiki_entity = (metadata.get('wiki_entity') or 
                          metadata.get('search_entity') or
                          metadata.get('topic'))
            
            if wiki_entity:
                entities.append(wiki_entity)
        
        print(f"📋 Retrieved {len(entities)} wiki entities from last {limit} videos")
        return entities
        
    except Exception as e:
        print(f"⚠️ Could not fetch wiki entities from DynamoDB: {e}")
        return []
