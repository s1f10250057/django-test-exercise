from django.contrib import admin
from todo.models import Task

# Register your models here.


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'completed', 'due_at')
    list_filter = ('owner', 'completed')
    search_fields = ('title', 'owner__username')
