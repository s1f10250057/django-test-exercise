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

    class Meta:
        model = Task
        fields = (
            'title',
            'tag',
            'due_at',
            'priority',
            'category',
            'status',
            'recurrence',
        )
        labels = {
            'title': 'タイトル',
            'tag': 'タグ',
            'due_at': '期限',
            'priority': '優先度',
            'category': 'カテゴリ',
            'status': 'ステータス',
            'recurrence': '繰り返し',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'タスク名を入力'}),
            'tag': forms.TextInput(attrs={'placeholder': '例: Django'}),
            'due_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }
