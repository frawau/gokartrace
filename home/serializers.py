# serializers.py
from rest_framework import serializers
from .models import ChangeLane

class ChangeLaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangeLane
        depth = 2 #This is very important so that the driver team and member data is also returned.
        fields = '__all__'
