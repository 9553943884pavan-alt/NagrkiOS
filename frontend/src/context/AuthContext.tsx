import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import {api,post} from '../lib/api';
import type {User} from '../types';
interface Session {user:User|null;loading:boolean;login:(email:string,password:string,mfaCode?:string)=>Promise<void>;logout:()=>Promise<void>}
const AuthContext=createContext<Session|null>(null);
export function AuthProvider({children}:{children:ReactNode}) {
  const [user,setUser]=useState<User|null>(null);
  const [loading,setLoading]=useState(true);
  useEffect(()=>{api<User>('/api/auth/me').then(setUser).catch(()=>setUser(null)).finally(()=>setLoading(false));},[]);
  useEffect(()=>{const expire=()=>setUser(null);window.addEventListener('nagrikos-session-expired',expire);return()=>window.removeEventListener('nagrikos-session-expired',expire);},[]);
  async function login(email:string,password:string,mfaCode=''){
    const result=await post<{user:User}>('/api/auth/login',{email,password,mfa_code:mfaCode});
    setUser(result.user);
  }
  async function logout(){
    try{await post('/api/auth/logout',{});}finally{setUser(null);}
  }
  return <AuthContext.Provider value={{user,loading,login,logout}}>{children}</AuthContext.Provider>;
}
export function useAuth(){const ctx=useContext(AuthContext);if(!ctx)throw Error('Missing auth provider');return ctx;}
