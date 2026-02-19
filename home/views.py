import os, base64, json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from django.contrib.auth.models import User
from groq import Groq                         
from .models import (
    WeekPlan, DailyPlan, MealRecipe,
    ChatMessage, WardrobeSession, WardrobeChat, WeekendPlan  
)


from groq import Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Create your views here.

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords don't match!")
            return render(request, 'signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken!")
            return render(request, 'signup.html')

        user = User.objects.create_user(username=username, password=password1)
        login(request, user)
        return redirect('index')

    return render(request, 'signup.html')

def logout_view(request):
    logout(request)
    return redirect("login")


def login_view(request):

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("index")   # redirect after login
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "login.html")

def index(request):
    return render(request,'index.html')
def About(request):
    return render(request,'About.html')
   # return HttpResponse("hey, you are on About page")
def Mystuff(request):
    return render(request,'Mystuff.html')
    
    #return HttpResponse("hey, you are on my stuff page")
def WeeklyPlans(request):
    return render(request,'WeeklyPlans.html')

def cleanup_old_plans():
    today_str = str(datetime.now().date())
    old_plans = WeekPlan.objects.exclude(date=today_str)
    if old_plans.exists():
        old_plans.delete()
        print("🗑️ Old meal plans deleted")


# ─────────────────────────────────────────────
# Main page — upload image + show meal plan
# ─────────────────────────────────────────────

@login_required
def mealplan(request):
    cleanup_old_plans()

    ingredients = ""
    today_meal = None
    all_meals = []
    error = None

    if request.method == "POST":
        print("✅ POST received")
        try:
            DailyPlan.objects.all().delete()
            WeekPlan.objects.all().delete()

            image_file = request.FILES["fridge"]
            print("✅ Image:", image_file.name)
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            mime_type = image_file.content_type

            # STEP 1 — detect ingredients from image
            print("⏳ Detecting ingredients...")
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                        {"type": "text", "text": "List all the food ingredients you can see in this fridge image. Return ONLY comma separated items. Nothing else."}
                    ]
                }]
            )
            ingredients = response.choices[0].message.content.strip()
            print("✅ Ingredients:", ingredients[:80])

            week = WeekPlan.objects.create(ingredients=ingredients, date=str(datetime.now().date()))

            # STEP 2 — generate 7-day Indian meal plan
            print("⏳ Generating meal plan...")
            meal_prompt = f"""
You are an Indian diet and meal planning expert.

Fridge ingredients: {ingredients}

Assume these are always available: haldi, jeera, dhania powder, garam masala, red chilli powder, hing, mustard seeds, curry leaves, oil, ghee, salt, sugar, atta, chawal, dal, besan, adrak, lahsun, hari mirch, pyaz, tamatar.

Create a 7-day Indian meal plan. Suggest traditional meals like paratha, sabzi, dal, khichdi, poha, upma, rajma, chole, pulao, roti etc. Vary meals across days.

Return ONLY this strict format:
Day 1 Breakfast: xxx
Day 1 Lunch: xxx
Day 1 Dinner: xxx
Day 2 Breakfast: xxx
Day 2 Lunch: xxx
Day 2 Dinner: xxx
Day 3 Breakfast: xxx
Day 3 Lunch: xxx
Day 3 Dinner: xxx
Day 4 Breakfast: xxx
Day 4 Lunch: xxx
Day 4 Dinner: xxx
Day 5 Breakfast: xxx
Day 5 Lunch: xxx
Day 5 Dinner: xxx
Day 6 Breakfast: xxx
Day 6 Lunch: xxx
Day 6 Dinner: xxx
Day 7 Breakfast: xxx
Day 7 Lunch: xxx
Day 7 Dinner: xxx
"""
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": meal_prompt}]
            )
            text = response.choices[0].message.content
            lines = text.splitlines()

            day = 1
            b = l = d = ""
            for line in lines:
                if "Breakfast" in line and ":" in line:
                    b = line.split(":", 1)[1].strip()
                if "Lunch" in line and ":" in line:
                    l = line.split(":", 1)[1].strip()
                if "Dinner" in line and ":" in line:
                    d = line.split(":", 1)[1].strip()
                    if day <= 7:
                        DailyPlan.objects.create(day=day, breakfast=b, lunch=l, dinner=d, week=week)
                        print(f"✅ Day {day} saved")
                        day += 1

            print("✅ All done!")

        except KeyError:
            error = "Please upload a fridge image."
        except Exception as e:
            error = f"Something went wrong: {str(e)}"
            print("❌ ERROR:", e)

    today = datetime.now().weekday() + 1
    if DailyPlan.objects.exists():
        today_meal = DailyPlan.objects.filter(day=today).first()
        all_meals = DailyPlan.objects.order_by("day")

    return render(request, "mealplan.html", {
        "ingredients": ingredients,
        "meal": today_meal,
        "all_meals": all_meals,
        "error": error,
    })


# ─────────────────────────────────────────────
# Recipe modal — fetch or generate recipe
# ─────────────────────────────────────────────
def get_recipe(request, plan_id, meal_type):
    try:
        plan = DailyPlan.objects.get(id=plan_id)
        dish_name = getattr(plan, meal_type)

        # Check if already generated
        existing = MealRecipe.objects.filter(daily_plan=plan, meal_type=meal_type).first()
        if existing:
            return JsonResponse({
                "dish": existing.dish_name,
                "ingredients": json.loads(existing.ingredients_list),
                "steps": existing.recipe_steps,
            })

        # Generate fresh recipe
        week = plan.week
        recipe_prompt = f"""
You are an Indian cooking expert.

Give a detailed recipe for: {dish_name}

Available fridge ingredients: {week.ingredients}
Basic staples always available: haldi, jeera, dhania powder, garam masala, red chilli powder, oil, ghee, salt, atta, chawal, dal, adrak, lahsun, pyaz, tamatar.

Return ONLY valid JSON in this exact format:
{{
  "dish": "{dish_name}",
  "ingredients": [
    {{"name": "ingredient name", "quantity": "amount", "available": true}},
    ...
  ],
  "steps": "Step 1: ...\\nStep 2: ...\\nStep 3: ..."
}}
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": recipe_prompt}]
        )
        raw = response.choices[0].message.content.strip()

        # Clean JSON
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        # Save to DB
        MealRecipe.objects.create(
            daily_plan=plan,
            meal_type=meal_type,
            dish_name=data["dish"],
            ingredients_list=json.dumps(data["ingredients"]),
            recipe_steps=data["steps"],
        )

        return JsonResponse(data)

    except Exception as e:
        print("❌ Recipe error:", e)
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# Substitute ingredient or change dish
# ─────────────────────────────────────────────
@csrf_exempt
def substitute(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        body = json.loads(request.body)
        plan_id = body.get("plan_id")
        meal_type = body.get("meal_type")
        action = body.get("action")          # "substitute" or "change_dish"
        ingredient = body.get("ingredient", "")

        plan = DailyPlan.objects.get(id=plan_id)
        dish_name = getattr(plan, meal_type)
        week = plan.week

        if action == "substitute":
            prompt = f"""
The recipe for {dish_name} uses "{ingredient}" but the user doesn't have it.
Suggest the best Indian kitchen substitute for "{ingredient}" in this dish.
Reply in 1-2 lines only. Be specific.
"""
        else:  # change_dish
            prompt = f"""
The user cannot make {dish_name} because they don't have: {ingredient}.
Suggest a different Indian {meal_type} dish they can make using:
Fridge: {week.ingredients}
Staples: haldi, jeera, oil, ghee, salt, atta, chawal, dal, adrak, lahsun, pyaz, tamatar.
Reply with ONLY the new dish name. Nothing else.
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip()

        # If change_dish — update DB
        if action == "change_dish":
            setattr(plan, meal_type, result)
            plan.save()
            # Delete old recipe so it gets regenerated
            MealRecipe.objects.filter(daily_plan=plan, meal_type=meal_type).delete()

        return JsonResponse({"result": result})

    except Exception as e:
        print("❌ Substitute error:", e)
        return JsonResponse({"error": str(e)}, status=500)


# ─────────────────────────────────────────────
# Chatbot page
# ─────────────────────────────────────────────
def chatbot(request):
    return render(request, "chatbot.html")


@csrf_exempt
def chat_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        body = json.loads(request.body)
        user_message = body.get("message", "").strip()
        session_key = body.get("session_key", "default")

        if not user_message:
            return JsonResponse({"error": "Empty message"}, status=400)

        # Save user message
        ChatMessage.objects.create(session_key=session_key, role="user", message=user_message)

        # Build conversation history (last 10 messages)
        history = ChatMessage.objects.filter(session_key=session_key).order_by("created_at")[:20]
        messages = [
            {
                "role": "system",
                "content": """You are a helpful Indian cooking and meal planning assistant.
You help users with:
- Indian recipes and cooking tips
- Ingredient substitutions
- Meal suggestions based on available ingredients
- Nutritional advice for Indian food
- Modifying meal plans

Current meal plan context:
""" + get_meal_plan_context()
            }
        ]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.message})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()

        # Save assistant reply
        ChatMessage.objects.create(session_key=session_key, role="assistant", message=reply)

        return JsonResponse({"reply": reply})

    except Exception as e:
        print("❌ Chat error:", e)
        return JsonResponse({"error": str(e)}, status=500)


def get_meal_plan_context():
    """Build a text summary of current meal plan for chatbot context"""
    plans = DailyPlan.objects.order_by("day")
    if not plans.exists():
        return "No meal plan generated yet."
    lines = []
    for p in plans:
        lines.append(f"Day {p.day}: Breakfast={p.breakfast} | Lunch={p.lunch} | Dinner={p.dinner}")
    return "\n".join(lines)




# ─────────────────────────────────────────────
# WARDROBE SYSTEM PROMPT — AI fashion stylist
# ─────────────────────────────────────────────
WARDROBE_SYSTEM = """You are a smart AI fashion stylist.
Analyze the wardrobe image and respond in EXACTLY this format — nothing more, nothing less:

🧥 Top: [specific item name + color]
👖 Bottom: [specific item name + color]
👟 Shoes: [suggestion]
✨ Why: [ONE line only — max 10 words]

Rules:
- No paragraphs, no analysis, no intro lines
- No markdown like ** or ##
- Just 4 lines total
- Be specific and stylish"""

# ─────────────────────────────────────────────
# VIEW 1 — Wardrobe image upload + AI suggestion
# ─────────────────────────────────────────────
@login_required
def wardrobe_view(request):
    session = None

    if request.method == 'POST' and request.FILES.get('wardrobe_image'):
        image_file = request.FILES['wardrobe_image']

        # Image ko base64 mein convert karo
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
        media_type = image_file.content_type  # e.g. image/jpeg

        # Groq Vision se outfit suggest karwao (same as mealplan)
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",  # same model as mealplan
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": WARDROBE_SYSTEM + "\n\nPlease analyze my wardrobe and suggest the best outfit for today."
                    }
                ]
            }]
        )

        ai_suggestion = response.choices[0].message.content.strip()

        # Image file save karo aur session banao
        image_file.seek(0)
        session = WardrobeSession.objects.create(
            user          = request.user,
            image         = image_file,
            ai_suggestion = ai_suggestion,
        )

        # Pehla AI message chat history mein save karo
        WardrobeChat.objects.create(
            session = session,
            role    = 'assistant',
            message = ai_suggestion,
        )

    return render(request, 'wardrobe.html', {'session': session})


# ─────────────────────────────────────────────
# VIEW 2 — Chatbot API (outfit change request)
# ─────────────────────────────────────────────
@login_required
@csrf_exempt
def wardrobe_chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data       = json.loads(request.body)
        session_id = data.get('session_id')
        user_msg   = data.get('message', '').strip()

        if not session_id or not user_msg:
            return JsonResponse({'error': 'session_id aur message required hai'}, status=400)

        session = get_object_or_404(WardrobeSession, id=session_id, user=request.user)

        # User message save karo
        WardrobeChat.objects.create(session=session, role='user', message=user_msg)

        # Poori chat history banao Groq ke liye
        history = session.chats.order_by('timestamp')

        messages_list = [
            {
                "role": "system",
                "content": WARDROBE_SYSTEM + "\nUser may ask you to change specific parts of the outfit. Be helpful and suggest alternatives from what's visible in the wardrobe."
            }
        ]

        for chat in history:
            messages_list.append({
                "role"   : chat.role,
                "content": chat.message
            })

        # Groq se response lo (same as chat_api)
        response = client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",  # same model as chatbot
            messages = messages_list
        )

        ai_reply = response.choices[0].message.content.strip()

        # AI reply save karo
        WardrobeChat.objects.create(session=session, role='assistant', message=ai_reply)

        return JsonResponse({'reply': ai_reply})

    except Exception as e:
        print("❌ Wardrobe chat error:", e)
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────────────────────────
# Weekend Planner
# ─────────────────────────────────────────────
@login_required
def weekend_planner(request):
    plan = None
    error = None
    chat_history = []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'generate':
            # User ke answers collect karo
            mood        = request.POST.get('mood')
            energy      = request.POST.get('energy')
            company     = request.POST.get('company')
            budget      = request.POST.get('budget')
            preference  = request.POST.get('preference')

            prompt = f"""
You are a weekend planning expert. Create a detailed 2-day weekend plan.

User preferences:
- Mood: {mood}
- Energy level: {energy}
- Company: {company}
- Budget: {budget}
- Activity preference: {preference}

Return ONLY this exact format, nothing else:

SATURDAY MORNING: [activity]
SATURDAY AFTERNOON: [activity]
SATURDAY EVENING: [activity]
SUNDAY MORNING: [activity]
SUNDAY AFTERNOON: [activity]
SUNDAY EVENING: [activity]
TIP: [one helpful tip]
"""
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                raw = response.choices[0].message.content.strip()

                # Parse into dict
                plan = {}
                for line in raw.splitlines():
                    if ':' in line:
                        key, val = line.split(':', 1)
                        plan[key.strip()] = val.strip()

                # Session mein save karo taaki chat mein use ho
                request.session['weekend_plan'] = plan
                request.session['weekend_prefs'] = {
                    'mood': mood, 'energy': energy,
                    'company': company, 'budget': budget,
                    'preference': preference
                }

            except Exception as e:
                error = f"Something went wrong: {str(e)}"

        elif action == 'chat':
            # Chat se plan modify karo
            user_msg = request.POST.get('message', '').strip()
            plan     = request.session.get('weekend_plan', {})
            history  = request.session.get('weekend_chat', [])

            if user_msg and plan:
                history.append({"role": "user", "content": user_msg})

                plan_text = "\n".join([f"{k}: {v}" for k, v in plan.items()])

                messages_list = [
                    {
                        "role": "system",
                        "content": f"""You are a weekend planning assistant.
Current weekend plan:
{plan_text}

User wants to modify this plan. Make the requested changes and return the COMPLETE updated plan in EXACTLY this format:
SATURDAY MORNING: [activity]
SATURDAY AFTERNOON: [activity]
SATURDAY EVENING: [activity]
SUNDAY MORNING: [activity]
SUNDAY AFTERNOON: [activity]
SUNDAY EVENING: [activity]
TIP: [one helpful tip]"""
                    }
                ] + history

                try:
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages_list
                    )
                    ai_reply = response.choices[0].message.content.strip()
                    history.append({"role": "assistant", "content": ai_reply})

                    # Updated plan parse karo
                    new_plan = {}
                    for line in ai_reply.splitlines():
                        if ':' in line:
                            key, val = line.split(':', 1)
                            k = key.strip()
                            if k in ['SATURDAY MORNING', 'SATURDAY AFTERNOON', 'SATURDAY EVENING',
                                     'SUNDAY MORNING', 'SUNDAY AFTERNOON', 'SUNDAY EVENING', 'TIP']:
                                new_plan[k] = val.strip()

                    if new_plan:
                        plan = new_plan
                        request.session['weekend_plan'] = plan

                    request.session['weekend_chat'] = history[-10:]  # last 10 messages rakhо
                    chat_history = history

                except Exception as e:
                    error = f"Chat error: {str(e)}"

        elif action == 'reset':
            request.session.pop('weekend_plan', None)
            request.session.pop('weekend_chat', None)
            return redirect('weekend')

    else:
        # GET request — session se plan lo agar hai
        plan         = request.session.get('weekend_plan', None)
        chat_history = request.session.get('weekend_chat', [])

    return render(request, 'weekend.html', {
        'plan'         : plan,
        'error'        : error,
        'chat_history' : chat_history,
    })

