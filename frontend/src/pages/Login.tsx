import {useEffect,useState} from 'react';
import {Activity,ArrowRight,LockKeyhole,ShieldCheck,Sparkles,Users} from 'lucide-react';
import {useAuth} from '../context/AuthContext';
import {api,post} from '../lib/api';

type Screen='login'|'signup'|'pending'|'forgot'|'reset'|'verify'|'invite'|'mfa';
const params=new URLSearchParams(window.location.hash.startsWith('#')?window.location.hash.slice(1):window.location.search);
const initial:Screen=params.has('verify')?'verify':params.has('reset')?'reset':params.has('invite')?'invite':'login';
const roles=[{label:'Administrator',email:'admin@demo.in'},{label:'Desk officer',email:'officer@demo.in'},{label:'Citizen',email:'citizen@demo.in'}];

export default function Login(){
 const {login,completeMfa}=useAuth();
 const [screen,setScreen]=useState<Screen>(initial),[demo,setDemo]=useState(false),[demoPassword,setDemoPassword]=useState(''),[mailReady,setMailReady]=useState(false);
 const [name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState('');
 const [code,setCode]=useState(''),[challenge,setChallenge]=useState(''),[showPassword,setShowPassword]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{api<{demo_enabled:boolean;demo_password?:string;registration_available:boolean}>('/api/auth/config').then(x=>{setDemo(x.demo_enabled);setDemoPassword(x.demo_password||'');setMailReady(x.registration_available);}).catch(()=>setError('Cannot connect to the account service.'));},[]);
 function go(next:Screen){if(['verify','reset','invite'].includes(screen))window.history.replaceState({},'',window.location.pathname);setScreen(next);setError('');setMessage('');setCode('');setPassword('');setConfirm('');setChallenge('');}
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');setMessage('');
  try{
   if(screen==='login'){const r=await login(email,password);setPassword('');if(r.challenge){setChallenge(r.challenge);setScreen('mfa');}}
   else if(screen==='mfa'){await completeMfa(challenge,code);setChallenge('');setCode('');}
   else if(screen==='signup'){if(password!==confirm)throw Error('Passwords do not match');const r=await post<{message:string}>('/api/auth/signup',{name,email,password});setMessage(r.message);setScreen('pending');setPassword('');setConfirm('');}
   else if(screen==='forgot'){const r=await post<{message:string}>('/api/auth/forgot-password',{email});setMessage(r.message);}
   else if(screen==='reset'){if(password!==confirm)throw Error('Passwords do not match');const r=await post<{message:string}>('/api/auth/reset-password',{token:params.get('reset'),new_password:password});setMessage(r.message);setScreen('login');window.history.replaceState({},'',window.location.pathname);setPassword('');setConfirm('');}
   else if(screen==='verify'){const r=await post<{message:string}>('/api/auth/verify-email',{token:params.get('verify')});setMessage(r.message);setScreen('login');window.history.replaceState({},'',window.location.pathname);}
   else if(screen==='invite'){if(password!==confirm)throw Error('Passwords do not match');const r=await post<{message:string}>('/api/auth/accept-invitation',{token:params.get('invite'),password});setMessage(r.message);setScreen('login');window.history.replaceState({},'',window.location.pathname);setPassword('');setConfirm('');}
  }catch(err){setError(err instanceof Error?err.message:'Request failed. Try again.');}finally{setBusy(false);}
 }
 const passwordInput=(autofill:'current-password'|'new-password')=><div className="auth-password-field"><label htmlFor="auth-password">Password</label><input id="auth-password" type={showPassword?'text':'password'} value={password} onChange={e=>setPassword(e.target.value)} required minLength={autofill==='new-password'?15:undefined} autoComplete={autofill} maxLength={1024}/><button type="button" className="auth-text-button" onClick={()=>setShowPassword(x=>!x)} aria-label={showPassword?'Hide password':'Show password'}>{showPassword?'Hide':'Show'}</button></div>;
 return <div className="login-layout"><div className="login-showcase"><div className="login-pattern"/><div className="showcase-content">
   <div className="login-brand"><div className="brand-mark"><Activity size={24}/></div><strong>Nagrik<span>OS</span></strong></div>
   <div className="showcase-main"><span className="showcase-pill"><Sparkles size={14}/> CIVIC INTELLIGENCE · PROTOTYPE</span><h1>Every grievance<br/><em>deserves to be heard.</em></h1><p>One workspace connecting citizen voices, government desks, and meaningful resolutions.</p></div>
   <div className="showcase-footer"><span><ShieldCheck size={16}/> Built for human-supervised decision making</span><span>AI Kaushal Hackathon Concept</span></div></div></div>
   <div className="login-form-panel"><div className="login-form-wrap"><span className="welcome-eyebrow">WELCOME TO THE WORKSPACE</span>
      <h2>{screen==='signup'?'Create a citizen account':screen==='pending'?'Check your email':screen==='forgot'?'Reset your password':screen==='reset'?'Choose a new password':screen==='verify'?'Verify your email':screen==='invite'?'Accept staff invitation':screen==='mfa'?'Two-step verification':'Sign in to NagrikOS'}</h2>
      <p className="login-intro">{screen==='pending'?'Open the verification link in your email before signing in. The link expires in 30 minutes.':screen==='mfa'?'Enter the current code from your authenticator app or a saved recovery code.':screen==='verify'?'Confirm the email address linked to your account.':screen==='forgot'?'We will send a time-limited link if this address has an account.':screen==='signup'?'Citizen accounts can submit and track their own grievances.':demo&&screen==='login'?'Use your account or choose a local demo identity.':'Access your civic workspace.'}</p>
      {demo&&screen==='login'&&<><div className="demo-picker-heading">LOCAL DEVELOPMENT DEMO</div><div className="role-picker">{roles.map(r=><button type="button" key={r.email} className={`role-choice ${email===r.email?'active':''}`} onClick={()=>{setEmail(r.email);setPassword(demoPassword);setError('');}}><span className="role-choice-icon"><Users size={18}/></span><span><strong>{r.label}</strong><small>{r.email}</small></span><span className="role-radio"/></button>)}</div><div className="demo-credentials"><LockKeyhole size={15}/><span>Local demo password: <strong>{demoPassword}</strong></span></div></>}
      {screen==='pending'?<div className="inline-message" role="status">{message}</div>:<form onSubmit={submit} className="login-fields">
       {screen==='signup'&&<label>Your name<input value={name} onChange={e=>setName(e.target.value)} required minLength={2} maxLength={100} autoComplete="name"/></label>}
       {['login','signup','forgot'].includes(screen)&&<label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={254} autoComplete="email"/></label>}
       {['login','signup','reset','invite'].includes(screen)&&passwordInput(screen==='login'?'current-password':'new-password')}
       {['signup','reset','invite'].includes(screen)&&<><label>Confirm password<input type={showPassword?'text':'password'} value={confirm} onChange={e=>setConfirm(e.target.value)} required minLength={15} maxLength={1024} autoComplete="new-password"/></label><small>Use at least 15 characters. Long passphrases, paste, and password managers work.</small></>}
       {screen==='mfa'&&<label>Authenticator or recovery code<input value={code} onChange={e=>setCode(e.target.value.trim().toUpperCase().slice(0,40))} required autoComplete="one-time-code" inputMode="text" autoFocus/></label>}
       {error&&<div className="form-error" role="alert">{error}</div>}{message&&<div className="inline-message" role="status">{message}</div>}
       {(screen==='signup'||screen==='forgot')&&!mailReady&&<div className="form-error" role="status">Email delivery is unavailable. Registration and recovery are disabled.</div>}
       <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy||((screen==='signup'||screen==='forgot')&&!mailReady)}>{busy?'Please wait…':screen==='login'?'Sign in':screen==='signup'?'Create account':screen==='forgot'?'Send reset link':screen==='reset'?'Change password':screen==='verify'?'Verify email':screen==='invite'?'Activate account':'Verify and sign in'} <ArrowRight size={18}/></button>
      </form>}
      <div className="auth-links">{screen==='login'?<><button onClick={()=>go('signup')}>Create citizen account</button><button onClick={()=>go('forgot')}>Forgot password?</button></>:<><button onClick={()=>go('login')}>{screen==='mfa'?'Cancel and sign in again':'Back to sign in'}</button>{screen==='pending'&&<button onClick={()=>go('signup')}>Use a different email</button>}</>}</div>
      <p className="login-footnote">This is an independent prototype, not an official government portal. Seeded cases and AI triage are illustrative.</p>
   </div></div></div>;
}
