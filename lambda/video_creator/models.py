from pydantic import BaseModel, Field, validator  # pyre-ignore[21]
from typing import List, Optional

# --- CORE STRUCTURES ---

class Hook(BaseModel):
    visual_prompt: str = Field(..., description="Visual description for the first 3 seconds")
    audio_text: str = Field(..., description="Voiceover text that grabs attention")
    
    @validator('audio_text')
    def check_length(cls, v):
        if len(v) > 200:
            print(f"⚠️ Warning: Hook audio text is long ({len(v)} chars).")
        return v

class Section(BaseModel):
    header: str = Field(..., description="Section header/title")
    body_text: str = Field(..., description="Main narrative text")
    duration_estimate: Optional[int] = Field(default=10, description="Estimated duration in seconds")

class VideoScript(BaseModel):
    title: str = Field(..., description="Video title")
    hook: Hook = Field(..., description="The hook object")
    sections: List[Section] = Field(..., description="List of script sections (context, body, outro)")
    cta: str = Field(..., description="Call to Action text")

    @validator('sections', pre=True)
    def validate_sections(cls, v):
        if not isinstance(v, list):
            return [v]
        return v

# --- INTERMEDIATE PIPELINE MODELS ---

class HookBatch(BaseModel):
    hooks: List[str]

class TitleBatch(BaseModel):
    titles: List[str]

class SectionVariants(BaseModel):
    variants: List[str]

class VisualRelevance(BaseModel):
    visual_relevance: int
    mismatch_risk: str
    suggestion: Optional[str] = ""

class HookKPI(BaseModel):
    instant_clarity: int
    curiosity_gap: int
    swipe_risk: int
    predicted_retention: int

class HookEvaluation(BaseModel):
    hook: str
    tension: Optional[float] = 0
    clarity: Optional[float] = 0
    scroll_stop: Optional[float] = 0
    word_count: Optional[float] = 0
    total: float
    fixes: List[str] = []

class HookEvaluationBatch(BaseModel):
    evaluations: List[HookEvaluation]

class SectionEvaluation(BaseModel):
    text: str
    clarity: Optional[float] = 0
    pacing: Optional[float] = 0
    punch: Optional[float] = 0
    total: float
    fixes: List[str] = []

class SectionEvaluationBatch(BaseModel):
    evaluations: List[SectionEvaluation]

class FinalEvaluation(BaseModel):
    """Structure for final script evaluation."""
    hook_impact: float
    flow: Optional[float] = 0  # Made optional - not always provided by LLM
    pacing: float
    punch: Optional[float] = 0  # Made optional - not always provided by LLM
    total: float
    weakest_section: str
    fix_suggestion: str
