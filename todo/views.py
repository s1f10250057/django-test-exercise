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


def index(request):
    if request.method == 'POST':
        task = Task(title=request.POST['title'],
                    tag=request.POST.get('tag', ''),
                    recurrence=request.POST.get('recurrence', Task.RECURRENCE_NONE),
                    due_at=parse_due_at(request.POST.get('due_at')))
        task.save()
    if request.GET.get('order') == 'due':
        tasks = Task.objects.order_by('due_at')
    elif request.GET.get('order') == 'tag':
        tasks = Task.objects.order_by('tag', '-posted_at')
    else:
        tasks = Task.objects.order_by('-posted_at')
    context = {
        'tasks': tasks,
        'recurrence_choices': Task.RECURRENCE_CHOICES,
    }
    return render(request, 'todo/index.html', context)


def detail(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")
    context = {
        'task': task,
        'subtasks': task.subtasks.order_by('created_at'),
    }
    return render(request, 'todo/detail.html', context)


def update(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")
    if request.method == 'POST':
        task.title = request.POST['title']
        task.tag = request.POST.get('tag', '')
        task.recurrence = request.POST.get('recurrence', Task.RECURRENCE_NONE)
        task.due_at = parse_due_at(request.POST.get('due_at'))
        task.save()
        return redirect(detail, task_id)
    context = {
        'task': task,
        'recurrence_choices': Task.RECURRENCE_CHOICES,
    }
    return render(request, "todo/edit.html", context)


@require_POST
def delete(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")
    task.delete()
    return redirect('index')


@require_POST
def complete(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")
    was_completed = task.completed
    task.completed = True
    task.save()
    if not was_completed:
        task.create_next_occurrence()
    return redirect('index')


@require_POST
def add_subtask(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("Task does not exist")
    title = request.POST.get('title', '').strip()
    if title:
        SubTask.objects.create(task=task, title=title)
    return redirect(detail, task_id)


@require_POST
def toggle_subtask(request, task_id, subtask_id):
    try:
        subtask = SubTask.objects.get(pk=subtask_id, task_id=task_id)
    except SubTask.DoesNotExist:
        raise Http404("SubTask does not exist")
    subtask.completed = not subtask.completed
    subtask.save()
    return redirect(detail, task_id)


@require_POST
def delete_subtask(request, task_id, subtask_id):
    try:
        subtask = SubTask.objects.get(pk=subtask_id, task_id=task_id)
    except SubTask.DoesNotExist:
        raise Http404("SubTask does not exist")
    subtask.delete()
    return redirect(detail, task_id)
