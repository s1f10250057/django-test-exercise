from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from todo.forms import TaskForm
from todo.models import SubTask, Task


def get_user_task_or_404(user, task_id):
    return get_object_or_404(Task, pk=task_id, owner=user)


def mark_task_done(task):
    with transaction.atomic():
        locked_task = Task.objects.select_for_update().get(pk=task.pk)
        if locked_task.status == Task.Status.DONE:
            return locked_task
        locked_task.status = Task.Status.DONE
        locked_task.save(update_fields=['status'])
        locked_task.create_next_occurrence()
        return locked_task


@login_required
def index(request):
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        return redirect('index')

    tasks = Task.objects.filter(owner=request.user)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    category = request.GET.get('category', '')
    order = request.GET.get('order', 'post')
    if order not in ('post', 'due', 'tag'):
        order = 'post'

    if query:
        tasks = tasks.filter(
            Q(title__icontains=query) | Q(tag__icontains=query)
        )
    if status in Task.Status.values:
        tasks = tasks.filter(status=status)
    if priority in Task.Priority.values:
        tasks = tasks.filter(priority=priority)
    if category in Task.Category.values:
        tasks = tasks.filter(category=category)

    if order == 'due':
        tasks = tasks.order_by(
            F('due_at').asc(nulls_last=True),
            '-posted_at',
        )
    elif order == 'tag':
        tasks = tasks.order_by('tag', '-posted_at')
    else:
        tasks = tasks.order_by('-posted_at')

    columns = [
        {
            'value': value,
            'label': label,
            'tasks': tasks.filter(status=value),
        }
        for value, label in Task.Status.choices
    ]
    context = {
        'form': form,
        'tasks': tasks,
        'columns': columns,
        'status_choices': Task.Status.choices,
        'priority_choices': Task.Priority.choices,
        'category_choices': Task.Category.choices,
        'filters': {
            'q': query,
            'status': status,
            'priority': priority,
            'category': category,
            'order': order,
        },
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
    form = TaskForm(request.POST or None, instance=task)
    if request.method == 'POST' and form.is_valid():
        updated_task = form.save(commit=False)
        updated_task.owner = request.user
        updated_task.save()
        return redirect('detail', task_id=task_id)
    context = {
        'task': task,
        'form': form,
    }
    return render(request, 'todo/edit.html', context)


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
    mark_task_done(task)
    return redirect('index')


@login_required
@require_POST
def change_status(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    status = request.POST.get('status')
    if status not in Task.Status.values:
        return HttpResponseBadRequest('Invalid status')
    if status == Task.Status.DONE:
        mark_task_done(task)
    else:
        task.status = status
        task.save(update_fields=['status'])
    return redirect('index')


@login_required
@require_POST
def add_subtask(request, task_id):
    task = get_user_task_or_404(request.user, task_id)
    title = request.POST.get('title', '').strip()
    if title:
        SubTask.objects.create(task=task, title=title)
    return redirect('detail', task_id=task_id)


@login_required
@require_POST
def toggle_subtask(request, task_id, subtask_id):
    task = get_user_task_or_404(request.user, task_id)
    subtask = get_object_or_404(
        SubTask,
        pk=subtask_id,
        task=task,
    )
    subtask.completed = not subtask.completed
    subtask.save(update_fields=['completed'])
    return redirect('detail', task_id=task_id)


@login_required
@require_POST
def delete_subtask(request, task_id, subtask_id):
    task = get_user_task_or_404(request.user, task_id)
    subtask = get_object_or_404(
        SubTask,
        pk=subtask_id,
        task=task,
    )
    subtask.delete()
    return redirect('detail', task_id=task_id)
