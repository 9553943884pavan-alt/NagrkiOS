import {lazy,Suspense} from 'react';
import {Navigate,Route,Routes} from 'react-router-dom';
import {useAuth} from './context/AuthContext';
import AppShell from './components/AppShell';
import {Spinner} from './components/UI';
import Login from './pages/Login';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import NewComplaint from './pages/NewComplaint';
import Departments from './pages/Departments';
import Settings from './pages/Settings';
import CitizenHome from './pages/CitizenHome';
import OfficerHome from './pages/OfficerHome';
const Overview=lazy(()=>import('./pages/Overview'));
const Insights=lazy(()=>import('./pages/Insights'));
export default function App(){
 const {user,loading}=useAuth();
 if(loading)return <div className="full-loader"><Spinner text="Opening NagrikOS…"/></div>;
 if(!user)return <Login/>;
 const admin=user.role==='admin';
 return <AppShell><Suspense fallback={<Spinner text="Opening workspace…"/>}><Routes>
 <Route path="/" element={admin?<Overview/>:user.role==='officer'?<OfficerHome/>:<CitizenHome/>}/>
 <Route path="/cases" element={<Cases/>}/>
 <Route path="/cases/:id" element={<CaseDetail/>}/>
 <Route path="/new" element={user.role==='officer'?<Navigate to="/" replace/>:<NewComplaint/>}/>
 <Route path="/insights" element={admin?<Insights/>:<Navigate to="/" replace/>}/>
 <Route path="/departments" element={admin?<Departments/>:<Navigate to="/" replace/>}/>
 <Route path="/settings" element={<Settings/>}/>
 <Route path="*" element={<Navigate to="/" replace/>}/>
 </Routes></Suspense></AppShell>;
}
