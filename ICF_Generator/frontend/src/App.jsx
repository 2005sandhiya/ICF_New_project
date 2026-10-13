import React, { useState, useEffect, useRef } from "react";
import {
  checkBackendHealth,
  getPreloadedStudies,
  getStudyDetail,
  getCanonicalStudyProtocol,
  processProtocolFile,
  canonicalizeProtocolFile,
  getStudyChunks,
  chunkProtocolFile,
  getStudyEmbeddings,
  embedProtocolFile,
  getVectorStoreStatus,
  indexStudy,
  indexProtocolFile,
  searchSimilarity,
  retrieveRAGContext,
  analyzeProtocol,
  generateICF,
  validateICF,
  startICFWorkflow,
  getICFWorkflow,
  getHumanReview,
  updateHumanReview,
  triggerFileDownload,
} from "./api/client";
import { API_BASE_URL } from "./config";
import {exportICFDocument} from './api/templates.js';
import {useICFTemplate} from './components/TemplatePanel.jsx';
import { AppShell } from './components/AppShell';
import { getMilestoneStages, getSourceKey, getPresentationState } from './components/workflow';
import { SourcePanel } from './components/SourcePanels';
import { GenerationPanel, ReviewPanel, ExportPanel } from './components/IntelligencePanels';

export function App() {
  const presentationProvenance = useRef(new WeakMap());
  const validationDrafts = useRef(new WeakMap());
  const [activePage, setActivePage] = useState('source');
  const [lastExport, setLastExport] = useState(null);
  const [exportFormat, setExportFormat] = useState('pdf');
  const [templateReviewed, setTemplateReviewed] = useState(false);
  const [workflowProgress, setWorkflowProgress] = useState(null);
  const [stagedTemplateFile, setStagedTemplateFile] = useState(null);
  const [stagedTemplateError, setStagedTemplateError] = useState('');
  const activeWorkflowController = useRef(null);
  const activeWorkflowSource = useRef(null);
  const currentSourceKey = useRef(null);
  const [revisionHistory, setRevisionHistory] = useState(null);
  const currentTarget = useRef(null);
  // Phase 1 Health Check State
  const [healthStatus, setHealthStatus] = useState("idle");
  const [healthData, setHealthData] = useState(null);
  const [healthError, setHealthError] = useState("");

  // Phase 2 Data Source Selector State
  const [sourceMode, setSourceMode] = useState("preloaded"); // 'preloaded' | 'upload'

  // Preloaded Study State
  const [studiesList, setStudiesList] = useState([]);
  const [isLoadingStudies, setIsLoadingStudies] = useState(false);
  const [selectedStudyId, setSelectedStudyId] = useState("");
  const [selectedStudyDetail, setSelectedStudyDetail] = useState(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [studyConfirmed, setStudyConfirmed] = useState(false);
  const [studiesError, setStudiesError] = useState("");

  // Upload Protocol State (Phase 3 Part 2 Text Extraction)
  const [selectedFile, setSelectedFile] = useState(null);
  currentSourceKey.current = getSourceKey({sourceMode, selectedStudyId, selectedFile});
  const [isProcessing, setIsProcessing] = useState(false);

  // Human-in-the-Loop Generation Preferences State
  const [preferredLength, setPreferredLength] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [processResult, setProcessResult] = useState(null);
  const [processError, setProcessError] = useState("");
  const [showFullText, setShowFullText] = useState(false);

  // Phase 3 Part 3 Canonical Protocol State
  const [isCanonicalizing, setIsCanonicalizing] = useState(false);
  const [canonicalResult, setCanonicalResult] = useState(null);
  const [canonicalError, setCanonicalError] = useState("");

  // Phase 4 Part 1 Chunking State
  const [isChunking, setIsChunking] = useState(false);
  const [chunkResult, setChunkResult] = useState(null);
  const [chunkError, setChunkError] = useState("");
  const [targetChunkSize, setTargetChunkSize] = useState(1000);
  const [chunkOverlap, setChunkOverlap] = useState(150);
  const [showSampleChunks, setShowSampleChunks] = useState(false);

  // Phase 4 Part 2 Embedding State
  const [isEmbedding, setIsEmbedding] = useState(false);
  const [embeddingResult, setEmbeddingResult] = useState(null);
  const [embeddingError, setEmbeddingError] = useState("");
  const [showEmbeddingPreview, setShowEmbeddingPreview] = useState(false);

  // Phase 4 Part 3 Vector Store State
  const [vectorStoreStatus, setVectorStoreStatus] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingResult, setIndexingResult] = useState(null);
  const [indexingError, setIndexingError] = useState("");

  // Phase 4 Part 4 Similarity Search State
  const [searchQuery, setSearchQuery] = useState(
    "What are the possible risks of the study?",
  );
  const [searchTopK, setSearchTopK] = useState(5);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState("");

  // Phase 5 Part 1 RAG Context Assembly State
  const [ragQuery, setRagQuery] = useState(
    "What are the possible risks of this study?",
  );
  const [ragStudyId, setRagStudyId] = useState("NCT00081328");
  const [ragTopK, setRagTopK] = useState(5);
  const [ragMinThreshold, setRagMinThreshold] = useState(0.0);
  const [isRetrievingRAG, setIsRetrievingRAG] = useState(false);
  const [ragResult, setRagResult] = useState(null);
  const [ragError, setRagError] = useState("");
  const [showRawRAGJson, setShowRawRAGJson] = useState(false);

  const handleRetrieveRAG = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    if (!ragQuery || !ragQuery.trim()) {
      setRagError(
        "Please enter a natural language information requirement query.",
      );
      return;
    }
    setIsRetrievingRAG(true);
    setRagError("");
    setRagResult(null);

    const res = await retrieveRAGContext(
      ragQuery,
      ragStudyId,
      ragTopK,
      ragMinThreshold,
      true,
    );
    setIsRetrievingRAG(false);

    if (res.success && res.data) {
      { presentationProvenance.current.set(res.data, presentationSourceKey); setRagResult(res.data); }
    } else {
      setRagError(res.error || "Failed to assemble RAG context");
    }
  };

  // Phase 5 Part 2 Protocol Analysis Agent State
  const [analysisStudyId, setAnalysisStudyId] = useState("NCT00081328");
  const [analysisQuery, setAnalysisQuery] = useState(
    "Analyze protocol evidence for ICF generation",
  );
  const [analysisTopK, setAnalysisTopK] = useState(5);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [showRawFactsJson, setShowRawFactsJson] = useState(false);

  const handleAnalyzeProtocol = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setIsAnalyzing(true);
    setAnalysisError("");
    setAnalysisResult(null);

    const res = await analyzeProtocol(
      analysisStudyId,
      analysisQuery,
      analysisTopK,
    );
    setIsAnalyzing(false);

    if (res.success && res.data) {
      { presentationProvenance.current.set(res.data, presentationSourceKey); setAnalysisResult(res.data); }
    } else {
      setAnalysisError(res.error || "Failed to execute protocol analysis");
    }
  };

  // Phase 5 Part 3 ICF Content Generation State
  const [icfStudyId, setIcfStudyId] = useState("NCT00081328");
  const [isGeneratingICF, setIsGeneratingICF] = useState(false);
  const [icfResult, setIcfResult] = useState(null);
  const [icfError, setIcfError] = useState("");
  const [icfTab, setIcfTab] = useState("structured");
  const [showRawIcfJson, setShowRawIcfJson] = useState(false);

  useEffect(() => {
    if (activeWorkflowSource.current && activeWorkflowSource.current !== currentSourceKey.current) {
      activeWorkflowController.current?.abort();
      activeWorkflowController.current = null;
      activeWorkflowSource.current = null;
      setIsGeneratingICF(false);
      setWorkflowProgress(null);
    }
  }, [sourceMode, selectedStudyId, selectedFile]);
  useEffect(() => () => activeWorkflowController.current?.abort(), []);

  currentTarget.current = icfStudyId;
  const templateState = useICFTemplate(icfStudyId, selection => {
    setTemplateReviewed(false); setLastExport(null); setExportError('');
    if (icfResult?.study_id === selection.study_id) {
      setHumanReview(null); setValidationResult(null);
      fetchHumanReviewState(selection.study_id);
    }
  });
  const acceptGeneratedResult = (data, sourceKey) => {
    if (currentTarget.current !== data.study_id) return;
    presentationProvenance.current.set(data, sourceKey);
    setIcfResult(data); setValidationStudyId(data.study_id);
    setTemplateReviewed(false); setLastExport(null);
    const report = data.validation_report;
    if (report) {
      presentationProvenance.current.set(report, sourceKey);
      validationDrafts.current.set(report, data.icf_draft);
    }
    setValidationResult(report || null); setValidationError('');
    fetchHumanReviewState(data.study_id);
  };

  const handleGenerateICF = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    const protocolFile = sourceMode === 'upload' ? selectedFile : null;
    const targetStudyId = sourceMode === 'preloaded' ? selectedStudyId : null;
    if ((!protocolFile && !targetStudyId) || (sourceMode === 'preloaded' && !selectedStudyDetail)) {
      setIcfError('Choose a study or upload a protocol before generating an ICF.'); return;
    }
    if (sourceMode === 'preloaded' && (templateState.busy || templateState.error || !templateState.selection)) {
      setIcfError('Resolve the selected study template before generating.'); return;
    }
    if (stagedTemplateError) {
      setIcfError(stagedTemplateError); return;
    }

    activeWorkflowController.current?.abort();
    const controller = new AbortController();
    activeWorkflowController.current = controller;
    activeWorkflowSource.current = presentationSourceKey;
    setIsGeneratingICF(true);
    setIcfError('');
    setWorkflowProgress(null);
    setValidationResult(null); setHumanReview(null); setHumanReviewError(''); setLastExport(null);

    try {
      const started = await startICFWorkflow({
        studyId: targetStudyId,
        protocolFile,
        templateFile: stagedTemplateFile,
        preferredLength,
        customInstructions,
      });
      if (!started.success || !started.data) throw new Error(started.error || 'The ICF workflow could not start.');
      let job = started.data;
      setWorkflowProgress(job);
      while (job.status === 'queued' || job.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 700));
        if (controller.signal.aborted || currentSourceKey.current !== presentationSourceKey) return;
        const status = await getICFWorkflow(job.job_id, controller.signal);
        if (status.aborted) return;
        if (!status.success || !status.data) throw new Error(status.error || 'Could not read workflow progress.');
        job = status.data;
        setWorkflowProgress(job);
      }
      if (controller.signal.aborted || currentSourceKey.current !== presentationSourceKey) return;
      if (job.status !== 'succeeded' || !job.result?.icf_result) {
        throw new Error(job.error || 'The ICF workflow could not finish.');
      }

      const data = job.result.icf_result;
      const actualStudyId = data.study_id;
      currentTarget.current = actualStudyId;
      setIcfStudyId(actualStudyId);
      setValidationStudyId(actualStudyId);
      if (job.result.analysis_result) {
        presentationProvenance.current.set(job.result.analysis_result, presentationSourceKey);
        setAnalysisResult(job.result.analysis_result);
      }
      if (job.result.canonical_protocol) {
        presentationProvenance.current.set(job.result.canonical_protocol, presentationSourceKey);
        setCanonicalResult(job.result.canonical_protocol);
      }
      setStagedTemplateFile(null);
      setStagedTemplateError('');
      acceptGeneratedResult(data, presentationSourceKey);
    } catch (err) {
      if (err.name !== 'AbortError') setIcfError(err.message || 'An error occurred during ICF generation.');
    } finally {
      if (activeWorkflowController.current === controller) {
        activeWorkflowController.current = null;
        activeWorkflowSource.current = null;
        setIsGeneratingICF(false);
      }
    }
  };

  // Phase 5 Part 4 Validation Agent State
  const [validationStudyId, setValidationStudyId] = useState("NCT00081328");
  const [isValidatingICF, setIsValidatingICF] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [validationError, setValidationError] = useState("");
  const [showRawValidationJson, setShowRawValidationJson] = useState(false);

  // Phase 6 Part 1 & 2 Human Review State
  const [humanReview, setHumanReview] = useState(null);
  const [reviewerComment, setReviewerComment] = useState("");
  const [humanReviewLoading, setHumanReviewLoading] = useState(false);
  const [humanReviewError, setHumanReviewError] = useState("");

  // Phase 6 Part 5 Final Document Export State
  const [isExportingDocx, setIsExportingDocx] = useState(false);
  const [exportError, setExportError] = useState("");

  const handleExportDocx = async (exportType = "patient_facing", format = "pdf") => {
    const targetStudyId = icfResult?.study_id;
    const revision = icfResult?.revision;
    if (!targetStudyId || targetStudyId !== icfStudyId || humanReview?.study_id !== targetStudyId ||
        humanReview?.review_status !== 'APPROVED' || humanReview.approved_revision !== revision) {
      setExportError('Export blocked. Generate, validate and approve the current study revision first.'); return;
    }
    setIsExportingDocx(true); setExportFormat(format); setExportError(''); setLastExport(null);
    try {
      const result = await exportICFDocument(targetStudyId, revision, exportType, format);
      if (!result.success) throw new Error(result.error);
      if (currentTarget.current !== targetStudyId) return;
      const filename = result.filename || `${targetStudyId}_Patient_Facing_ICF_v${revision}.${format}`;
      triggerFileDownload(result.blob, filename);
      setLastExport({filename, studyId: targetStudyId, revision, exportType, format, draft: icfResult.icf_draft});
    } catch (error) {setExportError(error.message || 'Document export failed.');}
    finally {setIsExportingDocx(false);}
  };

  const fetchHumanReviewState = async (targetStudyId) => {
    const presentationSourceKey = sourceMode === 'upload' ? getSourceKey({sourceMode, selectedStudyId, selectedFile}) : `study:${targetStudyId}`;
    if (!targetStudyId) {
      setHumanReview(null);
      return;
    }
    setHumanReviewLoading(true);
    setHumanReviewError("");
    const res = await getHumanReview(targetStudyId);
    if (currentTarget.current !== targetStudyId) return;
    setHumanReviewLoading(false);

    if (res.success && res.data) {
      { presentationProvenance.current.set(res.data, presentationSourceKey); setHumanReview(res.data); }
      if (res.data.reviewer_comment) {
        setReviewerComment(res.data.reviewer_comment);
      } else {
        setReviewerComment("");
      }
    } else {
      setHumanReviewError(res.error || "Failed to fetch human review state.");
    }
  };

  const handleUpdateHumanReview = async (newStatus) => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    const targetStudyId = icfResult?.study_id;
    if (!targetStudyId) {
      setHumanReviewError("No study selected for human review.");
      return;
    }

    if (
      newStatus === "CHANGES_REQUESTED" &&
      (!reviewerComment || !reviewerComment.trim())
    ) {
      setHumanReviewError(
        "Please provide a reviewer comment explaining what needs to change.",
      );
      return;
    }

    setHumanReviewLoading(true);
    setHumanReviewError("");

    const res = await updateHumanReview(
      targetStudyId,
      newStatus,
      reviewerComment ? reviewerComment.trim() : null,
      icfResult?.revision,
      templateReviewed,
    );
    setHumanReviewLoading(false);

    if (res.success && res.data) {
      { presentationProvenance.current.set(res.data, presentationSourceKey); setHumanReview(res.data); }
      if (newStatus === 'CHANGES_REQUESTED') await handleRegenerateICF(res.data);
    } else {
      // Non-optimistic error handling: preserve current state and display error banner
      setHumanReviewError(
        res.error || `Failed to update review status to ${newStatus}.`,
      );
    }
  };

  const handleRegenerateICF = async (savedReview = null) => {
    const targetStudyId = icfResult?.study_id;
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    const review = savedReview || humanReview;
    if (!targetStudyId) {
      setIcfError("Please select a study before regenerating.");
      return;
    }

    if (
      icfResult?.study_id !== targetStudyId ||
      review?.study_id !== targetStudyId
    ) {
      setIcfError(
        "Study data mismatch detected. Reload the current study and review before requesting a new draft.",
      );
      return;
    }

    if (
      review?.review_status !== 'CHANGES_REQUESTED' ||
      !review?.reviewer_comment ||
      !review.reviewer_comment.trim()
    ) {
      setIcfError(
        "No reviewer comment available for targeted ICF regeneration.",
      );
      return;
    }

    setIsGeneratingICF(true);
    setIcfError("");

    try {
      const currentRevision =
        icfResult?.icf_draft?.revision || icfResult?.revision || 1;

      const res = await generateICF(
        targetStudyId,
        analysisResult?.study_id === targetStudyId ? analysisResult.facts : null,
        true,
        review.reviewer_comment.trim(),
        icfResult.icf_draft,
      );

      if (!res.success || !res.data) {
        throw new Error(res.error || "ICF regeneration failed.");
      }

      const newIcfData = res.data;
      acceptGeneratedResult(newIcfData, presentationSourceKey);
    } catch (err) {
      setIcfError(
        err.message || "An error occurred during targeted ICF regeneration.",
      );
    } finally {
      setIsGeneratingICF(false);
    }
  };

  const handleValidateICF = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setIsValidatingICF(true);
    setValidationError("");
    setValidationResult(null);

    try {
      let draftToValidate = icfResult?.icf_draft;
      let pfToValidate = icfResult?.patient_friendly_icf || null;
      let factsToValidate = analysisResult?.facts;

      if (!draftToValidate || icfResult?.study_id !== validationStudyId) {
        if (
          !factsToValidate ||
          analysisResult?.study_id !== validationStudyId
        ) {
          const analysisRes = await analyzeProtocol(
            validationStudyId,
            "Extract structured protocol facts for ICF generation",
            10,
          );
          if (!analysisRes.success || !analysisRes.data) {
            throw new Error(
              analysisRes.error ||
                "Failed to extract structured facts for validation.",
            );
          }
          factsToValidate = analysisRes.data.facts;
          { presentationProvenance.current.set(analysisRes.data, presentationSourceKey); setAnalysisResult(analysisRes.data); }
        }

        const genRes = await generateICF(
          validationStudyId,
          factsToValidate,
          true,
        );
        if (!genRes.success || !genRes.data) {
          throw new Error(
            genRes.error ||
              "ICF Content Generation failed during validation preparation.",
          );
        }
        draftToValidate = genRes.data.icf_draft;
        pfToValidate = genRes.data.patient_friendly_icf;
        acceptGeneratedResult(genRes.data, presentationSourceKey);
      }

      const pfIcf = pfToValidate;

      const res = await validateICF(
        validationStudyId,
        draftToValidate,
        pfIcf,
        factsToValidate,
      );

      if (res.success && res.data) {
        { presentationProvenance.current.set(res.data, presentationSourceKey); validationDrafts.current.set(res.data, draftToValidate);
      setValidationResult(res.data); }
      } else {
        setValidationError(res.error || "Validation Agent execution failed.");
      }
    } catch (err) {
      setValidationError(
        err.message || "An error occurred during ICF validation.",
      );
    } finally {
      setIsValidatingICF(false);
    }
  };

  // Handle Phase 1 Health Check
  const handleCheckConnection = async () => {
    setHealthStatus("loading");
    setHealthData(null);
    setHealthError("");

    const result = await checkBackendHealth();

    if (result.success && result.data) {
      setHealthStatus("success");
      setHealthData(result.data);
    } else {
      setHealthStatus("error");
      setHealthError(
        result.error || "Failed to communicate with FastAPI backend",
      );
    }
  };

  // Fetch vector store status on component mount
  useEffect(() => {
    fetchVectorStoreStatus();
  }, []);

  const fetchVectorStoreStatus = async () => {
    const result = await getVectorStoreStatus();
    if (result.success && result.data) {
      setVectorStoreStatus(result.data);
    }
  };

  // Fetch preloaded studies list on mount or mode switch
  useEffect(() => {
    if (sourceMode === "preloaded" && studiesList.length === 0) {
      fetchStudies();
    }
  }, [sourceMode]);

  const fetchStudies = async (retries = 3, delayMs = 1000) => {
    setIsLoadingStudies(true);
    setStudiesError("");
    const result = await getPreloadedStudies(retries, delayMs);
    setIsLoadingStudies(false);

    if (result.success && Array.isArray(result.data)) {
      setStudiesList(result.data);
      if (result.data.length > 0) {
        handleStudyChange(result.data[0].study_id);
      }
    } else {
      setStudiesError(result.error || "Failed to load preloaded study listing");
    }
  };

  const handleStudyChange = async (studyId) => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setSelectedStudyId(studyId);
    setRagStudyId(studyId);
    setAnalysisStudyId(studyId);
    setIcfStudyId(studyId);
    setValidationStudyId(studyId);

    setStudyConfirmed(false);
    setCanonicalResult(null);
    setChunkResult(null);
    setEmbeddingResult(null);

    // Clear stale Phase 5 & 6 state & errors
    setRagResult(null);
    setAnalysisResult(null);
    setIcfResult(null);
    setValidationResult(null);
    setRagError("");
    setAnalysisError("");
    setIcfError("");
    setValidationError("");

    // Clear and fetch Human Review & Export state for newly selected study
    setHumanReview(null);
    setReviewerComment("");
    setHumanReviewError("");
    setExportError("");
    setIsExportingDocx(false);
    if (studyId) {
      fetchHumanReviewState(studyId);
    }

    if (!studyId) {
      setSelectedStudyDetail(null);
      return;
    }

    setIsLoadingDetail(true);
    const result = await getStudyDetail(studyId);
    setIsLoadingDetail(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setSelectedStudyDetail(result.data); }
    } else {
      setStudiesError(
        result.error || `Failed to fetch study details for ${studyId}`,
      );
    }
  };

  const handleConfirmStudySelection = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    if (selectedStudyDetail) {
      setStudyConfirmed(true);
      setChunkResult(null);
      setEmbeddingResult(null);
      // Fetch canonical protocol representation for selected study
      setIsCanonicalizing(true);
      setCanonicalError("");
      const canonRes = await getCanonicalStudyProtocol(selectedStudyId);
      setIsCanonicalizing(false);

      if (canonRes.success && canonRes.data) {
        { presentationProvenance.current.set(canonRes.data, presentationSourceKey); setCanonicalResult(canonRes.data); }
      } else {
        setCanonicalError(
          canonRes.error || "Failed to generate canonical protocol model.",
        );
      }
    }
  };

  // Upload Protocol Handler (Phase 3 Part 2 & Part 3)
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      activeWorkflowController.current?.abort();
      activeWorkflowController.current = null;
      activeWorkflowSource.current = null;
      setIsGeneratingICF(false);
      setSelectedFile(e.target.files[0]);
      currentTarget.current = '';
      setIcfStudyId('');
      setIcfResult(null); setIcfError(''); setAnalysisResult(null); setAnalysisError('');
      setValidationResult(null); setValidationError(''); setHumanReview(null); setHumanReviewLoading(false); setHumanReviewError('');
      setReviewerComment(''); setRevisionHistory(null); setTemplateReviewed(false);
      setLastExport(null); setExportError(''); setWorkflowProgress(null);
      setStagedTemplateFile(null); setStagedTemplateError('');
      setProcessResult(null);
      setCanonicalResult(null);
      setChunkResult(null);
      setEmbeddingResult(null);
      setProcessError("");
      setCanonicalError("");
      setChunkError("");
      setEmbeddingError("");
      setShowFullText(false);
    }
  };

  const handleSourceModeChange = (nextMode) => {
    if (nextMode === sourceMode) return;
    activeWorkflowController.current?.abort();
    activeWorkflowController.current = null;
    activeWorkflowSource.current = null;
    setIsGeneratingICF(false);
    setSourceMode(nextMode);
    const nextTarget = nextMode === 'preloaded' ? selectedStudyId : '';
    currentTarget.current = nextTarget;
    setIcfStudyId(nextTarget);
    setIcfResult(null); setIcfError(''); setAnalysisResult(null); setAnalysisError('');
    setValidationResult(null); setValidationError(''); setHumanReview(null); setHumanReviewLoading(false); setHumanReviewError('');
    setReviewerComment(''); setRevisionHistory(null); setTemplateReviewed(false);
    setLastExport(null); setExportError(''); setWorkflowProgress(null);
    setStagedTemplateFile(null); setStagedTemplateError('');
    if (nextTarget) fetchHumanReviewState(nextTarget);
  };

  const handleCanonicalizeSubmit = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    if (!selectedFile) {
      setProcessError("Please select a protocol file to process.");
      return;
    }

    setIsCanonicalizing(true);
    setCanonicalResult(null);
    setChunkResult(null);
    setEmbeddingResult(null);
    setCanonicalError("");

    const result = await canonicalizeProtocolFile(selectedFile);
    setIsCanonicalizing(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setCanonicalResult(result.data); }
    } else {
      setCanonicalError(
        result.error || "Canonical protocol extraction failed.",
      );
    }
  };

  // Phase 4 Part 1 Chunking Handler
  const handleGenerateChunks = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setIsChunking(true);
    setChunkResult(null);
    setChunkError("");

    let result;
    if (sourceMode === "preloaded") {
      result = await getStudyChunks(
        selectedStudyId,
        targetChunkSize,
        chunkOverlap,
      );
    } else {
      if (!selectedFile) {
        setChunkError("Please select a protocol file first.");
        setIsChunking(false);
        return;
      }
      result = await chunkProtocolFile(
        selectedFile,
        targetChunkSize,
        chunkOverlap,
      );
    }

    setIsChunking(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setChunkResult(result.data); }
    } else {
      setChunkError(result.error || "Chunking protocol failed.");
    }
  };

  // Phase 4 Part 2 Embedding Handler
  const handleGenerateEmbeddings = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setIsEmbedding(true);
    setEmbeddingResult(null);
    setEmbeddingError("");

    let result;
    if (sourceMode === "preloaded") {
      result = await getStudyEmbeddings(
        selectedStudyId,
        targetChunkSize,
        chunkOverlap,
      );
    } else {
      if (!selectedFile) {
        setEmbeddingError("Please select a protocol file first.");
        setIsEmbedding(false);
        return;
      }
      result = await embedProtocolFile(
        selectedFile,
        targetChunkSize,
        chunkOverlap,
      );
    }

    setIsEmbedding(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setEmbeddingResult(result.data); }
    } else {
      setEmbeddingError(result.error || "Generating embeddings failed.");
    }
  };

  // Phase 4 Part 3 Vector Store Indexing Handler
  const handleIndexIntoVectorStore = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    setIsIndexing(true);
    setIndexingResult(null);
    setIndexingError("");

    let result;
    if (sourceMode === "preloaded") {
      result = await indexStudy(selectedStudyId, targetChunkSize, chunkOverlap);
    } else {
      if (!selectedFile) {
        setIndexingError("Please select a protocol file first.");
        setIsIndexing(false);
        return;
      }
      result = await indexProtocolFile(
        selectedFile,
        targetChunkSize,
        chunkOverlap,
      );
    }

    setIsIndexing(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setIndexingResult(result.data); }
      fetchVectorStoreStatus();
    } else {
      setIndexingError(result.error || "Indexing into vector store failed.");
    }
  };

  // Phase 4 Part 4 Similarity Search Handlers
  const handleExecuteSearch = async (queryToRun = null) => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    const targetQuery = queryToRun !== null ? queryToRun : searchQuery;
    if (!targetQuery || !targetQuery.trim()) {
      setSearchError("Please enter a valid query string.");
      return;
    }

    setIsSearching(true);
    setSearchResults(null);
    setSearchError("");

    const targetStudyId = sourceMode === "preloaded" ? selectedStudyId : null;
    const result = await searchSimilarity(
      targetQuery,
      searchTopK,
      targetStudyId,
    );

    setIsSearching(false);

    if (result.success && result.data) {
      { presentationProvenance.current.set(result.data, presentationSourceKey); setSearchResults(result.data); }
    } else {
      setSearchError(result.error || "Similarity search failed.");
    }
  };

  const handleSampleQueryClick = (sampleQueryText) => {
    setSearchQuery(sampleQueryText);
    handleExecuteSearch(sampleQueryText);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const renderValueOrNull = (val) => {
    if (
      val === null ||
      val === undefined ||
      val === "" ||
      (Array.isArray(val) && val.length === 0)
    ) {
      return (
        <span className="muted">
          Not available in source
        </span>
      );
    }
    if (Array.isArray(val)) {
      return val.join(", ");
    }
    return val;
  };


  const handleProcessProtocol = async () => {
    const presentationSourceKey = getSourceKey({sourceMode, selectedStudyId, selectedFile});
    if (!selectedFile) {
      setProcessError('Please select a protocol file to process.');
      return;
    }
    setIsProcessing(true);
    setProcessResult(null);
    setProcessError('');
    const result = await processProtocolFile(selectedFile);
    setIsProcessing(false);
    if (result.success && result.data) { presentationProvenance.current.set(result.data, presentationSourceKey); setProcessResult(result.data); }
    else setProcessError(result.error || 'Document processing failed.');
  };

  useEffect(() => { handleCheckConnection(); }, []);
  useEffect(() => {
    let active = true;
    setRevisionHistory(null);
    if (icfResult?.study_id) {
      fetch(`${API_BASE_URL}/api/icf/revisions/${encodeURIComponent(icfResult.study_id)}`)
        .then(response => response.ok ? response.json() : null)
        .then(data => {if (active) setRevisionHistory(data);}).catch(() => {});
    }
    return () => {active = false;};
  }, [icfResult, humanReview]);

  const vm = {
    healthStatus,
    setHealthStatus,
    healthData,
    setHealthData,
    healthError,
    setHealthError,
    sourceMode,
    setSourceMode: handleSourceModeChange,
    studiesList,
    setStudiesList,
    isLoadingStudies,
    setIsLoadingStudies,
    selectedStudyId,
    setSelectedStudyId,
    selectedStudyDetail,
    setSelectedStudyDetail,
    isLoadingDetail,
    setIsLoadingDetail,
    studyConfirmed,
    setStudyConfirmed,
    studiesError,
    setStudiesError,
    selectedFile,
    setSelectedFile,
    isProcessing,
    setIsProcessing,
    processResult,
    setProcessResult,
    processError,
    setProcessError,
    showFullText,
    setShowFullText,
    isCanonicalizing,
    setIsCanonicalizing,
    canonicalResult,
    setCanonicalResult,
    canonicalError,
    setCanonicalError,
    isChunking,
    setIsChunking,
    chunkResult,
    setChunkResult,
    chunkError,
    setChunkError,
    targetChunkSize,
    setTargetChunkSize,
    chunkOverlap,
    setChunkOverlap,
    showSampleChunks,
    setShowSampleChunks,
    isEmbedding,
    setIsEmbedding,
    embeddingResult,
    setEmbeddingResult,
    embeddingError,
    setEmbeddingError,
    showEmbeddingPreview,
    setShowEmbeddingPreview,
    vectorStoreStatus,
    setVectorStoreStatus,
    isIndexing,
    setIsIndexing,
    indexingResult,
    setIndexingResult,
    indexingError,
    setIndexingError,
    searchQuery,
    setSearchQuery,
    searchTopK,
    setSearchTopK,
    isSearching,
    setIsSearching,
    searchResults,
    setSearchResults,
    searchError,
    setSearchError,
    ragQuery,
    setRagQuery,
    ragStudyId,
    setRagStudyId,
    ragTopK,
    setRagTopK,
    ragMinThreshold,
    setRagMinThreshold,
    isRetrievingRAG,
    setIsRetrievingRAG,
    ragResult,
    setRagResult,
    ragError,
    setRagError,
    showRawRAGJson,
    setShowRawRAGJson,
    handleRetrieveRAG,
    analysisStudyId,
    setAnalysisStudyId,
    analysisQuery,
    setAnalysisQuery,
    analysisTopK,
    setAnalysisTopK,
    isAnalyzing,
    setIsAnalyzing,
    analysisResult,
    setAnalysisResult,
    analysisError,
    setAnalysisError,
    showRawFactsJson,
    setShowRawFactsJson,
    handleAnalyzeProtocol,
    icfStudyId,
    setIcfStudyId,
    isGeneratingICF,
    setIsGeneratingICF,
    icfResult,
    setIcfResult,
    icfError,
    setIcfError,
    icfTab,
    setIcfTab,
    showRawIcfJson,
    setShowRawIcfJson,
    handleGenerateICF,
    validationStudyId,
    setValidationStudyId,
    isValidatingICF,
    setIsValidatingICF,
    validationResult,
    setValidationResult,
    validationError,
    setValidationError,
    showRawValidationJson,
    setShowRawValidationJson,
    humanReview,
    setHumanReview,
    reviewerComment,
    setReviewerComment,
    humanReviewLoading,
    setHumanReviewLoading,
    humanReviewError,
    setHumanReviewError,
    isExportingDocx,
    setIsExportingDocx,
    exportError,
    setExportError,
    handleExportDocx,
    fetchHumanReviewState,
    handleUpdateHumanReview,
    handleRegenerateICF,
    handleValidateICF,
    handleCheckConnection,
    fetchVectorStoreStatus,
    fetchStudies,
    handleStudyChange,
    handleConfirmStudySelection,
    handleFileChange,
    handleCanonicalizeSubmit,
    handleGenerateChunks,
    handleGenerateEmbeddings,
    handleIndexIntoVectorStore,
    handleExecuteSearch,
    handleSampleQueryClick,
    formatFileSize,
    renderValueOrNull,
    API_BASE_URL, lastExport, handleProcessProtocol,
    templateState, templateReviewed, setTemplateReviewed, exportFormat, revisionHistory,
    workflowProgress, stagedTemplateFile, stagedTemplateError, setStagedTemplateFile, setStagedTemplateError,
    preferredLength, setPreferredLength, customInstructions, setCustomInstructions,
    presentationProvenance: presentationProvenance.current, validationDrafts: validationDrafts.current,
  };
  const stages = getMilestoneStages(vm);
  const panels = {source: SourcePanel, generation: GenerationPanel, review: ReviewPanel, export: ExportPanel};
  const Panel = panels[activePage];
  const navigate = page => {
    setActivePage(page);
    window.scrollTo({top: 0, behavior: 'instant'});
    document.getElementById('workspace')?.focus({preventScroll: true});
  };
  return <AppShell vm={vm} activePage={activePage} onNavigate={navigate} stages={stages}>
    <Panel vm={getPresentationState(vm)} onNavigate={navigate}/>
  </AppShell>;
}

export default App;
