import os, json, io, re
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import jwt
from werkzeug.utils import secure_filename

try:
    import PyPDF2; HAS_PDF = True
except: HAS_PDF = False
try:
    from docx import Document; HAS_DOCX = True
except: HAS_DOCX = False

load_dotenv()
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, supports_credentials=True)

JWT_SECRET = os.getenv('JWT_SECRET', 'skillgraph-secret-key-2025')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

users_db = {}
posts_db = []
interviews_db = {}
chat_histories = {}
post_counter = 0

MARKET_TRENDS = [
    {"title":"AI/ML Engineer","growth":42,"skills":["Python","TensorFlow","LLMs","PyTorch"],"salary":"$145k–$210k","demand":"Very High"},
    {"title":"Full Stack Developer","growth":28,"skills":["React","Node.js","TypeScript","Docker"],"salary":"$110k–$170k","demand":"High"},
    {"title":"Data Engineer","growth":35,"skills":["Spark","Kafka","dbt","Snowflake"],"salary":"$125k–$185k","demand":"High"},
    {"title":"DevOps / SRE","growth":31,"skills":["Kubernetes","Terraform","CI/CD","AWS"],"salary":"$120k–$180k","demand":"High"},
    {"title":"Cloud Architect","growth":38,"skills":["AWS","Azure","GCP","Microservices"],"salary":"$150k–$220k","demand":"Very High"},
    {"title":"Cybersecurity Engineer","growth":33,"skills":["Penetration Testing","SIEM","Zero Trust","SOC"],"salary":"$130k–$190k","demand":"High"},
    {"title":"Product Manager","growth":22,"skills":["Roadmapping","Agile","A/B Testing","SQL"],"salary":"$120k–$180k","demand":"Medium"},
    {"title":"UX Designer","growth":18,"skills":["Figma","User Research","Prototyping","Accessibility"],"salary":"$95k–$150k","demand":"Medium"},
]

LEARNING_COURSES = [
    {"title":"Machine Learning Specialization","platform":"Coursera","instructor":"Andrew Ng","duration":"3 months","rating":4.9,"level":"Intermediate","url":"https://coursera.org/specializations/machine-learning-introduction","skills":["Python","ML","TensorFlow","AI/ML Engineer"],"tags":["ai","ml"]},
    {"title":"The Complete Python Bootcamp","platform":"Udemy","instructor":"Jose Portilla","duration":"22 hours","rating":4.8,"level":"Beginner","url":"https://udemy.com/course/complete-python-bootcamp/","skills":["Python"],"tags":["python","beginner"]},
    {"title":"AWS Certified Solutions Architect","platform":"Udemy","instructor":"Stephane Maarek","duration":"27 hours","rating":4.7,"level":"Professional","url":"https://udemy.com/course/aws-certified-solutions-architect-associate/","skills":["AWS","Cloud Architect"],"tags":["aws","cloud"]},
    {"title":"React – The Complete Guide","platform":"Udemy","instructor":"Maximilian Schwarzmüller","duration":"68 hours","rating":4.7,"level":"Intermediate","url":"https://udemy.com/course/react-the-complete-guide/","skills":["React","Full Stack Developer"],"tags":["react","frontend"]},
    {"title":"Deep Learning Specialization","platform":"Coursera","instructor":"Andrew Ng","duration":"5 months","rating":4.9,"level":"Advanced","url":"https://coursera.org/specializations/deep-learning","skills":["TensorFlow","PyTorch","ML","AI/ML Engineer"],"tags":["ai","deep-learning"]},
    {"title":"Docker & Kubernetes: The Practical Guide","platform":"Udemy","instructor":"Maximilian Schwarzmüller","duration":"24 hours","rating":4.7,"level":"Intermediate","url":"https://udemy.com/course/docker-kubernetes-the-practical-guide/","skills":["Docker","Kubernetes","DevOps / SRE"],"tags":["devops","docker"]},
    {"title":"The Complete SQL Bootcamp","platform":"Udemy","instructor":"Jose Portilla","duration":"9 hours","rating":4.7,"level":"Beginner","url":"https://udemy.com/course/the-complete-sql-bootcamp/","skills":["SQL","Data Engineer"],"tags":["sql","data"]},
    {"title":"CS50 Cybersecurity","platform":"edX","instructor":"David Malan","duration":"10 weeks","rating":4.8,"level":"Beginner","url":"https://edx.org/course/cs50s-introduction-to-cybersecurity","skills":["Cybersecurity Engineer"],"tags":["security"]},
    {"title":"Google UX Design Certificate","platform":"Coursera","instructor":"Google","duration":"6 months","rating":4.8,"level":"Beginner","url":"https://coursera.org/professional-certificates/google-ux-design","skills":["Figma","UX Designer"],"tags":["ux","design"]},
    {"title":"Terraform for DevOps Engineers","platform":"Udemy","instructor":"Bryan Krausen","duration":"12 hours","rating":4.6,"level":"Intermediate","url":"https://udemy.com/course/terraform-beginner/","skills":["Terraform","DevOps / SRE"],"tags":["devops","terraform"]},
    {"title":"TypeScript – The Complete Guide","platform":"Udemy","instructor":"Maximilian Schwarzmüller","duration":"15 hours","rating":4.7,"level":"Intermediate","url":"https://udemy.com/course/understanding-typescript/","skills":["TypeScript","Full Stack Developer"],"tags":["typescript","javascript"]},
    {"title":"Data Engineering with Apache Kafka","platform":"Udemy","instructor":"Stéphane Maarek","duration":"12 hours","rating":4.6,"level":"Advanced","url":"https://udemy.com/course/apache-kafka/","skills":["Kafka","Data Engineer"],"tags":["kafka","data"]},
]

SKILL_KEYWORDS = [
    "Python","JavaScript","TypeScript","Java","C++","C#","Go","Rust","Swift","Kotlin",
    "React","Angular","Vue","Node.js","Django","Flask","FastAPI","Spring","Express",
    "AWS","Azure","GCP","Docker","Kubernetes","Terraform","CI/CD","Jenkins",
    "SQL","PostgreSQL","MySQL","MongoDB","Redis","Elasticsearch","Cassandra","DynamoDB",
    "Machine Learning","Deep Learning","TensorFlow","PyTorch","Scikit-learn","NLP",
    "LLMs","GPT","Computer Vision","Data Science","Pandas","NumPy","Spark",
    "Kafka","Airflow","dbt","Snowflake","BigQuery","Power BI","Tableau",
    "REST API","GraphQL","Microservices","Agile","Scrum","DevOps","SRE",
    "Linux","Bash","Git","Figma","Sketch","UX","UI",
    "Penetration Testing","SIEM","Zero Trust","SOC","Cybersecurity",
]

def call_gemini(prompt, system="You are a helpful AI career assistant."):
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key not configured. Add GEMINI_API_KEY to your .env file.")
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    response = model.generate_content(f"{system}\n\n{prompt}")
    return response.text

def parse_json_response(text):
    # Strip markdown code fences
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text).strip()
    # Find the start of the JSON (array or object)
    arr_start = text.find('[')
    obj_start = text.find('{')
    if arr_start == -1 and obj_start == -1:
        raise ValueError("No JSON found in response")
    # Pick whichever comes first
    if arr_start == -1:
        start, open_ch, close_ch = obj_start, '{', '}'
    elif obj_start == -1:
        start, open_ch, close_ch = arr_start, '[', ']'
    else:
        if arr_start < obj_start:
            start, open_ch, close_ch = arr_start, '[', ']'
        else:
            start, open_ch, close_ch = obj_start, '{', '}'
    # Walk through to find matching closing bracket (handles nesting)
    depth = 0
    in_string = False
    escape = False
    end = start
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(text[start:end+1])


def generate_token(user_id, username):
    return jwt.encode({'user_id':user_id,'username':username,'exp':datetime.utcnow()+timedelta(days=7)}, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    try: return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except: return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization','').replace('Bearer ','')
        if not token: return jsonify({'error':'No token'}), 401
        payload = verify_token(token)
        if not payload: return jsonify({'error':'Invalid token'}), 401
        request.user_id = payload['user_id']
        request.username = payload['username']
        return f(*args, **kwargs)
    return decorated

def extract_text(file_bytes, filename):
    ext = filename.rsplit('.',1)[-1].lower()
    if ext == 'txt': return file_bytes.decode('utf-8', errors='ignore')
    if ext == 'pdf' and HAS_PDF:
        r = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return '\n'.join(p.extract_text() or '' for p in r.pages)
    if ext in ('doc','docx') and HAS_DOCX:
        doc = Document(io.BytesIO(file_bytes))
        return '\n'.join(p.text for p in doc.paragraphs)
    return file_bytes.decode('utf-8', errors='ignore')

def extract_skills(text):
    tl = text.lower()
    return [s for s in SKILL_KEYWORDS if s.lower() in tl]

# Static pages
def page(f): return open(f, encoding='utf-8').read()

@app.route('/') 
def r_login(): return page('login.html')
@app.route('/dashboard') 
def r_dashboard(): return page('dashboard.html')
@app.route('/community') 
def r_community(): return page('community.html')
@app.route('/aichat') 
def r_aichat(): return page('aichat.html')
@app.route('/resume') 
def r_resume(): return page('resumeiq.html')
@app.route('/mock-interview') 
def r_mock(): return page('mock-interview.html')
@app.route('/learning') 
def r_learning(): return page('learning.html')
@app.route('/market') 
def r_market(): return page('market.html')
@app.route('/global.css') 
def r_css(): return page('global.css'), 200, {'Content-Type':'text/css'}

# Auth
@app.route('/auth/register', methods=['POST'])
def register():
    d = request.get_json()
    u,p,e = d.get('username','').strip(), d.get('password','').strip(), d.get('email','').strip()
    if not all([u,p,e]): return jsonify({'error':'All fields required'}), 400
    if u in users_db: return jsonify({'error':'Username taken'}), 400
    uid = f"user_{len(users_db)+1}"
    users_db[u] = {'id':uid,'email':e,'password':p,'created_at':datetime.utcnow().isoformat(),'profile_pic':f'https://api.dicebear.com/7.x/avataaars/svg?seed={u}'}
    token = generate_token(uid, u)
    return jsonify({'success':True,'token':token,'user':{'id':uid,'username':u,'email':e,'profile_pic':users_db[u]['profile_pic']}})

@app.route('/auth/login', methods=['POST'])
def login():
    d = request.get_json()
    u,p = d.get('username','').strip(), d.get('password','').strip()
    if not u or not p: return jsonify({'error':'Missing credentials'}), 400
    if u not in users_db or users_db[u]['password'] != p: return jsonify({'error':'Invalid credentials'}), 401
    user = users_db[u]
    token = generate_token(user['id'], u)
    return jsonify({'success':True,'token':token,'user':{'id':user['id'],'username':u,'email':user['email'],'profile_pic':user['profile_pic']}})

@app.route('/auth/me', methods=['GET'])
@auth_required
def get_me():
    for u, user in users_db.items():
        if user['id'] == request.user_id:
            return jsonify({'id':user['id'],'username':u,'email':user['email'],'profile_pic':user['profile_pic']})
    return jsonify({'error':'Not found'}), 404

# Community
@app.route('/community/posts', methods=['GET'])
def get_posts(): return jsonify({'posts': list(reversed(posts_db))})

@app.route('/community/posts', methods=['POST'])
@auth_required
def create_post():
    global post_counter
    d = request.get_json()
    title, content = d.get('title','').strip(), d.get('content','').strip()
    if not title or not content: return jsonify({'error':'Title and content required'}), 400
    user = next((u for u in users_db.values() if u['id']==request.user_id), None)
    post = {'id':f"post_{post_counter}",'title':title,'content':content,'author':request.username,
            'author_pic':user['profile_pic'] if user else '','created_at':datetime.utcnow().isoformat(),
            'likes':0,'comments':[],'liked_by':[],'tags':d.get('tags',[])}
    post_counter += 1; posts_db.append(post)
    return jsonify({'success':True,'post':post}), 201

@app.route('/community/posts/<pid>/like', methods=['POST'])
@auth_required
def like_post(pid):
    for post in posts_db:
        if post['id'] == pid:
            if request.user_id not in post['liked_by']:
                post['liked_by'].append(request.user_id); post['likes'] += 1
            else:
                post['liked_by'].remove(request.user_id); post['likes'] -= 1
            return jsonify({'success':True,'likes':post['likes']})
    return jsonify({'error':'Not found'}), 404

@app.route('/community/posts/<pid>/comments', methods=['POST'])
@auth_required
def add_comment(pid):
    d = request.get_json(); text = d.get('text','').strip()
    if not text: return jsonify({'error':'Comment required'}), 400
    for post in posts_db:
        if post['id'] == pid:
            c = {'author':request.username,'text':text,'created_at':datetime.utcnow().isoformat()}
            post['comments'].append(c)
            return jsonify({'success':True,'comment':c}), 201
    return jsonify({'error':'Not found'}), 404

# AI Chat
@app.route('/ai/chat', methods=['POST'])
@auth_required
def ai_chat():
    d = request.get_json(); message = d.get('message','').strip()
    if not message: return jsonify({'error':'Message required'}), 400
    uid = request.user_id
    if uid not in chat_histories: chat_histories[uid] = []
    hist = chat_histories[uid]
    hist_text = '\n'.join([f"{m['role'].upper()}: {m['text']}" for m in hist[-8:]])
    system = "You are CareerAI, an expert career coach. Help with interviews, resumes, skills, and job market. Be concise and actionable."
    prompt = f"History:\n{hist_text}\n\nUSER: {message}\n\nCareerAI:"
    try:
        reply = call_gemini(prompt, system)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    hist.extend([{'role':'user','text':message},{'role':'assistant','text':reply}])
    if len(hist)>30: chat_histories[uid] = hist[-30:]
    return jsonify({'success':True,'reply':reply})

@app.route('/ai/chat/history', methods=['GET'])
@auth_required
def chat_history(): return jsonify({'history': chat_histories.get(request.user_id,[])})

@app.route('/ai/chat/clear', methods=['POST'])
@auth_required
def clear_chat():
    chat_histories[request.user_id] = []
    return jsonify({'success':True})

# Resume
@app.route('/resume/analyze', methods=['POST'])
@auth_required
def analyze_resume():
    if 'resume' not in request.files: return jsonify({'error':'No file'}), 400
    file = request.files['resume']
    role = request.form.get('role','Software Engineer')
    file_bytes = file.read()
    resume_text = extract_text(file_bytes, secure_filename(file.filename))
    if len(resume_text.strip()) < 50: return jsonify({'error':'Could not extract text'}), 400

    detected = extract_skills(resume_text)
    role_data = next((r for r in MARKET_TRENDS if role.lower() in r['title'].lower()), MARKET_TRENDS[0])
    required = role_data['skills']
    matched = [s for s in detected if any(s.lower() in r.lower() or r.lower() in s.lower() for r in required)]
    missing = [r for r in required if not any(r.lower() in s.lower() or s.lower() in r.lower() for s in detected)]
    score = round(len(matched)/max(len(required),1)*100)

    prompt = f"""Analyze this resume for {role}.
RESUME: {resume_text[:3000]}
DETECTED SKILLS: {', '.join(detected)}
REQUIRED: {', '.join(required)}
MATCHED: {', '.join(matched)}
MISSING: {', '.join(missing)}

Return ONLY JSON (no markdown):
{{"summary":"brief professional summary","strengths":["s1","s2","s3"],"improvements":["i1","i2","i3"],"experience_level":"Junior|Mid|Senior","recommended_courses":["c1","c2"],"ats_tips":["t1","t2"]}}"""

    try:
        ai = parse_json_response(call_gemini(prompt))
    except:
        ai = {"summary":"Resume analyzed successfully.","strengths":[],"improvements":[],"experience_level":"Mid","recommended_courses":[],"ats_tips":[]}

    return jsonify({'success':True,'score':score,'matched_skills':matched,'missing_skills':missing,
                    'all_detected_skills':detected,'target_role':role,'summary':ai.get('summary',''),
                    'strengths':ai.get('strengths',[]),'improvements':ai.get('improvements',[]),
                    'experience_level':ai.get('experience_level','Mid'),'recommended_courses':ai.get('recommended_courses',[]),
                    'ats_tips':ai.get('ats_tips',[])})

# Interview
@app.route('/interview/generate-questions', methods=['POST'])
def gen_questions():
    d = request.get_json(); prompt = d.get('prompt')
    if not prompt: return jsonify({'error':'No prompt'}), 400
    try:
        r = call_gemini(prompt)
        q = parse_json_response(r)
        if not isinstance(q, list): q = [q]
        return jsonify({'questions':q})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/interview/evaluate-answer', methods=['POST'])
def eval_answer():
    d = request.get_json(); prompt = d.get('prompt')
    if not prompt: return jsonify({'error':'No prompt'}), 400
    try:
        r = call_gemini(prompt)
        ev = parse_json_response(r)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    for f in ['score','technical_score','communication_score','confidence_score']:
        if f not in ev: ev[f] = 5
    for f in ['strengths','improvements']:
        if f not in ev: ev[f] = []
    if 'model_answer' not in ev: ev['model_answer'] = ''
    return jsonify(ev)

@app.route('/interview/generate-report', methods=['POST'])
def gen_report():
    d = request.get_json(); prompt = d.get('prompt')
    if not prompt: return jsonify({'error':'No prompt'}), 400
    try:
        r = call_gemini(prompt)
        rp = parse_json_response(r)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    defs = {'total_score':5,'technical_score':5,'communication_score':5,'confidence_score':5,
            'hiring_recommendation':'Maybe','overall_summary':'','top_strengths':[],'critical_improvements':[],
            'skill_gaps':[],'study_recommendations':[],'next_steps':[]}
    for k,v in defs.items():
        if k not in rp: rp[k] = v
    return jsonify(rp)

@app.route('/interview/save', methods=['POST'])
@auth_required
def save_interview():
    d = request.get_json()
    iv = {'id':f"iv_{len(interviews_db)+1}",'user_id':request.user_id,'username':request.username,
          'role':d.get('role'),'questions':d.get('questions'),'evaluations':d.get('evaluations'),
          'report':d.get('report'),'created_at':datetime.utcnow().isoformat()}
    interviews_db[request.user_id] = iv
    return jsonify({'success':True,'interview':iv})

@app.route('/interview/history', methods=['GET'])
@auth_required
def interview_history(): return jsonify({'interview': interviews_db.get(request.user_id)})

# Market + Learning
@app.route('/market/trends', methods=['GET'])
def market_trends(): return jsonify({'trends':MARKET_TRENDS,'updated_at':datetime.utcnow().isoformat()})

@app.route('/learning/courses', methods=['GET'])
def learning_courses():
    sf = request.args.get('skill','').lower()
    c = [x for x in LEARNING_COURSES if not sf or any(sf in s.lower() for s in x['skills']+x.get('tags',[]))]
    return jsonify({'courses':c})

@app.route('/health')
def health(): return jsonify({'status':'ok','gemini':bool(GEMINI_API_KEY)})

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error: ' + str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    print("Career Intelligence Platform")
    print(f"   Gemini: {'OK' if GEMINI_API_KEY else 'Missing - Set GEMINI_API_KEY in .env'}")
    app.run(debug=True, host='0.0.0.0', port=5000)
