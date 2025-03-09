# serializers.py
from rest_framework import serializers
from .models import ChangeLane

class ChangeLaneSerializer(serializers.ModelSerializer):
    driver = serializers.PrimaryKeyRelatedField(queryset=YourDriverModel.objects.all(), allow_null=True) #replace YourDriverModel
    class Meta:
        model = ChangeLane
        depth = 2
        fields = ['id', 'open', 'driver'] #add other fields as needed.
