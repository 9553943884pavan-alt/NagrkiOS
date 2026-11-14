// Dependency-free account screens. Authentication always uses the FastAPI routes.
const query=new URLSearchParams(location.hash.startsWith('#')?location.hash.slice(1):location.search);
let screen=query.has('verify')?'verify':query.has('reset')?'reset':query.has('invite')?'invite':'login';
let challenge='',config={demo_enabled:false,registration_available:false},configLoaded=false;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function ensureConfig(){if(configLoaded)return;try{const r=await fetch('/api/auth/config',{credentials:'same-origin'});if(r.ok)config=await r.json();}catch{}configLoaded=true;}
function showError(message){const box=document.querySelector('#account-error');if(box){box.textContent=message;box.hidden=false;}}
function showMessage(message){const box=document.querySelector('#account-message');if(box){box.textContent=message;box.hidden=false;}}
function clearLink(){history.replaceState({},'',location.pathname);}
export function showScreen(next){if(['verify','reset','invite'].includes(screen))clearLink();screen=next;challenge='';renderLogin();}
export async function renderLogin(){
 await ensureConfig();
 const app=document.querySelector('#app');if(!app)return;
 if(screen==='pending'){
  app.innerHTML='<div class="login"><div class="login-art"><div class="brand"><span class="brand-icon">∿</span><strong>Nagrik<span>OS</span></strong></div><div class="login-art-main"><h1>Every grievance<br><em>deserves to be heard.</em></h1></div></div><div class="login-panel"><div class="login-box"><span class="eyebrow">ACCOUNT CREATED</span><h2>Check your email</h2><p>Open the verification link before signing in. The link expires in 30 minutes.</p><div class="info" role="status">If this address can be registered, check your email for a verification link.</div><div class="actions"><button class="btn outline" data-auth-screen="login">Back to sign in</button><button class="btn outline" data-auth-screen="signup">Use a different email</button></div></div></div></div>';
  return;
 }
 const title={login:'Enter your workspace',signup:'Create a citizen account',forgot:'Reset your password',reset:'Choose a new password',verify:'Verify your email',invite:'Accept staff invitation',mfa:'Two-step verification'}[screen];
 const email=['login','signup','forgot'].includes(screen)?'<label>Email<input name="email" type="email" required autocomplete="email" maxlength="254"></label>':'';
 const password=['login','signup','reset','invite'].includes(screen)?`<label>Password<input name="password" type="password" required autocomplete="${screen==='login'?'current-password':'new-password'}" ${screen==='login'?'':'minlength="15"'} maxlength="1024"></label><button type="button" data-auth-action="toggle-password" class="btn outline">Show password</button>`:'';
 const confirm=['signup','reset','invite'].includes(screen)?'<label>Confirm password<input name="confirm" type="password" required autocomplete="new-password" minlength="15" maxlength="1024"></label><small>Use at least 15 characters. Paste and password managers are supported.</small>':'';
 const demo=config.demo_enabled&&screen==='login'?`<div class="role-options"><button type="button" data-demo="admin@demo.in">Administrator</button><button type="button" data-demo="officer@demo.in">Desk officer</button><button type="button" data-demo="citizen@demo.in">Citizen</button></div><div class="info">Local demo password: <b>${esc(config.demo_password)}</b></div>`:'';
 app.innerHTML=`<div class="login"><div class="login-art"><div class="brand"><span class="brand-icon">∿</span><strong>Nagrik<span>OS</span></strong></div><div class="login-art-main"><span class="outline-tag">CIVIC INTELLIGENCE PROTOTYPE</span><h1>Every grievance<br/><em>deserves to be heard.</em></h1><p>From citizen voices to action—one public service workspace.</p></div><small>Human-supervised decisions. Synthetic seed records.</small></div><div class="login-panel"><div class="login-box"><span class="eyebrow">WELCOME TO NAGRIKOS</span><h2>${title}</h2><p>${screen==='mfa'?'Enter a current authenticator or recovery code.':screen==='forgot'?'If the account exists, a reset link will be emailed.':screen==='signup'?'Citizen accounts can submit and track their own cases.':'Sign in to continue.'}</p>${demo}<form id="account-form">${screen==='signup'?'<label>Your name<input name="name" required minlength="2" maxlength="100" autocomplete="name"></label>':''}${email}${password}${confirm}${screen==='mfa'?'<label>Authenticator or recovery code<input name="code" required autocomplete="one-time-code" maxlength="40" autofocus></label>':''}<div id="account-error" class="error" role="alert" hidden></div><div id="account-message" class="info" role="status" hidden></div>${(['signup','forgot'].includes(screen)&&!config.registration_available)?'<div class="info warn">Email delivery is unavailable. Registration and recovery are disabled.</div>':''}<button class="btn primary" type="submit" ${(['signup','forgot'].includes(screen)&&!config.registration_available)?'disabled':''}>${{login:'Sign in',signup:'Create account',forgot:'Send reset link',reset:'Change password',verify:'Verify email',invite:'Activate account',mfa:'Verify and sign in'}[screen]}</button></form><div class="actions">${screen==='login'?'<button class="btn outline" data-auth-screen="signup">Create citizen account</button><button class="btn outline" data-auth-screen="forgot">Forgot password?</button>':'<button class="btn outline" data-auth-screen="login">Back to sign in</button>'}</div><small class="login-warning">Independent prototype; seeded cases and AI routing are illustrative.</small></div></div></div>`;
}
export function selectDemo(email){const form=document.querySelector('#account-form');if(form){form.elements.email.value=email;form.elements.password.value=config.demo_password||'';}}
export function togglePassword(){const fields=document.querySelectorAll('#account-form input[type=password],#account-form input[data-visible=true]');fields.forEach(x=>{x.type=x.type==='password'?'text':'password';x.dataset.visible=x.type==='text';});}
async function request(path,body){const csrf=document.cookie.split('; ').find(x=>x.startsWith('nagrikos_csrf='))?.slice(14)||'';let r;try{r=await fetch(path,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf)},body:JSON.stringify(body)});}catch{throw Error('Cannot connect to the service. Check your connection and try again.');}const value=await r.json().catch(()=>({detail:'Request failed'}));if(!r.ok)throw Error(typeof value.detail==='string'?value.detail:'Request failed');return value;}
export async function submitAccount(form){
 const button=form.querySelector('[type=submit]');button.disabled=true;const d=new FormData(form);
 try{
  if(screen==='login'){const r=await request('/api/auth/login',{email:d.get('email'),password:d.get('password')});if(r.mfa_required){challenge=r.challenge;screen='mfa';renderLogin();return null;}return r.user;}
  if(screen==='mfa'){const r=await request('/api/auth/mfa/challenge',{challenge,code:d.get('code')});challenge='';return r.user;}
  if(['signup','reset','invite'].includes(screen)&&d.get('password')!==d.get('confirm'))throw Error('Passwords do not match');
  let r;
  if(screen==='signup')r=await request('/api/auth/signup',{name:d.get('name'),email:d.get('email'),password:d.get('password')});
  if(screen==='forgot')r=await request('/api/auth/forgot-password',{email:d.get('email')});
  if(screen==='reset')r=await request('/api/auth/reset-password',{token:query.get('reset'),new_password:d.get('password')});
  if(screen==='verify')r=await request('/api/auth/verify-email',{token:query.get('verify')});
  if(screen==='invite')r=await request('/api/auth/accept-invitation',{token:query.get('invite'),password:d.get('password')});
  if(screen==='signup'){screen='pending';await renderLogin();return null;}
  if(['reset','verify','invite'].includes(screen)){screen='login';clearLink();await renderLogin();}
  showMessage(r.message);return null;
 }catch(e){showError(e.message);button.disabled=false;return null;}
}
