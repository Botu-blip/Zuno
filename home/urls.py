from django.urls import path
from . import views
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path("", views.index, name="index"),
    path("recipe/<int:plan_id>/<str:meal_type>/", views.get_recipe, name="get_recipe"),
    path("substitute/", views.substitute, name="substitute"),
    path("chatbot/", views.chatbot, name="chatbot"),
    path("chat-api/", views.chat_api, name="chat_api"),
    path("about/", views.About, name='about'),
    path("mystuff/", views.Mystuff, name='mystuff'),
    path("weekly/", views.WeeklyPlans, name='weekly'),
    path("mealplan/", views.mealplan, name="mealplan"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('wardrobe/', views.wardrobe_view,   name='wardrobe'),
    path('wardrobe/chat/', views.wardrobe_chat,   name='wardrobe_chat'), 
    path('register/', views.signup_view, name='signup'),
    path('weekend/', views.weekend_planner, name='weekend'),

]