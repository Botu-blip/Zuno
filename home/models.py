from django.db import models
from django.contrib.auth.models import User  # ← YEH ADD KARO


class WeekPlan(models.Model):
    ingredients = models.CharField(max_length=2000, blank=True, null=True)
    date = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.date or "WeekPlan"


class DailyPlan(models.Model):
    day = models.IntegerField()
    breakfast = models.CharField(max_length=500)
    lunch = models.CharField(max_length=500)
    dinner = models.CharField(max_length=500)
    week = models.ForeignKey(WeekPlan, on_delete=models.CASCADE)

    def __str__(self):
        return f"Day {self.day}"


class MealRecipe(models.Model):
    """Stores full recipe details for each meal"""
    MEAL_TYPES = [("breakfast", "Breakfast"), ("lunch", "Lunch"), ("dinner", "Dinner")]

    daily_plan = models.ForeignKey(DailyPlan, on_delete=models.CASCADE, related_name="recipes")
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    dish_name = models.CharField(max_length=300)
    ingredients_list = models.TextField()   # JSON string of ingredients
    recipe_steps = models.TextField()       # Step by step instructions
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.daily_plan} - {self.meal_type} - {self.dish_name}"


class ChatMessage(models.Model):
    """Stores chatbot conversation history"""
    ROLES = [("user", "User"), ("assistant", "Assistant")]

    session_key = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.message[:50]}"

class WardrobeSession(models.Model):
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wardrobe_sessions')
    image         = models.ImageField(upload_to='wardrobe/')
    ai_suggestion = models.TextField(blank=True)       # AI ka pehla outfit suggestion
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%d %b %Y %H:%M')}"


class WardrobeChat(models.Model):
    session   = models.ForeignKey(WardrobeSession, on_delete=models.CASCADE, related_name='chats')
    role      = models.CharField(max_length=10)   # 'user' ya 'assistant'
    message   = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.role}] {self.message[:50]}"


class WeekendPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField()

    def __str__(self):
        return self.title