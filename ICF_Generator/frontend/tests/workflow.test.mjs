import {getWorkflowStages, getMilestoneStages, getSourceKey, getPresentationState, navigation} from '../src/components/workflow.js';
// Isolated state fixtures audit presentation logic; no API requests or persisted data.
const studyId = 'audit-study-a';
const draft = {revision:1,sections:[{section_id:'purpose',content:'Protocol text'}]};
const done = {
  sourceMode:'preloaded', selectedStudyId:studyId,
  selectedStudyDetail:{study_id:studyId,source_file:'studies.json'},
  canonicalResult:{source:{filename:'studies.json',type:'json'},protocol:{study_id:studyId}},
  chunkResult:{study_id:studyId,total_chunks:1,source_filename:'studies.json'},
  embeddingResult:{study_id:studyId,total_chunks:1,source_filename:'studies.json'},
  ragResult:{study_id:studyId,evidence_count:1,retrieval_status:'success'},
  analysisResult:{study_id:studyId,facts:{}},
  icfResult:{study_id:studyId,icf_draft:draft,generation_status:'success'},
  validationResult:{study_id:studyId,revision:1,overall_status:'PASSED'},
  humanReview:{study_id:studyId,review_status:'APPROVED'},
  lastExport:{studyId,revision:1,draft},
};
const state = (v,label) => getWorkflowStages(v).find(s=>s.label===label)?.state;
const tracked = (v, sourceKey = getSourceKey(v)) => {
  const presentationProvenance = new WeakMap();
  for (const name of ['canonicalResult','processResult','chunkResult','embeddingResult','indexingResult','searchResults','ragResult','analysisResult','icfResult','validationResult','humanReview']) {
    if (v[name]) presentationProvenance.set(v[name], sourceKey);
  }
  return {...v,presentationProvenance};
};
const uploaded = {
  ...done,sourceMode:'upload',selectedFile:{name:'protocol.txt',size:200,lastModified:100},
  canonicalResult:{source:{filename:'protocol.txt',type:'txt'},protocol:{study_id:studyId}},
  chunkResult:{study_id:studyId,total_chunks:1,source_filename:'protocol.txt'},
  embeddingResult:{study_id:studyId,total_chunks:1,source_filename:'protocol.txt'},
  processResult:{filename:'protocol.txt',status:'processed'},
  indexingResult:{studies_indexed:[studyId]},
  searchResults:{results:[],results_count:0},
};
const trackedUpload=tracked(uploaded);
const checks = [
  ['Normal navigation exposes only the four user milestones', () => JSON.stringify(navigation.map(item=>item.id))===JSON.stringify(['source','generation','review','export'])],
  ['The user-facing pathway presents four milestones, not technical operations', () => getMilestoneStages(tracked(done)).map(s=>s.label).join(',')==='Study,Generate,Review,Export'],
  ['A selected protocol and generated consent appear complete in user-facing milestones', () => getMilestoneStages(trackedUpload).slice(0,2).every(s=>s.state==='complete')],
  ['A running automatic workflow marks generation active', () => getMilestoneStages({...trackedUpload,isGeneratingICF:true}).find(s=>s.page==='generation').state==='active'],
  ['Complete current study reports 10 complete stages', () => getWorkflowStages(done).every(s=>s.state==='complete')],
  ['Switching to empty upload cannot complete prior-source stages', () => getWorkflowStages({...done,sourceMode:'upload',selectedFile:null}).every(s=>s.state!=='complete')],
  ['Canonical response for another selected study is not complete', () => state({...done,selectedStudyId:'audit-study-b',selectedStudyDetail:{study_id:'audit-study-b'}},'Protocol')!=='complete'],
  ['New draft at same revision is not marked previously exported', () => state({...done,icfResult:{study_id:studyId,icf_draft:{revision:1,sections:[{section_id:'purpose',content:'New generation'}]}}},'Export')!=='complete'],
  ['Empty upload without retained results has no completed stages', () => getWorkflowStages({sourceMode:'upload',selectedFile:null}).every(s=>s.state!=='complete')],
  ['Validation on an older revision is not complete', () => state({...done,validationResult:{study_id:studyId,revision:0,overall_status:'PASSED'}},'Validate')!=='complete'],
  ['Failed validation is represented as error', () => state({...done,validationResult:{study_id:studyId,revision:1,overall_status:'FAILED'}},'Validate')==='error'],
  ['RAG threshold fallback is represented as warning', () => state({...done,ragResult:{study_id:studyId,evidence_count:1,retrieval_status:'fallback_below_threshold'}},'Retrieve')==='warning'],
  ['A tracked upload with current results can complete its workflow', () => getWorkflowStages(trackedUpload).every(s=>s.state==='complete')],
  ['A different upload with the same study ID cannot reuse tracked results', () => getWorkflowStages({...trackedUpload,selectedFile:{name:'other.txt',size:200,lastModified:100}}).filter(s=>s.label!=='Study').every(s=>s.state!=='complete')],
  ['A replacement file with the same name and different modification time is a different source', () => getSourceKey(uploaded)!==getSourceKey({...uploaded,selectedFile:{...uploaded.selectedFile,lastModified:101}})],
  ['Untracked uploaded results do not complete downstream stages', () => getWorkflowStages(uploaded).filter(s=>s.label!=='Study').every(s=>s.state!=='complete')],
  ['A late preloaded response cannot be attributed to an upload', () => getWorkflowStages({...tracked(done),sourceMode:'upload',selectedFile:uploaded.selectedFile}).filter(s=>s.label!=='Study').every(s=>s.state!=='complete')],
  ['Presentation hides stale source results while retaining explicit target-ID results', () => {
    const scoped=getPresentationState({...trackedUpload,selectedFile:null});
    return ['canonicalResult','processResult','chunkResult','embeddingResult','indexingResult','searchResults'].every(key=>scoped[key]===null) && ['ragResult','analysisResult','icfResult','validationResult'].every(key=>scoped[key]===trackedUpload[key]);
  }],
  ['A tracked empty search response remains visible as an empty state', () => getPresentationState(trackedUpload).searchResults===trackedUpload.searchResults],
  ['An index listing a study does not prove that study was the current indexing action', () => getPresentationState({...done,indexingResult:{studies_indexed:[studyId,'audit-study-b']}}).indexingResult===null],
  ['Validation of a different draft at the same revision is not complete', () => {
    const validationDrafts=new WeakMap([[done.validationResult,{...draft}]]);
    return state({...done,validationDrafts},'Validate')!=='complete';
  }],
  ['Validation sidecar for the current draft permits completion', () => {
    const validationDrafts=new WeakMap([[done.validationResult,draft]]);
    return state({...done,validationDrafts},'Validate')==='complete';
  }],
  ['Validation requiring review is shown as warning', () => state({...done,validationResult:{study_id:studyId,revision:1,overall_status:'REQUIRES_REVIEW'}},'Validate')==='warning'],
  ['Empty RAG response is shown as warning', () => state({...done,ragResult:{study_id:studyId,evidence_count:0,retrieval_status:'empty'}},'Retrieve')==='warning'],
  ['Requested human changes are shown as warning', () => state({...done,humanReview:{study_id:studyId,review_status:'CHANGES_REQUESTED'}},'Review')==='warning'],
  ['An in-progress validation overrides a stale error report', () => state({...done,isValidatingICF:true,validationResult:{study_id:studyId,revision:1,overall_status:'FAILED'}},'Validate')==='active'],
  ['An empty generated draft is not complete', () => state({...done,icfResult:{study_id:studyId,icf_draft:{revision:1,sections:[]}}},'Generate')!=='complete'],
];
const results = checks.map(([name,run]) => {try{return {name,passed:run()};}catch(error){return {name,passed:false,error:error.message};}});
console.log(JSON.stringify({results,passed:results.filter(r=>r.passed).length,total:results.length,emptyUploadRetainedStates:getWorkflowStages({...done,sourceMode:'upload',selectedFile:null})},null,2));
if(results.some(r=>!r.passed)) process.exitCode=1;

