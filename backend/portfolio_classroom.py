"""Public classroom bound to the original fictional LMS database."""
import os
import secrets
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp(prefix="lms-classroom-")) / "classroom.sqlite3")
os.environ["DJANGO_DEBUG"] = "false"
os.environ["DJANGO_ALLOWED_HOSTS"] = os.getenv("RENDER_EXTERNAL_HOSTNAME","localhost") + ",localhost,127.0.0.1"
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse, JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET
from apps.courses.models import Course
from apps.question_bank.models import Question
from apps.core.calculations import attendance_percentage

@require_GET
def courses(request):
    return JsonResponse(list(Course.objects.order_by("code").values("code","name","credits","description","semester_number")),safe=False)

@require_GET
def questions(request):
    rows=Question.objects.filter(course__code=request.GET.get("course","")[:30],status=Question.Status.APPROVED).prefetch_related("options")
    return JsonResponse([{"id":str(q.pk),"text":q.text,"kind":q.get_question_type_display(),
        "options":[{"id":str(o.pk),"label":o.text} for o in q.options.all()]} for q in rows],safe=False)

@require_GET
def grade(request):
    from apps.question_bank.models import QuestionOption
    from django.core.exceptions import ValidationError
    try:
        option=QuestionOption.objects.select_related("question").get(pk=request.GET.get("option",""),question__status=Question.Status.APPROVED)
    except (QuestionOption.DoesNotExist,ValueError,ValidationError):
        return JsonResponse({"error":"Unknown practice answer"},status=400)
    return JsonResponse({"correct":option.is_correct,"explanation":option.question.explanation})

@require_GET
def attendance(request):
    try:
        p,l,e,t=[int(request.GET.get(k,"0")) for k in ("present","late","excused","total")]
        if min(p,l,e,t)<0 or p+l+e>t or t>10000:raise ValueError()
    except ValueError:return JsonResponse({"error":"Check the session counts."},status=400)
    return JsonResponse({"percent":str(attendance_percentage(p,l,e,t))})

PAGE=r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Public Health LMS | Rikdeb Mandal</title><style>:root{font:16px/1.55 system-ui,sans-serif;color:#172e34;background:#f5f5ee}*{box-sizing:border-box}body{margin:0}main{max-width:1100px;margin:auto;padding:28px clamp(18px,5vw,64px) 70px}nav{border-bottom:1px solid #bdc9c1;padding-bottom:18px}a{color:#215a50}h1{font:normal clamp(42px,7vw,82px)/1.02 Georgia,serif;letter-spacing:-.06em;margin:32px 0 12px}h2{font-size:22px}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:20px}section{background:#fffefa;border:1px solid #c3cfc4;border-radius:12px;padding:22px;margin:18px 0}label{display:block;font-weight:600;margin:14px 0}textarea,select,input{font:inherit;border:1px solid #8caaa2;border-radius:6px;padding:9px;width:100%;background:white;color:#142824}button{font:inherit;border:0;border-radius:6px;padding:10px 18px;background:#245650;color:white;cursor:pointer}button:disabled{opacity:.55}article{padding:10px 0;border-top:1px solid #d0d9d2}progress{display:block;width:100%;accent-color:#2e7465}small{color:#49615a}details{margin:14px 0}summary{cursor:pointer;font-weight:600}.hint{max-width:76ch}@media(max-width:650px){.grid{grid-template-columns:1fr;gap:0}section{margin:10px 0}}</style><main><nav><a href="https://rikdeb-mandal.higgsfield.app/projects">← Portfolio projects</a></nav><h1>Public Health LMS</h1><p class="hint">Explore the original Django course catalogue, try the question bank and calculate attendance using the project’s academic rules. This public classroom uses the repository’s fictional teaching dataset.</p><div class="grid"><section><h2>Course catalogue</h2><label>Choose a course<select id="course"></select></label><p id="about" aria-live="polite">Loading courses…</p></section><section><h2>Attendance calculator</h2><form id="form"><label>Total sessions<input name="total" type="number" value="20" min="0" max="10000" required></label><label>Present<input name="present" type="number" value="14" min="0" required></label><label>Late<input name="late" type="number" value="1" min="0" required></label><label>Excused<input name="excused" type="number" value="1" min="0" required></label><button>Calculate attendance</button></form><output id="pct" aria-live="polite"></output></section></div><section><h2>Practice questions</h2><div id="bank"></div></section></main><script>
const el=id=>document.getElementById(id);function node(t,s){const e=document.createElement(t);e.textContent=s;return e}
async function get(path){const r=await fetch(path);if(!r.ok)throw Error();return r.json()}
async function init(){const courses=await get('/classroom/courses');for(const c of courses)el('course').add(new Option(c.code+' · '+c.name,c.code));
let ticket=0;async function show(){const next=++ticket,c=courses[el('course').selectedIndex];el('about').textContent=c.credits+' credits · Semester '+c.semester_number+' · '+c.description;el('bank').textContent='Loading questions…';
try{const qs=await get('/classroom/questions?course='+encodeURIComponent(c.code));if(next!==ticket)return;el('bank').replaceChildren();if(!qs.length)el('bank').textContent='This course has no published practice questions.';for(const q of qs){const box=node('article',''),out=node('p','');out.setAttribute('aria-live','polite');box.append(node('small',q.kind),node('p',q.text));for(const o of q.options){const b=node('button',o.label);b.style.margin='3px';b.onclick=async()=>{try{const r=await get('/classroom/grade?option='+encodeURIComponent(o.id));out.textContent=(r.correct?'Correct. ':'Try again. ')+r.explanation}catch{out.textContent='Could not score that answer.'}};box.append(b)}box.append(out);el('bank').append(box)}}catch{el('bank').textContent='Questions could not load.'}}
el('course').onchange=show;if(courses.length)await show()}
el('form').onsubmit=async e=>{e.preventDefault();try{const d=await get('/classroom/attendance?'+new URLSearchParams(new FormData(e.target)));el('pct').textContent=' Attendance · '+d.percent+'%'}catch{el('pct').textContent='Check that the counts fit the total.'}};
init().catch(()=>el('about').textContent='Could not load the classroom. Reload to retry.');</script></html>'''
urlpatterns=[path("",lambda request:HttpResponse(PAGE)),path("classroom/courses",courses),path("classroom/questions",questions),path("classroom/grade",grade),path("classroom/attendance",attendance)]
settings.ROOT_URLCONF=__name__
call_command("migrate",interactive=False,verbosity=0)
call_command("seed_demo",verbosity=0,stdout=open(os.devnull,"w"))
application=get_wsgi_application()
