import {useState} from 'react';
import {Activity,ArrowRight,BarChart3,CheckCircle2,ChevronRight,FileText,LockKeyhole,Route,ShieldCheck,Sparkles,Users,Workflow} from 'lucide-react';
import {useAuth} from '../context/AuthContext';
const roles=[
 {label:'Administrator',sub:'Full analytics & oversight',email:'admin@demo.in',icon:BarChart3},
 {label:'Desk officer',sub:'Manage & resolve grievances',email:'officer@demo.in',icon:Route},
 {label:'Citizen',sub:'Submit & track complaints',email:'citizen@demo.in',icon:Users}
];
export default function Login(){
 const {login}=useAuth();const[email,setEmail]=useState('admin@demo.in');const[password,setPassword]=useState('demo123');const[mfaCode,setMfaCode]=useState('');const[busy,setBusy]=useState(false);const[error,setError]=useState('');
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');try{await login(email,password,mfaCode);}catch(err){setError(err instanceof Error?err.message:'Sign in failed');}finally{setBusy(false);}}
 return <div className="login-layout"><div className="login-showcase"><div className="login-pattern"/><div className="showcase-content">
   <div className="login-brand"><div className="brand-mark"><Activity size={24}/></div><strong>Nagrik<span>OS</span></strong></div>
   <div className="showcase-main"><span className="showcase-pill"><Sparkles size={14}/> CIVIC INTELLIGENCE · DEMO</span><h1>Every grievance<br/><em>deserves to be heard.</em></h1><p>One intelligent workspace connecting citizen voices, government desks, and meaningful resolutions.</p>
     <div className="process-visual"><div className="process-step"><span><FileText size={21}/></span><div><b>1. Citizen reports</b><small>Text, voice or photo</small></div><CheckCircle2 size={17}/></div><div className="process-line"/><div className="process-step"><span><Workflow size={21}/></span><div><b>2. AI assists triage</b><small>Category, priority & routing</small></div><CheckCircle2 size={17}/></div><div className="process-line"/><div className="process-step"><span><Route size={21}/></span><div><b>3. Officers take action</b><small>Track, resolve and learn</small></div><ChevronRight size={18}/></div></div>
   </div><div className="showcase-footer"><span><ShieldCheck size={16}/> Built for human-supervised decision making</span><span>AI Kaushal Hackathon Concept</span></div></div></div>
   <div className="login-form-panel"><div className="login-form-wrap"><span className="welcome-eyebrow">WELCOME TO THE WORKSPACE</span><h2>Sign in to NagrikOS</h2><p className="login-intro">Explore the complete civic grievance workflow using a demo account.</p>
      <div className="demo-picker-heading">CHOOSE A DEMO ROLE</div><div className="role-picker">{roles.map(r=><button key={r.email} className={`role-choice ${email===r.email?'active':''}`} onClick={()=>{setEmail(r.email);setPassword('demo123');setMfaCode('');setError('');}}><span className="role-choice-icon"><r.icon size={18}/></span><span><strong>{r.label}</strong><small>{r.sub}</small></span><span className="role-radio"/></button>)}</div>
      <form onSubmit={submit} className="login-fields"><label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><label>Authenticator code (only if enabled)<input inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" maxLength={6} placeholder="6-digit verification code" value={mfaCode} onChange={e=>setMfaCode(e.target.value.replace(/\D/g,'').slice(0,6))}/></label>{error&&<div className="form-error">{error}</div>}<button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy?'Signing in…':<>Enter workspace <ArrowRight size={18}/></>}</button></form>
      <div className="demo-credentials"><LockKeyhole size={15}/><span>Demo password for all roles: <strong>demo123</strong></span></div>
      <p className="login-footnote">This is a standalone offline-friendly prototype, not an official government portal. All seeded cases are fictional.</p>
   </div></div></div>;
}
