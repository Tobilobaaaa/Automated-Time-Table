from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('lecturers', views.LecturerViewSet)
router.register('rooms', views.RoomViewSet)
router.register('groups', views.StudentGroupViewSet)
router.register('slots', views.TimeSlotViewSet)
router.register('courses', views.CourseViewSet)
router.register('availability', views.LecturerAvailabilityViewSet)
router.register('runs', views.TimetableRunViewSet)

urlpatterns = [
    # UI
    path('', views.dashboard, name='dashboard'),
    path('lecturers/', views.lecturers_page, name='lecturers'),
    path('lecturers/<int:pk>/edit/', views.edit_lecturer, name='edit_lecturer'),
    path('lecturers/<int:pk>/delete/', views.delete_lecturer, name='delete_lecturer'),
    path('rooms/', views.rooms_page, name='rooms'),
    path('rooms/<int:pk>/edit/', views.edit_room, name='edit_room'),
    path('rooms/<int:pk>/delete/', views.delete_room, name='delete_room'),
    path('groups/', views.groups_page, name='groups'),
    path('groups/<int:pk>/edit/', views.edit_group, name='edit_group'),
    path('groups/<int:pk>/delete/', views.delete_group, name='delete_group'),
    path('courses/', views.courses_page, name='courses'),
    path('courses/<int:pk>/edit/', views.edit_course, name='edit_course'),
    path('courses/<int:pk>/delete/', views.delete_course, name='delete_course'),
    path('slots/', views.slots_page, name='slots'),
    path('slots/<int:pk>/edit/', views.edit_slot, name='edit_slot'),
    path('slots/<int:pk>/delete/', views.delete_slot, name='delete_slot'),
    path('availability/', views.availability_page, name='availability'),
    path('availability/<int:pk>/edit/', views.edit_availability, name='edit_availability'),
    path(
        'availability/<int:pk>/delete/',
        views.delete_availability,
        name='delete_availability',
    ),
    path('generate/', views.generate_page, name='generate'),
    path('timetable/', views.timetable_active, name='timetable'),
    path('timetable/runs/', views.timetable_list, name='timetable_list'),
    path('timetable/<int:pk>/', views.timetable_detail, name='timetable_detail'),
    path('timetable/<int:pk>/export/', views.export_timetable, name='export_timetable'),
    path('timetable/<int:pk>/publish/', views.publish_run, name='publish_run'),
    # API
    path('api/', include(router.urls)),
    path('api/generate/', views.api_generate, name='api_generate'),
]
