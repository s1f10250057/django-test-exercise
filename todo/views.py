from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_POST
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_datetime
from todo.models import Task, SubTask

# Create your views here.


def parse_due_at(value):
    if not value:
        return None
    return make_aware(parse_datetime(value))


def get_user_task_or_404(user, task_id):
    try:
        return Task.objects.get(pk=task_id, owner=user)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")


@login_required
def index(request):
    if request.method == 'POST':
        task = Task(title=request.POST['title'],
                    owner=request.user,
                    tag=request.POST.get('tag', ''),
                    recurrence=request.POST.get('recurrence', Task.RECURRENCE_NONE),
                    due_at=parse_due_at(request.POST.get('due_at')))
        task.save()
    tasks = Task.objects.filter(owner=request.user)
    if request.GET.get('order') == 'due':
        tasks = tasks.order_by('due_at')
    elif request.GET.get('order') == 'tag':
        tasks = tasks.order_by('tag', '-posted_at')
    else:
        tasks = tasks.order_by('-posted_at')
    context = {
        'tasks': tasks,
        'recurrence_choices': Task.RECURRENCE_CHOICES,
    }
    return render(request, 'todo/index.html', context)


@login_required
def detail(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    context = {
        'task': task,
        'subtasks': task.subtasks.order_by('created_at'),
    }
    return render(request, 'todo/detail.html', context)


@login_required
def update(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    if request.method == 'POST':
        task.title = request.POST['title']
        task.tag = request.POST.get('tag', '')
        task.recurrence = request.POST.get('recurrence', Task.RECURRENCE_NONE)
        task.due_at = parse_due_at(request.POST.get('due_at'))
        task.save()
        return redirect('detail', task_id=task.id)
    context = {
        'task': task,
        'recurrence_choices': Task.RECURRENCE_CHOICES,
    }
    return render(request, "todo/edit.html", context)


@login_required
@require_POST
def delete(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    task.delete()
    return redirect('index')


@login_required
@require_POST
def complete(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    was_completed = task.completed
    task.completed = True
    task.save()
    if not was_completed:
        task.create_next_occurrence()
    return redirect('index')


@login_required
@require_POST
def add_subtask(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    title = request.POST.get('title', '').strip()
    if title:
        SubTask.objects.create(task=task, title=title)
    return redirect('detail', task_id=task.id)


@login_required
@require_POST
def toggle_subtask(request, task_id, subtask_id):
    task = get_user_task_or_404(request.user, task_id)
    try:
        subtask = task.subtasks.get(pk=subtask_id)
    except SubTask.DoesNotExist:
        raise Http404("SubTask does not exist")
    subtask.completed = not subtask.completed
    subtask.save()
    return redirect('detail', task_id=task.id)


@login_required
@require_POST
def delete_subtask(request, task_id, subtask_id):
    task = get_user_task_or_404(request.user, task_id)
    try:
        subtask = task.subtasks.get(pk=subtask_id)
    except SubTask.DoesNotExist:
        raise Http404("SubTask does not exist")
    subtask.delete()
    return redirect('detail', task_id=task.id)
