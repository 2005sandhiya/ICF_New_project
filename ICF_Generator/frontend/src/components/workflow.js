export const navigation = [
  {id: 'source', label: 'Study & protocol', icon: 'study', description: 'Choose the source evidence'},
  {id: 'generation', label: 'Generate ICF', icon: 'document', description: 'Prepare the patient-facing consent document'},
  {id: 'review', label: 'Human review', icon: 'user', description: 'Review and record a decision'},
  {id: 'export', label: 'Export documents', icon: 'download', description: 'Download the approved ICF'},
];

const status = (busy, error, complete, ready) => busy ? 'active' : error ? 'error' : complete ? 'complete' : ready ? 'ready' : 'waiting';

// Sidecars record this key when an operation starts, before a source can change.
// They leave the original result objects and API/state handlers intact.
export function getSourceKey(v) {
  if (v.sourceMode === 'preloaded') return v.selectedStudyId ? `study:${v.selectedStudyId}` : null;
  if (v.sourceMode !== 'upload' || !v.selectedFile) return null;
  const {name, size, lastModified} = v.selectedFile;
  return `upload:${JSON.stringify([name, size ?? null, lastModified ?? null])}`;
}

function belongsToSource(v, result, canInferStudy = false) {
  if (!result || typeof result !== 'object') return false;
  const key = getSourceKey(v);
  if (!key) return false;
  if (v.presentationProvenance) return v.presentationProvenance.get(result) === key;
  // Legacy/test callers can identify preloaded results from exact response IDs.
  // A filename or study ID alone cannot distinguish two uploaded documents.
  return v.sourceMode === 'preloaded' && canInferStudy;
}

function sourcePresentation(v) {
  const preloaded = v.sourceMode === 'preloaded';
  const sourceReady = preloaded
    ? Boolean(v.selectedStudyId && v.selectedStudyDetail?.study_id === v.selectedStudyId && !v.isLoadingDetail)
    : Boolean(v.sourceMode === 'upload' && v.selectedFile);
  const filename = preloaded ? v.selectedStudyDetail?.source_file : v.selectedFile?.name;
  const filenameMatches = returned => Boolean(returned && filename && returned === filename);
  const optionalStudyFilenameMatches = returned => !filename || !returned || returned === filename;
  const canonicalMatches = preloaded
    ? v.canonicalResult?.protocol?.study_id === v.selectedStudyId && optionalStudyFilenameMatches(v.canonicalResult?.source?.filename)
    : filenameMatches(v.canonicalResult?.source?.filename);
  const canonicalResult = sourceReady && v.canonicalResult?.protocol && canonicalMatches && belongsToSource(v, v.canonicalResult, canonicalMatches) ? v.canonicalResult : null;
  const chunkMatches = result => Boolean(result && (preloaded
    ? result.study_id === v.selectedStudyId && optionalStudyFilenameMatches(result.source_filename)
    : filenameMatches(result.source_filename)));
  const chunkResult = sourceReady && chunkMatches(v.chunkResult) && belongsToSource(v, v.chunkResult, true) ? v.chunkResult : null;
  const embeddingResult = sourceReady && chunkMatches(v.embeddingResult) && belongsToSource(v, v.embeddingResult, true) ? v.embeddingResult : null;
  const sourceId = preloaded ? v.selectedStudyId : canonicalResult
    ? canonicalResult.protocol.study_id || v.selectedFile.name
    : chunkResult?.study_id || embeddingResult?.study_id || null;
  const processResult = !preloaded && sourceReady && filenameMatches(v.processResult?.filename) && belongsToSource(v, v.processResult) ? v.processResult : null;
  // An indexing result contains every indexed study, so membership alone does
  // not identify which source produced this particular operation's response.
  const indexingResult = sourceReady && sourceId && belongsToSource(v, v.indexingResult) && v.indexingResult?.studies_indexed?.includes(sourceId) ? v.indexingResult : null;
  const inferSearchStudy = Boolean(v.searchResults?.results?.length && v.searchResults.results.every(item => item.study_id === sourceId));
  const searchResults = sourceReady && belongsToSource(v, v.searchResults, inferSearchStudy) ? v.searchResults : null;
  return {sourceReady, sourceId, canonicalResult, processResult, chunkResult, embeddingResult, indexingResult, searchResults};
}

export function getPresentationState(v) {
  const scoped = sourcePresentation(v);
  // Explicit target-ID panels retain their returned data and labels. Only the
  // source/processing/search panels need stale results hidden on source change.
  const {sourceReady, sourceId, ...results} = scoped;
  return {...v, ...results};
}

export function getWorkflowStages(input) {
  const scoped = sourcePresentation(input);
  const v = {...input, ...scoped};
  const {sourceReady, sourceId} = scoped;
  const preloaded = v.sourceMode === 'preloaded';
  const current = result => Boolean(sourceReady && result && sourceId && result.study_id === sourceId && belongsToSource(v, result, true));
  const canonical = Boolean(v.canonicalResult);
  const chunked = current(v.chunkResult) && v.chunkResult.total_chunks > 0;
  const embedded = current(v.embeddingResult) && v.embeddingResult.total_chunks > 0;
  const evidence = current(v.ragResult) && v.ragResult.evidence_count > 0;
  const analyzed = current(v.analysisResult) && Boolean(v.analysisResult.facts);
  const generated = current(v.icfResult) && Boolean(v.icfResult.icf_draft?.sections?.length);
  const validationMatchesDraft = !v.validationDrafts || v.validationDrafts.get(v.validationResult) === v.icfResult?.icf_draft;
  const validated = current(v.validationResult) && generated && validationMatchesDraft && v.validationResult.revision === v.icfResult.icf_draft.revision;
  const reviewed = current(v.humanReview) && generated;
  const revisionMatches = v.humanReview?.approved_revision === undefined || v.humanReview.approved_revision === v.icfResult?.revision;
  const templateMatches = !v.icfResult?.template || (v.humanReview?.approved_template_id === v.icfResult.template.template_id &&
    v.templateState?.selection?.template_id === v.icfResult.template.template_id);
  const approved = reviewed && v.humanReview.review_status === 'APPROVED' && revisionMatches && templateMatches;
  const exported = approved && v.lastExport?.studyId === sourceId && v.lastExport?.revision === (v.icfResult?.icf_draft?.revision || 1) && v.lastExport?.draft === v.icfResult?.icf_draft;
  const stages = [
    ['Study', 'source', status(v.isLoadingDetail || v.isLoadingStudies, v.studiesError && preloaded, sourceReady, true)],
    ['Protocol', 'source', status(v.isCanonicalizing || v.isProcessing, v.canonicalError || v.processError, canonical, sourceReady)],
    ['Process', 'processing', status(v.isChunking, v.chunkError, chunked, canonical)],
    ['Embed', 'processing', status(v.isEmbedding || v.isIndexing, v.embeddingError || v.indexingError, embedded, canonical)],
    ['Retrieve', 'retrieval', status(v.isRetrievingRAG || v.isSearching, v.ragError || v.searchError, evidence, sourceReady)],
    ['Analyze', 'analysis', status(v.isAnalyzing, v.analysisError, analyzed, sourceReady)],
    ['Generate', 'generation', status(v.isGeneratingICF, v.icfError, generated, sourceReady)],
    ['Validate', 'validation', status(v.isValidatingICF, v.validationError, validated && v.validationResult.overall_status === 'PASSED', generated)],
    ['Review', 'review', status(v.humanReviewLoading, v.humanReviewError, approved, generated)],
    ['Export', 'export', status(v.isExportingDocx, v.exportError, exported, approved)],
  ].map(([label, page, state]) => ({label, page, state}));
  if (v.ragResult && current(v.ragResult) && !v.isRetrievingRAG && !v.ragError && (v.ragResult.retrieval_status !== 'success' || !evidence)) stages[4].state = 'warning';
  if (validated && !v.isValidatingICF && !v.validationError && v.validationResult.overall_status !== 'PASSED') stages[7].state = v.validationResult.overall_status === 'FAILED' ? 'error' : 'warning';
  if (reviewed && !v.humanReviewLoading && !v.humanReviewError && v.humanReview.review_status === 'CHANGES_REQUESTED') stages[8].state = 'warning';
  return stages;
}

export function getMilestoneStages(v) {
  const scoped = sourcePresentation(v);
  const sourceKey = getSourceKey(v);
  const current = result => Boolean(result && sourceKey && belongsToSource(v, result, true));
  const generated = current(v.icfResult) && Boolean(v.icfResult.icf_draft?.sections?.length);
  const review = current(v.humanReview) ? v.humanReview : null;
  const templateMatches = !v.icfResult?.template || v.templateState?.selection?.template_id === v.icfResult.template.template_id;
  const approved = generated && review?.review_status === 'APPROVED' &&
    review.approved_revision === v.icfResult?.revision;
  const exportReady = generated && approved && templateMatches;
  const exported = exportReady && v.lastExport?.studyId === v.icfResult.study_id &&
    v.lastExport?.revision === v.icfResult.revision && v.lastExport?.draft === v.icfResult.icf_draft;
  return [
    {label: 'Study', page: 'source', state: v.sourceMode === 'preloaded' && (v.isLoadingDetail || v.isLoadingStudies) ? 'active' : v.sourceMode === 'preloaded' && v.studiesError ? 'error' : scoped.sourceReady ? 'complete' : 'waiting'},
    {label: 'Generate', page: 'generation', state: v.isGeneratingICF ? 'active' : v.icfError ? 'error' : generated ? 'complete' : 'waiting'},
    {label: 'Review', page: 'review', state: v.humanReviewLoading ? 'active' : v.humanReviewError ? 'error' : review?.review_status === 'CHANGES_REQUESTED' || (approved && !templateMatches) ? 'warning' : approved ? 'complete' : generated ? 'ready' : 'waiting'},
    {label: 'Export', page: 'export', state: v.isExportingDocx ? 'active' : v.exportError ? 'error' : exported ? 'complete' : exportReady ? 'ready' : 'waiting'},
  ];
}
