let lastPayload = null;
let profile = null;
const $ = (id) => document.getElementById(id);

async function loadProfile(){
  const r = await fetch('/api/profile');
  profile = await r.json();
  $('profileJson').value = JSON.stringify(profile,null,2);
}

$('dropZone').onclick = () => $('screenshot').click();
$('screenshot').addEventListener('change', () => {
  const f = $('screenshot').files[0];
  if(!f) return;
  $('shotPreview').src = URL.createObjectURL(f);
  $('shotPreview').style.display = 'block';
});
['dragenter','dragover'].forEach(ev => $('dropZone').addEventListener(ev,e=>{e.preventDefault();$('dropZone').style.borderColor='#c79a3b'}));
['dragleave','drop'].forEach(ev => $('dropZone').addEventListener(ev,e=>{e.preventDefault();$('dropZone').style.borderColor=''}));
$('dropZone').addEventListener('drop',e=>{const f=e.dataTransfer.files[0];if(f){const dt=new DataTransfer();dt.items.add(f);$('screenshot').files=dt.files;$('shotPreview').src=URL.createObjectURL(f);$('shotPreview').style.display='block'}});

async function generate(extra=''){
  $('status').textContent='קורא את המשרה ומתאים את הקורות חיים...';
  $('generateBtn').disabled = true;
  const fd = new FormData();
  fd.append('job_url',$('jobUrl').value.trim());
  fd.append('job_text',$('jobText').value.trim());
  fd.append('language',$('language').value);
  fd.append('extra_notes',extra);
  const shot=$('screenshot').files[0]; if(shot) fd.append('screenshot',shot);
  const r = await fetch('/api/generate',{method:'POST',body:fd});
  const data = await r.json();
  $('generateBtn').disabled = false;
  if(!r.ok){$('status').textContent=data.error||'אירעה שגיאה';return;}
  lastPayload = data;
  $('status').textContent = data.demo_mode ? 'מצב הדגמה: הוסף OPENAI_API_KEY לקבלת ניתוח AI מלא.' : 'מוכן.';
  renderResult(data);
}

function renderResult(data){
  const lang=data.cv.language;
  const he=lang==='he';
  document.documentElement.dir=he?'rtl':'ltr';
  document.documentElement.lang=lang;
  $('cvPage').dir=he?'rtl':'ltr';
  $('cvName').textContent=he?(profile.name_he||profile.name_en):(profile.name_en||profile.name_he);
  $('cvHeadline').textContent=data.cv.headline;
  $('contactBox').innerHTML=[profile.phone,profile.email,profile.linkedin,he?profile.location_he:profile.location_en].filter(Boolean).map(x=>`<div>${escapeHtml(x)}</div>`).join('');
  $('skillsTitle').textContent=he?'כישורים מרכזיים':'Core Skills';
  $('languagesTitle').textContent=he?'שפות':'Languages';
  $('experienceTitle').textContent=he?'ניסיון מקצועי':'Professional Experience';
  $('educationTitle').textContent=he?'השכלה והכשרה':'Education & Training';
  $('targetLabel').textContent=he?'קורות חיים מותאמים למשרה':'Tailored CV';
  $('targetTitle').textContent=[data.job.title,data.job.company].filter(Boolean).join(' — ');
  $('summary').textContent=data.cv.summary;
  $('skillsList').innerHTML=data.cv.skills.map(x=>`<li>${escapeHtml(x)}</li>`).join('');
  $('languagesList').innerHTML=data.cv.languages.map(x=>`<li>${escapeHtml(x)}</li>`).join('');
  $('educationList').innerHTML=data.cv.education.map(x=>`<li>${escapeHtml(x)}</li>`).join('');
  $('educationWrap').style.display=data.cv.education.length?'block':'none';
  $('experienceList').innerHTML=data.cv.experience.map(e=>`<div class="exp"><div class="exp-head"><h3>${escapeHtml(e.company)}</h3><span class="dates">${escapeHtml(e.dates)}</span></div><div class="role">${escapeHtml(e.role)}</div><ul>${e.bullets.map(b=>`<li>${escapeHtml(b)}</li>`).join('')}</ul></div>`).join('');
  $('coverMessage').textContent=data.cover_message;
  $('matchPill').textContent=(he?'התאמה לפרופיל: ':'Profile match: ')+data.match.score+'%';
  const gapTitle=he?'פערים/דברים שכדאי לאמת: ':'Gaps / items to verify: ';
  $('gapBox').innerHTML=`<strong>${gapTitle}</strong>${data.match.gaps.length?data.match.gaps.map(x=>`<span> • ${escapeHtml(x)}</span>`).join(''):(he?'אין פערים מרכזיים שזוהו.':'No major gaps identified.')}`;
  $('resultArea').classList.remove('hidden');
  if(data.needs_clarification && data.questions.length){
    $('questions').innerHTML='<ol>'+data.questions.map(q=>`<li>${escapeHtml(q)}</li>`).join('')+'</ol>';
    $('clarifyCard').classList.remove('hidden');
  }else $('clarifyCard').classList.add('hidden');
  setTimeout(()=>$('resultArea').scrollIntoView({behavior:'smooth'}),100);
}
function escapeHtml(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

$('generateBtn').onclick=()=>generate('');
$('regenerateBtn').onclick=()=>generate($('extraNotes').value.trim());
$('printBtn').onclick=()=>window.print();
$('copyMessage').onclick=async()=>{await navigator.clipboard.writeText($('coverMessage').textContent);$('copyMessage').textContent='הועתק ✓';setTimeout(()=>$('copyMessage').textContent='העתק הודעה',1200)};

$('profileBtn').onclick=async()=>{await loadProfile();$('profileDialog').showModal()};
$('saveProfile').onclick=async()=>{
  try{
    const data=JSON.parse($('profileJson').value);
    const r=await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    if(!r.ok) throw new Error('save failed');
    profile=data; alert('הפרופיל נשמר');
  }catch(e){alert('ה-JSON לא תקין. בדוק את המבנה ונסה שוב.');}
};
$('savePhoto').onclick=async()=>{
  const f=$('newPhoto').files[0]; if(!f){alert('בחר תמונה חדשה קודם');return;}
  if(!confirm('להחליף את תמונת הפרופיל הקבועה? היא תשמש מעכשיו בכל קורות החיים.')) return;
  const fd=new FormData();fd.append('photo',f);
  const r=await fetch('/api/profile-photo',{method:'POST',body:fd});const d=await r.json();
  if(!r.ok){alert(d.error||'שגיאה');return;}
  const src='/profile-photo?v='+Date.now();$('settingsPhoto').src=src;$('profilePhoto').src=src;alert('התמונה הוחלפה');
};

loadProfile();
