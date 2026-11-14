export type Role = 'citizen' | 'officer' | 'admin';
export type Status = 'new' | 'in_progress' | 'escalated' | 'resolved';
export type Priority = 'low' | 'medium' | 'high' | 'critical';
export type Channel = 'web' | 'voice' | 'photo';
export interface User { id:number; name:string; email:string; role:Role; department:string|null; district:string|null }
export interface DepartmentMeta { name:string; short:string; color:string }
export interface Meta { districts:string[]; departments:DepartmentMeta[]; categories:{name:string;department:string;sla_hours:number}[]; statuses:Status[]; priorities:Priority[]; is_demo:boolean;data_disclaimer:string }
export interface AIResult { category:string;department:string;priority:Priority;urgency_score:number;confidence:number;estimated_hours:number;rationale:string;tags:string[];language:string;requires_human_review:boolean;safety_flags:string[];model_version:string;similar_count:number;similar_cases:{id:number;ticket_no:string;title:string;similarity:number}[] }
export interface Case { id:number; ticket_no:string; title:string;description:string;district:string;category:string;department:string;priority:Priority;urgency_score:number;confidence:number;estimated_hours:number;rationale:string;language:string;tags:string[];status:Status;channel:Channel;citizen_id:number|null;assigned_to:number|null;assigned_name?:string|null;attachment_path:string|null;attachment_description:string|null;created_at:string;updated_at:string;due_at:string;resolved_at:string|null;requires_human_review:boolean }
export interface History {id:number;complaint_id:number;actor_id:number|null;actor_name?:string|null;action:string;details:string;created_at:string}
export interface Note {id:number;body:string;is_public:number;author_name:string;created_at:string}
export interface CaseDetail extends Case {history:History[];notes:Note[]}
export interface PageResult<T> {items:T[];total:number;page:number;page_size:number;pages:number}
export interface Dashboard {stats:{total:number;new_count:number;in_progress:number;escalated:number;resolved:number;urgent_open:number;overdue:number;avg_resolution_hours:number|null;resolution_rate:number;on_time_rate:number};by_category:{name:string;value:number}[];by_department:{name:string;open:number;resolved:number;total:number}[];by_district:{name:string;value:number}[];monthly:{month:string;total:number;urgent:number}[];attention:Case[];activity:(History & {ticket_no:string;title:string})[]}
export interface DepartmentStat {name:string;short:string;total:number;open:number;resolved:number;escalated:number;overdue:number;avg_resolution_hours:number|null;resolution_rate:number}
export interface Insights { clusters:{category:string;district:string;department:string;count:number;open:number;urgent:number}[];category_trends:{category:string;month:string;count:number}[];district_risk:{name:string;open:number;escalated:number;total:number}[];disclaimer:string }
