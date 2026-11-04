export type Choice={value:string;label:string};
export type EventItem={id:string;title:string;category:string;supported_age_groups:string[];supported_formats:string[]};
export type Options={regions:Choice[];grades:number[];duration_minutes:{value:number;label:string}[];formats:Choice[];rooms:Choice[];teacher_preferences:Record<string,Choice[]>};
export type RequestData={event_id:string;region_id:string;grade:number;pupils_count:number;duration_minutes:number;format:string;participants:{teachers_count:number;parents_enabled:boolean;parents_count:number;parent_roles:string[]};resources:{projector:boolean;printer:boolean;internet:boolean;audio:boolean;room:string;available_materials:string[]};teacher_preferences:{style:string;script_detail:string;difficulty:string;interaction_level:string;group_work:boolean;preparation_effort:string;notes:string|null};generation:{variants_count:number;language:'ru'}};
export type TimelineBlock={block_id:string;start_minute:number;duration_minutes:number;title:string;purpose?:string;teacher_script?:string;pupil_actions?:string[];material_ids?:string[]};
export type Variant={variant_id:string;title:string;concept?:{summary?:string;goal?:string;tasks?:string[];expected_outcomes?:string[]};roles?:{role_id:string;title:string;count:number}[];timeline?:TimelineBlock[];materials?:{material_id:string;title:string;type?:string;content?:string;used_in_blocks?:string[]}[];teacher_instructions?:string[];quality_report?:{status:string;issues?:{code:string;severity:string;message:string}[]}};
export type GenerationIssue={code?:string;message?:string;field?:string;variant_id?:string};
export type GenerationWarning=string|{code?:string;message?:string;field?:string};
export type Project={schema_version:string;project_id:string;status:string;variants:Variant[];generation_issues?:GenerationIssue[];generation_warnings?:GenerationWarning[];variant_statuses?:{variant_id:string;status:string}[]};
const apiBase=(import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'');
async function getJson<T>(path:string,init?:RequestInit):Promise<T>{
 const url=path.startsWith('http')?path:`${apiBase}${path}`;
 let r:Response;try{r=await fetch(url,{...init,headers:{'Content-Type':'application/json',...init?.headers}})}catch{throw new Error('╨Э╨╡╤В ╤Б╨╛╨╡╨┤╨╕╨╜╨╡╨╜╨╕╤П ╤Б ╤Б╨╡╤А╨▓╨╡╤А╨╛╨╝. ╨Я╤А╨╛╨▓╨╡╤А╤М╤В╨╡, ╤З╤В╨╛ ╨▒╤Н╨║╨╡╨╜╨┤ ╨╖╨░╨┐╤Г╤Й╨╡╨╜ ╨╜╨░ '+apiBase)}
 const data=await r.json().catch(()=>({}));
 if(!r.ok){const err=data?.error||data?.detail;let message=typeof err==='string'?err:err?.message||`╨Ю╤И╨╕╨▒╨║╨░ ╤Б╨╡╤А╨▓╨╡╤А╨░ (${r.status})`;if(Array.isArray(err))message=err.map((x:{msg?:string})=>x.msg||'╨Ю╤И╨╕╨▒╨║╨░ ╨┐╤А╨╛╨▓╨╡╤А╨║╨╕').join('; ');throw new Error(message)}
 return data as T;
}
export async function loadCatalog(){return Promise.all([getJson<EventItem[]>('/api/v1/catalog/events'),getJson<Options>('/api/v1/catalog/options')]);}

export type ActiveGeneration = {
  jobId: string;
  projectId: string;
  statusUrl: string;
  projectUrl: string;
  startedAt: number;
};

export async function startProject(request: RequestData): Promise<ActiveGeneration> {
  const started = await getJson<{
    job_id: string;
    project_id: string;
    status_url?: string;
    project_url?: string;
  }>('/api/v1/generations', {
    method: 'POST',
    body: JSON.stringify(request),
  });

  return {
    jobId: started.job_id,
    projectId: started.project_id,
    statusUrl: started.status_url || `/api/v1/generations/${started.job_id}`,
    projectUrl: started.project_url || `/api/v1/projects/${started.project_id}`,
    startedAt: Date.now(),
  };
}

export async function waitForProject(
  started: ActiveGeneration,
  onStatus: (status: string) => void,
  signal?: AbortSignal,
): Promise<Project> {
  const deadline = started.startedAt + 15 * 60 * 1000;

  while (true) {
    const state = await getJson<{
      status: string;
      completed_variants?: number;
      errors?: GenerationIssue[];
      warnings?: GenerationWarning[];
      variants?: { variant_id: string; status: string }[];
    }>(started.statusUrl, { signal });

    onStatus(state.status);

    if (
      state.status === 'completed' ||
      (state.status === 'partial' && (state.completed_variants ?? 0) > 0)
    ) {
      const result = await getJson<Project>(started.projectUrl, { signal });

      return {
        ...result,
        generation_issues: state.errors || [],
        generation_warnings: state.warnings || [],
        variant_statuses: state.variants || [],
        status: state.status,
      };
    }

    if (state.status === 'failed' || state.status === 'partial') {
      const reasons = (state.errors || [])
        .map(error => error.message || error.code)
        .filter(Boolean);

      throw new Error(
        reasons.length
          ? reasons.join('; ')
          : `╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╜╨╡ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜╨░ (${state.status}). ╨б╨╡╤А╨▓╨╕╤Б ╨╜╨╡ ╨┐╨╡╤А╨╡╨┤╨░╨╗ ╨┐╨╛╨┤╤А╨╛╨▒╨╜╤Г╤О ╨┐╤А╨╕╤З╨╕╨╜╤Г. ╨Ч╨░╨┤╨░╨╜╨╕╨╡: ${started.jobId}`
      );
    }

    if (Date.now() >= deadline) {
  break;
}

    await new Promise<void>((resolve, reject) => {
  if (signal?.aborted) {
    reject(new DOMException('╨Ю╨╢╨╕╨┤╨░╨╜╨╕╨╡ ╨╛╤В╨╝╨╡╨╜╨╡╨╜╨╛', 'AbortError'));
    return;
  }

  const timer = setTimeout(() => {
    signal?.removeEventListener('abort', onAbort);
    resolve();
  }, 1200);

  function onAbort() {
    clearTimeout(timer);
    reject(new DOMException('╨Ю╨╢╨╕╨┤╨░╨╜╨╕╨╡ ╨╛╤В╨╝╨╡╨╜╨╡╨╜╨╛', 'AbortError'));
  }

  signal?.addEventListener('abort', onAbort, { once: true });
});
  }

  throw new Error(
    `╨Я╤А╨╡╨▓╤Л╤И╨╡╨╜╨╛ ╨▓╤А╨╡╨╝╤П ╨╛╨╢╨╕╨┤╨░╨╜╨╕╤П ╨│╨╡╨╜╨╡╤А╨░╤Ж╨╕╨╕. ╨Ч╨░╨┤╨░╨╜╨╕╨╡: ${started.jobId}. ╨У╨╡╨╜╨╡╤А╨░╤Ж╨╕╤П ╨╝╨╛╨│╨╗╨░ ╨┐╤А╨╛╨┤╨╛╨╗╨╢╨╕╤В╤М╤Б╤П ╨╜╨░ ╤Б╨╡╤А╨▓╨╡╤А╨╡.`
  );
}
export async function createProject(
  request: RequestData,
  onStatus: (status: string) => void,
): Promise<Project> {
  const started = await startProject(request);
  return waitForProject(started, onStatus);
}

export const DEMO_EVENTS:EventItem[]=[{id:'knowledge_day',title:'╨Ф╨╡╨╜╤М ╨╖╨╜╨░╨╜╨╕╨╣',category:'╨Я╤А╨░╨╖╨┤╨╜╨╕╨║╨╕',supported_age_groups:['1-4','5-8','9-11'],supported_formats:['class_hour','school_event','interactive_lesson']},{id:'teacher_day',title:'╨Ф╨╡╨╜╤М ╤Г╤З╨╕╤В╨╡╨╗╤П',category:'╨и╨║╨╛╨╗╤М╨╜╤Л╨╡ ╨┐╤А╨░╨╖╨┤╨╜╨╕╨║╨╕',supported_age_groups:['1-4','5-8','9-11'],supported_formats:['class_hour','school_event']}];
export const DEMO_OPTIONS:Options={regions:[{value:'RU-SVE',label:'╨б╨▓╨╡╤А╨┤╨╗╨╛╨▓╤Б╨║╨░╤П ╨╛╨▒╨╗╨░╤Б╤В╤М'}],grades:Array.from({length:11},(_,i)=>i+1),duration_minutes:[30,45,60,90].map(v=>({value:v,label:`${v} ╨╝╨╕╨╜╤Г╤В`})),formats:[{value:'class_hour',label:'╨Ъ╨╗╨░╤Б╤Б╨╜╤Л╨╣ ╤З╨░╤Б'},{value:'school_event',label:'╨Ю╨▒╤Й╨╡╤И╨║╨╛╨╗╤М╨╜╨╛╨╡ ╨╝╨╡╤А╨╛╨┐╤А╨╕╤П╤В╨╕╨╡'},{value:'interactive_lesson',label:'╨Ш╨╜╤В╨╡╤А╨░╨║╤В╨╕╨▓╨╜╨╛╨╡ ╨╖╨░╨╜╤П╤В╨╕╨╡'}],rooms:[{value:'classroom',label:'╨Ъ╨╗╨░╤Б╤Б'},{value:'assembly_hall',label:'╨Р╨║╤В╨╛╨▓╤Л╨╣ ╨╖╨░╨╗'},{value:'gym',label:'╨б╨┐╨╛╤А╤В╨╖╨░╨╗'},{value:'other',label:'╨Ф╤А╤Г╨│╨╛╨╡'}],teacher_preferences:{style:[{value:'classic',label:'╨Ъ╨╗╨░╤Б╤Б╨╕╤З╨╡╤Б╨║╨╕╨╣'},{value:'interactive',label:'╨Ш╨╜╤В╨╡╤А╨░╨║╤В╨╕╨▓╨╜╤Л╨╣'},{value:'creative',label:'╨в╨▓╨╛╤А╤З╨╡╤Б╨║╨╕╨╣'},{value:'research',label:'╨Ш╤Б╤Б╨╗╨╡╨┤╨╛╨▓╨░╤В╨╡╨╗╤М╤Б╨║╨╕╨╣'}],script_detail:[{value:'brief',label:'╨Ъ╤А╨░╤В╨║╨░╤П'},{value:'standard',label:'╨б╤В╨░╨╜╨┤╨░╤А╤В╨╜╨░╤П'},{value:'detailed',label:'╨Я╨╛╨┤╤А╨╛╨▒╨╜╨░╤П'}]}};
export function makeDemoProject(input:RequestData,events:EventItem[]):Project{
 const event=events.find(e=>e.id===input.event_id)?.title||'╨и╨║╨╛╨╗╤М╨╜╨╛╨╡ ╨╝╨╡╤А╨╛╨┐╤А╨╕╤П╤В╨╕╨╡';
 const motifs=[['╨в╨░╨╣╨╜╨░ ╨╝╨░╨╗╨╡╨╜╤М╨║╨╕╤Е ╨╛╤В╨║╤А╤Л╤В╨╕╨╣','╨Т╨┤╨╛╤Е╨╜╨╛╨▓╨╕╤В╤М ╤Г╤З╨╡╨╜╨╕╨║╨╛╨▓ ╨╜╨░ ╤Б╨╛╨▓╨╝╨╡╤Б╤В╨╜╤Л╨╡ ╨╛╤В╨║╤А╤Л╤В╨╕╤П','╨Ъ╨╛╨╝╨░╨╜╨┤╨╜╨░╤П ╨╕╨│╤А╨░ ╨╕ ╨┐╨╛╨╕╤Б╨║ ╨╜╨╡╨╛╨▒╤Л╤З╨╜╤Л╤Е ╤А╨╡╤И╨╡╨╜╨╕╨╣'],['╨б╨╛╨╖╨▓╨╡╨╖╨┤╨╕╨╡ ╨╕╨┤╨╡╨╣','╨а╨░╨╖╨▓╨╕╤В╤М ╤В╨▓╨╛╤А╤З╨╡╤Б╨║╨╛╨╡ ╨╝╤Л╤И╨╗╨╡╨╜╨╕╨╡ ╨╕ ╨▓╨╖╨░╨╕╨╝╨╛╨┐╨╛╨╝╨╛╤Й╤М','╨Ь╨░╤Б╤В╨╡╤А╤Б╨║╨░╤П ╨╕╨┤╨╡╨╣ ╨╕ ╤В╨▓╨╛╤А╤З╨╡╤Б╨║╨╛╨╡ ╨╖╨░╨┤╨░╨╜╨╕╨╡'],['╨Я╤Г╤В╤М ╨║ ╤Г╤Б╨┐╨╡╤Е╤Г','╨б╤Д╨╛╤А╨╝╨╕╤А╨╛╨▓╨░╤В╤М ╨╝╨╛╤В╨╕╨▓╨░╤Ж╨╕╤О ╨╕ ╤З╤Г╨▓╤Б╤В╨▓╨╛ ╨║╨╛╨╝╨░╨╜╨┤╤Л','╨Ъ╨▓╨╕╨╖ ╨╕ ╨╛╨▒╤Б╤Г╨╢╨┤╨╡╨╜╨╕╨╡ ╨┐╨╗╨░╨╜╨╛╨▓']];
 return {schema_version:'demo',project_id:'demo-local',status:'completed',variants:Array.from({length:input.generation.variants_count},(_,i)=>{const [name,goal,activity]=motifs[i];const middle=input.duration_minutes-10;return {variant_id:`v${i+1}`,title:`${event} тАФ ${name} (╨┤╨╡╨╝╨╛)`,concept:{summary:`╨Я╤А╨╛╨▒╨╜╤Л╨╣ ╤Б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ┬л${name}┬╗ ╨┤╨╗╤П ${input.grade} ╨║╨╗╨░╤Б╤Б╨░.`,goal,tasks:[activity],expected_outcomes:['╨Ф╨╡╤В╨╕ ╤Б╨╝╨╛╨│╤Г╤В ╨┐╨╛╨┤╨╡╨╗╨╕╤В╤М╤Б╤П ╨▓╨┐╨╡╤З╨░╤В╨╗╨╡╨╜╨╕╤П╨╝╨╕ ╨╕ ╤А╨░╨▒╨╛╤В╨░╤В╤М ╨▓ ╨║╨╛╨╝╨░╨╜╨┤╨╡.']},roles:[{role_id:'teacher',title:'╨Я╨╡╨┤╨░╨│╨╛╨│',count:input.participants.teachers_count},{role_id:'students',title:'╨г╤З╨╡╨╜╨╕╨║╨╕',count:input.pupils_count}],timeline:[{block_id:'block_01',start_minute:0,duration_minutes:5,title:'╨Т╨╛╨╗╤И╨╡╨▒╨╜╨╛╨╡ ╨┐╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╨╕╨╡',purpose:'╨Э╨░╤Б╤В╤А╨╛╨╕╤В╤М ╤Г╤З╨░╤Б╤В╨╜╨╕╨║╨╛╨▓ ╨╜╨░ ╤Б╨╛╨▓╨╝╨╡╤Б╤В╨╜╤Г╤О ╤А╨░╨▒╨╛╤В╤Г',teacher_script:'╨Я╤А╨╕╨▓╨╡╤В╤Б╤В╨▓╤Г╨╣╤В╨╡ ╤Г╤З╨╡╨╜╨╕╨║╨╛╨▓. ╨Я╤А╨╡╨┤╨╗╨╛╨╢╨╕╤В╨╡ ╨║╨░╨╢╨┤╨╛╨╝╤Г ╨╜╨░╨╖╨▓╨░╤В╤М ╨╛╨┤╨╜╨╛ ╤Б╨╗╨╛╨▓╨╛, ╨║╨╛╤В╨╛╤А╨╛╨╡ ╨░╤Б╤Б╨╛╤Ж╨╕╨╕╤А╤Г╨╡╤В╤Б╤П ╤Б ╨╜╨╛╨▓╤Л╨╝ ╤Г╤З╨╡╨▒╨╜╤Л╨╝ ╨│╨╛╨┤╨╛╨╝.',pupil_actions:['╨Я╤А╨╡╨┤╤Б╤В╨░╨▓╨╗╤П╤О╤В╤Б╤П ╨╕ ╨┤╨╡╨╗╤П╤В╤Б╤П ╨╛╨╢╨╕╨┤╨░╨╜╨╕╤П╨╝╨╕.'],material_ids:[]},{block_id:'block_02',start_minute:5,duration_minutes:middle,title:activity,purpose:goal,teacher_script:'╨а╨░╨╖╨┤╨╡╨╗╨╕╤В╨╡ ╨║╨╗╨░╤Б╤Б ╨╜╨░ ╨╜╨╡╨▒╨╛╨╗╤М╤И╨╕╨╡ ╨│╤А╤Г╨┐╨┐╤Л. ╨Ю╨▒╤К╤П╤Б╨╜╨╕╤В╨╡ ╨╖╨░╨┤╨░╨╜╨╕╨╡, ╤А╨░╤Б╨┐╤А╨╡╨┤╨╡╨╗╨╕╤В╨╡ ╨╝╨░╤В╨╡╤А╨╕╨░╨╗╤Л ╨╕ ╨┐╨╛╨╝╨╛╨│╨░╨╣╤В╨╡ ╤Г╤З╨░╤Б╤В╨╜╨╕╨║╨░╨╝.',pupil_actions:['╨Ю╨▒╤Б╤Г╨╢╨┤╨░╤О╤В ╨╕╨┤╨╡╨╕','╨б╨╛╨▓╨╝╨╡╤Б╤В╨╜╨╛ ╨┐╤А╨╡╨┤╤Б╤В╨░╨▓╨╗╤П╤О╤В ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В'],material_ids:['m1']},{block_id:'block_03',start_minute:5+middle,duration_minutes:5,title:'╨д╨╕╨╜╨░╨╗╤М╨╜╨╛╨╡ ╤Б╨╛╨╖╨▓╨╡╨╖╨┤╨╕╨╡',purpose:'╨Ч╨░╨║╤А╨╡╨┐╨╕╤В╤М ╨▓╨┐╨╡╤З╨░╤В╨╗╨╡╨╜╨╕╤П',teacher_script:'╨Я╤А╨╡╨┤╨╗╨╛╨╢╨╕╤В╨╡ ╨║╨░╨╢╨┤╨╛╨╝╤Г ╤Г╤З╨░╤Б╤В╨╜╨╕╨║╤Г ╨┐╨╛╨┤╨╡╨╗╨╕╤В╤М╤Б╤П ╤Б╨░╨╝╤Л╨╝ ╨╕╨╜╤В╨╡╤А╨╡╤Б╨╜╤Л╨╝ ╨╛╤В╨║╤А╤Л╤В╨╕╨╡╨╝ ╤Б╨╡╨│╨╛╨┤╨╜╤П╤И╨╜╨╡╨│╨╛ ╨┤╨╜╤П.',pupil_actions:['╨Я╨╛╨┤╨▓╨╛╨┤╤П╤В ╨╕╤В╨╛╨│╨╕ ╨╕ ╨╛╨▒╨╝╨╡╨╜╨╕╨▓╨░╤О╤В╤Б╤П ╨▓╨┐╨╡╤З╨░╤В╨╗╨╡╨╜╨╕╤П╨╝╨╕.'],material_ids:[]}],materials:[{material_id:'m1',type:'handout',title:'╨Ъ╨░╤А╤В╨╛╤З╨║╨╕ ╤В╨▓╨╛╤А╤З╨╡╤Б╨║╨╛╨│╨╛ ╨╖╨░╨┤╨░╨╜╨╕╤П',content:'╨Я╨╛╨┤╨│╨╛╤В╨╛╨▓╤М╤В╨╡ ╨▒╤Г╨╝╨░╨│╤Г ╨╕ ╤Ж╨▓╨╡╤В╨╜╤Л╨╡ ╨║╨░╤А╨░╨╜╨┤╨░╤И╨╕ ╨┤╨╗╤П ╨║╨░╨╢╨┤╨╛╨╣ ╨║╨╛╨╝╨░╨╜╨┤╤Л.',used_in_blocks:['block_02']}],teacher_instructions:['╨Ч╨░╤А╨░╨╜╨╡╨╡ ╨┐╨╛╨┤╨│╨╛╤В╨╛╨▓╤М╤В╨╡ ╨╜╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╤Л╨╡ ╨╝╨░╤В╨╡╤А╨╕╨░╨╗╤Л.','╨Я╤А╨╕ ╨╜╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╨╛╤Б╤В╨╕ ╨░╨┤╨░╨┐╤В╨╕╤А╤Г╨╣╤В╨╡ ╨╖╨░╨┤╨░╨╜╨╕╤П ╨║ ╨▓╨╛╨╖╤А╨░╤Б╤В╤Г ╤Г╤З╨░╤Б╤В╨╜╨╕╨║╨╛╨▓.'],quality_report:{status:'warning',issues:[{code:'DEMO',severity:'warning',message:'╨н╤В╨╛ ╨┤╨╡╨╝╨╛╨╜╤Б╤В╤А╨░╤Ж╨╕╨╛╨╜╨╜╤Л╨╣ ╤Б╤Ж╨╡╨╜╨░╤А╨╕╨╣. ╨Ю╨╜ ╤Б╨╛╨╖╨┤╨░╨╜ ╨╗╨╛╨║╨░╨╗╤М╨╜╨╛ ╨╕ ╨╜╨╡ ╤П╨▓╨╗╤П╨╡╤В╤Б╤П ╨╛╤В╨▓╨╡╤В╨╛╨╝ ╤Б╨╡╤А╨▓╨╡╤А╨░ ╨╕╨╗╨╕ LLM.'}]}};})};
}
