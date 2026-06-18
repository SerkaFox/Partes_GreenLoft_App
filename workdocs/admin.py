from django.contrib import admin

from .models import Task, TaskEvent, TaskFile, TaskVoiceReport, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'user__email')


class TaskFileInline(admin.TabularInline):
    model = TaskFile
    extra = 0
    readonly_fields = ('created_at',)


class TaskEventInline(admin.TabularInline):
    model = TaskEvent
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'assigned_to', 'created_by', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('title', 'address', 'description', 'assigned_to__username', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'started_at', 'arrived_at', 'finished_at')
    inlines = [TaskFileInline, TaskEventInline]


@admin.register(TaskFile)
class TaskFileAdmin(admin.ModelAdmin):
    list_display = ('task', 'file_type', 'uploaded_by', 'original_name', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('task__title', 'original_name', 'comment')


@admin.register(TaskVoiceReport)
class TaskVoiceReportAdmin(admin.ModelAdmin):
    list_display = ('task', 'technician', 'transcript_status', 'created_at')
    list_filter = ('transcript_status', 'created_at')
    search_fields = ('task__title', 'technician__username', 'transcript_text')


@admin.register(TaskEvent)
class TaskEventAdmin(admin.ModelAdmin):
    list_display = ('task', 'event_type', 'user', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('task__title', 'comment', 'user__username')
