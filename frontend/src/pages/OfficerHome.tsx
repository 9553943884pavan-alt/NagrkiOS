import {useEffect,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {ArrowRight,CheckCircle2,Clock3,Inbox,ShieldAlert,Users} from 'lucide-react';
import {api} from '../lib/api';
import {useAuth} from '../context/AuthContext';
import {ErrorCard,PageHeader,PriorityBadge,SectionTitle,Spinner,StatCard,StatusBadge} from '../components/UI';
import type {Case} from '../types';
interface OfficerData {
 department:string;
 stats:{total:number;new_count:number;in_progress:number;escalated:number;resolved:number;urgent_open:number;overdue:number;resolution_rate:number};
 my_cases:Case[]; queue:Case[];monthly:{month:string;total:number}[];
}
export default function OfficerHome(){
 const {user}=useAuth();const nav=useNavigate();const[data,setData]=useState<OfficerData|null>(null);const[error,setError]=useState('');
 const load=()=>{api<OfficerData>('/api/officer/overview').then(setData).catch(e=>setError(e.message));};
 useEffect(load,[]);
 if(error)return <ErrorCard error={error} retry={load}/>;
 if(!data)return <Spinner text="Loading your department desk…"/>;
 return <div className="page-stack">
   <PageHeader eyebrow="DEPARTMENT OFFICER WORKSPACE" title={`Welcome, ${user?.name.split(' ')[0]}`} description={`Your ${data.department} case queue, assignments, and resolution progress.`}
      action={<button className="btn btn-primary" onClick={()=>nav('/cases')}>Open department queue <ArrowRight size={16}/></button>}/>
   <div className="insight-banner"><div className="insight-banner-icon"><Users size={24}/></div><div><strong>{data.department}</strong><p>Only cases routed to your department are visible here. Cross-department routing requires an administrator.</p></div><span className="demo-tag">OFFICER VIEW</span></div>
   <div className="stats-grid four">
     <StatCard label="Department cases" value={data.stats.total} icon={<Inbox size={21}/>} foot="Cases under your department"/>
     <StatCard label="Awaiting triage" value={data.stats.new_count||0} icon={<Clock3 size={21}/>} accent="blue" foot="New and unprocessed"/>
     <StatCard label="Urgent & open" value={data.stats.urgent_open||0} icon={<ShieldAlert size={21}/>} accent="rose" foot="High or critical urgency"/>
     <StatCard label="Resolved" value={`${data.stats.resolution_rate}%`} icon={<CheckCircle2 size={21}/>} accent="amber" foot="Department resolution rate"/>
   </div>
   <div className="overview-chart-grid lower-grid">
     <section className="panel"><SectionTitle title="Assigned to me" subtitle="Open cases with you as the current owner"/>
       {data.my_cases.length===0?<p className="muted">No active cases assigned to you yet.</p>:<div className="attention-list">{data.my_cases.map(c=><button key={c.id} className="attention-row" onClick={()=>nav(`/cases/${c.id}`)}><span className="attention-main"><b>{c.title}</b><small>{c.ticket_no} · {c.district}</small></span><StatusBadge status={c.status}/><ArrowRight size={15}/></button>)}</div>}
     </section>
     <section className="panel"><SectionTitle title="Department priority queue" subtitle="Highest-priority unresolved complaints"/>
       {data.queue.length===0?<p className="muted">All departmental cases are resolved.</p>:<div className="attention-list">{data.queue.map(c=><button key={c.id} className="attention-row" onClick={()=>nav(`/cases/${c.id}`)}><span className="attention-main"><b>{c.title}</b><small>{c.ticket_no} · {c.district}</small></span><PriorityBadge priority={c.priority}/><ArrowRight size={15}/></button>)}</div>}
     </section>
   </div>
 </div>;
}
