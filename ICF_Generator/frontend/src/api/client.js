import { API_BASE_URL, API_ENDPOINTS } from "../config";

export async function startICFWorkflow({studyId, protocolFile, templateFile, preferredLength, customInstructions}) {
  try {
    const body = new FormData();
    if (studyId) body.append("study_id", studyId);
    if (protocolFile) body.append("protocol", protocolFile);
    if (templateFile) body.append("template", templateFile);
    if (preferredLength) body.append("preferred_length", preferredLength);
    if (customInstructions) body.append("custom_instructions", customInstructions);
    const response = await fetch(`${API_BASE_URL}/api/icf/workflow`, {method: "POST", body});
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Server responded with status ${response.status}`);
    }
    return {success: true, data: await response.json()};
  } catch (error) {
    return {success: false, error: error.message || "Could not start the ICF workflow."};
  }
}

export async function getICFWorkflow(jobId, signal) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/icf/workflow/${encodeURIComponent(jobId)}`, {
      headers: {Accept: "application/json"}, signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Server responded with status ${response.status}`);
    }
    return {success: true, data: await response.json()};
  } catch (error) {
    if (error.name === "AbortError") return {success: false, aborted: true};
    return {success: false, error: error.message || "Could not read ICF workflow status."};
  }
}

/**
 * Phase 1: Checks backend health by sending a GET request to FastAPI /health
 */
export async function checkBackendHealth() {
  try {
    const response = await fetch(API_ENDPOINTS.HEALTH, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(
        `HTTP Error: Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Backend health check error:", error);
    return {
      success: false,
      error: error.message || "Failed to reach backend server",
    };
  }
}

/**
 * Phase 2: Fetches preloaded studies list GET /api/studies with retry capability
 */
export async function getPreloadedStudies(retries = 3, delayMs = 1000) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await fetch(API_ENDPOINTS.STUDIES, {
        method: "GET",
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(
          errData.detail || `Server responded with status ${response.status}`,
        );
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      console.warn(
        `Attempt ${attempt}/${retries} - Error fetching preloaded studies:`,
        error.message,
      );

      // If network error/refusal during server startup and retries remain, wait before next attempt
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      } else {
        console.error("Final attempt failed for preloaded studies:", error);
        return {
          success: false,
          error:
            error.message ||
            "Failed to load preloaded study list. Please check if backend is running on http://127.0.0.1:8001.",
        };
      }
    }
  }
}

/**
 * Phase 2: Fetches single study detail GET /api/studies/{study_id}
 */
export async function getStudyDetail(studyId) {
  try {
    const response = await fetch(
      `${API_ENDPOINTS.STUDIES}/${encodeURIComponent(studyId)}`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      },
    );

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(`Error fetching study ${studyId}:`, error);
    return {
      success: false,
      error: error.message || "Failed to load study details",
    };
  }
}

/**
 * Phase 3 Part 3: Fetches preloaded study canonical protocol GET /api/studies/{study_id}/canonical
 */
export async function getCanonicalStudyProtocol(studyId) {
  try {
    const response = await fetch(
      `${API_ENDPOINTS.STUDIES}/${encodeURIComponent(studyId)}/canonical`,
      {
        method: "GET",
        headers: { Accept: "application/json" },
      },
    );

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(`Error canonicalizing study ${studyId}:`, error);
    return {
      success: false,
      error: error.message || "Failed to fetch canonical protocol",
    };
  }
}

/**
 * Phase 3 Part 1: Uploads and validates a protocol file POST /api/protocol/upload
 */
export async function uploadProtocolFile(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(API_ENDPOINTS.UPLOAD, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error uploading protocol file:", error);
    return { success: false, error: error.message || "Upload failed" };
  }
}

/**
 * Phase 3 Part 2: Uploads, validates, and extracts text POST /api/protocol/process
 */
export async function processProtocolFile(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(API_ENDPOINTS.PROCESS, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error processing protocol document:", error);
    return {
      success: false,
      error: error.message || "Document processing failed",
    };
  }
}

/**
 * Phase 3 Part 3: Uploads and extracts Canonical Protocol Model POST /api/protocol/canonicalize
 */
export async function canonicalizeProtocolFile(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(API_ENDPOINTS.CANONICALIZE, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error canonicalizing protocol document:", error);
    return {
      success: false,
      error: error.message || "Canonicalization failed",
    };
  }
}

/**
 * Phase 4 Part 1: Fetches study chunks GET /api/studies/{study_id}/chunks
 */
export async function getStudyChunks(
  studyId,
  targetChunkSize = 1000,
  chunkOverlap = 150,
) {
  try {
    const url = `${API_ENDPOINTS.STUDIES}/${encodeURIComponent(studyId)}/chunks?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(`Error chunking study ${studyId}:`, error);
    return { success: false, error: error.message || "Study chunking failed" };
  }
}

/**
 * Phase 4 Part 1: Uploads protocol file and generates chunks POST /api/protocol/chunk
 */
export async function chunkProtocolFile(
  file,
  targetChunkSize = 1000,
  chunkOverlap = 150,
) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_ENDPOINTS.CHUNK}?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error chunking uploaded protocol file:", error);
    return {
      success: false,
      error: error.message || "Protocol chunking failed",
    };
  }
}

/**
 * Phase 4 Part 2: Fetches study embeddings GET /api/studies/{study_id}/embed
 */
export async function getStudyEmbeddings(
  studyId,
  targetChunkSize = 1000,
  chunkOverlap = 150,
  batchSize = 32,
) {
  try {
    const url = `${API_ENDPOINTS.STUDIES}/${encodeURIComponent(studyId)}/embed?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}&batch_size=${batchSize}`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(`Error generating embeddings for study ${studyId}:`, error);
    return {
      success: false,
      error: error.message || "Study embedding generation failed",
    };
  }
}

/**
 * Phase 4 Part 2: Uploads protocol file and generates embeddings POST /api/protocol/embed
 */
export async function embedProtocolFile(
  file,
  targetChunkSize = 1000,
  chunkOverlap = 150,
  batchSize = 32,
) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_ENDPOINTS.EMBED}?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}&batch_size=${batchSize}`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(
      "Error generating embeddings for uploaded protocol file:",
      error,
    );
    return {
      success: false,
      error: error.message || "Protocol embedding generation failed",
    };
  }
}

/**
 * Phase 4 Part 3: Fetches FAISS vector store status GET /api/vector-store/status
 */
export async function getVectorStoreStatus() {
  try {
    const response = await fetch(API_ENDPOINTS.VECTOR_STORE_STATUS, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching vector store status:", error);
    return {
      success: false,
      error: error.message || "Failed to fetch vector store status",
    };
  }
}

/**
 * Phase 4 Part 3: Indexes preloaded study embeddings into FAISS POST /api/studies/{study_id}/index
 */
export async function indexStudy(
  studyId,
  targetChunkSize = 1000,
  chunkOverlap = 150,
) {
  try {
    const url = `${API_ENDPOINTS.STUDIES}/${encodeURIComponent(studyId)}/index?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error(`Error indexing study ${studyId}:`, error);
    return { success: false, error: error.message || "Study indexing failed" };
  }
}

/**
 * Phase 4 Part 3: Uploads protocol file, embeds, and indexes into FAISS POST /api/protocol/index
 */
export async function indexProtocolFile(
  file,
  targetChunkSize = 1000,
  chunkOverlap = 150,
) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_ENDPOINTS.INDEX}?target_chunk_size=${targetChunkSize}&chunk_overlap=${chunkOverlap}`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error indexing uploaded protocol file:", error);
    return {
      success: false,
      error: error.message || "Protocol indexing failed",
    };
  }
}

/**
 * Phase 4 Part 4: Performs semantic similarity search POST /api/search
 */
export async function searchSimilarity(query, topK = 5, studyId = null) {
  try {
    const payload = {
      query: query,
      top_k: Number(topK) || 5,
    };
    if (studyId) {
      payload.study_id = studyId;
    }

    const response = await fetch(API_ENDPOINTS.SEARCH, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error executing similarity search:", error);
    return {
      success: false,
      error: error.message || "Similarity search failed",
    };
  }
}

/**
 * Phase 5 Part 1: Retrieves grounded protocol evidence & assembles RAG context package POST /api/rag/retrieve
 */
export async function retrieveRAGContext(
  query,
  studyId = "",
  topK = 5,
  minScoreThreshold = 0.0,
  enableDiversity = true,
) {
  try {
    const payload = {
      query: query,
      study_id: studyId || null,
      top_k: Number(topK) || 5,
      min_score_threshold: Number(minScoreThreshold) || 0.0,
      enable_diversity: Boolean(enableDiversity),
      diversity_penalty: 0.06,
    };

    const response = await fetch(API_ENDPOINTS.RAG_RETRIEVE, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error retrieving RAG context:", error);
    return {
      success: false,
      error: error.message || "RAG context retrieval failed",
    };
  }
}

/**
 * Phase 5 Part 2: Analyzes grounded protocol evidence into structured study facts POST /api/protocol/analyze
 */
export async function analyzeProtocol(
  studyId = "",
  query = "Analyze protocol evidence for ICF generation",
  topK = 5,
) {
  try {
    const payload = {
      study_id: studyId || null,
      query: query || "Analyze protocol evidence for ICF generation",
      top_k: Number(topK) || 5,
    };

    const response = await fetch(API_ENDPOINTS.ANALYZE_PROTOCOL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error analyzing protocol:", error);
    return {
      success: false,
      error: error.message || "Protocol analysis failed",
    };
  }
}

/**
 * Phase 5 Part 3 / Phase 6 Part 4: Generates or revises structured ICF draft POST /api/icf/generate
 */
export async function generateICF(
  studyId,
  analysisFacts = null,
  generatePatientFriendly = true,
  reviewerFeedback = null,
  previousIcfDraft = null,
) {
  try {
    const payload = {
      study_id: studyId,
      analysis_facts: analysisFacts,
      generate_patient_friendly: generatePatientFriendly,
      reviewer_feedback: reviewerFeedback,
      previous_icf_draft: previousIcfDraft,
    };

    const response = await fetch(API_ENDPOINTS.GENERATE_ICF, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error generating/revising ICF:", error);
    return {
      success: false,
      error: error.message || "ICF content generation failed.",
    };
  }
}

/**
 * Phase 5 Part 4: Validates ICF draft & transformation POST /api/icf/validate
 */
export async function validateICF(
  studyId,
  icfDraft,
  patientFriendlyICF = null,
  protocolFacts = null,
) {
  try {
    const payload = {
      study_id: studyId || null,
      icf_draft: icfDraft,
      patient_friendly_icf: patientFriendlyICF,
      protocol_facts: protocolFacts,
    };

    const response = await fetch(API_ENDPOINTS.VALIDATE_ICF, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error validating ICF:", error);
    return { success: false, error: error.message || "ICF validation failed" };
  }
}

/**
 * Phase 6 Part 2: Fetches current human review state for a study GET /api/icf/review/{study_id}
 */
export async function getHumanReview(studyId) {
  try {
    if (!studyId) {
      throw new Error("Study ID is required to fetch human review state.");
    }

    const response = await fetch(
      `${API_ENDPOINTS.HUMAN_REVIEW}/${encodeURIComponent(studyId)}`,
      {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching human review state:", error);
    return {
      success: false,
      error: error.message || "Failed to fetch human review state.",
    };
  }
}

/**
 * Phase 6 Part 2: Updates human review state for a study POST /api/icf/review/{study_id}
 */
export async function updateHumanReview(
  studyId,
  reviewStatus,
  reviewerComment = null,
  revision = null,
  templateReviewed = false,
) {
  try {
    if (!studyId) {
      throw new Error("Study ID is required to update human review state.");
    }

    const payload = {
      review_status: reviewStatus,
      reviewer_comment: reviewerComment,
      revision,
      template_reviewed: templateReviewed,
    };

    const response = await fetch(
      `${API_ENDPOINTS.HUMAN_REVIEW}/${encodeURIComponent(studyId)}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      },
    );

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Server responded with status ${response.status}`,
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error updating human review state:", error);
    return {
      success: false,
      error: error.message || "Failed to update human review state.",
    };
  }
}

/**
 * Phase 6 Part 5: Export approved ICF draft as Word (.docx) document
 * POST /api/icf/export/{study_id}?export_type=standard|patient_friendly
 */
export async function exportICFDocx(
  studyId,
  exportType = "standard",
  icfDraft = null,
  patientFriendlyICF = null,
) {
  try {
    if (!studyId) {
      throw new Error("Study ID is required for ICF document export.");
    }

    const url = `${API_ENDPOINTS.EXPORT_ICF}/${encodeURIComponent(studyId)}?export_type=${encodeURIComponent(exportType)}`;
    const payload = {};
    if (icfDraft) payload.icf_draft = icfDraft;
    if (patientFriendlyICF) payload.patient_friendly_icf = patientFriendlyICF;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || `Export failed with status ${response.status}`,
      );
    }

    const blob = await response.blob();
    return { success: true, blob };
  } catch (error) {
    console.error("Error exporting ICF DOCX:", error);
    return {
      success: false,
      error: error.message || "Failed to export ICF document.",
    };
  }
}

/**
 * Helper to trigger browser file download from Blob
 */
export function triggerFileDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
