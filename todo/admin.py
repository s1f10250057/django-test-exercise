from django.contrib import admin
from todo.models import Task

# Register your models here.


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'status', 'due_at')
    list_filter = ('owner', 'status')
    search_fields = ('title', 'owner__username')
