import logging
from typing import List, Optional, Dict, Any
from pydantic import Field

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.models.rag import RAGRetrieveRequest, RAGEvidenceItem
from app.models.chunk import ProtocolChunk
from app.services.context_assembler import context_assembler
from app.services.embedding_service import embedding_service

logger = logging.getLogger("icf_generator.langchain_adapters")


def to_langchain_document(source_obj: Any) -> Document:
    """
    Converts internal ProtocolChunk or RAGEvidenceItem into a standard LangChain Document object.
    Preserves all chunk metadata including chunk_id, section, page_number, and study_id.
    """
    if isinstance(source_obj, Document):
        return source_obj

    if isinstance(source_obj, RAGEvidenceItem):
        source = getattr(source_obj, "source", None)
        metadata = {
            "chunk_id": getattr(source_obj, "chunk_id", None),
            "section": getattr(source_obj, "section", None),
            "subsection": getattr(source_obj, "subsection", None),
            "similarity_score": getattr(source_obj, "similarity_score", None),
            "reranking_score": getattr(source_obj, "reranking_score", None),
            "source_filename": getattr(source, "filename", None) if source else None,
            "page_number": getattr(source, "page_number", None) if source else None,
            "study_id": getattr(source, "study_id", None) if source else None,
        }
        return Document(page_content=getattr(source_obj, "text", "") or "", metadata=metadata)

    if isinstance(source_obj, ProtocolChunk):
        meta = getattr(source_obj, "metadata", None)
        metadata = {
            "chunk_id": getattr(source_obj, "chunk_id", None) or getattr(meta, "chunk_id", None),
            "section": getattr(meta, "section", None),
            "subsection": getattr(meta, "subsection", None),
            "page_number": getattr(meta, "page_number", None),
            "study_id": getattr(meta, "study_id", None),
            "source_filename": getattr(meta, "source_filename", None),
            "chunk_index": getattr(meta, "chunk_index", None),
        }
        return Document(page_content=getattr(source_obj, "text", "") or "", metadata=metadata)

    if isinstance(source_obj, dict):
        content = source_obj.get("text") or source_obj.get("page_content") or ""
        meta = {k: v for k, v in source_obj.items() if k not in ("text", "page_content")}
        return Document(page_content=content, metadata=meta)

    return Document(page_content=str(source_obj), metadata={})


class ICFLangChainEmbeddings(Embeddings):
    """
    LangChain Embeddings interface adapter for the local SentenceTransformer embedding service.
    Generates 384-dimensional dense vectors using 'all-MiniLM-L6-v2'.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = embedding_service.get_model(self.model_name)
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in vectors]

    def embed_query(self, text: str) -> List[float]:
        if not text:
            return []
        model = embedding_service.get_model(self.model_name)
        vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return vector.tolist() if hasattr(vector, "tolist") else list(vector)


class ICFRAGRetriever(BaseRetriever):
    """
    LangChain BaseRetriever adapter bridging ContextAssembler & VectorStoreService
    to standard LangChain LCEL chains while preserving source_evidence_ids.
    """
    study_id: Optional[str] = Field(default=None, description="Target study identifier")
    top_k: int = Field(default=5, description="Top K candidate chunks to retrieve")
    min_score_threshold: float = Field(default=0.3, description="Minimum similarity score threshold")

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        request = RAGRetrieveRequest(
            query=query,
            study_id=self.study_id,
            top_k=self.top_k,
            min_score_threshold=self.min_score_threshold
        )
        response = context_assembler.assemble_context(request)
        return [to_langchain_document(ev) for ev in response.evidence]


def create_lcel_chat_prompt(system_prompt: str, user_prompt: str = "") -> ChatPromptTemplate:
    """
    Constructs a LangChain ChatPromptTemplate using direct SystemMessage and HumanMessage objects.
    Prevents f-string template expansion errors when system or user prompt content contains literal JSON braces.
    """
    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    if user_prompt:
        messages.append(HumanMessage(content=user_prompt))
    return ChatPromptTemplate.from_messages(messages)
