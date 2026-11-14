import type {ReactNode} from 'react';
import {AlertTriangle,ArrowRight,CheckCircle2,Clock3,Inbox,LoaderCircle,ShieldAlert} from 'lucide-react';
import {format,formatDistanceToNowStrict,isValid,parseISO} from 'date-fns';
import type {Priority,Status} from '../types';
export function dateLabel(v:string|null,withTime=false){if(!v)return '—';const d=parseISO(v);return isValid(d)?format(d,withTime?'dd MMM yyyy, h:mm a':'dd MMM yyyy'):'—';}
export function relativeDate(v:string|null){if(!v)return '—';const d=parseISO(v);return isValid(d)?formatDistanceToNowStrict(d,{addSuffix:true}):'—';}
export const statusText:Record<Status,string>={new:'New',in_progress:'In progress',escalated:'Escalated',resolved:'Resolved'};
export const priorityText:Record<Priority,string>={low:'Low',medium:'Medium',high:'High',critical:'Critical'};
export function StatusBadge({status}:{status:Status}){return <span className={`badge status-${status}`}><span className="badge-dot"/>{statusText[status]}</span>}
export function PriorityBadge({priority}:{priority:Priority}){return <span className={`badge priority-${priority}`}>{priority==='critical'?<ShieldAlert size={12}/>:priority==='high'?<AlertTriangle size={12}/>:null}{priorityText[priority]}</span>}
export function Spinner({text='Loading...'}:{text?:string}){return <div className="spinner-wrap"><LoaderCircle className="spin" size={25}/><span>{text}</span></div>}
export function Empty({title='Nothing here yet',text='There are no records matching your selection.',action}:{title?:string;text?:string;action?:ReactNode}){return <div className="empty"><div className="empty-icon"><Inbox size={25}/></div><h3>{title}</h3><p>{text}</p>{action}</div>}
export function ErrorCard({error,retry}:{error:string;retry?:()=>void}){return <div className="error-card"><AlertTriangle size={20}/><div><b>Something went wrong</b><p>{error}</p></div>{retry&&<button className="btn btn-outline btn-sm" onClick={retry}>Retry</button>}</div>}
export function PageHeader({eyebrow,title,description,action}:{eyebrow?:string;title:string;description?:string;action?:ReactNode}){return <div className="page-header"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description&&<p>{description}</p>}</div>{action&&<div className="page-actions">{action}</div>}</div>}
export function StatCard({label,value,foot,icon,accent='teal'}:{label:string;value:string|number;foot?:ReactNode;icon:ReactNode;accent?:'teal'|'amber'|'blue'|'rose'}){return <div className="stat-card"><div className="stat-top"><span>{label}</span><div className={`stat-icon ${accent}`}>{icon}</div></div><div className="stat-value">{value}</div><div className="stat-foot">{foot||<><CheckCircle2 size={13}/> Demonstration data</>}</div></div>}
export function SectionTitle({title,subtitle,action}:{title:string;subtitle?:string;action?:ReactNode}){return <div className="section-title"><div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>}
export function ArrowLink({children,onClick}:{children:ReactNode;onClick:()=>void}){return <button className="inline-link" onClick={onClick}>{children}<ArrowRight size={15}/></button>}
export function DueBadge({date,status}:{date:string;status:Status}){if(status==='resolved')return <span className="subtle"><CheckCircle2 size={13}/>Completed</span>;const late=new Date(date).getTime()<Date.now();return <span className={late?'due late':'due'}><Clock3 size={13}/>{late?'Overdue · ':'Due · '}{dateLabel(date)}</span>}
