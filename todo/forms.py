from django import forms

from todo.models import Task


class TaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recurrence'].choices = [
            (Task.RECURRENCE_NONE, 'なし'),
            (Task.RECURRENCE_DAILY, '毎日'),
            (Task.RECURRENCE_WEEKLY, '毎週'),
            (Task.RECURRENCE_MONTHLY, '毎月'),
        ]

    def save(self, commit=True):
        task = super().save(commit=False)
        if 'due_at' in self.changed_data:
            task.notified_at = None
        if task.recurrence != Task.RECURRENCE_MONTHLY or task.due_at is None:
            task.recurrence_day = None
        elif (
            task.recurrence_day is None
            or 'due_at' in self.changed_data
            or 'recurrence' in self.changed_data
        ):
            task.recurrence_day = task.due_at.day
        if commit:
            task.save()
            self.save_m2m()
        return task

    class Meta:
        model = Task
        fields = (
            'title',
            'tag',
            'description',
            'due_at',
            'priority',
            'category',
            'status',
            'recurrence',
        )
        labels = {
            'title': 'タイトル',
            'tag': 'タグ',
            'description': '説明',
            'due_at': '期限',
            'priority': '優先度',
            'category': 'カテゴリ',
            'status': 'ステータス',
            'recurrence': '繰り返し',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'タスク名を入力'}),
            'tag': forms.TextInput(attrs={'placeholder': '例: Django'}),
            'description': forms.Textarea(
                attrs={
                    'placeholder': 'メモや補足を入力',
                    'rows': 3,
                }
            ),
            'due_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }
