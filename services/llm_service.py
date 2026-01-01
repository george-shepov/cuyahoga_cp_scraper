"""
LLM Service Layer
Provides AI-powered analysis and extraction capabilities
Supports multiple LLM providers via LiteLLM
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

try:
    from litellm import completion, acompletion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not installed. LLM features will be disabled.")


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GROQ = "groq"


class LLMService:
    """
    Unified LLM service supporting multiple providers
    """
    
    def __init__(
        self,
        provider: LLMProvider = LLMProvider.OLLAMA,
        model: str = "llama3",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is required for LLM features. Install with: pip install litellm")
    
    def _get_model_name(self) -> str:
        """Get the full model name for litellm"""
        if self.provider == LLMProvider.OLLAMA:
            return f"ollama/{self.model}"
        elif self.provider == LLMProvider.OPENAI:
            return f"gpt-{self.model}"
        elif self.provider == LLMProvider.ANTHROPIC:
            return f"claude-{self.model}"
        return self.model
    
    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Internal method to call LLM"""
        try:
            response = await acompletion(
                model=self._get_model_name(),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=self.api_key,
                api_base=self.base_url if self.provider == LLMProvider.OLLAMA else None
            )
            
            return {
                "content": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None,
                "model": response.model
            }
        except Exception as e:
            return {
                "error": str(e),
                "content": None,
                "tokens_used": 0
            }
    
    async def extract_charges_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract structured charge information from unstructured text
        """
        prompt = f"""
        Extract all criminal charges from the following text and return them as a JSON array.
        For each charge, extract:
        - statute: The statute code (e.g., "2903.11.A(1)")
        - description: The charge description
        - severity: Classify as "felony" or "misdemeanor"
        - is_violent: true if it's a violent crime, false otherwise
        
        Text:
        {text}
        
        Return ONLY valid JSON, no other text.
        """
        
        messages = [
            {"role": "system", "content": "You are a legal data extraction assistant. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self._call_llm(messages, temperature=0.3)
        
        if result.get("error"):
            return []
        
        try:
            charges = json.loads(result["content"])
            return charges if isinstance(charges, list) else []
        except json.JSONDecodeError:
            return []
    
    async def analyze_docket_sentiment(self, docket_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze sentiment of docket entries to gauge case progression
        Returns sentiment scores and key events
        """
        # Combine docket entries into text
        docket_text = "\n".join([
            f"{entry.get('col1', '')}: {entry.get('col5', '')}"
            for entry in docket_entries[:20]  # Limit to recent 20 entries
        ])
        
        prompt = f"""
        Analyze the following court docket entries and provide:
        1. Overall sentiment score (-1 to 1, where -1 is very negative for defendant, 1 is very positive)
        2. Key favorable events for the defendant
        3. Key unfavorable events for the defendant
        4. Case momentum (improving, declining, stable)
        
        Docket entries:
        {docket_text}
        
        Return as JSON with keys: sentiment_score, favorable_events, unfavorable_events, momentum
        """
        
        messages = [
            {"role": "system", "content": "You are a legal analyst. Analyze court dockets objectively."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self._call_llm(messages, temperature=0.5)
        
        if result.get("error"):
            return {"sentiment_score": 0, "error": result["error"]}
        
        try:
            return json.loads(result["content"])
        except json.JSONDecodeError:
            return {"sentiment_score": 0, "error": "Failed to parse LLM response"}

    async def predict_case_outcome(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict likely case outcome based on historical patterns
        """
        # Extract key features
        charges = case_data.get("summary", {}).get("charges", [])
        docket_count = len(case_data.get("docket", []))
        has_attorney = len(case_data.get("attorneys", [])) > 0

        prompt = f"""
        Based on the following case information, predict the likely outcome:

        Charges: {len(charges)} charges
        Docket entries: {docket_count}
        Has attorney: {has_attorney}
        Judge: {case_data.get("summary", {}).get("fields", {}).get("Judge Name:", "Unknown")}

        Provide:
        1. predicted_outcome: One of [CONVICTED, DISMISSED, PLEA_BARGAIN, ACQUITTED]
        2. confidence: 0-1 score
        3. reasoning: Brief explanation
        4. key_factors: List of factors influencing prediction

        Return as JSON.
        """

        messages = [
            {"role": "system", "content": "You are a legal outcome prediction system."},
            {"role": "user", "content": prompt}
        ]

        result = await self._call_llm(messages, temperature=0.4)

        if result.get("error"):
            return {"predicted_outcome": "UNKNOWN", "confidence": 0, "error": result["error"]}

        try:
            return json.loads(result["content"])
        except json.JSONDecodeError:
            return {"predicted_outcome": "UNKNOWN", "confidence": 0, "error": "Parse error"}

    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text (people, organizations, dates, amounts)
        """
        prompt = f"""
        Extract all named entities from the following text:

        {text}

        Return JSON with keys:
        - people: List of person names
        - organizations: List of organizations
        - dates: List of dates
        - amounts: List of monetary amounts
        - locations: List of locations
        """

        messages = [
            {"role": "system", "content": "You are a named entity extraction system."},
            {"role": "user", "content": prompt}
        ]

        result = await self._call_llm(messages, temperature=0.2)

        if result.get("error"):
            return {}

        try:
            return json.loads(result["content"])
        except json.JSONDecodeError:
            return {}

    async def summarize_case(self, case_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable case summary
        """
        defendant_name = case_data.get("defendant", {}).get("name", "Unknown")
        case_id = case_data.get("metadata", {}).get("case_id", "Unknown")
        charges = case_data.get("summary", {}).get("charges", [])

        prompt = f"""
        Write a concise 2-3 sentence summary of this criminal case:

        Case ID: {case_id}
        Defendant: {defendant_name}
        Number of charges: {len(charges)}
        Status: {case_data.get("summary", {}).get("fields", {}).get("Status:", "Unknown")}

        Focus on the most important facts.
        """

        messages = [
            {"role": "system", "content": "You are a legal case summarizer."},
            {"role": "user", "content": prompt}
        ]

        result = await self._call_llm(messages, temperature=0.6, max_tokens=200)

        return result.get("content", "Summary unavailable")

    async def detect_anomalies(self, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect anomalies in PDF metadata (like Brad Davis pattern)
        """
        prompt = f"""
        Analyze this PDF metadata for anomalies:

        {json.dumps(pdf_metadata, indent=2)}

        Look for:
        - Unusual creator/author names
        - Mismatched dates
        - Suspicious patterns

        Return JSON with:
        - has_anomaly: boolean
        - anomaly_type: string or null
        - confidence: 0-1
        - details: explanation
        """

        messages = [
            {"role": "system", "content": "You are a document forensics analyst."},
            {"role": "user", "content": prompt}
        ]

        result = await self._call_llm(messages, temperature=0.3)

        if result.get("error"):
            return {"has_anomaly": False, "error": result["error"]}

        try:
            return json.loads(result["content"])
        except json.JSONDecodeError:
            return {"has_anomaly": False, "error": "Parse error"}

