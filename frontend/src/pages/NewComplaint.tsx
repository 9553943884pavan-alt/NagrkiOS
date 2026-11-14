import {useEffect,useRef,useState} from 'react';import {useNavigate} from 'react-router-dom';
import {AlertCircle,ArrowLeft,ArrowRight,BrainCircuit,CheckCircle2,FileText,ImagePlus,Info,MapPin,Mic,MicOff,Send,ShieldCheck,Sparkles,UploadCloud,X} from 'lucide-react';
import {api,post,upload} from '../lib/api';
import SelectMenu from '../components/SelectMenu';import {useAuth} from '../context/AuthContext';
import type {AIResult,Case,Meta} from '../types';import {PageHeader,PriorityBadge,Spinner} from '../components/UI';
interface SpeechResult {results:ArrayLike<ArrayLike<{transcript:string;confidence?:number}> & {isFinal?:boolean}>}
interface Recognition {lang:string;interimResults:boolean;continuous:boolean;onstart:(()=>void)|null;onresult:((event:SpeechResult)=>void)|null;onerror:((e:{error:string})=>void)|null;onend:(()=>void)|null;start:()=>void;stop:()=>void}
type SpeechWindow=Window & {SpeechRecognition?:new()=>Recognition;webkitSpeechRecognition?:new()=>Recognition};
const steps=[{n:1,label:'Describe issue'},{n:2,label:'AI assistance'},{n:3,label:'Submit grievance'}];
export default function NewComplaint(){const nav=useNavigate();const {user}=useAuth();
 const[meta,setMeta]=useState<Meta|null>(null);const[title,setTitle]=useState('');const[description,setDescription]=useState('');const[district,setDistrict]=useState(user?.district||'Prayagraj');const[language,setLanguage]=useState('hi-IN');
 const[attachment,setAttachment]=useState<File|null>(null);const[previewUrl,setPreviewUrl]=useState('');const[analysis,setAnalysis]=useState<AIResult|null>(null);const[analyzing,setAnalyzing]=useState(false);const[submitting,setSubmitting]=useState(false);const[error,setError]=useState('');const[completed,setCompleted]=useState<Case|null>(null);
 const analysisRevision=useRef(0);
 const[listening,setListening]=useState(false);const[voiceUsed,setVoiceUsed]=useState(false);const[voiceMessage,setVoiceMessage]=useState('');const recognition=useRef<Recognition|null>(null);const voiceBase=useRef('');const voiceLast=useRef('');const voiceFailure=useRef('');const voiceStopping=useRef(false);const fileInput=useRef<HTMLInputElement>(null);
 useEffect(()=>{api<Meta>('/api/meta').then(setMeta).catch(e=>setError(e.message));},[]);
 useEffect(()=>{if(!attachment){setPreviewUrl('');return;}const url=URL.createObjectURL(attachment);setPreviewUrl(url);return()=>URL.revokeObjectURL(url);},[attachment]);
 useEffect(()=>()=>{recognition.current?.stop();},[]);
 function invalidate(){analysisRevision.current++;setAnalysis(null);setError('');}
 function voice(){
  if(listening){
   if(voiceStopping.current)return;
   voiceStopping.current=true;
   setVoiceMessage('Finishing transcription…');
   recognition.current?.stop(); // Chrome can dispatch the last onresult AFTER stop().
   return;
  }
  const w=window as SpeechWindow;const Cls=w.SpeechRecognition||w.webkitSpeechRecognition;
  if(!Cls){setVoiceMessage('Speech-to-text is not supported in this browser. Try Chrome or Edge, or type the complaint.');return;}
  try{
   const rec=new Cls();recognition.current=rec;voiceBase.current=description.trim();voiceLast.current='';voiceFailure.current='';
   rec.lang=language;rec.continuous=true;rec.interimResults=true;
   rec.onstart=()=>{voiceStopping.current=false;setListening(true);setVoiceMessage('Listening… text will appear live below. Speak clearly, then press Stop.');};
   rec.onresult=e=>{
    const finalParts:string[]=[];const interimParts:string[]=[];
    for(let i=0;i<e.results.length;i++){
      const result=e.results[i];const segment=(result[0]?.transcript||'').trim();if(!segment)continue;
      if(result.isFinal)finalParts.push(segment);else interimParts.push(segment);
    }
    // Reconstruct from all browser results, not only the most recent event, avoiding duplicated text.
    const transcript=[...finalParts,...interimParts].join(' ').trim();
    if(transcript){
      voiceLast.current=transcript;
      setDescription([voiceBase.current,transcript].filter(Boolean).join(' '));
      setVoiceUsed(true);invalidate();
      setVoiceMessage(interimParts.length?'Transcribing live… please review the text below.':'Speech captured. Press Stop when finished.');
    }
   };
   rec.onerror=e=>{
    const advice:Record<string,string>={
      'not-allowed':'Microphone or speech-recognition permission was denied. Check browser site permissions.',
      'audio-capture':'No microphone was found. Select your microphone in Windows sound settings.',
      'network':'Browser speech recognition requires a network speech service that is currently unavailable. Type your complaint instead.',
      'no-speech':'No clear speech was detected. Speak closer to your microphone, or type the complaint.',
      'language-not-supported':'The speech service cannot recognize this language. Try Hindi or English.'
    };
    voiceFailure.current=advice[e.error]||`Speech recognition error (${e.error}). You can type the complaint instead.`;
    setVoiceMessage(voiceFailure.current);setListening(false);
   };
   rec.onend=()=>{
    setListening(false);voiceStopping.current=false;recognition.current=null;
    if(voiceFailure.current){setVoiceMessage(voiceFailure.current);return;}
    if(voiceLast.current){setVoiceMessage('Transcript inserted. Review and edit it, then run AI preview before submitting.');}
    else{setVoiceMessage('The microphone session ended without a transcript. Browser speech recognition may need an internet connection; try Chrome/Edge or type the complaint.');}
   };
   setListening(true);rec.start();
  }catch{
   setListening(false);voiceStopping.current=false;setVoiceMessage('Could not start browser speech recognition. Check microphone permissions or type the complaint.');
  }
 }
 async function doAnalyze(){if(title.trim().length<5||description.trim().length<12){setError('Provide a title (5+ characters) and detailed description (12+ characters) first.');return;}const revision=++analysisRevision.current;setAnalyzing(true);setError('');try{const r=await post<AIResult>('/api/ai/analyze',{title,description,district,image_hint:attachment?.name||''});if(revision===analysisRevision.current)setAnalysis(r);}catch(e){if(revision===analysisRevision.current)setError(e instanceof Error?e.message:'Could not analyze');}finally{setAnalyzing(false);}}
 async function submit(e:React.FormEvent){e.preventDefault();if(!analysis){setError('Run the AI preview first to review the recommended department.');return;}setSubmitting(true);setError('');try{let attachment_path:string|undefined;if(attachment){const result=await upload(attachment);attachment_path=result.path;}const c=await post<Case>('/api/complaints',{title:title.trim(),description:description.trim(),district,channel:attachment?'photo':voiceUsed?'voice':'web',attachment_path,image_hint:attachment?.name||''});setCompleted(c);}catch(e){setError(e instanceof Error?e.message:'Could not submit the grievance');}finally{setSubmitting(false);}}
 if(completed)return <div className="success-page"><div className="success-card"><div className="success-mark"><CheckCircle2 size={40}/></div><span className="eyebrow">GRIEVANCE RECEIVED</span><h1>Your grievance has been registered.</h1><p>A demo case has been created and stored locally. You can now follow its progress through the citizen or officer workspace.</p><div className="success-ticket"><small>REFERENCE NUMBER</small><strong>{completed.ticket_no}</strong><span>{completed.department} · {completed.district}</span></div><div className="success-actions"><button className="btn btn-primary" onClick={()=>nav(`/cases/${completed.id}`)}>View grievance <ArrowRight size={17}/></button><button className="btn btn-outline" onClick={()=>nav('/cases')}>All grievances</button></div><div className="success-note"><Info size={16}/> Demo only: nothing has been submitted to a real authority.</div></div></div>;
 return <div className="page-stack"><button className="back-link" onClick={()=>nav('/cases')}><ArrowLeft size={16}/> Back to grievances</button><PageHeader eyebrow="UNIFIED CITIZEN INTAKE" title="Lodge a new grievance" description="One shared workflow for written issues, voice transcripts and optional site photos."/>
 <div className="stepper">{steps.map((step,i)=><div key={step.n} className={`stepper-step ${i===0?'active':analysis?'complete':''}`}><span>{analysis&&i<2?<CheckCircle2 size={16}/>:step.n}</span>{step.label}{i<2&&<div className="step-line"/>}</div>)}</div>
 <form onSubmit={submit} className="submit-grid"><div className="submit-main"><section className="panel form-section"><div className="form-section-head"><div className="form-section-icon"><FileText size={20}/></div><div><h2>Describe your concern</h2><p>Clear details help the demo system suggest the correct desk.</p></div></div><label className="field-label">Grievance title <span>*</span><input value={title} onChange={e=>{setTitle(e.target.value);invalidate();}} placeholder="e.g. Drinking water supply interrupted in our area" maxLength={200} required minLength={5}/><small>A short, specific summary of the issue</small></label><label className="field-label">District <span>*</span><SelectMenu className="district-select" ariaLabel="District" searchable leftIcon={<MapPin size={18}/>} value={district} onChange={val=>{setDistrict(val);invalidate();}} options={(meta?.districts||[district]).map(d=>({value:d,label:d}))}/></label>
 <label className="field-label">Detailed description <span>*</span><textarea value={description} onChange={e=>{setDescription(e.target.value);invalidate();}} placeholder="Describe what happened, where it happened, how long it's been a problem, and who is affected. Hindi is welcome too.\n\nExample: पानी का पाइप टूट गया है और सड़क पर पानी भर रहा है..." rows={7} required minLength={12} maxLength={4000}/><small>{description.length}/4,000 characters · Do not include personal identification numbers.</small></label>
 <div className="voice-tools"><div><div className="voice-label"><Mic size={18}/> Speak instead of typing</div><p>Browser speech recognition (experimental). Check the transcript carefully.</p></div><div className="voice-actions"><SelectMenu className="speech-select" ariaLabel="Speech language" value={language} onChange={setLanguage} options={[{value:'hi-IN',label:'Hindi / Hindi dialects'},{value:'en-IN',label:'English (India)'}]}/><button type="button" className={`btn ${listening?'btn-danger':'btn-outline'}`} onClick={voice}>{listening?<MicOff size={16}/>:<Mic size={16}/>} {listening?'Stop':'Record'}</button></div></div>{voiceMessage&&<div className="hint-bar"><Info size={15}/>{voiceMessage}</div>}
 </section><section className="panel form-section"><div className="form-section-head"><div className="form-section-icon image"><ImagePlus size={20}/></div><div><h2>Attach a site photo <span className="optional">OPTIONAL</span></h2><p>Show damage, infrastructure or an unfinished public work.</p></div></div><input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" className="visually-hidden" onChange={e=>{const f=e.target.files?.[0]||null;if(f&&f.size>5*1024*1024){setError('Photo must be smaller than 5 MB');return;}setAttachment(f);invalidate();}}/>{attachment?<div className="uploaded-preview">{previewUrl&&<img src={previewUrl} alt="Photo ready for upload"/>}<div><b>{attachment.name}</b><span>{(attachment.size/1024).toFixed(0)} KB · Ready to upload</span><small>Photo content isn't analyzed by the mock vision model.</small></div><button type="button" className="icon-button" title="Remove photo" onClick={()=>{setAttachment(null);if(fileInput.current)fileInput.current.value='';invalidate();}}><X size={18}/></button></div>:<button type="button" className="upload-drop" onClick={()=>fileInput.current?.click()}><UploadCloud size={25}/><b>Click to upload a photo</b><span>PNG, JPEG or WEBP · max 5 MB</span></button>}</section></div>
 <aside className="submit-side"><section className="panel ai-preview"><div className="ai-preview-head"><span><BrainCircuit size={21}/></span><div><h2>AI triage preview</h2><p>Illustrative, rules-based suggestions</p></div><span className="mock-pill">MOCK</span></div>
 {analyzing?<Spinner text="Analyzing complaint…"/>:analysis?<div className="ai-preview-body"><div className="ai-preview-signal"><Sparkles size={19}/><div><b>Analysis complete</b><small>Review the classification before filing</small></div><CheckCircle2 size={19}/></div><div className="prediction-item"><small>SUGGESTED CATEGORY</small><strong>{analysis.category}</strong></div><div className="prediction-item"><small>ROUTE TO</small><strong>{analysis.department}</strong></div><div className="prediction-columns"><div className="prediction-item"><small>PRIORITY</small><PriorityBadge priority={analysis.priority}/></div><div className="prediction-item"><small>CONFIDENCE</small><strong>{Math.round(analysis.confidence*100)}%</strong></div></div><div className="prediction-meter"><span style={{width:`${analysis.confidence*100}%`}}/></div><div className="prediction-item"><small>ILLUSTRATIVE RESOLUTION TARGET</small><strong>{analysis.estimated_hours} hours</strong></div><p className="prediction-rationale">{analysis.rationale}</p>{analysis.requires_human_review&&<div className="review-alert"><AlertCircle size={16}/>Human review recommended.</div>}{analysis.similar_count>0&&<div className="hint-bar">{analysis.similar_count} potentially similar local case(s) in the demo dataset.</div>}</div>:<div className="preview-empty"><div><BrainCircuit size={33}/></div><h3>Ready when you are</h3><p>Fill in the grievance details, then run a mock analysis to preview routing, urgency and expected resolution time.</p></div>}
 <button className="btn btn-outline btn-block" type="button" disabled={analyzing||submitting} onClick={doAnalyze}><Sparkles size={17}/>{analysis?'Re-run AI analysis':'Analyze grievance'}</button></section>
 <div className="submission-notice"><ShieldCheck size={19}/><div><strong>Human review always matters</strong><p>Mock predictions are not government decisions and must be verified by authorized officers.</p></div></div>{error&&<div className="form-error" role="alert">{error}</div>}
 <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={!analysis||submitting}>{submitting?'Submitting grievance…':<>Submit grievance <Send size={17}/></>}</button><p className="submit-help"><Info size={14}/> Creates a local demo case only. No government APIs are contacted.</p></aside></form></div>;
}
