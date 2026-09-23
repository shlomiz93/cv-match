const $ = id => document.getElementById(id);
const STORAGE_PROFILE = 'cvmatch.profile.v2';
const STORAGE_PHOTO = 'cvmatch.photo.v2';
let profile = null;
let currentResult = null;

function emptyProfile(){
  return {
    personal:{name_he:'',name_en:'',phone:'',email:'',linkedin:'',website:'',location_he:'',location_en:''},
    summary_facts:[], experience:[], education:[], languages:[], skills:[], certifications:[], questions:[]
  };
}
function lines(v){return String(v||'').split(/\n|,/).map(x=>x.trim()).filter(Boolean)}
function esc(s){return String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]||c));}
function loadLocal(){
  try{profile=JSON.parse(localStorage.getItem(STORAGE_PROFILE)||'null')}catch(e){profile=null}
  if(!profile) profile=emptyProfile();
  normalizeProfileShape();
  renderProfile();
  renderPhoto();
  updateProfileState();
}
function normalizeProfileShape(){
  profile.personal=profile.personal||emptyProfile().personal;
  profile.summary_facts=profile.summary_facts||[];
  profile.experience=profile.experience||[];
  profile.education=profile.education||[];
  profile.languages=profile.languages||[];
  profile.skills=profile.skills||[];
  profile.certifications=profile.certifications||[];
  profile.questions=profile.questions||[];
}
function hasProfile(){
  return !!(profile?.personal?.name_he || profile?.personal?.name_en || profile?.experience?.length || profile?.skills?.length);
}
function saveLocal(showMessage=true){
  readProfileForm();
  sortExperienceClient();
  localStorage.setItem(STORAGE_PROFILE,JSON.stringify(profile));
  renderProfile();
  updateProfileState();
  if(showMessage) toast('הפרופיל נשמר בדפדפן ✓');
}
function toast(msg){
  const old=document.querySelector('.toast'); if(old) old.remove();
  const el=document.createElement('div');el.className='toast';el.textContent=msg;
  el.style.cssText='position:fixed;left:20px;bottom:20px;background:#071a2b;color:#fff;padding:12px 16px;border-radius:10px;z-index:9999;box-shadow:0 8px 25px #0004';document.body.appendChild(el);setTimeout(()=>el.remove(),1800);
}
function updateProfileState(){
  const exists=hasProfile();
  $('profileNotice').classList.toggle('hidden',exists);
  const p=profile.personal||{};
  const name=p.name_he||p.name_en||'ללא שם';
  $('profileMini').innerHTML=exists?`<strong>${esc(name)}</strong><br><span class="muted">${profile.experience.length} פריטי ניסיון · ${profile.skills.length} כישורים</span>`:'<strong>אין עדיין פרופיל</strong>';
  const score=profileCompleteness();
  $('progressBar').style.width=score+'%';
  $('completionText').textContent=score+'% — '+(score<50?'כדאי להוסיף עוד מידע':score<80?'בסיס טוב, אפשר להשלים עוד':'פרופיל חזק ומוכן להתאמות');
}
function profileCompleteness(){
  let s=0,total=8;
  if(profile.personal?.name_he||profile.personal?.name_en)s++;
  if(profile.personal?.phone||profile.personal?.email)s++;
  if(profile.experience?.length)s++;
  if((profile.experience||[]).filter(x=>x.start_date||x.date_text_original).length>=Math.min(2,profile.experience.length))s++;
  if(profile.skills?.length>=3)s++;
  if(profile.languages?.length)s++;
  if(profile.education?.length)s++;
  if(localStorage.getItem(STORAGE_PHOTO))s++;
  return Math.round(100*s/total);
}
function showSection(which){
  const isJob=which==='job';
  $('jobSection').classList.toggle('hidden',!isJob);
  $('profileSection').classList.toggle('hidden',isJob);
  $('jobNav').classList.toggle('active',isJob);$('profileNav').classList.toggle('active',!isJob);
  window.scrollTo({top:0,behavior:'smooth'});
}
$('jobNav').onclick=()=>showSection('job');
$('profileNav').onclick=()=>showSection('profile');
$('startProfileBtn').onclick=()=>{showSection('profile');openImportDialog()};

// Photo, locked locally per browser
function renderPhoto(){
  const src=localStorage.getItem(STORAGE_PHOTO);
  for(const [imgId,phId] of [['profileEditorPhoto','profileEditorPhotoPlaceholder'],['profilePhoto','photoPlaceholder']]){
    const img=$(imgId), ph=$(phId);
    if(src){img.src=src;img.classList.remove('hidden');ph.classList.add('hidden')}else{img.classList.add('hidden');ph.classList.remove('hidden')}
  }
}
async function compressImage(file){
  return new Promise((resolve,reject)=>{
    const img=new Image();const r=new FileReader();
    r.onload=()=>img.src=r.result;r.onerror=reject;
    img.onload=()=>{
      const max=900;let w=img.width,h=img.height;const scale=Math.min(1,max/Math.max(w,h));w=Math.round(w*scale);h=Math.round(h*scale);
      const c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').drawImage(img,0,0,w,h);
      resolve(c.toDataURL('image/jpeg',0.86));
    };r.readAsDataURL(file);
  });
}
$('replacePhotoBtn').onclick=async()=>{
  const f=$('newPhoto').files[0];if(!f){alert('בחר תמונה חדשה קודם');return}
  if(!confirm('להחליף את תמונת הפרופיל הקבועה? התמונה החדשה תשמש מעכשיו בכל קורות החיים בדפדפן הזה.'))return;
  try{const src=await compressImage(f);localStorage.setItem(STORAGE_PHOTO,src);renderPhoto();updateProfileState();toast('התמונה הוחלפה ✓')}catch(e){alert('לא הצלחנו לקרוא את התמונה')}
};

// Profile form
function renderProfile(){
  normalizeProfileShape();const p=profile.personal;
  $('pNameHe').value=p.name_he||'';$('pNameEn').value=p.name_en||'';$('pPhone').value=p.phone||'';$('pEmail').value=p.email||'';
  $('pLinkedin').value=p.linkedin||'';$('pWebsite').value=p.website||'';$('pLocationHe').value=p.location_he||'';$('pLocationEn').value=p.location_en||'';
  $('pSkills').value=(profile.skills||[]).join('\n');$('pCertifications').value=(profile.certifications||[]).join('\n');
  renderExperienceEditor();renderEducationEditor();renderLanguagesEditor();renderProfileQuestions();
}
function readProfileForm(){
  profile.personal={name_he:$('pNameHe').value.trim(),name_en:$('pNameEn').value.trim(),phone:$('pPhone').value.trim(),email:$('pEmail').value.trim(),linkedin:$('pLinkedin').value.trim(),website:$('pWebsite').value.trim(),location_he:$('pLocationHe').value.trim(),location_en:$('pLocationEn').value.trim()};
  profile.skills=lines($('pSkills').value);profile.certifications=lines($('pCertifications').value);
  profile.experience=[...document.querySelectorAll('.experience-item')].map(el=>({
    company:el.querySelector('[data-f=company]').value.trim(),role_he:el.querySelector('[data-f=role_he]').value.trim(),role_en:el.querySelector('[data-f=role_en]').value.trim(),category:el.querySelector('[data-f=category]').value,
    start_date:el.querySelector('[data-f=start_date]').value,end_date:el.querySelector('[data-f=end_date]').value,is_current:el.querySelector('[data-f=is_current]').checked,
    date_text_original:el.querySelector('[data-f=date_text_original]').value.trim(),location:el.querySelector('[data-f=location]').value.trim(),facts:lines(el.querySelector('[data-f=facts]').value)
  })).filter(x=>x.company||x.role_he||x.role_en||x.facts.length);
  profile.education=[...document.querySelectorAll('.education-item')].map(el=>({institution:el.querySelector('[data-f=institution]').value.trim(),program:el.querySelector('[data-f=program]').value.trim(),start_date:el.querySelector('[data-f=start_date]').value,end_date:el.querySelector('[data-f=end_date]').value,details:el.querySelector('[data-f=details]').value.trim()})).filter(x=>x.institution||x.program);
  profile.languages=[...document.querySelectorAll('.language-item')].map(el=>({name:el.querySelector('[data-f=name]').value.trim(),level:el.querySelector('[data-f=level]').value.trim()})).filter(x=>x.name);
}
function sortExperienceClient(){
  const val=d=>/^\d{4}-\d{2}$/.test(d||'')?d:'0000-01';
  profile.experience.sort((a,b)=>{const ac=a.is_current?1:0,bc=b.is_current?1:0;if(ac!==bc)return bc-ac;const ae=a.is_current?'9999-12':val(a.end_date),be=b.is_current?'9999-12':val(b.end_date);return be.localeCompare(ae)||val(b.start_date).localeCompare(val(a.start_date))});
}
function experienceTemplate(e={},i){
  const title=e.company||e.role_he||e.role_en||'ניסיון חדש';
  return `<div class="experience-item" data-i="${i}"><div class="item-top"><div class="item-title">${esc(title)}</div><button class="danger-btn remove-exp" type="button">מחק</button></div>
  <div class="grid3"><div><label>חברה / ארגון</label><input data-f="company" value="${esc(e.company||'')}"></div><div><label>תפקיד בעברית</label><input data-f="role_he" value="${esc(e.role_he||'')}"></div><div><label>סוג</label><select data-f="category"><option value="work">עבודה</option><option value="military">שירות צבאי</option><option value="project">פרויקט</option><option value="volunteer">התנדבות</option><option value="other">אחר</option></select></div></div>
  <div class="grid3"><div><label>Role in English</label><input data-f="role_en" value="${esc(e.role_en||'')}"></div><div><label>מיקום</label><input data-f="location" value="${esc(e.location||'')}"></div><div><label>ניסוח תאריך מקורי</label><input data-f="date_text_original" value="${esc(e.date_text_original||'')}" placeholder="למשל: 2020–2021"></div></div>
  <div class="grid3"><div><label>מתאריך</label><input type="month" data-f="start_date" value="${esc(e.start_date||'')}"></div><div><label>עד תאריך</label><input type="month" data-f="end_date" value="${esc(e.end_date||'')}"></div><div><label>&nbsp;</label><label class="checkline"><input type="checkbox" data-f="is_current" ${e.is_current?'checked':''}> עובד/ת כאן כיום</label></div></div>
  <label>מה עשית שם — עובדה אחת בכל שורה</label><textarea class="facts-area" data-f="facts">${esc((e.facts||[]).join('\n'))}</textarea></div>`;
}
function renderExperienceEditor(){
  $('experienceEditor').innerHTML=(profile.experience||[]).map(experienceTemplate).join('')||'<p class="muted">עדיין לא הוזן ניסיון.</p>';
  document.querySelectorAll('.experience-item').forEach((el,i)=>{el.querySelector('[data-f=category]').value=profile.experience[i]?.category||'work';el.querySelector('.remove-exp').onclick=()=>{readProfileForm();profile.experience.splice(i,1);renderProfile()}})
}
$('addExperienceBtn').onclick=()=>{readProfileForm();profile.experience.unshift({company:'',role_he:'',role_en:'',category:'work',start_date:'',end_date:'',is_current:false,date_text_original:'',location:'',facts:[]});renderProfile()};
function educationTemplate(e={},i){return `<div class="education-item"><div class="item-top"><div class="item-title">${esc(e.program||e.institution||'השכלה חדשה')}</div><button type="button" class="danger-btn remove-edu">מחק</button></div><div class="grid2"><div><label>מוסד</label><input data-f="institution" value="${esc(e.institution||'')}"></div><div><label>לימודים / תעודה</label><input data-f="program" value="${esc(e.program||'')}"></div><div><label>התחלה</label><input type="month" data-f="start_date" value="${esc(e.start_date||'')}"></div><div><label>סיום</label><input type="month" data-f="end_date" value="${esc(e.end_date||'')}"></div></div><label>פרטים</label><input data-f="details" value="${esc(e.details||'')}"></div>`}
function renderEducationEditor(){$('educationEditor').innerHTML=(profile.education||[]).map(educationTemplate).join('')||'<p class="muted">עדיין לא הוזנה השכלה.</p>';document.querySelectorAll('.education-item').forEach((el,i)=>el.querySelector('.remove-edu').onclick=()=>{readProfileForm();profile.education.splice(i,1);renderProfile()})}
$('addEducationBtn').onclick=()=>{readProfileForm();profile.education.push({institution:'',program:'',start_date:'',end_date:'',details:''});renderProfile()};
function languageTemplate(e={},i){return `<div class="language-item"><div class="grid2"><div><label>שפה</label><input data-f="name" value="${esc(e.name||'')}"></div><div><label>רמה</label><input data-f="level" value="${esc(e.level||'')}" placeholder="שפת אם / גבוהה / בסיסית"></div></div><button type="button" class="danger-btn remove-lang">מחק</button></div>`}
function renderLanguagesEditor(){$('languagesEditor').innerHTML=(profile.languages||[]).map(languageTemplate).join('')||'<p class="muted">עדיין לא הוזנו שפות.</p>';document.querySelectorAll('.language-item').forEach((el,i)=>el.querySelector('.remove-lang').onclick=()=>{readProfileForm();profile.languages.splice(i,1);renderProfile()})}
$('addLanguageBtn').onclick=()=>{readProfileForm();profile.languages.push({name:'',level:''});renderProfile()};
function renderProfileQuestions(){const q=profile.questions||[];$('profileQuestionsCard').classList.toggle('hidden',!q.length);$('profileQuestions').innerHTML=q.length?'<ol>'+q.map(x=>`<li>${esc(x)}</li>`).join('')+'</ol>':''}
$('saveProfileBtn').onclick=()=>saveLocal();$('saveProfileBottomBtn').onclick=()=>saveLocal();

// Import / onboarding
function openImportDialog(){
  $('importStatus').textContent='';$('oldCvFile').value='';$('profileFreeText').value='';$('profileSourceUrls').value='';
  $('importDialog').showModal();
}
$('openImportBtn').onclick=openImportDialog;
$('closeImport').onclick=()=>$('importDialog').close();$('cancelImportBtn').onclick=()=>$('importDialog').close();
function setMethod(v){
  document.querySelectorAll('.method-card').forEach(x=>x.classList.toggle('selected',x.dataset.method===v));
  $('methodFile').classList.toggle('hidden',v!=='file');$('methodFree').classList.toggle('hidden',v!=='free');$('methodQuestionnaire').classList.toggle('hidden',v!=='questionnaire');
  $('importProfileBtn').textContent=v==='questionnaire'?'עבור לשאלון':'נתח וסדר לי את הפרופיל';
}
document.querySelectorAll('input[name=method]').forEach(r=>r.onchange=()=>setMethod(r.value));
$('importProfileBtn').onclick=async()=>{
  const method=document.querySelector('input[name=method]:checked').value;
  if(method==='questionnaire'){$('importDialog').close();showSection('profile');return}
  const fd=new FormData();fd.append('current_profile',JSON.stringify(profile));
  if(method==='file'){
    const f=$('oldCvFile').files[0];if(!f){alert('בחר קובץ קורות חיים קודם');return}fd.append('cv_file',f);
  }else{
    const t=$('profileFreeText').value.trim(),u=$('profileSourceUrls').value.trim();if(!t&&!u){alert('כתוב מידע חופשי או הוסף קישור');return}fd.append('free_text',t);fd.append('source_urls',u);
  }
  $('importStatus').textContent='מנתח, מאחד ומסדר לפי תאריכים...';$('importProfileBtn').disabled=true;
  try{
    const r=await fetch('/api/profile/import',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||'שגיאה');
    profile=d.profile;localStorage.setItem(STORAGE_PROFILE,JSON.stringify(profile));renderProfile();updateProfileState();$('importDialog').close();showSection('profile');toast('המידע יובא וסודר ✓');
  }catch(e){$('importStatus').textContent='שגיאה: '+e.message}
  finally{$('importProfileBtn').disabled=false}
};

// Job screenshot
$('dropZone').onclick=()=>$('screenshot').click();
$('screenshot').onchange=()=>previewShot($('screenshot').files[0]);
$('dropZone').ondragover=e=>{e.preventDefault();$('dropZone').style.borderColor='#c79a3b'};
$('dropZone').ondragleave=()=>$('dropZone').style.borderColor='';
$('dropZone').ondrop=e=>{e.preventDefault();$('dropZone').style.borderColor='';const f=e.dataTransfer.files[0];if(f){const dt=new DataTransfer();dt.items.add(f);$('screenshot').files=dt.files;previewShot(f)}};
function previewShot(f){if(!f)return;const r=new FileReader();r.onload=()=>{$('shotPreview').src=r.result;$('shotPreview').style.display='block'};r.readAsDataURL(f)}

async function generate(extraNotes=''){
  saveLocal(false);
  if(!hasProfile()){showSection('profile');$('profileNotice').classList.remove('hidden');return}
  const fd=new FormData();fd.append('profile_json',JSON.stringify(profile));fd.append('job_text',$('jobText').value.trim());fd.append('job_url',$('jobUrl').value.trim());fd.append('language',$('language').value);fd.append('extra_notes',extraNotes);
  const f=$('screenshot').files[0];if(f)fd.append('screenshot',f);
  $('status').textContent='קורא את המשרה ומשווה לפרופיל שלך...';$('generateBtn').disabled=true;
  try{const r=await fetch('/api/generate',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw new Error(d.error||'שגיאה');currentResult=d;renderResult(d);$('status').textContent=d.demo_mode?'מצב הדגמה — צריך לחבר OpenAI API לניתוח מלא.':'מוכן ✓'}catch(e){$('status').textContent='שגיאה: '+e.message}finally{$('generateBtn').disabled=false}
}
$('generateBtn').onclick=()=>generate('');$('regenerateBtn').onclick=()=>generate($('extraNotes').value.trim());
function renderResult(data){
  const he=data.cv.language==='he';document.documentElement.dir=he?'rtl':'ltr';
  const p=profile.personal||{};$('cvName').textContent=he?(p.name_he||p.name_en):(p.name_en||p.name_he);$('cvHeadline').textContent=data.cv.headline;
  const contact=[p.phone,p.email,p.linkedin,p.website,he?p.location_he:p.location_en].filter(Boolean);$('contactBox').innerHTML=contact.map(x=>`<div>${esc(x)}</div>`).join('');
  $('skillsTitle').textContent=he?'כישורים מרכזיים':'Core Skills';$('languagesTitle').textContent=he?'שפות':'Languages';$('targetLabel').textContent=he?'קורות חיים מותאמים למשרה':'Tailored CV';$('experienceTitle').textContent=he?'ניסיון מקצועי':'Professional Experience';$('educationTitle').textContent=he?'השכלה והכשרה':'Education & Training';
  $('targetTitle').textContent=[data.job.title,data.job.company].filter(Boolean).join(' — ');$('summary').textContent=data.cv.summary;
  $('skillsList').innerHTML=data.cv.skills.map(x=>`<li>${esc(x)}</li>`).join('');$('languagesList').innerHTML=data.cv.languages.map(x=>`<li>${esc(x)}</li>`).join('');$('educationList').innerHTML=data.cv.education.map(x=>`<li>${esc(x)}</li>`).join('');$('educationWrap').style.display=data.cv.education.length?'block':'none';
  $('experienceList').innerHTML=data.cv.experience.map(e=>`<div class="exp"><div class="exp-head"><h3>${esc(e.company)}</h3><span class="dates">${esc(e.dates)}</span></div><div class="role">${esc(e.role)}</div><ul>${e.bullets.map(b=>`<li>${esc(b)}</li>`).join('')}</ul></div>`).join('');
  $('coverMessage').textContent=data.cover_message;$('matchPill').textContent=(he?'התאמה לפרופיל: ':'Profile match: ')+data.match.score+'%';
  const gt=he?'פערים/דברים שכדאי לאמת: ':'Gaps / items to verify: ',$g=$('gapBox');$g.innerHTML=`<strong>${gt}</strong> ${data.match.gaps.length?data.match.gaps.map(x=>`<span>• ${esc(x)} </span>`).join(''):(he?'אין פערים מרכזיים שזוהו.':'No major gaps identified.')}`;
  $('resultArea').classList.remove('hidden');if(data.needs_clarification&&data.questions.length){$('questions').innerHTML='<ol>'+data.questions.map(q=>`<li>${esc(q)}</li>`).join('')+'</ol>';$('clarifyCard').classList.remove('hidden')}else $('clarifyCard').classList.add('hidden');
  renderPhoto();setTimeout(()=>$('resultArea').scrollIntoView({behavior:'smooth'}),100);
}
$('printBtn').onclick=()=>window.print();$('copyMessage').onclick=async()=>{await navigator.clipboard.writeText($('coverMessage').textContent);toast('ההודעה הועתקה ✓')};

loadLocal();
