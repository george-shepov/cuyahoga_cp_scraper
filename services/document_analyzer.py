"""
Case Document Analysis Service
LLM-powered analysis of court documents, PDFs, and filings
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import PyPDF2
from services.llm_service import LLMService, LLMProvider


class DocumentAnalyzer:
    """
    Analyzes legal documents using LLM and traditional NLP
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService(
            provider=LLMProvider.OLLAMA,
            model="llama3"
        )
    
    async def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Comprehensive PDF analysis
        
        Returns:
            - text_content: Extracted text
            - metadata: PDF metadata
            - document_type: Type of document (motion, order, brief, etc.)
            - key_entities: Extracted names, dates, amounts
            - summary: AI-generated summary
            - sentiment: Sentiment analysis
            - anomalies: Any detected anomalies
        """
        if not os.path.exists(pdf_path):
            return {"error": f"File not found: {pdf_path}"}
        
        # Extract text and metadata
        text_content, metadata = self._extract_pdf_content(pdf_path)
        
        if not text_content:
            return {"error": "Could not extract text from PDF"}
        
        # Analyze with LLM
        document_type = await self._classify_document_type(text_content)
        key_entities = await self.llm.extract_entities(text_content[:4000])  # Limit for token count
        summary = await self._generate_document_summary(text_content, document_type)
        sentiment = await self._analyze_document_sentiment(text_content, document_type)
        anomalies = await self.llm.detect_anomalies(metadata)
        
        # Extract specific legal elements
        legal_elements = await self._extract_legal_elements(text_content, document_type)
        
        return {
            "file_path": pdf_path,
            "file_size_bytes": os.path.getsize(pdf_path),
            "page_count": metadata.get("page_count", 0),
            "pdf_metadata": metadata,
            "text_content": text_content[:1000],  # First 1000 chars
            "full_text_length": len(text_content),
            "document_type": document_type,
            "key_entities": key_entities,
            "summary": summary,
            "sentiment": sentiment,
            "legal_elements": legal_elements,
            "anomalies": anomalies,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def _extract_pdf_content(self, pdf_path: str) -> tuple[str, Dict[str, Any]]:
        """Extract text and metadata from PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract metadata
                metadata = {
                    "page_count": len(pdf_reader.pages),
                    "creator": pdf_reader.metadata.get('/Creator', '') if pdf_reader.metadata else '',
                    "producer": pdf_reader.metadata.get('/Producer', '') if pdf_reader.metadata else '',
                    "author": pdf_reader.metadata.get('/Author', '') if pdf_reader.metadata else '',
                    "title": pdf_reader.metadata.get('/Title', '') if pdf_reader.metadata else '',
                    "subject": pdf_reader.metadata.get('/Subject', '') if pdf_reader.metadata else '',
                    "creation_date": pdf_reader.metadata.get('/CreationDate', '') if pdf_reader.metadata else '',
                }
                
                # Extract text from all pages
                text_content = ""
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                
                return text_content.strip(), metadata
        except Exception as e:
            return "", {"error": str(e)}
    
    async def _classify_document_type(self, text: str) -> str:
        """Classify the type of legal document"""
        prompt = f"""
        Classify this legal document into one of these categories:
        - MOTION (motion to dismiss, motion to suppress, etc.)
        - ORDER (court order, judgment entry)
        - BRIEF (legal brief, memorandum)
        - INDICTMENT (criminal indictment)
        - PLEA_AGREEMENT (plea bargain document)
        - SENTENCING (sentencing entry, judgment entry)
        - DISCOVERY (discovery materials)
        - TRANSCRIPT (court transcript)
        - OTHER
        
        Document excerpt:
        {text[:1000]}
        
        Return ONLY the category name, nothing else.
        """
        
        messages = [
            {"role": "system", "content": "You are a legal document classifier."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm._call_llm(messages, temperature=0.2, max_tokens=50)
        return result.get("content", "OTHER").strip().upper()
    
    async def _generate_document_summary(self, text: str, doc_type: str) -> str:
        """Generate concise summary of document"""
        prompt = f"""
        Summarize this {doc_type} legal document in 2-3 sentences.
        Focus on the key legal points and outcomes.
        
        Document:
        {text[:2000]}
        """
        
        messages = [
            {"role": "system", "content": "You are a legal document summarizer."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm._call_llm(messages, temperature=0.5, max_tokens=200)
        return result.get("content", "Summary unavailable")
    
    async def _analyze_document_sentiment(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Analyze sentiment from defendant's perspective"""
        prompt = f"""
        Analyze this {doc_type} from the defendant's perspective.
        
        Return JSON with:
        - sentiment_score: -1 to 1 (-1 = very bad for defendant, 1 = very good)
        - favorable_points: List of favorable aspects
        - unfavorable_points: List of unfavorable aspects
        - overall_assessment: Brief assessment
        
        Document excerpt:
        {text[:2000]}
        """
        
        messages = [
            {"role": "system", "content": "You are a legal sentiment analyzer."},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm._call_llm(messages, temperature=0.4)
        
        try:
            return json.loads(result.get("content", "{}"))
        except:
            return {"sentiment_score": 0, "error": "Parse error"}

    async def _extract_legal_elements(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract specific legal elements based on document type"""
        if doc_type == "SENTENCING":
            return await self._extract_sentencing_details(text)
        elif doc_type == "MOTION":
            return await self._extract_motion_details(text)
        elif doc_type == "ORDER":
            return await self._extract_order_details(text)
        else:
            return {}

    async def _extract_sentencing_details(self, text: str) -> Dict[str, Any]:
        """Extract sentencing information"""
        prompt = f"""
        Extract sentencing details from this document:

        {text[:3000]}

        Return JSON with:
        - sentence_type: (INCARCERATION, PROBATION, FINE, COMMUNITY_SERVICE, etc.)
        - duration_days: Number of days (if applicable)
        - fine_amount: Dollar amount (if applicable)
        - restitution_amount: Dollar amount (if applicable)
        - probation_terms: List of probation conditions
        - special_conditions: Any special conditions
        """

        messages = [
            {"role": "system", "content": "You are a legal document parser."},
            {"role": "user", "content": prompt}
        ]

        result = await self.llm._call_llm(messages, temperature=0.2)

        try:
            return json.loads(result.get("content", "{}"))
        except:
            return {}

    async def _extract_motion_details(self, text: str) -> Dict[str, Any]:
        """Extract motion details"""
        prompt = f"""
        Extract motion details:

        {text[:2000]}

        Return JSON with:
        - motion_type: Type of motion
        - filed_by: Who filed (DEFENSE, PROSECUTION)
        - relief_sought: What is being requested
        - legal_basis: Legal grounds cited
        """

        messages = [
            {"role": "system", "content": "You are a legal document parser."},
            {"role": "user", "content": prompt}
        ]

        result = await self.llm._call_llm(messages, temperature=0.2)

        try:
            return json.loads(result.get("content", "{}"))
        except:
            return {}

    async def _extract_order_details(self, text: str) -> Dict[str, Any]:
        """Extract court order details"""
        prompt = f"""
        Extract order details:

        {text[:2000]}

        Return JSON with:
        - order_type: Type of order
        - ruling: GRANTED, DENIED, PARTIALLY_GRANTED
        - effective_date: Date order takes effect
        - key_provisions: List of key provisions
        """

        messages = [
            {"role": "system", "content": "You are a legal document parser."},
            {"role": "user", "content": prompt}
        ]

        result = await self.llm._call_llm(messages, temperature=0.2)

        try:
            return json.loads(result.get("content", "{}"))
        except:
            return {}

    async def analyze_case_documents(self, case_dir: str) -> Dict[str, Any]:
        """
        Analyze all PDFs in a case directory
        """
        case_path = Path(case_dir)
        if not case_path.exists():
            return {"error": f"Directory not found: {case_dir}"}

        pdf_files = list(case_path.glob("*.pdf"))

        if not pdf_files:
            return {"error": "No PDF files found in directory"}

        analyses = []
        for pdf_file in pdf_files:
            analysis = await self.analyze_pdf(str(pdf_file))
            analyses.append({
                "filename": pdf_file.name,
                "analysis": analysis
            })

        # Generate case-level summary
        case_summary = await self._generate_case_summary(analyses)

        return {
            "case_directory": case_dir,
            "total_documents": len(pdf_files),
            "documents": analyses,
            "case_summary": case_summary,
            "analyzed_at": datetime.utcnow().isoformat()
        }

    async def _generate_case_summary(self, document_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate overall case summary from all documents"""
        # Collect all summaries
        summaries = [
            f"{doc['filename']}: {doc['analysis'].get('summary', 'N/A')}"
            for doc in document_analyses
            if 'analysis' in doc and 'summary' in doc['analysis']
        ]

        combined_text = "\n\n".join(summaries)

        prompt = f"""
        Based on these document summaries, provide an overall case assessment:

        {combined_text}

        Return JSON with:
        - case_status: Current status assessment
        - key_developments: List of key developments
        - defendant_position: Assessment of defendant's position (STRONG, MODERATE, WEAK)
        - next_steps: Likely next steps in the case
        - overall_sentiment: -1 to 1 score for defendant
        """

        messages = [
            {"role": "system", "content": "You are a legal case analyst."},
            {"role": "user", "content": prompt}
        ]

        result = await self.llm._call_llm(messages, temperature=0.5, max_tokens=500)

        try:
            return json.loads(result.get("content", "{}"))
        except:
            return {"error": "Could not generate case summary"}

