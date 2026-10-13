from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ChunkMetadata(BaseModel):
    """
    Structured traceability metadata for a single protocol chunk.
    """
    chunk_id: str = Field(..., description="Unique chunk identifier e.g. NCT01713764_eligibility_001")
    study_id: Optional[str] = Field(None, description="Target study ID or protocol identifier")
    source_type: str = Field(..., description="Source document format: pdf, docx, txt, json")
    source_filename: str = Field(..., description="Original source document filename")
    section: str = Field(..., description="Logical protocol section e.g. eligibility, objectives, risks")
    subsection: Optional[str] = Field(None, description="Subsection e.g. inclusion, exclusion, primary")
    page_number: Optional[int] = Field(None, description="Page number for PDF documents, null for non-PDFs")
    source_field: Optional[str] = Field(None, description="JSON path or header reference")
    chunk_index: int = Field(..., description="1-indexed sequence index of chunk")
    total_chunks: int = Field(..., description="Total number of chunks created for document")
    character_count: int = Field(..., description="Character length of chunk text")

class ProtocolChunk(BaseModel):
    """
    Individual protocol text chunk with metadata.
    """
    chunk_id: str = Field(..., description="Unique chunk ID")
    text: str = Field(..., description="Text content of the chunk")
    metadata: ChunkMetadata = Field(..., description="Traceability metadata")

class ChunkingResponse(BaseModel):
    """
    API Response schema for Phase 4 Part 1 Chunking & Metadata.
    """
    status: str = Field("chunked", description="Processing status tag")
    study_id: Optional[str] = Field(None, description="Target study ID")
    source_filename: str = Field(..., description="Original source filename")
    source_type: str = Field(..., description="Source format")
    total_chunks: int = Field(..., description="Total count of chunks generated")
    target_chunk_size: int = Field(..., description="Configured target chunk size in characters")
    chunk_overlap: int = Field(..., description="Configured chunk overlap in characters")
    chunks: List[ProtocolChunk] = Field(default_factory=list, description="List of generated protocol chunks")
    message: str = Field("Chunking and metadata extraction successful.", description="Detail message")

class EmbeddedProtocolChunk(BaseModel):
    """
    Protocol chunk with attached semantic embedding vector (Phase 4 Part 2).
    """
    chunk_id: str = Field(..., description="Unique chunk ID")
    text: str = Field(..., description="Text content of the chunk")
    metadata: ChunkMetadata = Field(..., description="Traceability metadata")
    embedding: List[float] = Field(..., description="Semantic embedding vector")

class EmbeddingResponse(BaseModel):
    """
    API Response schema for Phase 4 Part 2 Semantic Embeddings.
    """
    status: str = Field("embedded", description="Processing status tag")
    study_id: Optional[str] = Field(None, description="Target study ID")
    source_filename: str = Field(..., description="Original source filename")
    source_type: str = Field(..., description="Source format")
    embedding_model: str = Field(..., description="Name of embedding model used e.g. all-MiniLM-L6-v2")
    embedding_dimension: int = Field(..., description="Dimension of embedding vectors e.g. 384")
    batch_size: int = Field(..., description="Configured batch size e.g. 32")
    total_chunks: int = Field(..., description="Total count of embedded chunks")
    embedded_chunks: List[EmbeddedProtocolChunk] = Field(default_factory=list, description="List of chunks with embeddings attached")
    message: str = Field("Semantic embedding generation successful.", description="Detail message")

class VectorMetadataRecord(BaseModel):
    """
    Metadata record stored alongside a FAISS vector ID (Phase 4 Part 3).
    """
    vector_id: int = Field(..., description="Stable 0-indexed position inside FAISS index")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    study_id: Optional[str] = Field(None, description="Target study identifier")
    source_type: str = Field(..., description="Source format: pdf, docx, txt, json")
    source_filename: str = Field(..., description="Original filename")
    section: str = Field(..., description="Protocol section name")
    subsection: Optional[str] = Field(None, description="Subsection name if available")
    page_number: Optional[int] = Field(None, description="Page number if PDF document")
    source_reference: Optional[str] = Field(None, description="Formatted source reference string")
    source_field: Optional[str] = Field(None, description="JSON field path or header reference")
    chunk_index: int = Field(..., description="1-indexed sequence index of chunk")
    total_chunks: int = Field(..., description="Total chunks for document")

class VectorStoreManifest(BaseModel):
    """
    Manifest schema describing the FAISS index configuration and state.
    """
    embedding_model: str = Field(..., description="Name of embedding model used")
    embedding_dimension: int = Field(..., description="Dimension of vectors in FAISS index")
    index_type: str = Field("IndexFlatIP", description="FAISS index type e.g. IndexFlatIP")
    total_vectors: int = Field(..., description="Total number of vectors stored")
    created_at: str = Field(..., description="ISO timestamp of index creation")
    updated_at: str = Field(..., description="ISO timestamp of last index update")
    source_studies: List[str] = Field(default_factory=list, description="List of study IDs stored in index")

class VectorStoreStatusResponse(BaseModel):
    """
    API Response schema for vector store status query GET /api/vector-store/status.
    """
    status: str = Field(..., description="Status string e.g. indexed, empty, error")
    embedding_model: str = Field(..., description="Embedding model name")
    embedding_dimension: int = Field(..., description="Vector dimension")
    index_type: str = Field(..., description="FAISS index type")
    total_vectors: int = Field(..., description="Total vectors currently in index")
    studies_indexed: List[str] = Field(default_factory=list, description="Unique study IDs indexed")
    storage_directory: str = Field(..., description="Local directory path storing FAISS index")
    is_persisted: bool = Field(..., description="True if index and metadata files exist on disk")

class VectorIndexingResponse(BaseModel):
    """
    API Response schema for indexing operations POST /api/protocol/index and GET /api/studies/{study_id}/index.
    """
    status: str = Field("indexed", description="Processing status tag")
    embedding_model: str = Field(..., description="Embedding model used")
    embedding_dimension: int = Field(..., description="Vector dimension")
    index_type: str = Field("IndexFlatIP", description="FAISS index type used")
    vectors_added: int = Field(..., description="Count of new vectors added in this request")
    total_vectors: int = Field(..., description="Total count of vectors now stored in FAISS")
    studies_indexed: List[str] = Field(default_factory=list, description="List of unique study IDs indexed")
    message: str = Field("Indexing successful.", description="Detail message")

class SimilaritySearchResultItem(BaseModel):
    """
    Individual search result hit returned from FAISS IndexFlatIP vector search.
    """
    rank: int = Field(..., description="1-indexed result rank order (1 = highest similarity)")
    similarity_score: float = Field(..., description="Raw FAISS Inner-Product cosine similarity score (0.0 to 1.0)")
    reranking_score: Optional[float] = Field(None, description="Adjusted score after section diversity re-ranking")
    vector_id: int = Field(..., description="FAISS 0-indexed position inside vector index")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    study_id: Optional[str] = Field(None, description="Target study identifier")
    source_type: str = Field(..., description="Source document format: pdf, docx, txt, json")
    source_filename: str = Field(..., description="Original filename")
    section: str = Field(..., description="Protocol section name")
    subsection: Optional[str] = Field(None, description="Subsection name if available")
    page_number: Optional[int] = Field(None, description="Page number for PDF documents")
    source_reference: Optional[str] = Field(None, description="Formatted source reference string")
    source_field: Optional[str] = Field(None, description="JSON path or header reference")
    chunk_index: int = Field(..., description="1-indexed chunk sequence index")

class SimilaritySearchRequest(BaseModel):
    """
    API Request body schema for POST /api/search.
    """
    query: str = Field(..., min_length=1, description="Natural language query string e.g. 'What are the possible risks?'")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of top matching results to retrieve")
    study_id: Optional[str] = Field(None, description="Optional study ID filter")
    enable_diversity: bool = Field(default=True, description="Enable section diversity re-ranking")
    diversity_penalty: float = Field(default=0.06, ge=0.0, le=0.5, description="Section repetition penalty factor")


class SimilaritySearchResponse(BaseModel):
    """
    API Response schema for similarity search operations POST/GET /api/search.
    """
    status: str = Field("success", description="Processing status tag")
    query: str = Field(..., description="Original query string executed")
    top_k: int = Field(..., description="Requested top-K parameter")
    total_vectors_searched: int = Field(..., description="Total vectors present in FAISS store at search time")
    embedding_model: str = Field(..., description="Model used to encode query vector e.g. all-MiniLM-L6-v2")
    results_count: int = Field(..., description="Number of relevant matching results returned")
    results: List[SimilaritySearchResultItem] = Field(default_factory=list, description="Ranked list of similarity search results")



