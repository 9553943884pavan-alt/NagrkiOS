// Sessions use short-lived, server-revocable HttpOnly cookies (no bearer token in JS storage).
const BASE = import.meta.env.VITE_API_BASE || '';
function csrfToken(): string {
  const cookie = document.cookie.split('; ').find(c => c.startsWith('nagrikos_csrf='));
  return cookie ? decodeURIComponent(cookie.slice('nagrikos_csrf='.length)) : '';
}
export class ApiError extends Error { constructor(public status:number, message:string){ super(message); this.name='ApiError'; } }
export async function api<T>(path:string, options:RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const method = (options.method || 'GET').toUpperCase();
  if (!['GET','HEAD','OPTIONS'].includes(method) && path !== '/api/auth/login') {
    headers.set('X-CSRF-Token', csrfToken());
  }
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  let response:Response;
  try { response = await fetch(`${BASE}${path}`, {...options,credentials:'same-origin',headers}); }
  catch {throw new ApiError(0,'Cannot connect to the backend. Start FastAPI on port 8000.');}
  if (!response.ok) {
    const payload = await response.json().catch(()=>({detail:response.statusText}));
    const detail = payload.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((x:{msg?:string})=>x.msg).join('; ') : 'Request failed';
    if (response.status === 401 && !['/api/auth/login','/api/auth/me'].includes(path)) window.dispatchEvent(new Event('nagrikos-session-expired'));
    throw new ApiError(response.status,message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export function post<T>(path:string, payload:unknown){return api<T>(path,{method:'POST',body:JSON.stringify(payload)});}
export function patch<T>(path:string, payload:unknown){return api<T>(path,{method:'PATCH',body:JSON.stringify(payload)});}
export async function upload(file:File){const fd=new FormData();fd.append('file',file);return api<{path:string;url:string;description:string;filename:string;size:number}>('/api/attachments',{method:'POST',body:fd});}
export async function fetchBlob(path:string){
  const r = await fetch(`${BASE}${path}`,{credentials:'same-origin'});
  if (!r.ok) {
    if(r.status===401) window.dispatchEvent(new Event('nagrikos-session-expired'));
    const err=await r.json().catch(()=>({detail:'Could not download the attachment or report'}));
    throw new ApiError(r.status,typeof err.detail==='string'?err.detail:'Download denied');
  }
  return r.blob();
}
export async function downloadReport(){
  const blob=await fetchBlob('/api/export/complaints.csv');
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='nagrikos_demo_cases.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
