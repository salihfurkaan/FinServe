"""
FinServe AI Email Triage Engine
===============================
A proof-of-concept for automating client support email processing at FinServe.

Solves the problem: "Support tickets and emails are answered individually,
without a shared knowledge base or standard responses."

Architecture:
  1. Sensitivity Filter  — flags high-risk content for immediate human review
  2. Entity Extraction    — LLM extracts structured data from unstructured email
  3. Knowledge Retrieval  — matches category to policy knowledge base
  4. Draft Generation     — LLM generates a grounded, cited response
  5. Verification         — programmatically checks that the AI cited real sources
"""

import os
import json
import re
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from litellm import completion


# ──────────────────────────────────────────────
# 1. CONFIGURATION & DATA MODELS
# ──────────────────────────────────────────────

VALID_CATEGORIES = [
    "Loan Status",
    "Document Request",
    "Technical Issue",
    "Billing",
    "General Inquiry",
]

VALID_URGENCY_LEVELS = ["Low", "Medium", "High", "Critical"]


class EntityExtraction(BaseModel):
    """Structured representation of an incoming client email."""
    client_name: Optional[str] = None
    loan_id: Optional[str] = Field(None, pattern=r"LN-\d+")
    category: str
    urgency: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            return "General Inquiry"
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        if v not in VALID_URGENCY_LEVELS:
            return "Medium"
        return v


# ──────────────────────────────────────────────
# 2. KNOWLEDGE BASE
# ──────────────────────────────────────────────
# Centralised policy source — solves the "no shared knowledge base" problem.
# Each entry includes a traceable [Source: ...] tag for citation verification.

KNOWLEDGE_BASE = {
    "Loan Status": (
        "Loan disbursements typically process within 3-5 business days after all "
        "documents are verified. Clients can check real-time status via the client "
        "portal under 'My Applications'. For escalations, contact your assigned "
        "relationship manager. [Source: Ops-Manual-v2]"
    ),
    "Document Request": (
        "For SME loan applications, the following documents are required: "
        "(1) Valid government-issued ID, (2) Proof of registered business address, "
        "(3) Last 3 months of business bank statements, (4) Most recent audited "
        "financial statements or tax returns, (5) Company registration certificate. "
        "Documents can be uploaded via the client portal or emailed to "
        "documents@finserve.com. [Source: Compliance-HB]"
    ),
    "Technical Issue": (
        "For client portal access issues: try clearing browser cache or using an "
        "incognito window. Password resets can be initiated at portal.finserve.com/reset. "
        "If the issue persists, our IT support team is available Mon-Fri 9 AM - 5 PM. "
        "[Source: IT-Support-KB]"
    ),
    "Billing": (
        "Repayment due dates are set at loan origination. A 7-day grace period applies "
        "to all products; after that, a 2% monthly late-payment penalty is charged. "
        "Early repayment is allowed with no penalty for loans originated after Jan 2024. "
        "For billing disputes, contact billing@finserve.com. [Source: Loan-Terms]"
    ),
    "General Inquiry": (
        "FinServe offices are open Monday to Friday, 9 AM - 5 PM. You can reach us "
        "via email at support@finserve.com, by phone at +1-800-FINSERVE, or through "
        "the client portal chat. [Source: FAQ-General]"
    ),
}


# ──────────────────────────────────────────────
# 3. THE AI ENGINE
# ──────────────────────────────────────────────

class FinServeAIEngine:
    """
    Skeptical AI engine: extracts entities, retrieves policy, generates a draft,
    and then programmatically verifies the draft cites real sources.
    """

    def __init__(self, api_key: str = None, provider: str = "groq"):
        self.api_key = api_key
        self.model = (
            "groq/llama-3.3-70b-versatile" if provider == "groq"
            else "gpt-3.5-turbo"
        )
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key

    # ── Sensitivity filter ──────────────────────
    def _is_sensitive(self, text: str) -> bool:
        """Flags emails containing high-risk legal/compliance terms."""
        danger_terms = [
            "lawsuit", "legal action", "complain", "complaint",
            "ombudsman", "regulator", "fca", "fraud", "sue",
        ]
        return any(term in text.lower() for term in danger_terms)

    # ── Entity extraction ───────────────────────
    def _extract_entities(self, text: str, passed_api_key: str = None) -> EntityExtraction:
        """Uses LLM to extract structured data from unstructured email text."""
        system_prompt = (
            "You are a data extraction assistant for FinServe, a financial services company.\n"
            "Extract the following fields from the email and return ONLY valid JSON:\n"
            "- client_name: the sender's name (string or null)\n"
            "- loan_id: loan reference in format LN-XXXXX (string or null)\n"
            f"- category: one of {VALID_CATEGORIES}\n"
            f"- urgency: one of {VALID_URGENCY_LEVELS}\n"
            "Return ONLY the JSON object, no extra text."
        )
        
        # Determine which key to use
        current_key = passed_api_key or self.api_key or os.getenv("GROQ_API_KEY")
        if not current_key:
            raise ValueError("No Groq API Key provided.")
            
        if passed_api_key:
             os.environ["GROQ_API_KEY"] = passed_api_key

        response = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
        )
        raw_data = json.loads(response.choices[0].message.content)
        return EntityExtraction(**raw_data)

    # ── Draft generation ────────────────────────
    def _generate_draft(self, email_body: str, policy: str, client_name: str | None, passed_api_key: str = None) -> str:
        """Generates a grounded response using the retrieved policy context."""
        greeting = f"Dear {client_name}" if client_name else "Dear Client"
        system_prompt = (
            "You are a Senior Client Support Executive at FinServe, a corporate financial services firm.\n"
            "Rules:\n"
            "1. Address the client's query explicitly and exclusively using the provided policy.\n"
            "2. You MUST include the exact [Source: ...] tag from the policy within your response.\n"
            "3. Maintain a highly professional, formal, and objective corporate tone. Do not use overly enthusiastic or colloquial language.\n"
            "4. Keep the response concise, authoritative, and clear.\n"
            f"5. Start the response with '{greeting},'.\n"
            "6. Sign off as 'FinServe Client Support'."
        )
        
        current_key = passed_api_key or self.api_key or os.getenv("GROQ_API_KEY")
        if not current_key:
            raise ValueError("No Groq API Key provided.")
            
        if passed_api_key:
             os.environ["GROQ_API_KEY"] = passed_api_key
             
        response = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Client email: {email_body}\n\nPolicy to reference: {policy}"},
            ],
        )
        return response.choices[0].message.content

    # ── Main pipeline ───────────────────────────
    def process_email(self, subject: str, body: str, passed_api_key: str = None) -> Dict:
        """End-to-end email processing pipeline."""
        full_text = f"Subject: {subject}\n\n{body}"

        # Step 1: Risk assessment — bypass AI entirely for sensitive content
        if self._is_sensitive(full_text):
            return {
                "status": "ESCALATED",
                "reason": "High-risk terms detected. Routed to human agent immediately.",
                "audit_trail": {
                    "timestamp": datetime.now().isoformat(),
                    "process_version": "v1.0-skeptical",
                },
            }

        # Step 2: Entity extraction
        entities = self._extract_entities(full_text, passed_api_key)

        # Step 3: Knowledge retrieval
        policy_content = KNOWLEDGE_BASE.get(
            entities.category, KNOWLEDGE_BASE["General Inquiry"]
        )
        source_tag = re.search(r"\[Source: (.*?)\]", policy_content).group(1)

        # Step 4: Draft generation
        raw_draft = self._generate_draft(body, policy_content, entities.client_name, passed_api_key)

        # Step 5: Verification — check the AI actually cited the source
        source_verified = f"[Source: {source_tag}]" in raw_draft
        
        # Step 6: Formatting — Strip internal tags from the client-facing response
        clean_draft = re.sub(r'\[Source:.*?\]', '', raw_draft).strip()
        # Clean up any excessive whitespace left behind by the stripping
        clean_draft = re.sub(r'  +', ' ', clean_draft)
        clean_draft = re.sub(r' \.', '.', clean_draft)

        return {
            "status": "DRAFT_READY",
            "metadata": entities.model_dump(),
            "verification": {
                "source_cited": source_verified,
                "policy_used": source_tag,
            },
            "response_draft": clean_draft,
            "audit_trail": {
                "timestamp": datetime.now().isoformat(),
                "process_version": "v1.0-skeptical",
            },
        }


# ──────────────────────────────────────────────
# 4. DEMO SCENARIOS
# ──────────────────────────────────────────────

DEMO_SCENARIOS = [
    {
        "name": "Document Request — SME Loan",
        "subject": "Missing documents for LN-99821",
        "body": (
            "Hi, I am Salih. Which documents do I need to send for "
            "my SME loan application LN-99821?"
        ),
    },
    {
        "name": "Loan Status Enquiry",
        "subject": "When will my loan be disbursed?",
        "body": (
            "Hello, my name is Ahmed. I submitted all required documents "
            "for loan LN-10234 last week. Can you tell me when the funds "
            "will be disbursed?"
        ),
    },
    {
        "name": "Billing Dispute",
        "subject": "Late payment fee on my account",
        "body": (
            "Dear FinServe, I was charged a late fee on my loan LN-55123 "
            "but I paid within the grace period. Can you look into this?"
        ),
    },
    {
        "name": "Sensitive / Escalation (Legal Threat)",
        "subject": "Formal complaint regarding my loan",
        "body": (
            "I am extremely dissatisfied and will be filing a formal complaint "
            "with the financial ombudsman if this is not resolved immediately."
        ),
    },
]


def print_result(scenario_name: str, result: Dict) -> None:
    """Pretty-print a processing result to the console."""
    print(f"\n{'='*70}")
    print(f"  SCENARIO: {scenario_name}")
    print(f"{'='*70}")

    status = result["status"]
    if status == "ESCALATED":
        print(f"  Status   : {status}")
        print(f"  Reason   : {result['reason']}")
    else:
        meta = result["metadata"]
        verif = result["verification"]
        print(f"  Status   : {status}")
        print(f"  Client   : {meta.get('client_name', 'N/A')}")
        print(f"  Loan ID  : {meta.get('loan_id', 'N/A')}")
        print(f"  Category : {meta.get('category')}")
        print(f"  Urgency  : {meta.get('urgency')}")
        print(f"  Source OK : {'Yes' if verif['source_cited'] else 'NO — needs review'}")
        print(f"  Policy   : {verif['policy_used']}")
        print(f"\n  --- Draft Response ---")
        # Word-wrap the draft for readability
        draft = result["response_draft"]
        for line in draft.split("\n"):
            print(f"  {line}")

    print(f"\n  Timestamp: {result['audit_trail']['timestamp']}")
    print(f"{'='*70}\n")


# ──────────────────────────────────────────────
# 5. MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    load_dotenv()

    API_KEY = os.getenv("GROQ_API_KEY")
    if not API_KEY:
        raise SystemExit(
            "Error: GROQ_API_KEY environment variable is not set.\n"
            "Create a .env file with: GROQ_API_KEY=your-key-here\n"
            "Or set it in PowerShell: $env:GROQ_API_KEY = 'your-key-here'"
        )

    engine = FinServeAIEngine(api_key=API_KEY)

    print("\n" + "="*70)
    print("  FinServe AI Email Triage Engine — Demo")
    print("  Processing", len(DEMO_SCENARIOS), "sample emails...")
    print("="*70)

    for scenario in DEMO_SCENARIOS:
        result = engine.process_email(scenario["subject"], scenario["body"])
        print_result(scenario["name"], result)