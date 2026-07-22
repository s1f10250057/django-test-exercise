"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from todo import views as todo_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('signup/', todo_views.signup, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', todo_views.dashboard, name='dashboard'),
    path('', todo_views.index, name='index'),
    path('<int:task_id>/complete/', todo_views.complete, name='complete'),
    path('<int:task_id>/status/', todo_views.change_status, name='change_status'),
    path(
        '<int:task_id>/subtasks/add/',
        todo_views.add_subtask,
        name='add_subtask',
    ),
    path(
        '<int:task_id>/subtasks/<int:subtask_id>/toggle/',
        todo_views.toggle_subtask,
        name='toggle_subtask',
    ),
    path(
        '<int:task_id>/subtasks/<int:subtask_id>/delete/',
        todo_views.delete_subtask,
        name='delete_subtask',
    ),
    path('<int:task_id>/', todo_views.detail, name='detail'),
    path('<int:task_id>/update', todo_views.update, name='update'),
    path('<int:task_id>/delete/', todo_views.delete, name='delete'),
]
