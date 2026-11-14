import {useEffect,useState,type ReactNode} from 'react';
import {NavLink,useLocation,useNavigate} from 'react-router-dom';
import {Activity,BarChart3,Bell,Building2,ChevronDown,ClipboardList,Command,FilePlus2,Home,LayoutDashboard,LogOut,Menu,Search,Settings2,ShieldCheck,SlidersHorizontal, X} from 'lucide-react';
import {useAuth} from '../context/AuthContext';
import {api} from '../lib/api';

type NavItem = {label:string;path:string;icon:typeof Home};
const officerNav:NavItem[]=[
  {label:'My desk',path:'/',icon:LayoutDashboard},
  {label:'Department queue',path:'/cases',icon:ClipboardList},
];
const adminNav:NavItem[]=[
  {label:'Overview',path:'/',icon:LayoutDashboard},
  {label:'Grievances',path:'/cases',icon:ClipboardList},
  {label:'Intelligence',path:'/insights',icon:BarChart3},
  {label:'Departments',path:'/departments',icon:Building2},
  {label:'New grievance',path:'/new',icon:FilePlus2},
];
const citizenNav:NavItem[]=[
  {label:'My dashboard',path:'/',icon:Home},
  {label:'My grievances',path:'/cases',icon:ClipboardList},
  {label:'Submit grievance',path:'/new',icon:FilePlus2},
];
export default function AppShell({children}:{children:ReactNode}){
 const {user,logout}=useAuth(); const navigate=useNavigate();const location=useLocation();
 const [collapsed,setCollapsed]=useState(false); const [mobileOpen,setMobileOpen]=useState(false);
 const [search,setSearch]=useState('');const [profileOpen,setProfileOpen]=useState(false);
 const [notifsOpen,setNotifsOpen]=useState(false);
 const [demo,setDemo]=useState(false);
 useEffect(()=>{api<{demo_enabled:boolean}>('/api/auth/config').then(x=>setDemo(x.demo_enabled)).catch(()=>{});},[]);
 const nav=user?.role==='admin'?adminNav:user?.role==='officer'?officerNav:citizenNav;
 const current = [...nav,{label:'Settings',path:'/settings',icon:Settings2}].find(n=>n.path===location.pathname);
 const navlink=(item:NavItem)=><NavLink end={item.path==='/'} key={item.path} to={item.path} title={item.label} onClick={()=>setMobileOpen(false)} className={({isActive})=>`side-link ${isActive?'selected':''}`}><item.icon size={19}/><span>{item.label}</span></NavLink>;
 return <div className={`shell ${collapsed?'is-collapsed':''}`}>
   <aside className={`sidebar ${mobileOpen?'mobile-open':''}`}>
     <div className="brand"><div className="brand-mark"><Activity size={23} strokeWidth={2.5}/></div><div className="brand-text"><strong>Nagrik<span>OS</span></strong><small>Civic Intelligence Platform</small></div><button className="sidebar-close" onClick={()=>setMobileOpen(false)} aria-label="Close menu"><X size={19}/></button></div>
     <div className="sidebar-inner">
       <div className="sidebar-label">WORKSPACE</div>
       <nav className="side-nav">{nav.map(navlink)}</nav>
       <div className="sidebar-label" style={{marginTop:30}}>ACCOUNT</div>
       <nav className="side-nav">{navlink({label:'Settings',path:'/settings',icon:Settings2})}</nav>
       <div className="sidebar-bottom">
        <div className="pilot-card"><div className="pilot-icon"><ShieldCheck size={17}/></div><strong>{demo?'Local demo environment':'Prototype workspace'}</strong><p>Example cases are synthetic. AI predictions are simulated, not official decisions.</p><span><span className="online-dot"/> {demo?'Sandbox active':'Account active'}</span></div>
        <button className="sidebar-collapse" onClick={()=>setCollapsed(x=>!x)} title="Collapse navigation"><SlidersHorizontal size={16}/><span>Collapse sidebar</span></button>
       </div>
     </div>
   </aside>
   {mobileOpen&&<button className="mobile-overlay" onClick={()=>setMobileOpen(false)} aria-label="Close menu"/>}
   <div className="main-area"><header className="topbar">
     <div className="topbar-left"><button className="icon-button mobile-menu" onClick={()=>setMobileOpen(true)} aria-label="Open menu"><Menu size={21}/></button><span className="breadcrumb-parent">Workspace</span><span className="breadcrumb-sep">/</span><span className="breadcrumb-current">{current?.label||'Case details'}</span></div>
     <div className="topbar-right">
       <form className="top-search" onSubmit={e=>{e.preventDefault();navigate(`/cases?search=${encodeURIComponent(search)}`);setSearch('');}}><Search size={17}/><input placeholder="Search cases, tickets..." aria-label="Search cases" value={search} onChange={e=>setSearch(e.target.value)}/><kbd>↵</kbd></form>
       {demo&&<span className="top-env"><span className="online-dot"/> DEMO</span>}
       <div className="top-popover-anchor"><button className="icon-button" title="Notifications" onClick={()=>{setNotifsOpen(x=>!x);setProfileOpen(false);}}><Bell size={20}/><span className="notif-indicator"/></button>
         {notifsOpen&&<div className="mini-popover notifications"><strong>Case alerts</strong><p>Open the grievance queue to review urgent cases and unresolved complaints.</p><button className="btn btn-primary btn-sm" onClick={()=>{navigate('/cases?priority=critical');setNotifsOpen(false);}}>View critical cases</button></div>}
       </div>
       <div className="top-popover-anchor"><button className="profile-button" onClick={()=>{setProfileOpen(x=>!x);setNotifsOpen(false);}}><span className="avatar">{user?.name.split(' ').map(s=>s[0]).slice(0,2).join('')}</span><span className="profile-text"><strong>{user?.name}</strong><small>{user?.role==='admin'?'Administrator':user?.role==='officer'?'Desk officer':'Citizen'}</small></span><ChevronDown size={15}/></button>
          {profileOpen&&<div className="mini-popover profile-menu"><div className="profile-menu-heading"><strong>{user?.name}</strong><span>{user?.email}</span></div><button onClick={()=>{navigate('/settings');setProfileOpen(false);}}><Settings2 size={16}/> Settings</button><button onClick={()=>{void logout().catch(e=>window.alert(e instanceof Error?e.message:'Could not revoke session'));setProfileOpen(false);}}><LogOut size={16}/> Sign out</button></div>}
       </div>
     </div>
   </header>
   <div className="disclaimer-bar"><ShieldCheck size={15}/><span><strong>Prototype mode</strong> · All preloaded complaints are synthetic. AI classification, urgency, and ETA are rule-based simulations.</span><button onClick={()=>navigate('/settings')}>Learn more</button></div>
   <main className="page-content">{children}</main>
   <footer className="app-footer"><span><Command size={13}/> NagrikOS © 2026 · Independent civic-tech prototype</span><span>Not affiliated with CM Helpline 1076 or Jansunwai</span></footer>
   </div>
 </div>;
}
