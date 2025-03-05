from django.urls import path
from . import views

urlpatterns = [
    path('', views.person_list, name='Everybody'),
    path('create/', views.person_create, name='person_create'),
    path('update/<int:pk>/', views.person_update, name='person_update'),
    path('delete/<int:pk>/', views.person_delete, name='person_delete'),
]
