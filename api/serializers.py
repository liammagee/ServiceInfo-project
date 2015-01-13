from django.contrib.auth.models import Group
from rest_framework import serializers
from email_user.models import EmailUser
from services.models import Service, Provider


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = EmailUser
        fields = ('url', 'email', 'groups')


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ('url', 'name')


class ProviderSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Provider
        fields = ('url', 'id', 'name', 'type', 'phone_number', 'website', 'description', 'user')


class ServiceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Service
        fields = ('url', 'id', 'provider', 'name', 'area_of_service', 'description',
                  'hours_of_service', 'additional_info', 'cost_of_service', 'selection_criteria',
                  'status', 'update_of',
        )