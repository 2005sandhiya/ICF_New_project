import React, { useState } from "react";
import {
  Icon, Button, Badge, SectionHeader, Field, ErrorNotice, EmptyState,
  BusyNotice, JsonView, DataFields, Metric, TechnicalDetails,
} from "./ui.jsx";

const QUERY_PRESETS = [
  { label: "Purpose", query: "What is the purpose of this study?" },
  { label: "Eligibility", query: "What are the eligibility requirements?" },
  { label: "Interventions", query: "What treatments or interventions are being studied?" },
  { label: "Risks", query: "What are the possible risks?" },
  { label: "Outcomes", query: "What are the expected outcomes?" },
];

function display(value) {
  if (value === null || value === undefined || value === "") return "Not available";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "Not available";
  return String(value);
}

function Score({ label = "Similarity", value }) {
  if (value === undefined || value === null) return null;
  return <Badge tone="neutral">{label} {typeof value === "number" ? value.toFixed(4) : value}</Badge>;
}

function CanonicalSummary({ result }) {
  return (
    <div className="inset-card canonical-summary">
      <div className="status-line">
        <Icon name="check" size={18} />
        <strong>Canonical protocol ready</strong>
        <Badge tone="success">{result.status}</Badge>
      </div>
      <div className="three-column">
        <Metric label="Populated fields" value={result.extracted_fields_count ?? "—"} />
        <Metric label="Missing source fields" value={result.missing_fields_count ?? "—"} />
        <Metric label="Study identifier" value={result.protocol?.study_id || "Not in source"} />
      </div>
      {result.message && <p className="muted">{result.message}</p>}
    </div>
  );
}

export function SourcePanel({ vm, onNavigate }) {
  const {
    sourceMode, setSourceMode, studiesList, isLoadingStudies, selectedStudyId,
    selectedStudyDetail, isLoadingDetail, studiesError, fetchStudies,
    handleStudyChange, selectedFile, handleFileChange, formatFileSize,
  } = vm;
  const [isDragging, setIsDragging] = useState(false);

  function switchSourceWithKeyboard(event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? "preloaded" : event.key === "End" ? "upload" : sourceMode === "preloaded" ? "upload" : "preloaded";
    setSourceMode(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  return (
    <section className="panel" aria-label="Protocol source">
      <SectionHeader eyebrow="01 / Protocol source" title="Start with the evidence." description="Choose a clinical study or upload a protocol to prepare your consent workflow." />
      <div className="tabs" role="tablist" aria-label="Protocol source">
        <button type="button" role="tab" id="tab-preloaded" aria-controls="source-preloaded" aria-selected={sourceMode === "preloaded"} tabIndex={sourceMode === "preloaded" ? 0 : -1} className={`tab ${sourceMode === "preloaded" ? "active" : ""}`} onClick={() => setSourceMode("preloaded")} onKeyDown={switchSourceWithKeyboard}>
          <Icon name="database" size={17} /> Preloaded study
        </button>
        <button type="button" role="tab" id="tab-upload" aria-controls="source-upload" aria-selected={sourceMode === "upload"} tabIndex={sourceMode === "upload" ? 0 : -1} className={`tab ${sourceMode === "upload" ? "active" : ""}`} onClick={() => setSourceMode("upload")} onKeyDown={switchSourceWithKeyboard}>
          <Icon name="upload" size={17} /> Upload protocol
        </button>
      </div>

      {sourceMode === "preloaded" ? (
        <div role="tabpanel" id="source-preloaded" aria-labelledby="tab-preloaded" className="section-stack">
          <Field label="Clinical study" id="study-dropdown" hint={`${studiesList.length} studies available in the connected dataset`}>
            <select id="study-dropdown" value={selectedStudyId} onChange={(event) => handleStudyChange(event.target.value)} disabled={isLoadingStudies || studiesList.length === 0}>
              {isLoadingStudies ? <option value="">Loading studies…</option> : studiesList.length === 0 ? <option value="">No studies available</option> : studiesList.map((study) => <option key={study.study_id} value={study.study_id}>{study.study_id} — {study.brief_title}</option>)}
            </select>
          </Field>
          {studiesError && <ErrorNotice title="Unable to load study data" message={studiesError} onRetry={isLoadingStudies ? undefined : () => fetchStudies(3, 500)} />}
          {(isLoadingStudies || isLoadingDetail) && <BusyNotice>{isLoadingStudies ? "Loading the study library…" : "Loading study details…"}</BusyNotice>}
          {!isLoadingStudies && !isLoadingDetail && !studiesError && studiesList.length === 0 && (
            <EmptyState icon="database" title="The study library is empty">Add a protocol using the upload tab, or refresh the library.<div className="form-actions"><Button variant="secondary" onClick={() => fetchStudies(3, 500)}>Refresh library</Button></div></EmptyState>
          )}
          {!isLoadingDetail && selectedStudyDetail && (
            <article className="card study-preview">
              <div className="status-line"><span className="eyebrow">Selected protocol</span><Badge tone="neutral">{display(selectedStudyDetail.overall_status)}</Badge></div>
              <h3 id="source-panel-title">{selectedStudyDetail.brief_title || selectedStudyDetail.study_id}</h3>
              <div className="metadata-grid">
                <Metric label="Study ID" value={selectedStudyDetail.study_id} />
                <Metric label="Study type" value={display(selectedStudyDetail.study_type)} />
                <Metric label="Phase" value={display(selectedStudyDetail.phases)} />
                <Metric label="Enrollment" value={display(selectedStudyDetail.enrollment)} />
              </div>
              {selectedStudyDetail.brief_summary && <p className="study-summary">{selectedStudyDetail.brief_summary}</p>}
              <TechnicalDetails label="Study metadata and source"><DataFields data={selectedStudyDetail} /></TechnicalDetails>
              <div className="form-actions">
                <Button id="select-study-btn" onClick={() => onNavigate('generation')} disabled={isLoadingDetail}><Icon name="document" size={17} />Continue to Generate ICF<Icon name="arrow" size={17} /></Button>
              </div>
            </article>
          )}
        </div>
      ) : (
        <div role="tabpanel" id="source-upload" aria-labelledby="tab-upload" className="section-stack">
          <div className={`upload-dropzone ${isDragging ? "is-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false); }} onDrop={(event) => { event.preventDefault(); setIsDragging(false); if (event.dataTransfer.files.length) handleFileChange({ target: { files: event.dataTransfer.files } }); }}>
            <div className="upload-symbol"><Icon name="upload" size={26} /></div>
            <h3>{selectedFile ? selectedFile.name : "Your protocol starts here"}</h3>
            <p className="muted">{selectedFile ? `${selectedFile.name.split(".").pop().toUpperCase()} · ${formatFileSize(selectedFile.size)}` : "Drop a protocol document here, or select a file below."}</p>
            <label htmlFor="protocol-file-input" className="eyebrow">PDF, DOCX, TXT or JSON · up to 50 MB</label>
            <input type="file" id="protocol-file-input" className="protocol-file-input" accept=".pdf,.docx,.txt,.json" onChange={handleFileChange} />
          </div>
          {selectedFile && <div className="form-actions"><Button id="continue-protocol-btn" onClick={() => onNavigate('generation')}><Icon name="document" size={17} />Continue to Generate ICF<Icon name="arrow" size={17} /></Button></div>}
        </div>
      )}
    </section>
  );
}

export function ProcessingPanel({ vm, onNavigate }) {
  const {
    canonicalResult, targetChunkSize, setTargetChunkSize, chunkOverlap, setChunkOverlap,
    handleGenerateChunks, isChunking, chunkResult, chunkError, showSampleChunks, setShowSampleChunks,
    handleGenerateEmbeddings, isEmbedding, embeddingResult, embeddingError,
    showEmbeddingPreview, setShowEmbeddingPreview, handleIndexIntoVectorStore,
    isIndexing, indexingResult, indexingError, vectorStoreStatus, fetchVectorStoreStatus,
  } = vm;
  const firstEmbedding = embeddingResult?.embedded_chunks?.[0];

  return (
    <section className="panel" aria-label="Protocol processing">
      <SectionHeader eyebrow="02 / Protocol processing" title="Give the protocol structure." description="Prepare section-aware chunks, encode their meaning, and index the evidence for retrieval." />
      <div className="processing-summary" aria-label="Processing stages">{[
        ['Canonical model', vm.isCanonicalizing, Boolean(canonicalResult?.protocol)],
        ['Document chunks', isChunking, Boolean(chunkResult?.total_chunks)],
        ['Semantic embeddings', isEmbedding, Boolean(embeddingResult?.total_chunks)],
        ['Evidence index', isIndexing, Boolean(indexingResult)],
      ].map(([label, active, complete]) => <div key={label}><Icon name={complete ? 'check' : active ? 'refresh' : 'layers'} size={17}/><strong>{label}</strong><Badge tone={complete ? 'success' : 'neutral'}>{active ? 'In progress' : complete ? 'Complete' : 'Waiting'}</Badge></div>)}</div>
      {canonicalResult?.protocol ? (
        <div className="section-stack">
          <CanonicalSummary result={canonicalResult} />
          <article className="card">
            <SectionHeader title="Prepare protocol evidence" description="Chunk size and overlap apply to the selected study or uploaded file." />
            <div className="two-column">
              <Field label="Target chunk size" id="target-chunk-size" hint="Characters per chunk"><input id="target-chunk-size" type="number" value={targetChunkSize} onChange={(event) => setTargetChunkSize(Number(event.target.value))} /></Field>
              <Field label="Chunk overlap" id="chunk-overlap" hint="Characters shared between adjacent chunks"><input id="chunk-overlap" type="number" value={chunkOverlap} onChange={(event) => setChunkOverlap(Number(event.target.value))} /></Field>
            </div>
            <div className="form-actions">
              <Button id="generate-chunks-btn" onClick={handleGenerateChunks} disabled={isChunking || isEmbedding} busy={isChunking}>{isChunking ? "Generating chunks…" : "Generate chunks"}</Button>
              <Button variant="secondary" id="generate-embeddings-btn" onClick={handleGenerateEmbeddings} disabled={isEmbedding || isChunking || isIndexing} busy={isEmbedding}>{isEmbedding ? "Encoding embeddings…" : "Generate embeddings"}</Button>
              <Button variant="secondary" id="index-vector-store-btn" onClick={handleIndexIntoVectorStore} disabled={isIndexing || isEmbedding || isChunking} busy={isIndexing}>{isIndexing ? "Indexing evidence…" : "Index evidence"}</Button>
            </div>
            {chunkError && <ErrorNotice title="Chunking failed" message={chunkError} onRetry={!isChunking && !isEmbedding ? handleGenerateChunks : undefined} />}
            {embeddingError && <ErrorNotice title="Embedding failed" message={embeddingError} onRetry={!isEmbedding && !isChunking && !isIndexing ? handleGenerateEmbeddings : undefined} />}
            {indexingError && <ErrorNotice title="Indexing failed" message={indexingError} onRetry={!isIndexing && !isEmbedding && !isChunking ? handleIndexIntoVectorStore : undefined} />}
          </article>

          {chunkResult && (
            <article className="card">
              <SectionHeader eyebrow="Protocol chunks" title={`${chunkResult.total_chunks ?? 0} chunks prepared`} action={<Button variant="secondary" aria-expanded={showSampleChunks} aria-controls="sample-chunks" onClick={() => setShowSampleChunks(!showSampleChunks)}>{showSampleChunks ? "Hide sample chunks" : "Inspect sample chunks"}</Button>} />
              <div className="metadata-grid"><Metric label="Target size" value={`${chunkResult.target_chunk_size} characters`} /><Metric label="Overlap" value={`${chunkResult.chunk_overlap} characters`} /><Metric label="Source" value={chunkResult.source_filename} /><Metric label="Format" value={chunkResult.source_type} /></div>
              {showSampleChunks && <div id="sample-chunks" className="result-list">{chunkResult.chunks?.length ? chunkResult.chunks.slice(0, 5).map((chunk) => <article className="evidence-card" key={chunk.chunk_id}><div className="status-line"><Badge tone="neutral">{chunk.metadata?.section || "Section unavailable"}</Badge>{chunk.metadata?.subsection && <span className="muted">{chunk.metadata.subsection}</span>}<span className="mono">{chunk.metadata?.chunk_index} / {chunk.metadata?.total_chunks}</span></div><p className="evidence-text">{chunk.text}</p><div className="metadata-grid"><Metric label="Chunk ID" value={chunk.chunk_id} /><Metric label="Page" value={display(chunk.metadata?.page_number)} /><Metric label="Source field" value={display(chunk.metadata?.source_field)} /><Metric label="Characters" value={chunk.metadata?.character_count} /></div></article>) : <EmptyState icon="document" title="No chunks returned">The source did not return any sample chunks.</EmptyState>}{chunkResult.chunks?.length > 5 && <p className="muted">Showing 5 of {chunkResult.total_chunks} chunks. The full response is available below.</p>}</div>}
              <TechnicalDetails label="Complete chunking response"><JsonView data={chunkResult} /></TechnicalDetails>
            </article>
          )}

          {embeddingResult && (
            <article className="card">
              <SectionHeader eyebrow="Semantic embeddings" title="Embedding result" action={<Button variant="secondary" aria-expanded={showEmbeddingPreview} aria-controls="embedding-preview" onClick={() => setShowEmbeddingPreview(!showEmbeddingPreview)}>{showEmbeddingPreview ? "Hide vector preview" : "Inspect vector preview"}</Button>} />
              <div className="metadata-grid"><Metric label="Embedding model" value={embeddingResult.embedding_model} /><Metric label="Dimensions" value={embeddingResult.embedding_dimension} /><Metric label="Batch size" value={embeddingResult.batch_size} /><Metric label="Chunks embedded" value={embeddingResult.total_chunks} /></div>
              {showEmbeddingPreview && <div id="embedding-preview" className="inset-card">{firstEmbedding ? <><p className="eyebrow">Sample vector</p><p className="mono">{firstEmbedding.chunk_id}</p><p className="muted">Section: {firstEmbedding.metadata?.section || "Not available"} · {firstEmbedding.embedding?.length ?? 0} dimensions</p><pre className="evidence-text mono">[{firstEmbedding.embedding?.slice(0, 6).map((value) => Number(value).toFixed(4)).join(", ")}{firstEmbedding.embedding?.length > 6 ? `, … ${firstEmbedding.embedding.length - 6} more values` : ""}]</pre></> : <p className="muted">No vector preview was returned.</p>}</div>}
              <TechnicalDetails label="Complete embedding response"><JsonView data={embeddingResult} /></TechnicalDetails>
            </article>
          )}
          {indexingResult && <article className="card"><SectionHeader eyebrow="Evidence index" title="Indexing result" action={<Badge tone="success">{indexingResult.status}</Badge>} /><p>{indexingResult.message}</p><div className="three-column"><Metric label="Vectors added" value={indexingResult.vectors_added} /><Metric label="Total vectors" value={indexingResult.total_vectors} /><Metric label="Dimensions" value={indexingResult.embedding_dimension} /></div><TechnicalDetails><DataFields data={indexingResult} /></TechnicalDetails></article>}
        </div>
      ) : <EmptyState icon="layers" title="A protocol model comes first">Choose a source and build its canonical protocol model to enable processing.</EmptyState>}
      <article className="card section-divider">
        <SectionHeader eyebrow="Connected evidence store" title="Vector store" action={<Button variant="secondary" onClick={fetchVectorStoreStatus}><Icon name="refresh" size={16} /> Refresh status</Button>} />
        {vectorStoreStatus ? <><div className="status-line"><Badge tone={vectorStoreStatus.status === "indexed" ? "success" : "neutral"}>{vectorStoreStatus.status}</Badge><span className="muted">{vectorStoreStatus.embedding_model}</span></div><div className="metadata-grid"><Metric label="Stored vectors" value={vectorStoreStatus.total_vectors} /><Metric label="Dimensions" value={vectorStoreStatus.embedding_dimension} /><Metric label="Index type" value={vectorStoreStatus.index_type} /><Metric label="Indexed studies" value={vectorStoreStatus.studies_indexed?.join(", ") || "None"} /></div><TechnicalDetails><DataFields data={vectorStoreStatus} /></TechnicalDetails></> : <EmptyState icon="database" title="Vector status is unavailable">Refresh the status to check the connected evidence store.</EmptyState>}
      </article>
      {onNavigate && <div className="form-actions"><Button variant="secondary" onClick={() => onNavigate('retrieval')}>Open evidence retrieval <Icon name="arrow" size={17}/></Button></div>}
    </section>
  );
}

function EvidenceCard({ item, rag = false }) {
  const source = rag ? item.source || {} : item;
  return (
    <article className="evidence-card">
      <div className="status-line"><Badge tone="neutral">Rank {item.rank}</Badge><Score value={item.similarity_score} /><Score label="Reranked" value={item.reranking_score} /></div>
      <h4>{display(item.section)}{item.subsection ? ` / ${item.subsection}` : ""}</h4>
      <p className="evidence-text">{item.text}</p>
      <div className="metadata-grid">
        <Metric label="Source" value={display(rag ? source.filename : source.source_filename)} />
        <Metric label="Study ID" value={display(source.study_id)} />
        <Metric label="Chunk ID" value={display(item.chunk_id)} />
        {!rag && <Metric label="Vector ID" value={item.vector_id} />}
        <Metric label="Page" value={display(source.page_number)} />
        {source.source_field && <Metric label="Source field" value={source.source_field} />}
        {source.source_reference && <Metric label="Source reference" value={source.source_reference} />}
      </div>
    </article>
  );
}

export function RetrievalPanel({ vm, onNavigate }) {
  const {
    sourceMode, selectedStudyId, searchQuery, setSearchQuery, searchTopK, setSearchTopK,
    isSearching, searchResults, searchError, handleExecuteSearch, handleSampleQueryClick,
    ragStudyId, setRagStudyId, ragTopK, setRagTopK, ragMinThreshold, setRagMinThreshold,
    ragQuery, setRagQuery, isRetrievingRAG, handleRetrieveRAG, ragError, ragResult,
    showRawRAGJson, setShowRawRAGJson,
  } = vm;
  return (
    <section className="panel" aria-label="Evidence retrieval">
      <SectionHeader eyebrow="03 / Evidence retrieval" title="Find the detail that matters." description="Search the indexed protocol, inspect its sources, and assemble evidence for downstream generation." />
      <article className="card">
        <SectionHeader title="Search protocol evidence" description={sourceMode === "preloaded" && selectedStudyId ? `Results are scoped to ${selectedStudyId}.` : "Search across the connected evidence index."} />
        <form onSubmit={(event) => { event.preventDefault(); if (!isSearching) handleExecuteSearch(); }}>
          <Field label="Natural language query" id="similarity-query"><input id="similarity-query" type="text" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="What are the possible risks of the study?" /></Field>
          <div className="query-presets" aria-label="Run a sample search"><span className="muted">Try a question</span>{QUERY_PRESETS.map((preset) => <Button key={preset.label} variant="ghost" title={preset.query} onClick={() => handleSampleQueryClick(preset.query)}>{preset.label}</Button>)}</div>
          <div className="form-grid">
            <Field label="Results to retrieve" id="search-top-k"><select id="search-top-k" value={searchTopK} onChange={(event) => setSearchTopK(Number(event.target.value))}>{[3, 5, 10, 20].map((count) => <option key={count} value={count}>{count} matches{count === 5 ? " (default)" : ""}</option>)}</select></Field>
            <div className="form-actions"><Button type="submit" disabled={isSearching} busy={isSearching}><Icon name="search" size={17} />{isSearching ? "Searching evidence…" : "Search evidence"}</Button></div>
          </div>
        </form>
        {searchError && <ErrorNotice title="Search could not complete" message={searchError} onRetry={!isSearching ? () => handleExecuteSearch() : undefined} />}
        {isSearching && <BusyNotice>Retrieving matching protocol passages…</BusyNotice>}
        {searchResults ? <div className="section-divider section-stack"><div className="status-line"><Badge tone="neutral">{searchResults.results_count} matches</Badge><span className="muted">{searchResults.total_vectors_searched} vectors searched · {searchResults.embedding_model}</span></div><p>Results for “{searchResults.query}”</p>{searchResults.results?.length ? <div className="result-list">{searchResults.results.map((item, index) => <EvidenceCard key={`${item.vector_id}-${index}`} item={item} />)}</div> : <EmptyState icon="search" title="No matching evidence">Try a different query or confirm that the selected study has been indexed.</EmptyState>}<TechnicalDetails label="Complete search response"><JsonView data={searchResults} /></TechnicalDetails></div> : !isSearching && !searchError && <EmptyState icon="search" title="Your evidence appears here">Run a query to view matching passages with their study and source references.</EmptyState>}
      </article>

      <article className="card section-divider">
        <SectionHeader eyebrow="Grounded context" title="Assemble evidence for generation" description="Retrieve and organize source passages with study filtering, deduplication, and a similarity threshold." />
        <div className={`rag-flow ${isRetrievingRAG ? 'is-active' : ''}`} aria-label="How retrieval works">{['Information need', 'Vector retrieval', 'Relevant evidence', 'Context assembly', 'AI agent'].map((label, index) => <React.Fragment key={label}>{index > 0 && <Icon name="arrow" size={14}/>}<span>{label}</span></React.Fragment>)}</div>
        <form onSubmit={(event) => { event.preventDefault(); if (!isRetrievingRAG) handleRetrieveRAG(); }}>
          <div className="three-column">
            <Field label="Target study ID" id="rag-study-id"><input id="rag-study-id" type="text" value={ragStudyId} onChange={(event) => setRagStudyId(event.target.value)} placeholder="e.g. NCT00081328" /></Field>
            <Field label="Evidence to retrieve" id="rag-top-k"><select id="rag-top-k" value={ragTopK} onChange={(event) => setRagTopK(Number(event.target.value))}>{[3, 5, 10].map((count) => <option key={count} value={count}>{count} chunks{count === 5 ? " (default)" : ""}</option>)}</select></Field>
            <Field label="Minimum similarity" id="rag-threshold"><select id="rag-threshold" value={ragMinThreshold} onChange={(event) => setRagMinThreshold(Number(event.target.value))}><option value={0}>0.0 · no threshold</option><option value={0.15}>0.15 · light filtering</option><option value={0.25}>0.25 · moderate filtering</option><option value={0.35}>0.35 · strict threshold</option></select></Field>
          </div>
          <Field label="Information requirement" id="rag-query"><input id="rag-query" type="text" value={ragQuery} onChange={(event) => setRagQuery(event.target.value)} placeholder="What information should the context include?" /></Field>
          <div className="query-presets" aria-label="Context query presets">{QUERY_PRESETS.map((preset) => <Button key={preset.label} variant="ghost" onClick={() => setRagQuery(preset.query)}>{preset.query}</Button>)}</div>
          <div className="form-actions"><Button type="submit" disabled={isRetrievingRAG} busy={isRetrievingRAG}>{isRetrievingRAG ? "Assembling context…" : "Assemble RAG context"}<Icon name="arrow" size={17} /></Button></div>
        </form>
        {ragError && <ErrorNotice title="Context retrieval failed" message={ragError} onRetry={!isRetrievingRAG ? handleRetrieveRAG : undefined} />}
        {isRetrievingRAG && <BusyNotice>Retrieving, filtering, and organizing source evidence…</BusyNotice>}
        {ragResult ? <div className="section-divider section-stack"><div className="status-line"><Badge tone="neutral">{ragResult.evidence_count} evidence items</Badge><Badge tone={ragResult.retrieval_status === "success" ? "success" : "warning"}>{ragResult.retrieval_status}</Badge><Button variant="secondary" aria-expanded={showRawRAGJson} aria-controls="raw-rag-response" onClick={() => setShowRawRAGJson(!showRawRAGJson)}>{showRawRAGJson ? "Hide raw context JSON" : "View raw context JSON"}</Button></div>{ragResult.warning_message && <div className="notice notice-warning" role="status"><strong>Retrieval notice</strong><p>{ragResult.warning_message}</p></div>}{showRawRAGJson && <div id="raw-rag-response"><JsonView data={ragResult} /></div>}{ragResult.evidence?.length ? <div className="result-list">{ragResult.evidence.map((item, index) => <EvidenceCard key={`${item.chunk_id}-${index}`} item={item} rag />)}</div> : <EmptyState icon="document" title="No grounded evidence returned">Adjust your query, study identifier, or threshold and try again.</EmptyState>}</div> : !isRetrievingRAG && !ragError && <EmptyState icon="layers" title="Context is ready to assemble">Define the information you need to collect passages from the protocol.</EmptyState>}
      </article>
      {onNavigate && <div className="form-actions"><Button variant="secondary" onClick={() => onNavigate('analysis')}>Open protocol analysis <Icon name="arrow" size={17}/></Button></div>}
    </section>
  );
}

