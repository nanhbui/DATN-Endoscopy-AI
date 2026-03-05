from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class BoundingBox(BaseModel):
    """Bounding box coordinates for detected object."""

    x1: float = Field(..., description="Top-left X coordinate")
    y1: float = Field(..., description="Top-left Y coordinate")
    x2: float = Field(..., description="Bottom-right X coordinate")
    y2: float = Field(..., description="Bottom-right Y coordinate")

    @validator('x2')
    def x2_greater_than_x1(cls, v, values):
        """Ensure x2 > x1."""
        if 'x1' in values and v <= values['x1']:
            raise ValueError('x2 must be greater than x1')
        return v

    @validator('y2')
    def y2_greater_than_y1(cls, v, values):
        """Ensure y2 > y1."""
        if 'y1' in values and v <= values['y1']:
            raise ValueError('y2 must be greater than y1')
        return v

    def area(self) -> float:
        """Calculate bounding box area."""
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def center(self) -> tuple[float, float]:
        """Calculate center point of bounding box."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class AngleMetadata(BaseModel):
    """
    Metadata from Phase 1 capture for a single angle.

    This model represents the data captured for one angle/view of the product,
    including image path, quality assessment results, and detection information.
    """

    angle_number: int = Field(..., ge=1, description="Angle number (1-indexed)")
    image_path: str = Field(..., description="Path to the captured image")
    timestamp: datetime = Field(default_factory=datetime.now, description="Capture timestamp")
    bbox: BoundingBox = Field(..., description="Bounding box of detected object")
    bbox_area: float = Field(..., gt=0, description="Area of bounding box in pixels²")
    track_id: Optional[int] = Field(None, description="YOLO tracking ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    iqa_passed: bool = Field(..., description="Whether IQA quality check passed")
    iqa_reason: str = Field(..., description="Reason for IQA result")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VisionFeatures(BaseModel):
    """
    Features extracted from product images using OpenAI Vision Model (GPT-4o).

    This model stores the structured output from the Vision API's multimodal analysis.
    """

    product_type: Optional[str] = Field(None, description="Identified product category or type")
    dominant_colors: List[str] = Field(default_factory=list, description="Main colors observed")
    material_guess: Optional[str] = Field(None, description="Estimated material composition")
    text_found: List[str] = Field(default_factory=list, description="Any visible text or labels")
    shape_description: Optional[str] = Field(None, description="Overall shape characteristics")
    dimensions_estimate: Optional[str] = Field(None, description="Approximate size description")
    notable_features: List[str] = Field(default_factory=list, description="Distinctive characteristics")
    condition: Optional[str] = Field(None, description="Product condition assessment")
    brand_identified: Optional[str] = Field(None, description="Any visible brand information")
    additional_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any other relevant details from vision analysis"
    )
    raw_response: Optional[str] = Field(None, description="Raw LLM response for reference")


class MVVResult(BaseModel):
    """
    Result of Multi-View Verification process.

    This model contains the output from the simulated MVV algorithm that
    validates consistency across multiple captured angles, plus vision-extracted features.
    """

    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score from MVV (0.0 to 1.0)"
    )
    summary_text: str = Field(
        ...,
        description="Compiled summary of all identifying features across angles"
    )
    angle_consistency: Dict[str, Any] = Field(
        default_factory=dict,
        description="Consistency metrics between angles"
    )
    verified: bool = Field(..., description="Whether MVV verification passed")
    verification_reason: str = Field(..., description="Reason for verification result")

    # Vision Model extracted features
    vision_features: Optional[VisionFeatures] = Field(
        None,
        description="Features extracted using OpenAI Vision Model (GPT-4o)"
    )


class ProductRecord(BaseModel):
    """
    Primary schema for storing product data in MongoDB.

    This is the complete record that combines Phase 1 metadata,
    MVV results, and prepares data for RAG retrieval.
    """

    # Session and identification
    session_id: str = Field(..., description="Unique session identifier")
    product_id: Optional[str] = Field(None, description="Product identifier (if known)")

    # Capture metadata
    total_angles: int = Field(..., ge=1, description="Total number of angles captured")
    captured_angles: List[AngleMetadata] = Field(
        ...,
        min_items=1,
        description="List of all captured angle metadata"
    )

    # Multi-View Verification results
    mvv_result: Optional[MVVResult] = Field(None, description="MVV verification results")

    # RAG-ready summary
    summary_for_rag: str = Field(
        ...,
        description="Consolidated summary text optimized for RAG retrieval"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")

    # Additional metadata
    output_directory: str = Field(..., description="Directory containing captured images")
    notes: Optional[str] = Field(None, description="Additional notes or comments")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('captured_angles')
    def validate_angles_count(cls, v, values):
        """Ensure captured angles match total_angles."""
        if 'total_angles' in values and len(v) != values['total_angles']:
            raise ValueError(
                f"Number of captured angles ({len(v)}) must match "
                f"total_angles ({values['total_angles']})"
            )
        return v


class ScopeClassification(str, Enum):
    """Scope classification for chatbot queries."""

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"


class TopicClassificationResult(BaseModel):
    """
    Model for the output of scope control logic in the RAG chatbot.

    This determines whether a user query is relevant to the product
    domain or should be rejected.
    """

    classification: ScopeClassification = Field(
        ...,
        description="Whether query is in-scope or out-of-scope"
    )
    is_in_scope: bool = Field(..., description="Boolean flag for scope check")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence of classification (0.0 to 1.0)"
    )
    reason: str = Field(..., description="Explanation for the classification")
    suggested_response: Optional[str] = Field(
        None,
        description="Suggested response if out-of-scope"
    )

    @validator('is_in_scope', always=True)
    def sync_is_in_scope(cls, v, values):
        """Ensure is_in_scope matches classification."""
        if 'classification' in values:
            return values['classification'] == ScopeClassification.IN_SCOPE
        return v


class RetrievalResult(BaseModel):
    """Result from vector database retrieval."""
    document_text: str = Field(..., description="Retrieved document text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    similarity_score: float = Field(
        ...,
        description="Score indicating distance/similarity (can be negative or outside 0-1)"
    )

class ToolCallResult(BaseModel):
    """Result from a tool invocation (RAG or Tavily)."""

    tool_name: str = Field(..., description="Name of the tool called")
    success: bool = Field(..., description="Whether tool call succeeded")
    result: Any = Field(..., description="Tool result data")
    error: Optional[str] = Field(None, description="Error message if failed")


class AgentState(BaseModel):
    """
    State object for the LangGraph workflow.

    This maintains the conversation state as the agent processes
    a user query through the RAG pipeline.
    """

    # User input
    user_query: str = Field(..., description="Original user query")

    # Topic classification
    topic_classification: Optional[TopicClassificationResult] = Field(
        None,
        description="Result of scope classification"
    )

    # Retrieval results
    rag_results: List[RetrievalResult] = Field(
        default_factory=list,
        description="Results from RAG retrieval"
    )

    # External search results
    tavily_results: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Results from Tavily search (if invoked)"
    )

    # Tool calls
    tool_calls: List[ToolCallResult] = Field(
        default_factory=list,
        description="History of tool calls made"
    )

    # Context for generation
    context: str = Field(default="", description="Compiled context for LLM generation")

    # Final response
    final_response: Optional[str] = Field(None, description="Generated response")

    # Workflow control
    should_retrieve: bool = Field(True, description="Whether to perform RAG retrieval")
    should_search_external: bool = Field(False, description="Whether to use Tavily search")
    workflow_complete: bool = Field(False, description="Whether workflow is complete")

    # Metadata
    conversation_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        description="Unique conversation identifier"
    )
    started_at: datetime = Field(default_factory=datetime.now, description="Conversation start time")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatMessage(BaseModel):
    """Individual chat message in a conversation."""

    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationHistory(BaseModel):
    """Complete conversation history for a chat session."""

    conversation_id: str = Field(..., description="Unique conversation identifier")
    messages: List[ChatMessage] = Field(default_factory=list, description="List of messages")
    started_at: datetime = Field(default_factory=datetime.now, description="Conversation start")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last message time")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a new message to the conversation."""
        message = ChatMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_updated = datetime.now()
