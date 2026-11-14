import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import {api,post} from '../lib/api';
import type {User} from '../types';
interface Session {user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<{challenge?:string}>;completeMfa:(challenge:string,code:string)=>Promise<void>;logout:()=>Promise<void>;clearSession:()=>void}
const AuthContext=createContext<Session|null>(null);
export function AuthProvider({children}:{children:ReactNode}) {
  const [user,setUser]=useState<User|null>(null);
  const [loading,setLoading]=useState(true);
  useEffect(()=>{api<User>('/api/auth/me').then(setUser).catch(()=>setUser(null)).finally(()=>setLoading(false));},[]);
  useEffect(()=>{const expire=()=>setUser(null);window.addEventListener('nagrikos-session-expired',expire);return()=>window.removeEventListener('nagrikos-session-expired',expire);},[]);
  async function login(email:string,password:string){
    const result=await post<{user?:User;mfa_required?:boolean;challenge?:string}>('/api/auth/login',{email,password});
    if(result.user)setUser(result.user);
    return {challenge:result.mfa_required?result.challenge:undefined};
  }
  async function completeMfa(challenge:string,code:string){
    const result=await post<{user:User}>('/api/auth/mfa/challenge',{challenge,code});
    setUser(result.user);
  }
  async function logout(){
    await post('/api/auth/logout',{});
    setUser(null);
  }
  return <AuthContext.Provider value={{user,loading,login,completeMfa,logout,clearSession:()=>setUser(null)}}>{children}</AuthContext.Provider>;
}
export function useAuth(){const ctx=useContext(AuthContext);if(!ctx)throw Error('Missing auth provider');return ctx;}
