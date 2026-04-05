"""Response models for the indexes router."""

from pydantic import BaseModel


class IndexRecommendationSummary(BaseModel):
    """Aggregated index recommendation by type and confidence."""

    recommendation_type: str
    confidence: str
    count: str
    pending_review: str
    approved: str
    executed: str
    rejected: str


IndexRecommendationsResponse = list[IndexRecommendationSummary]
